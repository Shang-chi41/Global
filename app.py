# app.py - Dashboard với tooltip khi chạm vào biểu đồ
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
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                background: #1a1a2e; color: white; padding: 10px;
                -webkit-tap-highlight-color: transparent;
            }
            .container { max-width: 1000px; margin: 0 auto; }
            h1 { text-align: center; color: #4ecdc4; margin-bottom: 10px; font-size: 20px; }
            
            /* Gauges */
            .gauges { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 10px; }
            .card { background: #16213e; padding: 12px; border-radius: 12px; text-align: center; }
            .card-label { color: #888; font-size: 11px; margin-bottom: 4px; }
            .card-value { font-size: 28px; font-weight: bold; }
            .temp-color { color: #ff6b6b; }
            .load-color { color: #4ecdc4; }
            
            .status-badge {
                display: inline-block; padding: 5px 12px; border-radius: 12px;
                font-size: 14px; font-weight: bold; margin-top: 3px;
            }
            .running { background: #00b894; }
            .idle { background: #fdcb6e; color: #333; }
            .maintenance { background: #e17055; }
            .error { background: #d63031; animation: blink 0.5s infinite; }
            @keyframes blink { 50% { opacity: 0.5; } }
            
            /* Buttons */
            .btn-group { 
                display: flex; gap: 6px; justify-content: center; 
                margin-bottom: 10px; flex-wrap: wrap;
            }
            .btn {
                background: #16213e; color: white; border: 2px solid #4ecdc4;
                padding: 6px 12px; border-radius: 15px; cursor: pointer;
                font-size: 12px; transition: all 0.2s; touch-action: manipulation;
            }
            .btn:active { background: #4ecdc4; color: #1a1a2e; }
            .btn.active { background: #4ecdc4; color: #1a1a2e; font-weight: bold; }
            
            /* Chart */
            .chart-box { 
                background: #16213e; padding: 12px; border-radius: 12px; margin-bottom: 10px;
                position: relative;
            }
            .chart-box h3 { margin-bottom: 6px; color: #ddd; font-size: 14px; }
            canvas { width: 100%; height: 250px !important; touch-action: none; }
            
            /* Tooltip custom */
            .chart-tooltip {
                position: absolute; background: rgba(0,0,0,0.9); color: white;
                padding: 8px 12px; border-radius: 8px; font-size: 13px;
                pointer-events: none; z-index: 10; display: none;
                border: 1px solid #4ecdc4; white-space: nowrap;
            }
            
            /* Info */
            .info-bar { 
                display: flex; justify-content: space-between; align-items: center;
                color: #888; font-size: 11px; margin-bottom: 8px; flex-wrap: wrap; gap: 4px;
            }
            
            .download-btn {
                background: #ff6b6b; color: white; border: none;
                padding: 8px 16px; border-radius: 15px; cursor: pointer;
                font-size: 12px; display: block; margin: 8px auto;
                touch-action: manipulation;
            }
            .download-btn:active { opacity: 0.7; }
        </style>
    </head>
    <body>
        <div class="container" id="dashboard">
            <h1>🏭 CNC Machine Monitor</h1>
            
            <!-- TIME BUTTONS -->
            <div class="btn-group">
                <button class="btn active" onclick="changeTime(10)">10 phút</button>
                <button class="btn" onclick="changeTime(30)">30 phút</button>
                <button class="btn" onclick="changeTime(60)">1 giờ</button>
                <button class="btn" onclick="changeTime(360)">6 giờ</button>
                <button class="btn" onclick="changeTime(1440)">1 ngày</button>
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
            
            <!-- TEMPERATURE CHART -->
            <div class="chart-box" id="tempChartBox">
                <h3>📈 Nhiệt độ (°C)</h3>
                <canvas id="tempChart"></canvas>
                <div class="chart-tooltip" id="tempTooltip"></div>
            </div>
            
            <!-- LOAD CHART -->
            <div class="chart-box" id="loadChartBox">
                <h3>📈 Tải (%)</h3>
                <canvas id="loadChart"></canvas>
                <div class="chart-tooltip" id="loadTooltip"></div>
            </div>
            
            <!-- DOWNLOAD -->
            <button class="download-btn" onclick="downloadImage()">📸 Tải ảnh về máy</button>
        </div>

        <script>
            let currentTimeRange = 10;
            
            // ==========================================
            // CHART SETUP WITH TOOLTIP
            // ==========================================
            function createChart(canvasId, tooltipId, color, yMin, yMax) {
                const ctx = document.getElementById(canvasId).getContext('2d');
                const tooltip = document.getElementById(tooltipId);
                const chartBox = tooltip.parentElement;
                
                const chart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            data: [],
                            borderColor: color,
                            backgroundColor: color.replace(')', ',0.1)').replace('rgb', 'rgba'),
                            borderWidth: 2.5,
                            pointRadius: 0,
                            pointHoverRadius: 6,
                            pointHoverBackgroundColor: 'white',
                            pointHoverBorderColor: color,
                            pointHoverBorderWidth: 2,
                            tension: 0.3,
                            fill: true
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        animation: { duration: 200 },
                        interaction: {
                            mode: 'index',
                            intersect: false
                        },
                        scales: {
                            x: { 
                                ticks: { color: '#888', maxTicksLimit: 8, font: { size: 10 } },
                                grid: { color: '#2d2d2d' }
                            },
                            y: { 
                                ticks: { color: '#888', font: { size: 10 } },
                                grid: { color: '#2d2d2d' },
                                min: yMin, max: yMax
                            }
                        },
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                enabled: false,  // Tắt tooltip mặc định
                                external: function(context) {
                                    // Tooltip custom
                                    const tooltipModel = context.tooltip;
                                    
                                    if (tooltipModel.opacity === 0) {
                                        tooltip.style.display = 'none';
                                        return;
                                    }
                                    
                                    if (tooltipModel.dataPoints && tooltipModel.dataPoints.length > 0) {
                                        const dp = tooltipModel.dataPoints[0];
                                        const label = dp.label || '';
                                        const value = dp.raw !== undefined ? dp.raw.toFixed(1) : '--';
                                        const datasetLabel = context.chart.data.datasets[dp.datasetIndex].label || '';
                                        
                                        tooltip.innerHTML = `
                                            <div style="color:#4ecdc4;margin-bottom:4px;">🕐 ${label}</div>
                                            <div style="font-size:16px;font-weight:bold;color:${color};">
                                                ${value}
                                            </div>
                                        `;
                                        tooltip.style.display = 'block';
                                        
                                        // Vị trí tooltip
                                        const rect = chartBox.getBoundingClientRect();
                                        const canvasRect = context.chart.canvas.getBoundingClientRect();
                                        const x = canvasRect.left - rect.left + tooltipModel.caretX;
                                        const y = canvasRect.top - rect.top + tooltipModel.caretY - 60;
                                        
                                        tooltip.style.left = Math.min(x, rect.width - 120) + 'px';
                                        tooltip.style.top = Math.max(y, 5) + 'px';
                                    }
                                }
                            }
                        }
                    }
                });
                
                return chart;
            }
            
            const tempChart = createChart('tempChart', 'tempTooltip', '#ff6b6b', 20, 60);
            const loadChart = createChart('loadChart', 'loadTooltip', '#4ecdc4', 0, 100);
            
            // ==========================================
            // CHANGE TIME
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
            // FETCH HISTORY
            // ==========================================
            async function fetchHistory() {
                try {
                    const res = await fetch('/api/history?minutes=' + currentTimeRange);
                    const data = await res.json();
                    
                    // Clear
                    tempChart.data.labels = [];
                    tempChart.data.datasets[0].data = [];
                    loadChart.data.labels = [];
                    loadChart.data.datasets[0].data = [];
                    
                    // Add data
                    const labels = [];
                    const temps = [];
                    const loads = [];
                    
                    data.forEach(d => {
                        let time = '';
                        try {
                            const t = new Date(d.time);
                            time = t.toLocaleTimeString('vi-VN', {hour:'2-digit', minute:'2-digit'});
                        } catch(e) {
                            time = d.time || '';
                        }
                        
                        labels.push(time);
                        temps.push(d.temp || 0);
                        loads.push(d.load || 0);
                    });
                    
                    tempChart.data.labels = labels;
                    tempChart.data.datasets[0].data = temps;
                    loadChart.data.labels = labels;
                    loadChart.data.datasets[0].data = loads;
                    
                    tempChart.update();
                    loadChart.update();
                    
                    document.getElementById('updateInfo').textContent = 
                        '🔄 ' + new Date().toLocaleTimeString() + ' | ' + data.length + ' điểm';
                    
                } catch(e) {
                    console.error(e);
                }
            }
            
            // ==========================================
            // FETCH LATEST
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
                    const link = document.createElement('a');
                    link.download = 'CNC_' + new Date().toISOString().slice(0,16).replace(/:/g,'-') + '.png';
                    link.href = canvas.toDataURL('image/png');
                    link.click();
                });
            }
            
            // ==========================================
            // INIT
            // ==========================================
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
            return jsonify({
                "temp": doc.get("temp", 0),
                "load": doc.get("load", 0),
                "status": doc.get("status", "unknown")
            })
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
        query = {"mqtt_timestamp": {"$gte": start_time.isoformat()}}
        docs = list(collection.find(query).sort("mqtt_timestamp", 1))
        
        data = []
        for doc in docs:
            data.append({
                "time": doc.get("mqtt_timestamp", ""),
                "temp": doc.get("temp", 0),
                "load": doc.get("load", 0),
                "status": doc.get("status", "")
            })
        return jsonify(data)
    except:
        return jsonify([])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
