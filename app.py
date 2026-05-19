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
        <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: -apple-system, Arial, sans-serif; background: #1a1a2e; color: white; padding: 12px; }
            .container { max-width: 680px; margin: 0 auto; }
            h1 { text-align: center; color: #4ecdc4; font-size: 19px; font-weight: 600; margin-bottom: 12px; }

            .mode-row { display: flex; justify-content: center; margin-bottom: 12px; }
            .mode-pill { background: #16213e; border-radius: 20px; overflow: hidden; display: flex; }
            .mode-btn { padding: 9px 22px; font-size: 13px; font-weight: 600; border: none; background: transparent; color: #888; cursor: pointer; transition: all .2s; }
            .mode-btn.active { background: #4ecdc4; color: #1a1a2e; }

            .info-bar { display: flex; justify-content: space-between; font-size: 11px; color: #888; margin-bottom: 10px; }
            .dot { width: 8px; height: 8px; background: #00b894; border-radius: 50%; display: inline-block; margin-right: 5px; animation: pulse 1.5s infinite; }
            @keyframes pulse { 50% { opacity: 0.3; } }

            .gauges { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 12px; }
            .card { background: #16213e; padding: 12px 8px; border-radius: 12px; text-align: center; }
            .card-label { color: #888; font-size: 10px; margin-bottom: 6px; letter-spacing: .5px; }
            .card-val { font-size: 26px; font-weight: 700; line-height: 1; }
            .red { color: #ff6b6b; }
            .teal { color: #4ecdc4; }
            .badge { display: inline-block; padding: 5px 12px; border-radius: 10px; font-size: 12px; font-weight: 700; margin-top: 4px; }
            .running { background: #00b894; color: white; }
            .idle { background: #fdcb6e; color: #333; }
            .maintenance { background: #e17055; color: white; }
            .error { background: #d63031; color: white; animation: blink .5s infinite; }
            @keyframes blink { 50% { opacity: .5; } }

            .history-btns { display: none; justify-content: center; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }
            .hbtn { background: #16213e; color: #ccc; border: 1.5px solid #4ecdc4; padding: 6px 14px; border-radius: 14px; font-size: 11px; cursor: pointer; transition: all .2s; }
            .hbtn.active { background: #4ecdc4; color: #1a1a2e; font-weight: 700; }

            .chart-box { background: #16213e; border-radius: 12px; padding: 12px; margin-bottom: 10px; }
            .chart-label { font-size: 12px; color: #ccc; margin-bottom: 8px; }
            .chart-wrap { position: relative; height: 130px; }
            svg.lc { width: 100%; height: 100%; overflow: visible; display: block; }

            .axis-x { display: flex; justify-content: space-between; padding: 2px 4px 0; }
            .axis-x span { font-size: 9px; color: #555; }

            /* Tooltip */
            .tt { position: absolute; background: rgba(0,0,0,.92); border: 1.5px solid #4ecdc4; border-radius: 8px; padding: 8px 12px; font-size: 12px; pointer-events: none; display: none; z-index: 10; text-align: center; }
            .tt-time { color: #4ecdc4; font-size: 10px; margin-bottom: 3px; }
            .tt-val { font-size: 18px; font-weight: 700; }

            .dl-btn { display: block; margin: 12px auto 4px; background: #ff6b6b; color: white; border: none; padding: 10px 24px; border-radius: 20px; font-size: 13px; cursor: pointer; font-weight: 600; }
        </style>
    </head>
    <body>
        <div class="container" id="dashboard">
            <h1>&#127981; CNC Machine Monitor</h1>

            <div class="mode-row">
                <div class="mode-pill">
                    <button class="mode-btn active" onclick="switchMode('live', this)">&#128308; LIVE</button>
                    <button class="mode-btn" onclick="switchMode('history', this)">&#128197; LỊCH SỬ</button>
                </div>
            </div>

            <div class="info-bar">
                <span id="infoLeft"><span class="dot"></span> REAL-TIME</span>
                <span id="infoRight">Đang tải...</span>
            </div>

            <div class="gauges">
                <div class="card">
                    <div class="card-label">🌡️ NHIỆT ĐỘ</div>
                    <div class="card-val red" id="tvTemp">--°C</div>
                </div>
                <div class="card">
                    <div class="card-label">⚙️ TẢI</div>
                    <div class="card-val teal" id="tvLoad">--%</div>
                </div>
                <div class="card">
                    <div class="card-label">📌 TRẠNG THÁI</div>
                    <div style="margin-top:4px"><span class="badge" id="tvStatus">--</span></div>
                </div>
            </div>

            <div class="history-btns" id="histBtns">
                <button class="hbtn active" onclick="changeTime(10,this)">10 phút</button>
                <button class="hbtn" onclick="changeTime(30,this)">30 phút</button>
                <button class="hbtn" onclick="changeTime(60,this)">1 giờ</button>
                <button class="hbtn" onclick="changeTime(360,this)">6 giờ</button>
                <button class="hbtn" onclick="changeTime(1440,this)">1 ngày</button>
            </div>

            <div class="chart-box">
                <div class="chart-label">📈 Nhiệt độ (°C)</div>
                <div class="chart-wrap" id="wrapTemp">
                    <svg class="lc" id="svgTemp" viewBox="0 0 560 120" preserveAspectRatio="none"></svg>
                    <div class="tt" id="ttTemp"><div class="tt-time"></div><div class="tt-val red"></div></div>
                </div>
                <div class="axis-x" id="axTemp"></div>
            </div>

            <div class="chart-box">
                <div class="chart-label">📈 Tải (%)</div>
                <div class="chart-wrap" id="wrapLoad">
                    <svg class="lc" id="svgLoad" viewBox="0 0 560 120" preserveAspectRatio="none"></svg>
                    <div class="tt" id="ttLoad"><div class="tt-time"></div><div class="tt-val teal"></div></div>
                </div>
                <div class="axis-x" id="axLoad"></div>
            </div>

            <button class="dl-btn" onclick="downloadImage()">📸 Tải ảnh về máy</button>
        </div>

        <script>
        const W = 560, H = 120, PAD = 10;
        let currentMode = 'live';
        let historyMinutes = 10;
        let liveTimer = null, historyTimer = null;
        const MAX_LIVE = 60;

        let tLabels = [], tData = [], lData = [];

        // ── SVG line chart renderer ─────────────────────────────────────────
        function drawChart(svgId, axId, tooltipId, data, labels, color, yMin, yMax, unit) {
            const svg = document.getElementById(svgId);
            const n = data.length;
            if (n < 2) { svg.innerHTML = ''; return; }

            const xS = i => PAD + (i / (n - 1)) * (W - PAD * 2);
            const yS = v => H - PAD - Math.max(0, Math.min(1, (v - yMin) / (yMax - yMin))) * (H - PAD * 2);

            const pts = data.map((v, i) => [xS(i), yS(v)]);

            // Smooth cubic bezier path
            let d = `M ${pts[0][0]},${pts[0][1]}`;
            for (let i = 1; i < pts.length; i++) {
                const mx = (pts[i-1][0] + pts[i][0]) / 2;
                d += ` C ${mx},${pts[i-1][1]} ${mx},${pts[i][1]} ${pts[i][0]},${pts[i][1]}`;
            }
            const fd = d + ` L ${pts[n-1][0]},${H} L ${pts[0][0]},${H} Z`;

            // Grid lines
            let grid = '';
            for (let g = 0; g <= 4; g++) {
                const y = PAD + (g / 4) * (H - PAD * 2);
                grid += `<line x1="${PAD}" y1="${y}" x2="${W - PAD}" y2="${y}" stroke="#252540" stroke-width="1"/>`;
            }

            svg.innerHTML = `
                <defs>
                    <linearGradient id="gr_${svgId}" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="${color}" stop-opacity="0.4"/>
                        <stop offset="100%" stop-color="${color}" stop-opacity="0.03"/>
                    </linearGradient>
                </defs>
                ${grid}
                <path d="${fd}" fill="url(#gr_${svgId})"/>
                <path d="${d}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
                <circle id="dot_${svgId}" cx="-99" cy="-99" r="5" fill="white" stroke="${color}" stroke-width="2.5" style="display:none"/>
            `;

            // Axis labels
            if (axId) {
                const ax = document.getElementById(axId);
                const idxs = [0, Math.floor(n*0.25), Math.floor(n*0.5), Math.floor(n*0.75), n-1];
                ax.innerHTML = idxs.map(i => `<span>${labels[i] || ''}</span>`).join('');
            }

            // Tap/click tooltip on SVG
            setupTooltip(svgId, tooltipId, pts, data, labels, color, unit);
        }

        function setupTooltip(svgId, tooltipId, pts, data, labels, color, unit) {
            const svg = document.getElementById(svgId);
            const tt = document.getElementById(tooltipId);
            const wrap = tt.parentElement;

            function showTip(clientX, clientY) {
                const rect = svg.getBoundingClientRect();
                const rx = (clientX - rect.left) / rect.width;
                const idx = Math.round(rx * (pts.length - 1));
                if (idx < 0 || idx >= pts.length) return;

                const dot = document.getElementById('dot_' + svgId);
                if (dot) {
                    dot.setAttribute('cx', pts[idx][0]);
                    dot.setAttribute('cy', pts[idx][1]);
                    dot.style.display = 'block';
                }

                tt.querySelector('.tt-time').textContent = '🕐 ' + (labels[idx] || '');
                tt.querySelector('.tt-val').textContent = data[idx].toFixed(1) + ' ' + unit;
                tt.style.display = 'block';

                const wRect = wrap.getBoundingClientRect();
                let tx = clientX - wRect.left - 55;
                let ty = clientY - wRect.top - 72;
                tx = Math.max(4, Math.min(tx, wRect.width - 120));
                ty = Math.max(4, ty);
                tt.style.left = tx + 'px';
                tt.style.top = ty + 'px';

                clearTimeout(tt._t);
                tt._t = setTimeout(() => {
                    tt.style.display = 'none';
                    if (dot) dot.style.display = 'none';
                }, 2500);
            }

            svg.onclick = e => showTip(e.clientX, e.clientY);
            svg.addEventListener('touchstart', e => {
                e.preventDefault();
                showTip(e.touches[0].clientX, e.touches[0].clientY);
            }, { passive: false });
        }

        function redraw() {
            drawChart('svgTemp', 'axTemp', 'ttTemp', tData, tLabels, '#ff6b6b', 30, 70, '°C');
            drawChart('svgLoad', 'axLoad', 'ttLoad', lData, tLabels, '#4ecdc4', 0, 100, '%');
        }

        // ── Live mode ──────────────────────────────────────────────────────
        function startLive() {
            function fetchLive() {
                fetch('/api/latest?_t=' + Date.now()).then(r => r.json()).then(d => {
                    document.getElementById('tvTemp').textContent = d.temp ? d.temp.toFixed(1) + '°C' : '--°C';
                    document.getElementById('tvLoad').textContent = d.load != null ? d.load + '%' : '--%';
                    const sb = document.getElementById('tvStatus');
                    sb.className = 'badge ' + (d.status || '');
                    sb.textContent = (d.status || '--').toUpperCase();

                    if (d.temp === 0 && d.load === 0) return;
                    const now = new Date().toLocaleTimeString('vi-VN', {hour:'2-digit', minute:'2-digit', second:'2-digit'});
                    tLabels.push(now); tData.push(d.temp || 0); lData.push(d.load || 0);
                    if (tLabels.length > MAX_LIVE) { tLabels.shift(); tData.shift(); lData.shift(); }
                    redraw();
                    document.getElementById('infoRight').textContent = '🔄 ' + now + ' | ' + tLabels.length + ' điểm';
                }).catch(() => {});
            }
            fetchLive();
            liveTimer = setInterval(fetchLive, 5000);
        }

        // ── History mode ───────────────────────────────────────────────────
        function startHistory() { fetchHistory(); historyTimer = setInterval(fetchHistory, 30000); }

        function fetchHistory() {
            document.getElementById('infoRight').textContent = '🔄 Đang tải...';
            fetch('/api/history?minutes=' + historyMinutes + '&_t=' + Date.now())
                .then(r => r.json()).then(data => {
                    tLabels = []; tData = []; lData = [];
                    data.forEach(d => {
                        let t = '';
                        try { t = new Date(d.time).toLocaleTimeString('vi-VN', {hour:'2-digit', minute:'2-digit'}); } catch(e) { t = d.time || ''; }
                        tLabels.push(t); tData.push(d.temp || 0); lData.push(d.load || 0);
                    });
                    redraw();
                    document.getElementById('infoRight').textContent = '🔄 ' + new Date().toLocaleTimeString('vi-VN') + ' | ' + data.length + ' điểm';
                }).catch(() => {});
        }

        function changeTime(mins, btn) {
            historyMinutes = mins;
            document.querySelectorAll('#histBtns .hbtn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            fetchHistory();
        }

        function switchMode(mode, btn) {
            currentMode = mode;
            document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            clearInterval(liveTimer); clearInterval(historyTimer);
            tLabels = []; tData = []; lData = [];
            redraw();

            if (mode === 'live') {
                document.getElementById('histBtns').style.display = 'none';
                document.getElementById('infoLeft').innerHTML = '<span class="dot"></span> REAL-TIME';
                startLive();
            } else {
                document.getElementById('histBtns').style.display = 'flex';
                document.getElementById('infoLeft').textContent = '📅 LỊCH SỬ';
                startHistory();
            }
        }

        // ── Latest for cards only (faster refresh) ────────────────────────
        function fetchLatest() {
            fetch('/api/latest?_t=' + Date.now()).then(r => r.json()).then(d => {
                document.getElementById('tvTemp').textContent = d.temp ? d.temp.toFixed(1) + '°C' : '--°C';
                document.getElementById('tvLoad').textContent = d.load != null ? d.load + '%' : '--%';
                const sb = document.getElementById('tvStatus');
                sb.className = 'badge ' + (d.status || '');
                sb.textContent = (d.status || '--').toUpperCase();
            }).catch(() => {});
        }

        function downloadImage() {
            html2canvas(document.getElementById('dashboard'), { backgroundColor: '#1a1a2e', scale: 2 }).then(canvas => {
                const a = document.createElement('a');
                a.download = 'CNC_' + new Date().toISOString().slice(0,19).replace(/:/g,'-') + '.png';
                a.href = canvas.toDataURL('image/png'); a.click();
            });
        }

        // ── Boot ──────────────────────────────────────────────────────────
        fetchLatest();
        startLive();
        setInterval(fetchLatest, 3000);
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

        now = datetime.utcnow() + timedelta(hours=7)
        start_time = now - timedelta(minutes=minutes)

        start_str = start_time.strftime("%Y-%m-%dT%H:%M:%S.000000")
        now_str    = now.strftime("%Y-%m-%dT%H:%M:%S.999999")

        print(f"📅 Giờ VN hiện tại: {now.strftime('%H:%M:%S')}")
        print(f"📅 Từ: {start_str}  →  Đến: {now_str}")

        query = {
            "mqtt_timestamp": {
                "$gte": start_str,
                "$lte": now_str
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
