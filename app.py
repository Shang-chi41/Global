# app.py - CNC Monitor + Chat AI (Friday)
# Flow: WebUI → MongoDB(Chat_Jobs) → Worker(VS Code) → AI → MongoDB(Chat_Messages) → WebUI poll

from flask import Flask, jsonify, request, session, redirect, render_template, url_for
from pymongo import MongoClient
from datetime import datetime, timedelta
from bson import ObjectId
from functools import wraps

app = Flask(__name__)
app.secret_key = "cnc_hanu_2026_secret"

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
#  API: SENSOR
# ─────────────────────────────────────────────
@app.route("/api/latest")
@login_required
def api_latest():
    if collection is None:
        return jsonify({"temp": 0, "load": 0, "status": "db_error"})
    try:
        doc = collection.find_one(sort=[("mqtt_timestamp", -1)])
        if doc:
            return jsonify({
                "temp":   doc.get("temp", 0),
                "load":   doc.get("load", 0),
                "status": doc.get("status", "unknown")
            })
        return jsonify({"temp": 0, "load": 0, "status": "no_data"})
    except:
        return jsonify({"temp": 0, "load": 0, "status": "error"})

@app.route("/api/history")
@login_required
def api_history():
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
            "load": d.get("load", 0)
        } for d in docs])

    except Exception as e:
        print(f"❌ History error: {e}")
        return jsonify([])

# ─────────────────────────────────────────────
#  API: CHAT
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
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
