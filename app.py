# app.py - SỬA LẠI
from flask import Flask, render_template, jsonify
from pymongo import MongoClient
import os

app = Flask(__name__)

MONGO_URI = "mongodb+srv://tn042182_db_user:pRCe.YNp34Lh8v4@cluster0.rk7eki0.mongodb.net/"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client["CNC_Database"]
    collection = db["Sensor_Data"]
    print("✅ MongoDB connected")
except Exception as e:
    print(f"❌ MongoDB error: {e}")
    collection = None

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/latest")
def api_latest():
    if collection is None:
        return jsonify({"temp": 0, "load": 0, "status": "error"})
    
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
