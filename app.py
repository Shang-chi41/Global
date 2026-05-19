# app.py - Dashboard với tooltip khi chạm vào biểu đồ
from flask import Flask, jsonify, request
from pymongo import MongoClient
from datetime import datetime, timedelta
import pytz

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
            
            .loading {
                display: inline-block;
                width: 12px;
                height: 12px;
                border: 2px solid #4ecdc4;
                border-top-color: transparent;
                border-radius: 50%;
                animation: spin 0.6s linear infinite;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
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
            let isLoading = false;
            
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
                                enabled: false,
                                external: function(context) {
                                    const tooltipModel = context.tooltip;
                                    
                                    if (tooltipModel.opacity === 0) {
                                        tooltip.style.display = 'none';
                                        return;
                                    }
                                    
                                    if (tooltipModel.dataPoints && tooltipModel.dataPoints.length > 0) {
                                        const dp = tooltipModel.dataPoints[0];
                                        const label = dp.label || '';
                                        const value = dp.raw !== undefined ? dp.raw.toFixed(1) : '--';
                                        
                                        tooltip.innerHTML = `
                                            <div style="color:#4ecdc4;margin-bottom:4px;">🕐 ${label}</div>
                                            <div style="font-size:16px;font-weight:bold;color:${color};">
                                                ${value}
                                            </div>
                                        `;
                                        tooltip.style.display = 'block';
                                        
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
            function changeTime(minutes, btnElement) {
                if (isLoading) return;
                
                currentTimeRange = minutes;
                
                // Update active button
                document.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
                btnElement.classList.add('active');
                
                // Update label
                let label = '';
                if (minutes >= 10080) {
                    label = (minutes/10080).toFixed(0) + ' tuần';
                } else if (minutes >= 1440) {
                    label = (minutes/1440).toFixed(0) + ' ngày';
                } else if (minutes >= 360) {
                    label = (minutes/60).toFixed(0) + ' giờ';
                } else if (minutes >= 60) {
                    label = (minutes/60).toFixed(0) + ' giờ';
                } else {
                    label = minutes + ' phút';
                }
                document.getElementById('timeRange').textContent = '📅 ' + label + ' gần đây (từ hiện tại)';
                
                // Fetch new data
                fetchHistory();
            }
            
            // ==========================================
            // FETCH HISTORY - LẤY DỮ LIỆU TỪ HIỆN TẠI TRỞ VỀ
            // ==========================================
            async function fetchHistory() {
                if (isLoading) return;
                
                isLoading = true;
                document.getElementById('updateInfo').innerHTML = '<span class="loading"></span> Đang tải dữ liệu...';
                
                try {
                    const now = new Date();
                    const url = `/api/history?minutes=${currentTimeRange}&_t=${now.getTime()}`; // Thêm timestamp để tránh cache
                    const res = await fetch(url);
                    
                    if (!res.ok) {
                        throw new Error('Network response was not ok');
                    }
                    const data = await res.json();
                    
                    // Clear existing data
                    tempChart.data.labels = [];
                    tempChart.data.datasets[0].data = [];
                    loadChart.data.labels = [];
                    loadChart.data.datasets[0].data = [];
                    
                    if (data.length === 0) {
                        document.getElementById('updateInfo').innerHTML = '⚠️ Không có dữ liệu trong ' + currentTimeRange + ' phút qua';
                        isLoading = false;
                        tempChart.update();
                        loadChart.update();
                        return;
                    }
                    
                    // Process data
                    const labels = [];
                    const temps = [];
                    const loads = [];
                    
                    data.forEach(d => {
                        let time = '';
                        try {
                            const t = new Date(d.time);
                            // Format time based on range
                            if (currentTimeRange >= 10080) {
                                // For weeks, show date and hour
                                time = t.toLocaleString('vi-VN', {month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'});
                            } else if (currentTimeRange >= 1440) {
                                // For days, show date and hour
                                time = t.toLocaleString('vi-VN', {month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit'});
                            } else if (currentTimeRange >= 360) {
                                // For hours, show hour:minute
                                time = t.toLocaleTimeString('vi-VN', {hour:'2-digit', minute:'2-digit'});
                            } else {
                                // For minutes, show hour:minute:second
                                time = t.toLocaleTimeString('vi-VN', {hour:'2-digit', minute:'2-digit', second:'2-digit'});
                            }
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
                    
                    tempChart.update('none');
                    loadChart.update('none');
                    
                    // Calculate time range text
                    let startTime = new Date(data[0].time);
                    let endTime = new Date(data[data.length-1].time);
                    document.getElementById('updateInfo').innerHTML = 
                        `🔄 ${new Date().toLocaleTimeString('vi-VN')} | ${data.length} điểm | ${startTime.toLocaleTimeString('vi-VN')} → ${endTime.toLocaleTimeString('vi-VN')}`;
                    
                } catch(e) {
                    console.error('Error fetching history:', e);
                    document.getElementById('updateInfo').innerHTML = '❌ Lỗi kết nối, thử lại sau...';
                } finally {
                    isLoading = false;
                }
            }
            
            // ==========================================
            // FETCH LATEST
            // ==========================================
            async function fetchLatest() {
                try {
                    const res = await fetch('/api/latest?_t=' + new Date().getTime());
                    if (!res.ok) throw new Error('Network error');
                    const d = await res.json();
                    
                    if (d.temp !== undefined && d.temp !== null && d.temp !== 0) {
                        document.getElementById('tempValue').textContent = d.temp.toFixed(1) + '°C';
                    } else {
                        document.getElementById('tempValue').textContent = '--°C';
                    }
                    
                    if (d.load !== undefined && d.load !== null && d.load !== 0) {
                        document.getElementById('loadValue').textContent = d.load + '%';
                    } else {
                        document.getElementById('loadValue').textContent = '--%';
                    }
                    
                    const statusEl = document.getElementById('statusValue');
                    if (d.status && d.status !== 'unknown' && d.status !== 'no_data' && d.status !== 'db_error') {
                        statusEl.innerHTML = '<span class="status-badge ' + d.status + '">' + d.status.toUpperCase() + '</span>';
                    } else {
                        statusEl.innerHTML = '<span class="status-badge">NO DATA</span>';
                    }
                    
                } catch(e) {
                    console.error('Error fetching latest:', e);
                }
            }
            
            // ==========================================
            // DOWNLOAD IMAGE
            // ==========================================
            function downloadImage() {
                const btn = document.querySelector('.download-btn');
                btn.textContent = '📸 Đang xử lý...';
                btn.disabled = true;
                
                html2canvas(document.getElementById('dashboard'), {
                    backgroundColor: '#1a1a2e',
                    scale: 2,
                    logging: false,
                    useCORS: false
                }).then(canvas => {
                    const link = document.createElement('a');
                    const now = new Date();
                    link.download = `CNC_${now.getFullYear()}-${now.getMonth()+1}-${now.getDate()}_${now.getHours()}-${now.getMinutes()}-${now.getSeconds()}.png`;
                    link.href = canvas.toDataURL('image/png');
                    link.click();
                    btn.textContent = '📸 Tải ảnh về máy';
                    btn.disabled = false;
                }).catch(error => {
                    console.error('Error generating image:', error);
                    btn.textContent = '📸 Lỗi, thử lại';
                    btn.disabled = false;
                    setTimeout(() => {
                        btn.textContent = '📸 Tải ảnh về máy';
                    }, 2000);
                });
            }
            
            // ==========================================
            // INIT & AUTO REFRESH
            // ==========================================
            // Initial load
            fetchLatest();
            fetchHistory();
            
            // Auto refresh latest data every 3 seconds
            setInterval(fetchLatest, 3000);
            
            // Auto refresh history every 30 seconds (cập nhật dữ liệu mới nhất)
            setInterval(fetchHistory, 30000);
        </script>
    </body>
    </html>
    """

@app.route("/api/latest")
def api_latest():
    """Lấy dữ liệu mới nhất"""
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
        print(f"Error in api_latest: {e}")
        return jsonify({"temp": 0, "load": 0, "status": "error"})

@app.route("/api/history")
def api_history():
    """Lấy dữ liệu trong khoảng thời gian từ hiện tại trở về trước"""
    if collection is None:
        return jsonify([])
    try:
        minutes = int(request.args.get("minutes", 10))
        
        # Lấy thời điểm hiện tại
        now = datetime.now()
        
        # Tính thời điểm bắt đầu (hiện tại trừ đi số phút)
        start_time = now - timedelta(minutes=minutes)
        
        print(f"📊 Query: {minutes} minutes ago")
        print(f"   From: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   To:   {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Query để lấy dữ liệu trong khoảng thời gian
        # CẦN CHÚ Ý: Đảm bảo field 'mqtt_timestamp' tồn tại và đúng định dạng
        query = {"mqtt_timestamp": {"$gte": start_time.isoformat(), "$lte": now.isoformat()}}
        
        # Sort theo thời gian tăng dần
        docs = list(collection.find(query).sort("mqtt_timestamp", 1))
        
        print(f"   Found: {len(docs)} records")
        
        # Nếu quá nhiều dữ liệu, lấy mẫu để hiển thị (tối đa 500 điểm)
        if len(docs) > 500:
            step = len(docs) // 500
            docs = docs[::step]
            print(f"   Sampled: {len(docs)} records")
        
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
        print(f"❌ Error in api_history: {e}")
        import traceback
        traceback.print_exc()
        return jsonify([])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
