# app.py - Dashboard với biểu đồ Chart.js
from flask import Flask, jsonify
from pymongo import MongoClient
from datetime import datetime, timedelta

app = Flask(__name__)

MONGO_URI = "mongodb+srv://tn042182_db_user:pRCe.YNp34hL8v4@cluster0.rk7eki0.mongodb.net/"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    client.admin.command('ping')
    db = client["CNC_Database"]
    collection = db["Sensor_Data"]
    print("✅ MongoDB connected!")
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
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: Arial; background: #1a1a2e; color: white; padding: 20px; }
            .container { max-width: 1000px; margin: 0 auto; }
            h1 { text-align: center; color: #4ecdc4; margin-bottom: 20px; }
            
            .gauges { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px; }
            .card { background: #16213e; padding: 20px; border-radius: 15px; text-align: center; }
            .card-label { color: #888; font-size: 14px; margin-bottom: 10px; }
            .card-value { font-size: 40px; font-weight: bold; }
            .temp-color { color: #ff6b6b; }
            .load-color { color: #4ecdc4; }
            
            .status-badge {
                display: inline-block; padding: 8px 20px; border-radius: 20px;
                font-size: 20px; font-weight: bold; margin-top: 10px;
            }
            .running { background: #00b894; }
            .idle { background: #fdcb6e; color: #333; }
            .maintenance { background: #e17055; }
            .error { background: #d63031; animation: blink 0.5s infinite; }
            @keyframes blink { 50% { opacity: 0.5; } }
            
            .chart-box { background: #16213e; padding: 20px; border-radius: 15px; margin-bottom: 15px; }
            .chart-box h3 { margin-bottom: 10px; color: #ddd; }
            canvas { width: 100%; max-height: 300px; }
            
            .info { text-align: center; color: #888; margin-top: 10px; font-size: 14px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🏭 CNC Machine Monitor</h1>
            
            <div class="gauges">
                <div class="card">
                    <div class="card-label">🌡️ TEMPERATURE</div>
                    <div class="card-value temp-color" id="tempValue">--°C</div>
                </div>
                <div class="card">
                    <div class="card-label">⚙️ LOAD</div>
                    <div class="card-value load-color" id="loadValue">--%</div>
                </div>
                <div class="card">
                    <div class="card-label">📌 STATUS</div>
                    <div id="statusValue"><span class="status-badge">--</span></div>
                </div>
            </div>
            
            <div class="chart-box">
                <h3>📈 Temperature (°C)</h3>
                <canvas id="tempChart"></canvas>
            </div>
            
            <div class="chart-box">
                <h3>📈 Load (%)</h3>
                <canvas id="loadChart"></canvas>
            </div>
            
            <div class="info" id="updateInfo">Waiting for data...</div>
        </div>

        <script>
            // ==========================================
            // CHART SETUP
            // ==========================================
            const MAX_POINTS = 50;
            const timeLabels = [];
            const tempData = [];
            const loadData = [];
            
            const chartOptions = {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 300 },
                scales: {
                    x: { 
                        ticks: { color: '#888', maxTicksLimit: 8 },
                        grid: { color: '#2d2d2d' }
                    },
                    y: { 
                        ticks: { color: '#888' },
                        grid: { color: '#2d2d2d' },
                        beginAtZero: false
                    }
                },
                plugins: { legend: { display: false } }
            };
            
            // Temperature Chart
            const tempCtx = document.getElementById('tempChart').getContext('2d');
            const tempChart = new Chart(tempCtx, {
                type: 'line',
                data: {
                    labels: timeLabels,
                    datasets: [{
                        data: tempData,
                        borderColor: '#ff6b6b',
                        backgroundColor: 'rgba(255, 107, 107, 0.1)',
                        borderWidth: 2,
                        pointRadius: 0,
                        tension: 0.3,
                        fill: true
                    }]
                },
                options: chartOptions
            });
            
            // Load Chart
            const loadCtx = document.getElementById('loadChart').getContext('2d');
            const loadChart = new Chart(loadCtx, {
                type: 'line',
                data: {
                    labels: timeLabels,
                    datasets: [{
                        data: loadData,
                        borderColor: '#4ecdc4',
                        backgroundColor: 'rgba(78, 205, 196, 0.1)',
                        borderWidth: 2,
                        pointRadius: 0,
                        tension: 0.3,
                        fill: true
                    }]
                },
                options: {...chartOptions, scales: {...chartOptions.scales, y: {...chartOptions.scales.y, min: 0, max: 100}}}
            });
            
            // ==========================================
            // FETCH DATA
            // ==========================================
            async function fetchData() {
                try {
                    const res = await fetch('/api/latest');
                    const d = await res.json();
                    
                    // Update gauges
                    document.getElementById('tempValue').textContent = d.temp ? d.temp.toFixed(1) + '°C' : '--°C';
                    document.getElementById('loadValue').textContent = d.load ? d.load + '%' : '--%';
                    
                    // Update status badge
                    const statusEl = document.getElementById('statusValue');
                    statusEl.innerHTML = '<span class="status-badge ' + d.status + '">' + d.status + '</span>';
                    
                    // Add to charts
                    const now = new Date().toLocaleTimeString();
                    timeLabels.push(now);
                    tempData.push(d.temp || 0);
                    loadData.push(d.load || 0);
                    
                    // Limit points
                    if (timeLabels.length > MAX_POINTS) {
                        timeLabels.shift();
                        tempData.shift();
                        loadData.shift();
                    }
                    
                    // Update charts
                    tempChart.update();
                    loadChart.update();
                    
                    // Update info
                    document.getElementById('updateInfo').textContent = 
                        'Last update: ' + now + ' | Data points: ' + timeLabels.length;
                    
                } catch(e) {
                    console.error(e);
                }
            }
            
            // Fetch immediately, then every 3 seconds
            fetchData();
            setInterval(fetchData, 3000);
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
        return jsonify({"temp": 0, "load": 0, "status": "error"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
