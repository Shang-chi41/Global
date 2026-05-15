# app.py - SỬA LẠI
from flask import Flask, jsonify
from pymongo import MongoClient
import os

app = Flask(__name__)

# DÙNG TRỰC TIẾP URI, KHÔNG QUA ENVIRONMENT
MONGO_URI = "mongodb+srv://tn042182_db_user:pRCe.YNp34hL8v4@cluster0.rk7eki0.mongodb.net/"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    client.admin.command('ping')
    db = client["CNC_Database"]
    collection = db["Sensor_Data"]
    print("✅ MongoDB connected from Render!")
except Exception as e:
    print(f"❌ MongoDB error: {e}")
    collection = None

@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>CNC Monitor</title>
        <meta charset="UTF-8">
        <meta http-equiv="refresh" content="3">
        <style>
            body { font-family: Arial; background: #1a1a2e; color: white; padding: 50px; text-align: center; }
            .temp { font-size: 80px; color: #ff6b6b; font-weight: bold; }
            .load { font-size: 80px; color: #4ecdc4; font-weight: bold; }
            .status { font-size: 30px; padding: 10px 30px; border-radius: 30px; display: inline-block; }
            .running { background: #00b894; }
            .idle { background: #fdcb6e; color: #333; }
            .maintenance { background: #e17055; }
            .error { background: #d63031; }
        </style>
    </head>
    <body>
        <h1>🏭 CNC Monitor</h1>
        <div id="data">Loading...</div>
        <script>
            fetch('/api/latest')
                .then(r => r.json())
                .then(d => {
                    document.getElementById('data').innerHTML = 
                        '<p>🌡️ Temperature</p><div class="temp">' + (d.temp ? d.temp.toFixed(1) : '--') + '°C</div>' +
                        '<p>⚙️ Load</p><div class="load">' + (d.load || '--') + '%</div>' +
                        '<p>Status: <span class="status ' + d.status + '">' + d.status + '</span></p>';
                })
                .catch(e => {
                    document.getElementById('data').innerHTML = '<p>Connecting to database...</p>';
                });
        </script>
    </body>
    </html>
    """

@app.route("/api/latest")
def api_latest():
    if collection is None:
        return jsonify({"temp": 0, "load": 0, "status": "db_error"})
    
    try:
        doc = collection.find_one(sort=[("mqtt_timestamp", -1)])
        if doc:
            return jsonify({
                "temp": doc.get("temp", 0),
                "load": doc.get("load", 0),
                "status": doc.get("status", "unknown")
            })
        return jsonify({"temp": 0, "load": 0, "status": "no_data"})
    except Exception as e:
        return jsonify({"temp": 0, "load": 0, "status": str(e)[:20]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
