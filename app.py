# app.py - CNC Monitor + Chat AI (Friday)
# Flow: WebUI → MongoDB(Chat_Jobs) → Worker(VS Code) → AI → MongoDB(Chat_Messages) → WebUI poll

from flask import Flask, jsonify, request, session, redirect, render_template, url_for, send_from_directory
from pymongo import MongoClient
from datetime import datetime, timedelta
from bson import ObjectId
from functools import wraps
from flask_cors import CORS
import json
import os
import base64
import re

app = Flask(__name__)
app.secret_key = "cnc_hanu_2026_secret"
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

CORS(app, resources={r"/api/*": {"origins": "*"}})

MONGO_URI = "mongodb+srv://tn042182_db_user:pRCe.YNp34hL8v4@cluster0.rk7eki0.mongodb.net/"

USERS = {
    "admin": "cnc2026",
    "user":  "123456",
}

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    db = client["CNC_Database"]
    sensor_data    = db["Sensor_Data"]
    uploaded_images = db["Uploaded_Images"]
    generated_gcode = db["Generated_GCode"]
    chat_messages  = db["Chat_Messages"]
    chat_jobs      = db["Chat_Jobs"]
    alarms         = db["Alarms"]
    machine_config = db["Machine_Config"]
    client.admin.command('ping')
    print("✅ MongoDB Atlas connected!")
except Exception as e:
    print(f"❌ MongoDB error: {e}")
    db = sensor_data = uploaded_images = generated_gcode = None
    chat_messages = chat_jobs = alarms = machine_config = None

# ─────────────────────────────────────────────
#  DECORATOR
# ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────
#  AUTH
# ─────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("home"))
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if USERS.get(username) == password:
            session["logged_in"] = True
            session["username"]  = username
            return redirect(url_for("home"))
        error = "❌ Sai tài khoản hoặc mật khẩu"
    return render_template("login.html", error=error)

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─────────────────────────────────────────────
#  PAGES
# ─────────────────────────────────────────────
@app.route("/")
@login_required
def home():
    return render_template("base.html", username=session.get("username", "admin"))

@app.route("/control")
@login_required
def control():
    return render_template("control.html", username=session.get("username", "admin"))

@app.route("/monitor")
@login_required
def monitor():
    return render_template("monitor.html", username=session.get("username", "admin"))

@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html", username=session.get("username", "admin"))

@app.route('/static/unity/<path:filename>')
def serve_unity(filename):
    return send_from_directory('static/unity', filename)

# ─────────────────────────────────────────────
#  API: UPLOAD IMAGE
# ─────────────────────────────────────────────
@app.route("/api/upload/image", methods=["POST"])
@login_required
def api_upload_image():
    if uploaded_images is None:
        return jsonify({"error": "Database not connected"}), 500
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        file_content = file.read()
        file_base64  = base64.b64encode(file_content).decode('utf-8')
        result = uploaded_images.insert_one({
            "filename":       file.filename,
            "file_extension": file.filename.split('.')[-1].lower(),
            "file_size":      len(file_content),
            "file_base64":    file_base64,
            "mime_type":      file.content_type,
            "uploaded_by":    session.get("username", "unknown"),
            "uploaded_at":    (datetime.utcnow() + timedelta(hours=7)).isoformat(),
            "description":    request.form.get("description", ""),
            "used":           False
        })
        return jsonify({"status": "ok", "image_id": str(result.inserted_id),
                        "filename": file.filename, "file_size": len(file_content)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/images", methods=["GET"])
@login_required
def api_get_images():
    if uploaded_images is None:
        return jsonify([])
    try:
        limit = int(request.args.get("limit", 20))
        docs  = list(uploaded_images.find({}, {"file_base64": 0})
                     .sort("uploaded_at", -1).limit(limit))
        for doc in docs:
            doc["_id"] = str(doc["_id"])
        return jsonify(docs)
    except:
        return jsonify([])

@app.route("/api/images/<image_id>", methods=["GET"])
@login_required
def api_get_image_by_id(image_id):
    if uploaded_images is None:
        return jsonify({"error": "Database not connected"}), 500
    try:
        doc = uploaded_images.find_one({"_id": ObjectId(image_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
            return jsonify(doc)
        return jsonify({"error": "Image not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────
#  API: SENSOR DATA
# ─────────────────────────────────────────────
@app.route("/api/latest")
@login_required
def api_latest():
    if sensor_data is None:
        return jsonify({"temp": 0, "load": 0, "status": "db_error"})
    try:
        doc = sensor_data.find_one(sort=[("mqtt_timestamp", -1)])
        if doc:
            return jsonify({
                "temp":       doc.get("temp", 0),
                "load":       doc.get("load", 0),
                "status":     doc.get("status", "unknown"),
                "vi_tri_x":   doc.get("vi_tri_x",  doc.get("position_x", 0)),
                "vi_tri_y":   doc.get("vi_tri_y",  doc.get("position_y", 0)),
                "vi_tri_z":   doc.get("vi_tri_z",  doc.get("position_z", 0)),
                "van_toc_x":  doc.get("van_toc_x", doc.get("velocity",   0)),
                "van_toc_y":  doc.get("van_toc_y", 0),
                "van_toc_z":  doc.get("van_toc_z", 0),
                "moment_x":   doc.get("moment_x",  doc.get("moment",     0)),
                "moment_y":   doc.get("moment_y",  0),
                "moment_z":   doc.get("moment_z",  0),
            })
        return jsonify({"temp": 0, "load": 0, "status": "no_data"})
    except:
        return jsonify({"temp": 0, "load": 0, "status": "error"})

@app.route("/api/history")
@login_required
def api_history():
    if sensor_data is None:
        return jsonify([])
    try:
        minutes    = int(request.args.get("minutes", 10))
        now        = datetime.utcnow() + timedelta(hours=7)   # giờ Việt Nam
        start_time = now - timedelta(minutes=minutes)
        start_str  = start_time.strftime("%Y-%m-%dT%H:%M:%S.000000")
        now_str    = now.strftime("%Y-%m-%dT%H:%M:%S.999999")

        print(f"📅 Giờ VN: {now.strftime('%H:%M:%S')} | Từ: {start_str} → {now_str}")

        docs = list(sensor_data.find({
            "mqtt_timestamp": {"$gte": start_str, "$lte": now_str}
        }).sort("mqtt_timestamp", 1))

        print(f"📊 Tìm được: {len(docs)} bản ghi")

        if len(docs) > 2000:
            step = len(docs) // 2000
            docs = docs[::step]

        return jsonify([{
            "time":      d.get("mqtt_timestamp", ""),

            # Cảm biến cũ
            "temp":      d.get("temp", 0),
            "load":      d.get("load", 0),

            # ✅ Vị trí X / Y / Z (mm)
            "vi_tri_x":  d.get("vi_tri_x",  d.get("position_x", 0)),
            "vi_tri_y":  d.get("vi_tri_y",  d.get("position_y", 0)),
            "vi_tri_z":  d.get("vi_tri_z",  d.get("position_z", 0)),

            # ✅ Vận tốc X / Y / Z (mm/s)
            "van_toc_x": d.get("van_toc_x", d.get("velocity",   0)),
            "van_toc_y": d.get("van_toc_y", 0),
            "van_toc_z": d.get("van_toc_z", 0),

            # ✅ Moment X / Y / Z (N·m)
            "moment_x":  d.get("moment_x",  d.get("moment",     0)),
            "moment_y":  d.get("moment_y",  0),
            "moment_z":  d.get("moment_z",  0),
        } for d in docs])

    except Exception as e:
        print(f"❌ History error: {e}")
        return jsonify([])

# ─────────────────────────────────────────────
#  API: CHAT AI
# ─────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    if chat_messages is None or chat_jobs is None:
        return jsonify({"error": "DB không kết nối"}), 500
    data    = request.json or {}
    message = data.get("message", "").strip()
    image_id = data.get("image_id", "")
    if not message:
        return jsonify({"error": "Tin nhắn trống"}), 400
    conv_id = data.get("conversation_id") or str(ObjectId())
    image_info = ""
    if image_id:
        try:
            img_doc = uploaded_images.find_one({"_id": ObjectId(image_id)})
            if img_doc:
                image_info = f"\n[ẢNH ĐÍNH KÈM: {img_doc.get('filename')}]\n"
                image_info += f"[BASE64: {img_doc.get('file_base64', '')[:200]}...]\n"
                uploaded_images.update_one(
                    {"_id": ObjectId(image_id)},
                    {"$set": {"used": True, "used_at": (datetime.utcnow() + timedelta(hours=7)).isoformat()}}
                )
        except:
            pass
    chat_messages.insert_one({
        "conversation_id": conv_id,
        "role":            "user",
        "message":         message,
        "image_id":        image_id,
        "username":        session.get("username", "unknown"),
        "timestamp":       (datetime.utcnow() + timedelta(hours=7)).isoformat()
    })
    chat_jobs.insert_one({
        "conversation_id": conv_id,
        "question":        message + image_info,
        "image_id":        image_id,
        "status":          "pending",
        "created_at":      (datetime.utcnow() + timedelta(hours=7)).isoformat()
    })
    return jsonify({"status": "ok", "conversation_id": conv_id, "message": "AI đang xử lý..."})

@app.route("/api/chat/messages/<conv_id>")
@login_required
def api_chat_messages(conv_id):
    if chat_messages is None:
        return jsonify({"messages": [], "done": False})
    try:
        messages = list(chat_messages.find({"conversation_id": conv_id}).sort("timestamp", 1))
        job_done = chat_jobs.find_one({"conversation_id": conv_id, "status": "done"})
        result_messages = []
        for m in messages:
            msg_data = {"role": m["role"], "message": m["message"], "time": m.get("timestamp", "")}
            if m["role"] == "assistant":
                gcode_match = re.search(r'```gcode\n(.*?)\n```', m["message"], re.DOTALL)
                if gcode_match:
                    msg_data["has_gcode"] = True
                    msg_data["gcode"]     = gcode_match.group(1)
            result_messages.append(msg_data)
        return jsonify({"messages": result_messages, "done": job_done is not None})
    except Exception as e:
        return jsonify({"messages": [], "done": False})

# ─────────────────────────────────────────────
#  API: G-CODE
# ─────────────────────────────────────────────
@app.route("/api/gcode/save", methods=["POST"])
@login_required
def api_save_gcode():
    if generated_gcode is None:
        return jsonify({"error": "Database not connected"}), 500
    try:
        data  = request.json
        gcode = data.get("gcode", "")
        if not gcode:
            return jsonify({"error": "No G-Code provided"}), 400
        result = generated_gcode.insert_one({
            "gcode":       gcode,
            "image_id":    data.get("image_id", ""),
            "created_by":  session.get("username", "unknown"),
            "created_at":  (datetime.utcnow() + timedelta(hours=7)).isoformat(),
            "is_downloaded": False
        })
        return jsonify({"status": "ok", "gcode_id": str(result.inserted_id)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/gcode/latest", methods=["GET"])
@login_required
def api_get_latest_gcode():
    if generated_gcode is None:
        return jsonify({"gcode": ""}), 500
    try:
        doc = generated_gcode.find_one(sort=[("created_at", -1)])
        if doc:
            return jsonify({"gcode": doc.get("gcode", ""), "created_at": doc.get("created_at", ""), "gcode_id": str(doc["_id"])})
        return jsonify({"gcode": "", "message": "Chưa có G-Code nào"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────
#  API: CONTROL
# ─────────────────────────────────────────────
@app.route("/api/control/gcode", methods=["POST"])
@login_required
def api_control_gcode():
    try:
        data  = request.json
        gcode = data.get("gcode", "")
        print(f"📝 G-Code từ {session.get('username')}: {len(gcode)} chars")
        return jsonify({"status": "ok", "message": "Đã nhận G-Code"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/api/control/stop", methods=["POST"])
@login_required
def api_control_stop():
    try:
        print(f"🛑 DỪNG KHẨN CẤP bởi {session.get('username')}")
        if alarms is not None:
            alarms.insert_one({
                "alarm_class": "Dừng khẩn cấp",
                "data_type":   "Hệ thống",
                "timestamp":   (datetime.utcnow() + timedelta(hours=7)).isoformat(),
                "status_text": f"Người dùng {session.get('username')} đã dừng khẩn cấp",
                "resolved":    False
            })
        return jsonify({"status": "ok", "message": "Đã dừng khẩn cấp"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/api/control/home", methods=["POST"])
@login_required
def api_control_home():
    try:
        print(f"🏠 HOME bởi {session.get('username')}")
        return jsonify({"status": "ok", "message": "Đã gửi lệnh Home"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/api/control/jog", methods=["POST"])
@login_required
def api_control_jog():
    try:
        data      = request.json
        axis      = data.get("axis", "X")
        direction = data.get("direction", "+")
        step      = data.get("step", 10)
        print(f"🎮 Jog: {axis}{direction} {step}mm")
        return jsonify({"status": "ok", "message": f"Jog {axis}{direction} {step}mm"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

# ─────────────────────────────────────────────
#  API: ALARMS
# ─────────────────────────────────────────────
@app.route("/api/alarms")
@login_required
def api_alarms():
    if alarms is None:
        return jsonify([])
    try:
        limit = int(request.args.get("limit", 100))
        docs  = list(alarms.find({}).sort("timestamp", -1).limit(limit))
        return jsonify([{
            "alarm_class": d.get("alarm_class", ""),
            "data_type":   d.get("data_type",   ""),
            "timestamp":   d.get("timestamp",   ""),
            "status_text": d.get("status_text", ""),
            "resolved":    d.get("resolved",    False)
        } for d in docs])
    except:
        return jsonify([])

@app.route("/api/alarms/resolve/<alarm_id>", methods=["POST"])
@login_required
def api_resolve_alarm(alarm_id):
    if alarms is None:
        return jsonify({"error": "DB not connected"}), 500
    try:
        result = alarms.update_one(
            {"_id": ObjectId(alarm_id)},
            {"$set": {
                "resolved":    True,
                "resolved_by": session.get("username"),
                "resolved_at": (datetime.utcnow() + timedelta(hours=7)).isoformat()
            }}
        )
        return jsonify({"status": "ok", "modified": result.modified_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────
#  API: MACHINE CONFIG
# ─────────────────────────────────────────────
DEFAULT_CONFIG = {
    "steps_x": 80.00,   "steps_y": 80.00,   "steps_z": 80.00,
    "max_speed_x": 250.00, "max_speed_y": 250.00, "max_speed_z": 150.00,
    "acc_x": 1000.00,   "acc_y": 1000.00,   "acc_z": 800.00,
    "max_travel_x": 400.00, "max_travel_y": 400.00, "max_travel_z": 150.00,
    "enable_homing": True, "homing_speed": 50.00, "homing_pulloff": 5.00
}

@app.route("/api/config", methods=["GET", "POST"])
@login_required
def api_config():
    if machine_config is None:
        return jsonify({"error": "Database not connected"}), 500
    if request.method == "GET":
        try:
            doc = machine_config.find_one({"_id": "current"})
            if doc:
                del doc["_id"]
                return jsonify(doc)
            return jsonify(DEFAULT_CONFIG)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        try:
            data = request.json
            data["last_updated"] = (datetime.utcnow() + timedelta(hours=7)).isoformat()
            data["updated_by"]   = session.get("username", "unknown")
            machine_config.update_one({"_id": "current"}, {"$set": data}, upsert=True)
            return jsonify({"status": "ok", "message": "Cấu hình đã được lưu"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/api/config/export", methods=["GET"])
@login_required
def api_config_export():
    if machine_config is None:
        return jsonify({"error": "Database not connected"}), 500
    try:
        doc = machine_config.find_one({"_id": "current"}) or DEFAULT_CONFIG
        yaml_content = f"""# CNC Machine Configuration
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

machine_tuning:
  steps_per_mm:
    x: {doc.get('steps_x', 80.00)}
    y: {doc.get('steps_y', 80.00)}
    z: {doc.get('steps_z', 80.00)}

motion:
  max_speed_mm_s:
    x: {doc.get('max_speed_x', 250.00)}
    y: {doc.get('max_speed_y', 250.00)}
    z: {doc.get('max_speed_z', 150.00)}
  acceleration_mm_s2:
    x: {doc.get('acc_x', 1000.00)}
    y: {doc.get('acc_y', 1000.00)}
    z: {doc.get('acc_z', 800.00)}

travel_limits:
  max_travel_mm:
    x: {doc.get('max_travel_x', 400.00)}
    y: {doc.get('max_travel_y', 400.00)}
    z: {doc.get('max_travel_z', 150.00)}

homing:
  enabled: {str(doc.get('enable_homing', True)).lower()}
  speed_mm_s: {doc.get('homing_speed', 50.00)}
  pull_off_mm: {doc.get('homing_pulloff', 5.00)}
"""
        return jsonify({"yaml": yaml_content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────
#  API: UNITY STATUS
# ─────────────────────────────────────────────
@app.route("/api/unity/status")
@login_required
def api_unity_status():
    if sensor_data is None:
        return jsonify({"connected": False})
    try:
        latest = sensor_data.find_one(sort=[("mqtt_timestamp", -1)])
        return jsonify({
            "connected": True,
            "position": {
                "x": latest.get("vi_tri_x", latest.get("position_x", 0)) if latest else 0,
                "y": latest.get("vi_tri_y", latest.get("position_y", 0)) if latest else 0,
                "z": latest.get("vi_tri_z", latest.get("position_z", 0)) if latest else 0,
            },
            "velocity": latest.get("van_toc_x", latest.get("velocity", 0)) if latest else 0,
            "load":     latest.get("load", 0) if latest else 0,
            "temp":     latest.get("temp", 0) if latest else 0,
        })
    except:
        return jsonify({"connected": False})

# ─────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
