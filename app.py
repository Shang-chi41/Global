# app.py - CNC Monitor Dashboard - HOÀN CHỈNH
from flask import Flask, jsonify, request
from pymongo import MongoClient
from datetime import datetime, timedelta

app = Flask(__name__)

# ============================================
# MONGODB ATLAS CONFIG
# ============================================
MONGO_URI = "mongodb+srv://tn042182_db_user:pRCe.YNp34hL8v4@cluster0.rk7eki0.mongodb.net/"
DATABASE = "CNC_Database"
COLLECTION = "Sensor_Data"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    db = client[DATABASE]
    collection = db[COLLECTION]
    client.admin.command('ping')
    print("✅ MongoDB Atlas connected!")
except Exception as e:
    print(f"❌ MongoDB error: {e}")
    collection = None

# ============================================
# ROUTES
# ============================================
@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html lang="vi">
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
                -webkit-tap-highlight-color: transparent;
            }
            .container { max-width: 1000px; margin: 0 auto; }
            h1 { text-align: center; color: #4ecdc4; margin-bottom: 12px; font-size: 22px; }
            
            .gauges { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 12px; }
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
                margin-bottom: 12px; flex-wrap: wrap;
            }
            .btn {
                background: #16213e; color: white; border: 2px solid #4ecdc4;
                padding: 7px 14px; border-radius: 18px; cursor: pointer;
                font-size: 12px; transition: all 0.2s; touch-action: manipulation;
            }
            .btn:hover, .btn:active { background: #4ecdc4; color: #1a1a2e; }
            .btn.active { background: #4ecdc4; color: #1a1a2e; font-weight: bold; }
            
            .chart-box { 
                background: #16213e; padding: 12px; border-radius: 12px; margin-bottom: 12px;
                position: relative;
            }
            .chart-box h3 { margin-bottom: 6px; color: #ddd; font-size: 14px; }
            canvas { width: 100%; height: 260px !important; touch-action: none; }
            
            .chart-tooltip {
                position: absolute; background: rgba(0,0,0,0.95); color: white;
                padding: 10px 14px; border-radius: 10px; font-size: 13px;
                pointer-events: none; z-index: 10; display: none;
                border: 2px solid #4ecdc4; text-align: center;
                box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            }
            .chart-tooltip .tt-time { color: #4ecdc4; font-size: 12px; margin-bottom: 4px; }
            .chart-tooltip .tt-value { font-size: 20px; font-weight: bold; }
            
            .info-bar { 
                display: flex; justify-content: space-between; align-items: center;
                color: #888; font-size: 11px; margin-bottom: 10px; flex-wrap: wrap; gap: 4px;
            }
            
            .download-btn {
                background: #ff6b6b; color: white; border: none;
                padding: 10px 20px; border-radius: 20px; cursor: pointer;
                font-size: 14px; display: block; margin: 10px auto;
                touch-action: manipulation;
            }
            .download-btn:active { opacity: 0.7; }
            
            .loading-spinner {
                display: inline-block; width: 12px; height: 12px;
                border: 2px solid #4ecdc4; border-top-color: transparent;
                border-radius: 50%; animation: spin 0.6s linear infinite;
            }
            @keyframes spin { to { transform: rotate(360deg); } }
        </style>
    </head>
    <body>
        <div class="container" id="dashboard">
            <h1>🏭 CNC Machine Monitor</h1>
            
            <!-- TIME BUTTONS -->
            <div class="btn-group">
                <button class="btn active" onclick="changeTime(10, this)">10 phút</button>
                <button class="btn" onclick="changeTime(30, this)">30 phút</button>
                <button class="btn" onclick="changeTime(60, this)">1 giờ</button>
                <button class="btn" onclick="changeTime(360, this)">6 giờ</button>
                <button class="btn" onclick="changeTime(1440, this)">1 ngày</button>
                <button class="btn" onclick="changeTime(10080, this)">1 tuần</button>
            </div>
            
            <!-- INFO BAR -->
            <div class="info-bar">
                <span id="timeRange">📅 10 phút gần đây</span>
                <span id="updateInfo">🔄 Đang tải...</span>
            </div>
            
            <!-- GAUGES -->
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
            
            <!-- TEMP CHART -->
            <div class="chart-box" id="tempChartBox">
                <h3>📈 Nhiệt độ (°C) — Chạm vào đồ thị để xem chi tiết</h3>
                <canvas id="tempChart"></canvas>
                <div class="chart-tooltip" id="tempTooltip">
                    <div class="tt-time"></div>
                    <div class="tt-value"></div>
                </div>
            </div>
            
            <!-- LOAD CHART -->
            <div class="chart-box" id="loadChartBox">
                <h3>📈 Tải (%) — Chạm vào đồ thị để xem chi tiết</h3>
                <canvas id="loadChart"></canvas>
                <div class="chart-tooltip" id="loadTooltip">
                    <div class="tt-time"></div>
                    <div class="tt-value"></div>
                </div>
            </div>
            
            <button class="download-btn" onclick="downloadImage()">📸 Tải ảnh về máy</button>
        </div>

        <script>
            let currentTimeRange = 10;
            let isLoading = false;
            
            // ==========================================
            // CREATE CHART
            // ==========================================
            function createChart(canvasId, tooltipId, color, yMin, yMax, unit) {
                const canvas = document.getElementById(canvasId);
                const ctx = canvas.getContext('2d');
                const tooltip = document.getElementById(tooltipId);
                const chartBox = tooltip.parentElement;
                
                const chart = new Chart(ctx, {
                    type: 'line',
                    data: { labels: [], datasets: [{
                        data: [], borderColor: color,
                        backgroundColor: color.replace(')', ',0.1)').replace('rgb', 'rgba'),
                        borderWidth: 3, pointRadius: 0, pointHoverRadius: 8,
                        pointHoverBackgroundColor: 'white', pointHoverBorderColor: color,
                        pointHoverBorderWidth: 3, tension: 0.4, fill: true
                    }]},
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        animation: { duration: 300 },
                        interaction: { mode: 'index', intersect: false },
                        onClick: function(e, elements) {
                            if (elements.length > 0) {
                                const idx = elements[0].index;
                                const label = chart.data.labels[idx];
                                const value = chart.data.datasets[0].data[idx];
                                
                                chart.data.datasets[0].pointRadius = Array(chart.data.labels.length).fill(0);
                                chart.data.datasets[0].pointRadius[idx] = 8;
                                chart.data.datasets[0].pointBackgroundColor = 'white';
                                chart.data.datasets[0].pointBorderColor = color;
                                chart.data.datasets[0].pointBorderWidth = 3;
                                chart.update();
                                
                                const rect = chartBox.getBoundingClientRect();
                                const canvasRect = canvas.getBoundingClientRect();
                                const x = canvasRect.left - rect.left + elements[0].element.x;
                                const y = canvasRect.top - rect.top + elements[0].element.y - 75;
                                
                                tooltip.querySelector('.tt-time').textContent = '🕐 ' + label;
                                tooltip.querySelector('.tt-value').textContent = value.toFixed(1) + ' ' + unit;
                                tooltip.querySelector('.tt-value').style.color = color;
                                tooltip.style.display = 'block';
                                tooltip.style.left = Math.min(Math.max(x - 60, 5), rect.width - 130) + 'px';
                                tooltip.style.top = Math.max(y, 5) + 'px';
                                
                                clearTimeout(tooltip._timeout);
                                tooltip._timeout = setTimeout(() => {
                                    tooltip.style.display = 'none';
                                    chart.data.datasets[0].pointRadius = 0;
                                    chart.update();
                                }, 3000);
                            }
                        },
                        scales: {
                            x: { ticks: { color: '#888', maxTicksLimit: 8, font:{size:10} }, grid: { color: '#2d2d2d' } },
                            y: { ticks: { color: '#888', font:{size:10} }, grid: { color: '#2d2d2d' }, min: yMin, max: yMax }
                        },
                        plugins: { legend: { display: false }, tooltip: { enabled: false } }
                    }
                });
                return chart;
            }
            
            const tempChart = createChart('tempChart', 'tempTooltip', '#ff6b6b', 30, 60, '°C');
            const loadChart = createChart('loadChart', 'loadTooltip', '#4ecdc4', 0, 100, '%');
            
            // ==========================================
            // CHANGE TIME
            // ==========================================
            function changeTime(minutes, btn) {
                if (isLoading) return;
                currentTimeRange = minutes;
                document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                let label = '';
                if (minutes >= 10080) label = Math.round(minutes/10080) + ' tuần';
                else if (minutes >= 1440) label = Math.round(minutes/1440) + ' ngày';
                else if (minutes >= 60) label = Math.round(minutes/60) + ' giờ';
                else label = minutes + ' phút';
                document.getElementById('timeRange').textContent = '📅 ' + label + ' gần đây';
                
                fetchHistory();
            }
            
            // ==========================================
            // FETCH HISTORY
            // ==========================================
            async function fetchHistory() {
                if (isLoading) return;
                isLoading = true;
                document.getElementById('updateInfo').innerHTML = '<span class="loading-spinner"></span> Đang tải...';
                
                try {
                    const url = '/api/history?minutes=' + currentTimeRange + '&_t=' + Date.now();
                    const res = await fetch(url);
                    const data = await res.json();
                    
                    tempChart.data.labels = [];
                    tempChart.data.datasets[0].data = [];
                    loadChart.data.labels = [];
                    loadChart.data.datasets[0].data = [];
                    
                    if (!data.length) {
                        document.getElementById('updateInfo').textContent = '⚠️ Không có dữ liệu';
                        isLoading = false;
                        tempChart.update(); loadChart.update();
                        return;
                    }
                    
                    const labels = [], temps = [], loads = [];
                    data.forEach(d => {
                        let time = '';
                        try {
                            const t = new Date(d.time);
                            time = t.toLocaleTimeString('vi-VN', {hour:'2-digit', minute:'2-digit'});
                        } catch(e) { time = d.time || ''; }
                        labels.push(time);
                        temps.push(d.temp || 0);
                        loads.push(d.load || 0);
                    });
                    
                    tempChart.data.labels = labels;
                    tempChart.data.datasets[0].data = temps;
                    loadChart.data.labels = labels;
                    loadChart.data.datasets[0].data = loads;
                    tempChart.update(); loadChart.update();
                    
                    document.getElementById('updateInfo').textContent = 
                        '🔄 ' + new Date().toLocaleTimeString('vi-VN') + ' | ' + data.length + ' điểm';
                } catch(e) {
                    document.getElementById('updateInfo').textContent = '❌ Lỗi tải dữ liệu';
                } finally {
                    isLoading = false;
                }
            }
            
            // ==========================================
            // FETCH LATEST
            // ==========================================
            async function fetchLatest() {
                try {
                    const res = await fetch('/api/latest?_t=' + Date.now());
                    const d = await res.json();
                    document.getElementById('tempValue').textContent = d.temp ? d.temp.toFixed(1) + '°C' : '--°C';
                    document.getElementById('loadValue').textContent = d.load ? d.load + '%' : '--%';
                    document.getElementById('statusValue').innerHTML = 
                        '<span class="status-badge ' + (d.status||'') + '">' + (d.status||'--').toUpperCase() + '</span>';
                } catch(e) {}
            }
            
            function downloadImage() {
                html2canvas(document.getElementById('dashboard'), { backgroundColor: '#1a1a2e', scale: 2 })
                    .then(canvas => {
                        const a = document.createElement('a');
                        a.download = 'CNC_' + new Date().toISOString().slice(0,19).replace(/:/g,'-') + '.png';
                        a.href = canvas.toDataURL('image/png');
                        a.click();
                    });
            }
            
            fetchLatest(); fetchHistory();
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
    if collection is None:
        return jsonify([])
    try:
        minutes = int(request.args.get("minutes", 10))
        now = datetime.now()
        start_time = now - timedelta(minutes=minutes)
        
        print(f"🕐 NOW: {now.strftime('%H:%M:%S')}")
        print(f"🕐 FROM: {start_time.strftime('%H:%M:%S')} ({minutes} phút trước)")
        
        query = {
            "mqtt_timestamp": {
                "$gte": start_time.isoformat(),
                "$lte": now.isoformat()
            }
        }
        docs = list(collection.find(query).sort("mqtt_timestamp", 1))
        
        print(f"📊 Found: {len(docs)} records")
        
        # Giới hạn 500 điểm
        if len(docs) > 500:
            step = len(docs) // 500
            docs = docs[::step]
        
        data = []
        for doc in docs:
            data.append({
                "time": doc.get("mqtt_timestamp", ""),
                "temp": doc.get("temp", 0),
                "load": doc.get("load", 0)
            })
        return jsonify(data)
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify([])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
