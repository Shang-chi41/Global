# app.py - Biểu đồ sóng với điểm chạm nổi bật
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
        <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { 
                font-family: -apple-system, Arial, sans-serif;
                background: #1a1a2e; color: white; padding: 10px;
            }
            .container { max-width: 1000px; margin: 0 auto; }
            h1 { text-align: center; color: #4ecdc4; margin-bottom: 10px; font-size: 20px; }
            
            .gauges { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 10px; }
            .card { background: #16213e; padding: 12px; border-radius: 12px; text-align: center; }
            .card-label { color: #888; font-size: 11px; }
            .card-value { font-size: 28px; font-weight: bold; margin-top: 4px; }
            .temp-color { color: #ff6b6b; }
            .load-color { color: #4ecdc4; }
            
            .status-badge {
                display: inline-block; padding: 5px 12px; border-radius: 12px;
                font-size: 14px; font-weight: bold; margin-top: 4px;
            }
            .running { background: #00b894; }
            .idle { background: #fdcb6e; color: #333; }
            .maintenance { background: #e17055; }
            .error { background: #d63031; animation: blink 0.5s infinite; }
            @keyframes blink { 50% { opacity: 0.5; } }
            
            .btn-group { 
                display: flex; gap: 6px; justify-content: center; 
                margin-bottom: 10px; flex-wrap: wrap;
            }
            .btn {
                background: #16213e; color: white; border: 2px solid #4ecdc4;
                padding: 6px 12px; border-radius: 15px; cursor: pointer;
                font-size: 12px;
            }
            .btn.active { background: #4ecdc4; color: #1a1a2e; font-weight: bold; }
            
            .chart-box { 
                background: #16213e; padding: 12px; border-radius: 12px; margin-bottom: 10px;
                position: relative;
            }
            .chart-box h3 { margin-bottom: 6px; color: #ddd; font-size: 14px; }
            canvas { width: 100%; height: 280px !important; }
            
            /* Popup khi chạm */
            .touch-popup {
                position: absolute; background: rgba(0,0,0,0.95); color: white;
                padding: 10px 14px; border-radius: 10px; font-size: 13px;
                pointer-events: none; z-index: 10; display: none;
                border: 2px solid #4ecdc4; text-align: center;
                box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            }
            .touch-popup .popup-time { color: #4ecdc4; font-size: 12px; margin-bottom: 4px; }
            .touch-popup .popup-value { font-size: 22px; font-weight: bold; }
            
            .info-bar { 
                display: flex; justify-content: space-between;
                color: #888; font-size: 11px; margin-bottom: 8px;
            }
            
            .download-btn {
                background: #ff6b6b; color: white; border: none;
                padding: 8px 16px; border-radius: 15px; cursor: pointer;
                font-size: 12px; display: block; margin: 8px auto;
            }
        </style>
    </head>
    <body>
        <div class="container" id="dashboard">
            <h1>🏭 CNC Machine Monitor</h1>
            
            <div class="btn-group">
                <button class="btn active" onclick="changeTime(10)">10 phút</button>
                <button class="btn" onclick="changeTime(30)">30 phút</button>
                <button class="btn" onclick="changeTime(60)">1 giờ</button>
                <button class="btn" onclick="changeTime(360)">6 giờ</button>
                <button class="btn" onclick="changeTime(1440)">1 ngày</button>
            </div>
            
            <div class="info-bar">
                <span id="timeRange">📅 10 phút</span>
                <span id="updateInfo">🔄 Đang tải...</span>
            </div>
            
            <div class="gauges">
                <div class="card">
                    <div class="card-label">🌡️ NHIỆT ĐỘ</div>
                    <div class="card-value temp-color" id="tempValue">--°C</div>
                </div>
                <div class="card">
                    <div class="card-label">⚙️ TẢI</div>
                    <div class="card-value load-color" id="loadValue">--%</div>
                </div>
                <div class="card">
                    <div class="card-label">📌 TRẠNG THÁI</div>
                    <div id="statusValue"><span class="status-badge">--</span></div>
                </div>
            </div>
            
            <div class="chart-box" id="tempBox">
                <h3>📈 Nhiệt độ (°C) — Chạm vào đồ thị để xem</h3>
                <canvas id="tempChart"></canvas>
                <div class="touch-popup" id="tempPopup">
                    <div class="popup-time"></div>
                    <div class="popup-value"></div>
                </div>
            </div>
            
            <div class="chart-box" id="loadBox">
                <h3>📈 Tải (%) — Chạm vào đồ thị để xem</h3>
                <canvas id="loadChart"></canvas>
                <div class="touch-popup" id="loadPopup">
                    <div class="popup-time"></div>
                    <div class="popup-value"></div>
                </div>
            </div>
            
            <button class="download-btn" onclick="downloadImage()">📸 Tải ảnh</button>
        </div>

        <script>
            let currentTimeRange = 10;
            
            // ==========================================
            // TẠO BIỂU ĐỒ SÓNG + CHẠM HIỆN POPUP
            // ==========================================
            function createWaveChart(canvasId, popupId, color, yMin, yMax, unit) {
                const canvas = document.getElementById(canvasId);
                const ctx = canvas.getContext('2d');
                const popup = document.getElementById(popupId);
                const box = popup.parentElement;
                
                // Dữ liệu gốc (lưu để truy xuất khi chạm)
                let rawData = [];
                
                const chart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            data: [],
                            borderColor: color,
                            backgroundColor: color.replace(')', ',0.15)').replace('rgb', 'rgba'),
                            borderWidth: 3,
                            pointRadius: 0,
                            tension: 0.4,  // Đường cong mượt
                            fill: true
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: false,
                        interaction: { mode: 'index', intersect: false },
                        scales: {
                            x: { 
                                ticks: { color: '#555', maxTicksLimit: 6, font: { size: 10 } },
                                grid: { color: '#1e1e32' }
                            },
                            y: { 
                                ticks: { color: '#555', font: { size: 10 } },
                                grid: { color: '#1e1e32' },
                                min: yMin, max: yMax
                            }
                        },
                        plugins: {
                            legend: { display: false },
                            tooltip: { enabled: false }
                        },
                        // Sự kiện chạm/click
                        onClick: function(e, elements) {
                            if (elements.length > 0) {
                                const idx = elements[0].index;
                                const label = chart.data.labels[idx];
                                const value = chart.data.datasets[0].data[idx];
                                
                                // Thêm chấm tròn tại vị trí chạm
                                chart.data.datasets[0].pointRadius = Array(chart.data.labels.length).fill(0);
                                chart.data.datasets[0].pointRadius[idx] = 8;
                                chart.data.datasets[0].pointBackgroundColor = Array(chart.data.labels.length).fill('transparent');
                                chart.data.datasets[0].pointBackgroundColor[idx] = 'white';
                                chart.data.datasets[0].pointBorderColor = Array(chart.data.labels.length).fill('transparent');
                                chart.data.datasets[0].pointBorderColor[idx] = color;
                                chart.data.datasets[0].pointBorderWidth = Array(chart.data.labels.length).fill(0);
                                chart.data.datasets[0].pointBorderWidth[idx] = 3;
                                chart.update();
                                
                                // Hiện popup
                                const rect = box.getBoundingClientRect();
                                const canvasRect = canvas.getBoundingClientRect();
                                const x = elements[0].element.x;
                                const y = elements[0].element.y;
                                
                                const popupX = canvasRect.left - rect.left + x;
                                const popupY = canvasRect.top - rect.top + y - 70;
                                
                                popup.querySelector('.popup-time').textContent = '🕐 ' + label;
                                popup.querySelector('.popup-value').textContent = value.toFixed(1) + ' ' + unit;
                                popup.querySelector('.popup-value').style.color = color;
                                popup.style.display = 'block';
                                popup.style.left = Math.min(Math.max(popupX - 60, 5), rect.width - 130) + 'px';
                                popup.style.top = Math.max(popupY, 5) + 'px';
                                
                                // Ẩn popup sau 3 giây
                                clearTimeout(popup._timeout);
                                popup._timeout = setTimeout(() => {
                                    popup.style.display = 'none';
                                    chart.data.datasets[0].pointRadius = 0;
                                    chart.update();
                                }, 3000);
                            }
                        }
                    }
                });
                
                // Lưu chart để truy cập sau
                canvas._chart = chart;
                return chart;
            }
            
            const tempChart = createWaveChart('tempChart', 'tempPopup', '#ff6b6b', 20, 60, '°C');
            const loadChart = createWaveChart('loadChart', 'loadPopup', '#4ecdc4', 0, 100, '%');
            
            // ==========================================
            // ĐỔI THỜI GIAN
            // ==========================================
            function changeTime(minutes) {
                currentTimeRange = minutes;
                document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
                event.target.classList.add('active');
                
                let label = minutes + ' phút';
                if (minutes >= 1440) label = (minutes/1440).toFixed(0) + ' ngày';
                else if (minutes >= 60) label = (minutes/60).toFixed(0) + ' giờ';
                document.getElementById('timeRange').textContent = '📅 ' + label + ' gần đây';
                
                fetchHistory();
            }
            
            // ==========================================
            // LẤY DỮ LIỆU LỊCH SỬ
            // ==========================================
            async function fetchHistory() {
                try {
                    const res = await fetch('/api/history?minutes=' + currentTimeRange);
                    const data = await res.json();
                    
                    const labels = [], temps = [], loads = [];
                    data.forEach(d => {
                        let time = '';
                        try {
                            time = new Date(d.time).toLocaleTimeString('vi-VN', {hour:'2-digit', minute:'2-digit'});
                        } catch(e) { time = ''; }
                        labels.push(time);
                        temps.push(d.temp || 0);
                        loads.push(d.load || 0);
                    });
                    
                    tempChart.data.labels = labels;
                    tempChart.data.datasets[0].data = temps;
                    tempChart.data.datasets[0].pointRadius = 0;
                    
                    loadChart.data.labels = labels;
                    loadChart.data.datasets[0].data = loads;
                    loadChart.data.datasets[0].pointRadius = 0;
                    
                    tempChart.update();
                    loadChart.update();
                    
                    document.getElementById('updateInfo').textContent = 
                        '🔄 ' + new Date().toLocaleTimeString() + ' | ' + data.length + ' điểm';
                    
                } catch(e) { console.error(e); }
            }
            
            // ==========================================
            // LẤY GIÁ TRỊ MỚI NHẤT
            // ==========================================
            async function fetchLatest() {
                try {
                    const res = await fetch('/api/latest');
                    const d = await res.json();
                    document.getElementById('tempValue').textContent = d.temp ? d.temp.toFixed(1) + '°C' : '--°C';
                    document.getElementById('loadValue').textContent = d.load ? d.load + '%' : '--%';
                    document.getElementById('statusValue').innerHTML = 
                        '<span class="status-badge ' + d.status + '">' + d.status + '</span>';
                } catch(e) {}
            }
            
            function downloadImage() {
                html2canvas(document.getElementById('dashboard'), { backgroundColor: '#1a1a2e', scale: 2 })
                    .then(canvas => {
                        const a = document.createElement('a');
                        a.download = 'CNC_' + new Date().toISOString().slice(0,16).replace(/:/g,'-') + '.png';
                        a.href = canvas.toDataURL('image/png');
                        a.click();
                    });
            }
            
            fetchLatest();
            fetchHistory();
            setInterval(fetchLatest, 3000);
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
            return jsonify({"temp": doc.get("temp", 0), "load": doc.get("load", 0), "status": doc.get("status", "unknown")})
        return jsonify({"temp": 0, "load": 0, "status": "no_data"})
    except:
        return jsonify({"temp": 0, "load": 0, "status": "error"})

@app.route("/api/history")
def api_history():
    if collection is None:
        return jsonify([])
    try:
        minutes = int(request.args.get("minutes", 10))
        start_time = datetime.now() - timedelta(minutes=minutes)
        docs = list(collection.find({"mqtt_timestamp": {"$gte": start_time.isoformat()}}).sort("mqtt_timestamp", 1))
        return jsonify([{
            "time": d.get("mqtt_timestamp", ""),
            "temp": d.get("temp", 0),
            "load": d.get("load", 0)
        } for d in docs])
    except:
        return jsonify([])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
