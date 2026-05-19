# app.py - Dashboard với nút thời gian + nút tải ảnh
from flask import Flask, jsonify, request
from pymongo import MongoClient
from datetime import datetime, timedelta

app = Flask(__name__)

MONGO_URI = "mongodb+srv://tn042182_db_user:pRCe.YNp34hL8v4@cluster0.rk7eki0.mongodb.net/"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
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
        <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: Arial; background: #1a1a2e; color: white; padding: 15px; }
            .container { max-width: 1000px; margin: 0 auto; }
            h1 { text-align: center; color: #4ecdc4; margin-bottom: 15px; font-size: 22px; }
            
            /* Gauge cards */
            .gauges { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 15px; }
            .card { background: #16213e; padding: 15px; border-radius: 12px; text-align: center; }
            .card-label { color: #888; font-size: 12px; margin-bottom: 5px; }
            .card-value { font-size: 32px; font-weight: bold; }
            .temp-color { color: #ff6b6b; }
            .load-color { color: #4ecdc4; }
            
            /* Status */
            .status-badge {
                display: inline-block; padding: 6px 15px; border-radius: 15px;
                font-size: 16px; font-weight: bold; margin-top: 5px;
            }
            .running { background: #00b894; }
            .idle { background: #fdcb6e; color: #333; }
            .maintenance { background: #e17055; }
            .error { background: #d63031; animation: blink 0.5s infinite; }
            @keyframes blink { 50% { opacity: 0.5; } }
            
            /* Time buttons */
            .btn-group { 
                display: flex; gap: 8px; justify-content: center; 
                margin-bottom: 15px; flex-wrap: wrap;
            }
            .btn {
                background: #16213e; color: white; border: 2px solid #4ecdc4;
                padding: 8px 16px; border-radius: 20px; cursor: pointer;
                font-size: 14px; transition: all 0.3s;
            }
            .btn:hover { background: #4ecdc4; color: #1a1a2e; }
            .btn.active { background: #4ecdc4; color: #1a1a2e; font-weight: bold; }
            
            /* Chart */
            .chart-box { background: #16213e; padding: 15px; border-radius: 12px; margin-bottom: 15px; }
            .chart-box h3 { margin-bottom: 8px; color: #ddd; font-size: 16px; }
            canvas { width: 100%; max-height: 280px; }
            
            /* Info bar */
            .info-bar { 
                display: flex; justify-content: space-between; align-items: center;
                color: #888; font-size: 12px; margin-bottom: 10px; flex-wrap: wrap; gap: 5px;
            }
            
            /* Download button */
            .download-btn {
                background: #ff6b6b; color: white; border: none;
                padding: 10px 20px; border-radius: 20px; cursor: pointer;
                font-size: 14px; display: block; margin: 10px auto;
            }
            .download-btn:hover { opacity: 0.8; }
        </style>
    </head>
    <body>
        <div class="container" id="dashboard">
            <h1>🏭 CNC Machine Monitor</h1>
            
            <!-- TIME BUTTONS -->
            <div class="btn-group">
                <button class="btn active" onclick="changeTime(10)">10 phút</button>
                <button class="btn" onclick="changeTime(20)">20 phút</button>
                <button class="btn" onclick="changeTime(30)">30 phút</button>
                <button class="btn" onclick="changeTime(60)">1 giờ</button>
                <button class="btn" onclick="changeTime(1440)">1 ngày</button>
                <button class="btn" onclick="changeTime(10080)">1 tuần</button>
            </div>
            
            <!-- INFO BAR -->
            <div class="info-bar">
                <span id="timeRange">Đang xem: 10 phút gần đây</span>
                <span id="updateInfo">Đang tải...</span>
            </div>
            
            <!-- GAUGES -->
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
            
            <!-- CHARTS -->
            <div class="chart-box">
                <h3>📈 Temperature (°C)</h3>
                <canvas id="tempChart"></canvas>
            </div>
            
            <div class="chart-box">
                <h3>📈 Load (%)</h3>
                <canvas id="loadChart"></canvas>
            </div>
            
            <!-- DOWNLOAD BUTTON -->
            <button class="download-btn" onclick="downloadImage()">📸 Tải ảnh về điện thoại</button>
        </div>

        <script>
            // ==========================================
            // CHART SETUP
            // ==========================================
            let currentTimeRange = 10; // Mặc định 10 phút
            
            const tempCtx = document.getElementById('tempChart').getContext('2d');
            const tempChart = new Chart(tempCtx, {
                type: 'line',
                data: { labels: [], datasets: [{
                    data: [], borderColor: '#ff6b6b', backgroundColor: 'rgba(255,107,107,0.1)',
                    borderWidth: 2, pointRadius: 0, tension: 0.3, fill: true
                }]},
                options: {
                    responsive: true, animation: { duration: 200 },
                    scales: {
                        x: { ticks: { color: '#888', maxTicksLimit: 8 }, grid: { color: '#2d2d2d' } },
                        y: { ticks: { color: '#888' }, grid: { color: '#2d2d2d' } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
            
            const loadCtx = document.getElementById('loadChart').getContext('2d');
            const loadChart = new Chart(loadCtx, {
                type: 'line',
                data: { labels: [], datasets: [{
                    data: [], borderColor: '#4ecdc4', backgroundColor: 'rgba(78,205,196,0.1)',
                    borderWidth: 2, pointRadius: 0, tension: 0.3, fill: true
                }]},
                options: {
                    responsive: true, animation: { duration: 200 },
                    scales: {
                        x: { ticks: { color: '#888', maxTicksLimit: 8 }, grid: { color: '#2d2d2d' } },
                        y: { ticks: { color: '#888', grid: { color: '#2d2d2d' }, min: 0, max: 100 } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
            
            // ==========================================
            // CHANGE TIME RANGE
            // ==========================================
            function changeTime(minutes) {
                currentTimeRange = minutes;
                
                // Update active button
                document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
                event.target.classList.add('active');
                
                // Update label
                let label = minutes + ' phút gần đây';
                if (minutes >= 1440) label = (minutes/1440).toFixed(0) + ' ngày gần đây';
                else if (minutes >= 10080) label = (minutes/10080).toFixed(0) + ' tuần gần đây';
                else if (minutes >= 60) label = (minutes/60).toFixed(0) + ' giờ gần đây';
                document.getElementById('timeRange').textContent = 'Đang xem: ' + label;
                
                // Reload data
                fetchHistory();
            }
            
            // ==========================================
            // FETCH HISTORY
            // ==========================================
            async function fetchHistory() {
                try {
                    const res = await fetch('/api/history?minutes=' + currentTimeRange);
                    const data = await res.json();
                    
                    // Clear old data
                    tempChart.data.labels = [];
                    tempChart.data.datasets[0].data = [];
                    loadChart.data.labels = [];
                    loadChart.data.datasets[0].data = [];
                    
                    // Add new data
                    data.forEach(d => {
                        // Format time
                        let time = '';
                        try {
                            const t = new Date(d.time);
                            time = t.toLocaleTimeString('vi-VN', {hour:'2-digit', minute:'2-digit'});
                        } catch(e) {
                            time = d.time || '';
                        }
                        
                        tempChart.data.labels.push(time);
                        tempChart.data.datasets[0].data.push(d.temp || 0);
                        loadChart.data.labels.push(time);
                        loadChart.data.datasets[0].data.push(d.load || 0);
                    });
                    
                    tempChart.update();
                    loadChart.update();
                    
                    document.getElementById('updateInfo').textContent = 
                        'Cập nhật: ' + new Date().toLocaleTimeString() + ' | ' + data.length + ' điểm';
                    
                } catch(e) {
                    console.error(e);
                }
            }
            
            // ==========================================
            // FETCH LATEST (gauges)
            // ==========================================
            async function fetchLatest() {
                try {
                    const res = await fetch('/api/latest');
                    const d = await res.json();
                    
                    document.getElementById('tempValue').textContent = d.temp ? d.temp.toFixed(1) + '°C' : '--°C';
                    document.getElementById('loadValue').textContent = d.load ? d.load + '%' : '--%';
                    
                    const statusEl = document.getElementById('statusValue');
                    statusEl.innerHTML = '<span class="status-badge ' + d.status + '">' + d.status + '</span>';
                    
                } catch(e) {}
            }
            
            // ==========================================
            // DOWNLOAD IMAGE
            // ==========================================
            function downloadImage() {
                html2canvas(document.getElementById('dashboard'), {
                    backgroundColor: '#1a1a2e',
                    scale: 2
                }).then(canvas => {
                    // Tạo link download
                    const link = document.createElement('a');
                    link.download = 'CNC_Monitor_' + new Date().toISOString().slice(0,16).replace(/:/g,'-') + '.png';
                    link.href = canvas.toDataURL('image/png');
                    link.click();
                });
            }
            
            // ==========================================
            // INIT
            // ==========================================
            fetchLatest();
            fetchHistory();
            
            // Update gauges every 3 seconds
            setInterval(fetchLatest, 3000);
            // Update chart every 30 seconds
            setInterval(fetchHistory, 30000);
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

@app.route("/api/history")
def api_history():
    """API: Lấy dữ liệu lịch sử theo khoảng thời gian"""
    if collection is None:
        return jsonify([])
    
    try:
        # Lấy tham số minutes từ URL
        minutes = int(request.args.get("minutes", 10))
        
        # Tính thời gian bắt đầu
        start_time = datetime.now() - timedelta(minutes=minutes)
        
        # Query MongoDB: lấy dữ liệu từ start_time đến hiện tại
        query = {"mqtt_timestamp": {"$gte": start_time.isoformat()}}
        
        # Lấy dữ liệu, sắp xếp từ cũ đến mới
        docs = list(collection.find(query).sort("mqtt_timestamp", 1))
        
        # Format response
        data = []
        for doc in docs:
            data.append({
                "time": doc.get("mqtt_timestamp", ""),
                "temp": doc.get("temp", 0),
                "load": doc.get("load", 0),
                "status": doc.get("status", "")
            })
        
        return jsonify(data)
        
    except Exception as e:
        return jsonify([])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
