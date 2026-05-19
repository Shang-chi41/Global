# app.py - CNC Monitor HOÀN CHỈNH
# 2 chế độ: LIVE (real-time) + LỊCH SỬ (query từ hiện tại trở về X phút)
from flask import Flask, jsonify, request
from pymongo import MongoClient
from datetime import datetime, timedelta

app = Flask(__name__)

MONGO_URI = "mongodb+srv://tn042182_db_user:pRCe.YNp34hL8v4@cluster0.rk7eki0.mongodb.net/"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000)
    db = client["CNC_Database"]
    collection = db["Sensor_Data"]
    client.admin.command('ping')
    print("✅ MongoDB Atlas connected!")
except Exception as e:
    print(f"❌ MongoDB error: {e}")
    collection = None

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
            body { font-family: -apple-system, Arial, sans-serif; background: #1a1a2e; color: white; padding: 10px; }
            .container { max-width: 1000px; margin: 0 auto; }
            h1 { text-align: center; color: #4ecdc4; font-size: 20px; margin-bottom: 10px; }
            
            .mode-switch { display: flex; justify-content: center; margin-bottom: 12px; background: #16213e; border-radius: 25px; overflow: hidden; width: fit-content; margin: 0 auto 12px auto; }
            .mode-btn { padding: 10px 24px; cursor: pointer; font-size: 13px; font-weight: bold; border: none; color: #888; background: transparent; }
            .mode-btn.active { background: #4ecdc4; color: #1a1a2e; }
            
            .gauges { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 12px; }
            .card { background: #16213e; padding: 12px; border-radius: 12px; text-align: center; }
            .card-label { color: #888; font-size: 11px; }
            .card-value { font-size: 28px; font-weight: bold; margin-top: 4px; }
            .temp-color { color: #ff6b6b; }
            .load-color { color: #4ecdc4; }
            
            .status-badge { display: inline-block; padding: 5px 12px; border-radius: 12px; font-size: 14px; font-weight: bold; margin-top: 4px; }
            .running { background: #00b894; }
            .idle { background: #fdcb6e; color: #333; }
            .maintenance { background: #e17055; }
            .error { background: #d63031; animation: blink 0.5s infinite; }
            @keyframes blink { 50% { opacity: 0.5; } }
            
            .btn-group { display: flex; gap: 6px; justify-content: center; margin-bottom: 12px; flex-wrap: wrap; }
            .btn { background: #16213e; color: white; border: 2px solid #4ecdc4; padding: 7px 14px; border-radius: 18px; cursor: pointer; font-size: 12px; }
            .btn.active { background: #4ecdc4; color: #1a1a2e; font-weight: bold; }
            
            .chart-box { background: #16213e; padding: 12px; border-radius: 12px; margin-bottom: 12px; position: relative; }
            .chart-box h3 { margin-bottom: 6px; color: #ddd; font-size: 14px; }
            canvas { width: 100%; height: 260px !important; touch-action: none; }
            
            .chart-tooltip { position: absolute; background: rgba(0,0,0,0.95); color: white; padding: 10px 14px; border-radius: 10px; font-size: 13px; pointer-events: none; z-index: 10; display: none; border: 2px solid #4ecdc4; text-align: center; }
            .chart-tooltip .tt-time { color: #4ecdc4; font-size: 12px; margin-bottom: 4px; }
            .chart-tooltip .tt-value { font-size: 20px; font-weight: bold; }
            
            .info-bar { display: flex; justify-content: space-between; color: #888; font-size: 11px; margin-bottom: 10px; }
            .live-dot { width: 10px; height: 10px; background: #00b894; border-radius: 50%; display: inline-block; animation: pulse 1.5s infinite; }
            @keyframes pulse { 50% { opacity: 0.3; } }
            
            .download-btn { background: #ff6b6b; color: white; border: none; padding: 10px 20px; border-radius: 20px; cursor: pointer; font-size: 14px; display: block; margin: 10px auto; }
        </style>
    </head>
    <body>
        <div class="container" id="dashboard">
            <h1>🏭 CNC Machine Monitor</h1>
            
            <div class="mode-switch">
                <button class="mode-btn active" onclick="switchMode('live')">🔴 LIVE</button>
                <button class="mode-btn" onclick="switchMode('history')">📅 LỊCH SỬ</button>
            </div>
            
            <div class="info-bar">
                <span id="infoLeft"><span class="live-dot"></span> REAL-TIME</span>
                <span id="infoRight">🔄 Đang tải...</span>
            </div>
            
            <div class="gauges">
                <div class="card"><div class="card-label">🌡️ NHIỆT ĐỘ</div><div class="card-value temp-color" id="tempValue">--°C</div></div>
                <div class="card"><div class="card-label">⚙️ TẢI</div><div class="card-value load-color" id="loadValue">--%</div></div>
                <div class="card"><div class="card-label">📌 TRẠNG THÁI</div><div id="statusValue"><span class="status-badge">--</span></div></div>
            </div>
            
            <div class="btn-group" id="historyBtns" style="display:none;">
                <button class="btn active" onclick="changeTime(10, this)">10 phút</button>
                <button class="btn" onclick="changeTime(30, this)">30 phút</button>
                <button class="btn" onclick="changeTime(60, this)">1 giờ</button>
                <button class="btn" onclick="changeTime(360, this)">6 giờ</button>
                <button class="btn" onclick="changeTime(1440, this)">1 ngày</button>
            </div>
            
            <div class="chart-box" id="tempChartBox">
                <h3>📈 Nhiệt độ (°C)</h3>
                <canvas id="tempChart"></canvas>
                <div class="chart-tooltip" id="tempTooltip"><div class="tt-time"></div><div class="tt-value"></div></div>
            </div>
            
            <div class="chart-box" id="loadChartBox">
                <h3>📈 Tải (%)</h3>
                <canvas id="loadChart"></canvas>
                <div class="chart-tooltip" id="loadTooltip"><div class="tt-time"></div><div class="tt-value"></div></div>
            </div>
            
            <button class="download-btn" onclick="downloadImage()">📸 Tải ảnh về máy</button>
        </div>

        <script>
            let currentMode = 'live';
            let historyMinutes = 10;
            let liveTimer = null;
            let historyTimer = null;
            const MAX_LIVE_POINTS = 60;
            
            function createChart(canvasId, tooltipId, color, yMin, yMax, unit) {
                const canvas = document.getElementById(canvasId);
                const ctx = canvas.getContext('2d');
                const tooltip = document.getElementById(tooltipId);
                const chartBox = tooltip.parentElement;
                
                const chart = new Chart(ctx, {
                    type: 'line',
                    data: { labels: [], datasets: [{ data: [], borderColor: color, backgroundColor: color.replace(')', ',0.1)').replace('rgb', 'rgba'), borderWidth: 3, pointRadius: 0, pointHoverRadius: 8, pointHoverBackgroundColor: 'white', pointHoverBorderColor: color, pointHoverBorderWidth: 3, tension: 0.4, fill: true }]},
                    options: {
                        responsive: true, maintainAspectRatio: false, animation: { duration: 200 },
                        interaction: { mode: 'index', intersect: false },
                        onClick: function(e, elements) {
                            if (elements.length > 0) {
                                const idx = elements[0].index;
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
                                
                                tooltip.querySelector('.tt-time').textContent = '🕐 ' + chart.data.labels[idx];
                                tooltip.querySelector('.tt-value').textContent = chart.data.datasets[0].data[idx].toFixed(1) + ' ' + unit;
                                tooltip.querySelector('.tt-value').style.color = color;
                                tooltip.style.display = 'block';
                                tooltip.style.left = Math.min(Math.max(x - 60, 5), rect.width - 130) + 'px';
                                tooltip.style.top = Math.max(y, 5) + 'px';
                                
                                clearTimeout(tooltip._timeout);
                                tooltip._timeout = setTimeout(() => { tooltip.style.display = 'none'; chart.data.datasets[0].pointRadius = 0; chart.update(); }, 3000);
                            }
                        },
                        scales: { x: { ticks: { color: '#888', maxTicksLimit: 8, font:{size:10} }, grid: { color: '#2d2d2d' } }, y: { ticks: { color: '#888', font:{size:10} }, grid: { color: '#2d2d2d' }, min: yMin, max: yMax } },
                        plugins: { legend: { display: false }, tooltip: { enabled: false } }
                    }
                });
                return chart;
            }
            
            const tempChart = createChart('tempChart', 'tempTooltip', '#ff6b6b', 30, 60, '°C');
            const loadChart = createChart('loadChart', 'loadTooltip', '#4ecdc4', 0, 100, '%');
            
            function switchMode(mode) {
                currentMode = mode;
                document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
                event.target.classList.add('active');
                if (liveTimer) clearInterval(liveTimer);
                if (historyTimer) clearInterval(historyTimer);
                
                tempChart.data.labels = []; tempChart.data.datasets[0].data = []; tempChart.data.datasets[0].pointRadius = 0;
                loadChart.data.labels = []; loadChart.data.datasets[0].data = []; loadChart.data.datasets[0].pointRadius = 0;
                tempChart.update(); loadChart.update();
                
                if (mode === 'live') {
                    document.getElementById('historyBtns').style.display = 'none';
                    document.getElementById('infoLeft').innerHTML = '<span class="live-dot"></span> REAL-TIME';
                    startLiveMode();
                } else {
                    document.getElementById('historyBtns').style.display = 'flex';
                    document.getElementById('infoLeft').textContent = '📅 LỊCH SỬ';
                    startHistoryMode();
                }
            }
            
            function startLiveMode() {
                function fetchLiveData() {
                    fetch('/api/latest?_t=' + Date.now()).then(r => r.json()).then(d => {
                        document.getElementById('tempValue').textContent = d.temp ? d.temp.toFixed(1) + '°C' : '--°C';
                        document.getElementById('loadValue').textContent = d.load ? d.load + '%' : '--%';
                        document.getElementById('statusValue').innerHTML = '<span class="status-badge ' + (d.status||'') + '">' + (d.status||'--').toUpperCase() + '</span>';
                        if (d.temp === 0 && d.load === 0) return;
                        
                        const now = new Date().toLocaleTimeString('vi-VN', {hour:'2-digit', minute:'2-digit', second:'2-digit'});
                        tempChart.data.labels.push(now); tempChart.data.datasets[0].data.push(d.temp || 0);
                        loadChart.data.labels.push(now); loadChart.data.datasets[0].data.push(d.load || 0);
                        if (tempChart.data.labels.length > MAX_LIVE_POINTS) { tempChart.data.labels.shift(); tempChart.data.datasets[0].data.shift(); loadChart.data.labels.shift(); loadChart.data.datasets[0].data.shift(); }
                        tempChart.update('none'); loadChart.update('none');
                        document.getElementById('infoRight').textContent = '🔄 ' + now + ' | ' + tempChart.data.labels.length + ' điểm';
                    });
                }
                fetchLiveData();
                liveTimer = setInterval(fetchLiveData, 5000);
            }
            
            function startHistoryMode() { fetchHistory(); historyTimer = setInterval(fetchHistory, 30000); }
            
            function changeTime(minutes, btn) {
                historyMinutes = minutes;
                document.querySelectorAll('#historyBtns .btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                fetchHistory();
            }
            
            function fetchHistory() {
                document.getElementById('infoRight').textContent = '🔄 Đang tải...';
                fetch('/api/history?minutes=' + historyMinutes + '&_t=' + Date.now()).then(r => r.json()).then(data => {
                    tempChart.data.labels = []; tempChart.data.datasets[0].data = [];
                    loadChart.data.labels = []; loadChart.data.datasets[0].data = [];
                    data.forEach(d => {
                        let time = ''; try { time = new Date(d.time).toLocaleTimeString('vi-VN', {hour:'2-digit', minute:'2-digit'}); } catch(e) { time = d.time || ''; }
                        tempChart.data.labels.push(time); tempChart.data.datasets[0].data.push(d.temp || 0);
                        loadChart.data.labels.push(time); loadChart.data.datasets[0].data.push(d.load || 0);
                    });
                    tempChart.update(); loadChart.update();
                    document.getElementById('infoRight').textContent = '🔄 ' + new Date().toLocaleTimeString('vi-VN') + ' | ' + data.length + ' điểm';
                });
            }
            
            function fetchLatest() {
                fetch('/api/latest?_t=' + Date.now()).then(r => r.json()).then(d => {
                    document.getElementById('tempValue').textContent = d.temp ? d.temp.toFixed(1) + '°C' : '--°C';
                    document.getElementById('loadValue').textContent = d.load ? d.load + '%' : '--%';
                    document.getElementById('statusValue').innerHTML = '<span class="status-badge ' + (d.status||'') + '">' + (d.status||'--').toUpperCase() + '</span>';
                });
            }
            
            function downloadImage() {
                html2canvas(document.getElementById('dashboard'), { backgroundColor: '#1a1a2e', scale: 2 }).then(canvas => {
                    const a = document.createElement('a');
                    a.download = 'CNC_' + new Date().toISOString().slice(0,19).replace(/:/g,'-') + '.png';
                    a.href = canvas.toDataURL('image/png'); a.click();
                });
            }
            
            fetchLatest(); startLiveMode(); setInterval(fetchLatest, 3000);
        </script>
    </body>
    </html>
    """

@app.route("/api/latest")
def api_latest():
    if collection is None: return jsonify({"temp": 0, "load": 0, "status": "db_error"})
    try:
        doc = collection.find_one(sort=[("mqtt_timestamp", -1)])
        if doc: return jsonify({"temp": doc.get("temp", 0), "load": doc.get("load", 0), "status": doc.get("status", "unknown")})
        return jsonify({"temp": 0, "load": 0, "status": "no_data"})
    except: return jsonify({"temp": 0, "load": 0, "status": "error"})

@app.route("/api/history")
def api_history():
    if collection is None: return jsonify([])
    try:
        minutes = int(request.args.get("minutes", 10))
        
        # ✅ Dùng giờ Việt Nam (UTC+7)
        now = datetime.utcnow() + timedelta(hours=7)
        start_time = now - timedelta(minutes=minutes)
        
        start_str = start_time.strftime("%Y-%m-%dT%H:%M:%S.000000")
        now_str    = now.strftime("%Y-%m-%dT%H:%M:%S.999999")
        
        print(f"📅 Giờ VN hiện tại: {now.strftime('%H:%M:%S')}")
        print(f"📅 Từ: {start_str}  →  Đến: {now_str}")
        
        query = {
            "mqtt_timestamp": {
                "$gte": start_str,
                "$lte": now_str   # ✅ Giữ lại $lte để chặn chính xác
            }
        }
        
        docs = list(collection.find(query).sort("mqtt_timestamp", 1))
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
        print(f"❌ Error: {e}")
        return jsonify([])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
