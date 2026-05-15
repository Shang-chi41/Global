# app.py
from flask import Flask, render_template, jsonify
from pymongo import MongoClient
import os

app = Flask(__name__)

# Lấy MongoDB URI từ environment variable (Render)
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://tn042182_db_user:pRCe.YNp34hL8v4@cluster0.rk7eki0.mongodb.net/")
DATABASE_NAME = "CNC_Database"
COLLECTION_NAME = "Sensor_Data"

# Kết nối MongoDB Atlas
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/latest")
def api_latest():
    doc = collection.find_one(sort=[("mqtt_timestamp", -1)])
    if doc:
        return jsonify({
            "temp": doc.get("temp", 0),
            "load": doc.get("load", 0),
            "status": doc.get("status", "unknown"),
            "rssi": doc.get("rssi", 0),
            "timestamp": doc.get("mqtt_timestamp", "")
        })
    return jsonify({"temp": 0, "load": 0, "status": "no_data"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)