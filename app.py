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

app = Flask(__name__)
app.secret_key = "cnc_hanu_2026_secret"

# Enable CORS for Unity WebGL
CORS(app, resources={r"/api/*": {"origins": "*"}})

MONGO_URI = "mongodb+srv://tn042182_db_user:pRCe.YNp34hL8v4@cluster0.rk7eki0.mongodb.net/"

# Tài khoản đăng nhập (có thể thêm nhiều user)
USERS = {
    "admin": "cnc2026",
}

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    db = client["CNC_Database"]
    collection = db["Sensor_Data"]
    client.admin.command('ping')
    print("✅ MongoDB Atlas connected!")
except Exception as e:
    print(f"❌ MongoDB error: {e}")
    db = None
    collection = None

# ─────────────────────────────────────────────
#  DECORATOR: bảo vệ route cần đăng nhập
# ─────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ─────────────────────────────────────────────
#  AUTH ROUTES
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
            session["username"] = username
            return redirect(url_for("home"))
        else:
            error = "❌ Sai tài khoản hoặc mật khẩu"

    return render_template("login.html", error=error)

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─────────────────────────────────────────────
#  PAGE ROUTES
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

# ─────────────────────────────────────────────
#  API: SENSOR (CHO MONITOR)
# ─────────────────────────────────────────────
@app.route("/api/latest")
@login_required
def api_latest():
    """Lấy dữ liệu cảm biến mới nhất"""
    if collection is None:
        return jsonify({"temp": 0, "load": 0, "status": "db_error", "position_x": 0, "position_y": 0, "position_z": 0})
    try:
        doc = collection.find_one(sort=[("mqtt_timestamp", -1)])
        if doc:
            return jsonify({
                "temp":   doc.get("temp", 0),
                "load":   doc.get("load", 0),
                "status": doc.get("status", "unknown"),
                "position_x": doc.get("position_x", 0),
                "position_y": doc.get("position_y", 0),
                "position_z": doc.get("position_z", 0),
                "velocity": doc.get("velocity", 0),
                "timestamp": doc.get("mqtt_timestamp", "")
            })
        return jsonify({"temp": 0, "load": 0, "status": "no_data", "position_x": 0, "position_y": 0, "position_z": 0})
    except Exception as e:
        print(f"❌ Latest error: {e}")
        return jsonify({"temp": 0, "load": 0, "status": "error", "position_x": 0, "position_y": 0, "position_z": 0})

@app.route("/api/history")
@login_required
def api_history():
    """Lấy dữ liệu lịch sử cho biểu đồ"""
    if collection is None:
        return jsonify([])
    try:
        minutes    = int(request.args.get("minutes", 10))
        now        = datetime.utcnow() + timedelta(hours=7)  # giờ Việt Nam
        start_time = now - timedelta(minutes=minutes)

        start_str = start_time.strftime("%Y-%m-%dT%H:%M:%S.000000")
        now_str   = now.strftime("%Y-%m-%dT%H:%M:%S.999999")

        print(f"📅 Giờ VN: {now.strftime('%H:%M:%S')}  |  Từ: {start_str} → Đến: {now_str}")

        docs = list(collection.find({
            "mqtt_timestamp": {"$gte": start_str, "$lte": now_str}
        }).sort("mqtt_timestamp", 1))

        print(f"📊 Tìm được: {len(docs)} bản ghi")

        if len(docs) > 2000:
            step = len(docs) // 2000
            docs = docs[::step]

        return jsonify([{
            "time": d.get("mqtt_timestamp", ""),
            "temp": d.get("temp", 0),
            "load": d.get("load", 0),
            "vi_tri": d.get("position_x", 0),
            "van_toc": d.get("velocity", 0),
            "moment": d.get("moment", 0)
        } for d in docs])

    except Exception as e:
        print(f"❌ History error: {e}")
        return jsonify([])

# ─────────────────────────────────────────────
#  API: CONTROL (CHO CONTROL.HTML)
# ─────────────────────────────────────────────
@app.route("/api/control/gcode", methods=["POST"])
@login_required
def api_control_gcode():
    """Nhận G-Code từ web và gửi đến máy CNC"""
    try:
        data = request.json
        gcode = data.get("gcode", "")
        
        print(f"📝 Nhận G-Code từ {session.get('username')}:")
        print(f"--- G-CODE START ---")
        print(gcode[:500])  # In 500 ký tự đầu
        print(f"--- G-CODE END ---")
        
        # TODO: Gửi G-Code đến máy CNC thật qua:
        # - Serial (USB)
        # - MQTT
        # - TCP Socket
        # - HTTP to ESP32
        
        # Lưu vào database để theo dõi
        if db is not None:
            db["GCode_History"].insert_one({
                "username": session.get("username", "unknown"),
                "gcode": gcode,
                "timestamp": (datetime.utcnow() + timedelta(hours=7)).isoformat(),
                "status": "sent"
            })
        
        return jsonify({
            "status": "ok", 
            "message": "Đã nhận G-Code",
            "length": len(gcode)
        })
    except Exception as e:
        print(f"❌ GCode error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/api/control/stop", methods=["POST"])
@login_required
def api_control_stop():
    """Dừng khẩn cấp máy CNC"""
    try:
        print(f"🛑 DỪNG KHẨN CẤP bởi {session.get('username')}!")
        
        # TODO: Gửi lệnh dừng đến máy CNC
        # - Serial.write(b'!')
        # - MQTT publish "emergency_stop"
        
        # Lưu vào alarm
        if db is not None:
            db["Alarms"].insert_one({
                "alarm_class": "Dừng khẩn cấp",
                "data_type": "Hệ thống",
                "timestamp": (datetime.utcnow() + timedelta(hours=7)).isoformat(),
                "status_text": f"Người dùng {session.get('username')} đã dừng khẩn cấp",
                "resolved": False
            })
        
        return jsonify({"status": "ok", "message": "Đã dừng khẩn cấp"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/api/control/home", methods=["POST"])
@login_required
def api_control_home():
    """Đưa máy về vị trí Home"""
    try:
        print(f"🏠 Đưa máy về HOME bởi {session.get('username')}")
        
        # TODO: Gửi lệnh home đến máy CNC
        # G28 (lệnh G-Code home)
        
        return jsonify({"status": "ok", "message": "Đã gửi lệnh Home"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/api/control/jog", methods=["POST"])
@login_required
def api_control_jog():
    """Điều khiển manual từng bước (Jog)"""
    try:
        data = request.json
        axis = data.get("axis", "X")  # X, Y, Z
        direction = data.get("direction", "+")  # + or -
        step = data.get("step", 10)  # mm
        
        print(f"🎮 Jog: {axis}{direction} {step}mm")
        
        # TODO: Gửi lệnh jog đến máy CNC
        # G91 (relative mode)
        # G0 X{step} hoặc G0 X-{step}
        
        return jsonify({"status": "ok", "message": f"Jog {axis}{direction} {step}mm"})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

# ─────────────────────────────────────────────
#  API: CHAT (CHO FRIDAY AI)
# ─────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    if db is None:
        return jsonify({"error": "DB không kết nối"}), 500

    data    = request.json or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Tin nhắn trống"}), 400

    conv_id = data.get("conversation_id") or str(ObjectId())

    # Lưu tin nhắn user
    db["Chat_Messages"].insert_one({
        "conversation_id": conv_id,
        "role":            "user",
        "message":         message,
        "username":        session.get("username", "unknown"),
        "timestamp":       (datetime.utcnow() + timedelta(hours=7)).isoformat()
    })

    # Tạo job cho worker VS Code
    db["Chat_Jobs"].insert_one({
        "conversation_id": conv_id,
        "question":        message,
        "status":          "pending",
        "created_at":      (datetime.utcnow() + timedelta(hours=7)).isoformat()
    })

    return jsonify({
        "status":          "ok",
        "conversation_id": conv_id,
        "message":         "Friday đang xử lý..."
    })

@app.route("/api/chat/messages/<conv_id>")
@login_required
def api_chat_messages(conv_id):
    if db is None:
        return jsonify({"messages": [], "done": False})
    try:
        messages = list(
            db["Chat_Messages"]
            .find({"conversation_id": conv_id})
            .sort("timestamp", 1)
        )
        job_done = db["Chat_Jobs"].find_one({
            "conversation_id": conv_id,
            "status":          "done"
        })
        return jsonify({
            "messages": [{
                "role":    m["role"],
                "message": m["message"],
                "time":    m.get("timestamp", "")
            } for m in messages],
            "done": job_done is not None
        })
    except Exception as e:
        print(f"❌ Chat poll error: {e}")
        return jsonify({"messages": [], "done": False})

# ─────────────────────────────────────────────
#  API: ALARMS (CHO MONITOR)
# ─────────────────────────────────────────────
@app.route("/api/alarms")
@login_required
def api_alarms():
    """
    Trả về danh sách alarm từ MongoDB collection Alarms
    """
    if db is None:
        return jsonify([])
    try:
        limit = int(request.args.get("limit", 100))
        docs = list(
            db["Alarms"]
            .find({})
            .sort("timestamp", -1)
            .limit(limit)
        )
        return jsonify([{
            "alarm_class": d.get("alarm_class", ""),
            "data_type":   d.get("data_type", ""),
            "timestamp":   d.get("timestamp", ""),
            "status_text": d.get("status_text", ""),
            "resolved":    d.get("resolved", False)
        } for d in docs])
    except Exception as e:
        print(f"❌ Alarms error: {e}")
        return jsonify([])

@app.route("/api/alarms/resolve/<alarm_id>", methods=["POST"])
@login_required
def api_resolve_alarm(alarm_id):
    """Đánh dấu alarm đã xử lý"""
    if db is None:
        return jsonify({"error": "DB not connected"}), 500
    try:
        result = db["Alarms"].update_one(
            {"_id": ObjectId(alarm_id)},
            {"$set": {"resolved": True, "resolved_by": session.get("username"), "resolved_at": (datetime.utcnow() + timedelta(hours=7)).isoformat()}}
        )
        return jsonify({"status": "ok", "modified": result.modified_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────
#  API: MACHINE CONFIG (CHO SETTINGS)
# ─────────────────────────────────────────────
@app.route("/api/config", methods=["GET", "POST"])
@login_required
def api_config():
    """
    GET:  Lấy cấu hình máy từ MongoDB
    POST: Lưu cấu hình máy vào MongoDB
    """
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    if request.method == "GET":
        try:
            doc = db["Machine_Config"].find_one({"_id": "current"})
            if doc:
                del doc["_id"]
                return jsonify(doc)
            # Config mặc định
            default_config = {
                "steps_x": 80.00, "steps_y": 80.00, "steps_z": 80.00,
                "max_speed_x": 250.00, "max_speed_y": 250.00, "max_speed_z": 150.00,
                "acc_x": 1000.00, "acc_y": 1000.00, "acc_z": 800.00,
                "max_travel_x": 400.00, "max_travel_y": 400.00, "max_travel_z": 150.00,
                "enable_homing": True, "homing_speed": 50.00, "homing_pulloff": 5.00
            }
            return jsonify(default_config)
        except Exception as e:
            print(f"❌ GET config error: {e}")
            return jsonify({"error": str(e)}), 500
    
    elif request.method == "POST":
        try:
            data = request.json
            if not data:
                return jsonify({"error": "No data provided"}), 400
            
            data["last_updated"] = (datetime.utcnow() + timedelta(hours=7)).isoformat()
            data["updated_by"] = session.get("username", "unknown")
            
            result = db["Machine_Config"].update_one(
                {"_id": "current"}, 
                {"$set": data}, 
                upsert=True
            )
            
            print(f"✅ Config saved by {session.get('username')}")
            return jsonify({
                "status": "ok", 
                "message": "Cấu hình đã được lưu thành công"
            })
        except Exception as e:
            print(f"❌ POST config error: {e}")
            return jsonify({"error": str(e)}), 500

@app.route("/api/config/export", methods=["GET"])
@login_required
def api_config_export():
    """Export cấu hình dạng YAML"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    try:
        doc = db["Machine_Config"].find_one({"_id": "current"})
        if not doc:
            doc = {
                "steps_x": 80.00, "steps_y": 80.00, "steps_z": 80.00,
                "max_speed_x": 250.00, "max_speed_y": 250.00, "max_speed_z": 150.00,
                "acc_x": 1000.00, "acc_y": 1000.00, "acc_z": 800.00,
                "max_travel_x": 400.00, "max_travel_y": 400.00, "max_travel_z": 150.00,
                "enable_homing": True, "homing_speed": 50.00, "homing_pulloff": 5.00
            }
        
        yaml_content = f"""# CNC Machine Configuration
# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# ============================================

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

# End of configuration
"""
        return jsonify({"yaml": yaml_content})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ─────────────────────────────────────────────
#  API: UNITY WEBGL SUPPORT
# ─────────────────────────────────────────────
@app.route("/api/unity/status")
@login_required
def api_unity_status():
    """Trạng thái cho Unity WebGL"""
    if collection is None:
        return jsonify({"connected": False})
    try:
        latest = collection.find_one(sort=[("mqtt_timestamp", -1)])
        return jsonify({
            "connected": True,
            "position": {
                "x": latest.get("position_x", 0) if latest else 0,
                "y": latest.get("position_y", 0) if latest else 0,
                "z": latest.get("position_z", 0) if latest else 0
            },
            "velocity": latest.get("velocity", 0) if latest else 0,
            "load": latest.get("load", 0) if latest else 0,
            "temp": latest.get("temp", 0) if latest else 0
        })
    except:
        return jsonify({"connected": False})

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
