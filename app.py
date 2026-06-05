# app.py - CNC Monitor + Chat AI (Friday)
# Flow: WebUI → MongoDB(Chat_Jobs) → Worker(VS Code) → AI → MongoDB(Chat_Messages) → WebUI poll

from flask import Flask, jsonify, request
from pymongo import MongoClient
from datetime import datetime, timedelta
from bson import ObjectId

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
    db = None
    collection = None

# ─────────────────────────────────────────────
#  TRANG CHỦ
# ─────────────────────────────────────────────
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
            * { margin:0; padding:0; box-sizing:border-box; }
            body { font-family:-apple-system,Arial,sans-serif; background:#1a1a2e; color:white; padding:10px; }
            .container { max-width:1000px; margin:0 auto; }
            h1 { text-align:center; color:#4ecdc4; font-size:20px; margin-bottom:10px; }

            /* ── Tabs ── */
            .mode-switch { display:flex; justify-content:center; margin-bottom:12px; background:#16213e; border-radius:25px; overflow:hidden; width:fit-content; margin:0 auto 12px auto; }
            .mode-btn { padding:10px 22px; cursor:pointer; font-size:13px; font-weight:bold; border:none; color:#888; background:transparent; transition:.2s; }
            .mode-btn.active { background:#4ecdc4; color:#1a1a2e; }

            /* ── Gauge cards ── */
            .gauges { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-bottom:12px; }
            .card { background:#16213e; padding:12px; border-radius:12px; text-align:center; }
            .card-label { color:#888; font-size:11px; }
            .card-value { font-size:28px; font-weight:bold; margin-top:4px; }
            .temp-color { color:#ff6b6b; }
            .load-color { color:#4ecdc4; }
            .status-badge { display:inline-block; padding:5px 12px; border-radius:12px; font-size:14px; font-weight:bold; margin-top:4px; }
            .running { background:#00b894; }
            .idle { background:#fdcb6e; color:#333; }
            .maintenance { background:#e17055; }
            .error { background:#d63031; animation:blink .5s infinite; }
            @keyframes blink { 50%{opacity:.5} }

            /* ── History buttons ── */
            .btn-group { display:flex; gap:6px; justify-content:center; margin-bottom:12px; flex-wrap:wrap; }
            .btn { background:#16213e; color:white; border:2px solid #4ecdc4; padding:7px 14px; border-radius:18px; cursor:pointer; font-size:12px; }
            .btn.active { background:#4ecdc4; color:#1a1a2e; font-weight:bold; }

            /* ── Chart ── */
            .chart-box { background:#16213e; padding:12px; border-radius:12px; margin-bottom:12px; }
            .chart-box h3 { margin-bottom:6px; color:#ddd; font-size:14px; }
            canvas { width:100% !important; height:300px !important; }

            /* ── Info bar ── */
            .info-bar { display:flex; justify-content:space-between; color:#888; font-size:11px; margin-bottom:10px; }
            .live-dot { width:10px; height:10px; background:#00b894; border-radius:50%; display:inline-block; animation:pulse 1.5s infinite; }
            @keyframes pulse { 50%{opacity:.3} }

            /* ── Download ── */
            .download-btn { background:#ff6b6b; color:white; border:none; padding:10px 20px; border-radius:20px; cursor:pointer; font-size:14px; display:block; margin:10px auto; }

            /* ── Chat ── */
            #chatBox { display:none; }
            #chatMessages {
                background:#16213e; border-radius:12px; padding:12px;
                height:400px; overflow-y:auto; margin-bottom:10px;
                scroll-behavior:smooth;
            }
            .chat-default { text-align:center; color:#888; padding-top:160px; font-size:14px; }
            .chat-row { margin-bottom:10px; }
            .chat-row.user { text-align:right; }
            .chat-row.ai  { text-align:left;  }
            .chat-name { font-size:10px; color:#888; margin-bottom:3px; }
            .chat-bubble {
                display:inline-block; padding:9px 14px; border-radius:16px;
                max-width:78%; font-size:14px; line-height:1.5; white-space:pre-wrap; word-break:break-word;
            }
            .chat-row.user .chat-bubble { background:#1a3a3a; color:#4ecdc4; }
            .chat-row.ai  .chat-bubble { background:#2a1a2e; color:#f0f0f0; }
            .chat-input-row { display:flex; gap:8px; }
            #chatInput {
                flex:1; padding:12px 16px; border-radius:20px; border:none;
                background:#16213e; color:white; font-size:14px; outline:none;
                border:1px solid #2a2a4a;
            }
            #chatInput:focus { border-color:#4ecdc4; }
            .send-btn {
                background:#4ecdc4; color:#1a1a2e; border:none;
                padding:12px 20px; border-radius:20px; font-weight:700;
                cursor:pointer; font-size:14px; white-space:nowrap;
            }
            .send-btn:disabled { background:#555; color:#888; cursor:not-allowed; }
            .typing-dots span {
                display:inline-block; width:7px; height:7px; border-radius:50%;
                background:#4ecdc4; margin:0 2px;
                animation:bounce .8s infinite;
            }
            .typing-dots span:nth-child(2){animation-delay:.15s}
            .typing-dots span:nth-child(3){animation-delay:.3s}
            @keyframes bounce { 0%,80%,100%{transform:translateY(0)} 40%{transform:translateY(-7px)} }
        </style>
    </head>
    <body>
    <div class="container" id="dashboard">
        <h1>🏭 CNC Machine Monitor</h1>

        <!-- Tabs -->
        <div class="mode-switch">
            <button class="mode-btn active" onclick="switchTab('live',this)">🔴 LIVE</button>
            <button class="mode-btn"        onclick="switchTab('history',this)">📅 LỊCH SỬ</button>
            <button class="mode-btn"        onclick="switchTab('chat',this)">💬 CHAT AI</button>
        </div>

        <!-- Info bar (chỉ hiện ở LIVE / HISTORY) -->
        <div class="info-bar" id="infoBar">
            <span id="infoLeft"><span class="live-dot"></span> REAL-TIME</span>
            <span id="infoRight">🔄 Đang tải...</span>
        </div>

        <!-- ════ DASHBOARD CONTENT ════ -->
        <div id="dashboardContent">
            <!-- Gauge cards -->
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

            <!-- History time buttons -->
            <div class="btn-group" id="histBtns" style="display:none;">
                <button class="btn active" onclick="changeTime(10,this)">10 phút</button>
                <button class="btn"        onclick="changeTime(30,this)">30 phút</button>
                <button class="btn"        onclick="changeTime(60,this)">1 giờ</button>
                <button class="btn"        onclick="changeTime(360,this)">6 giờ</button>
                <button class="btn"        onclick="changeTime(1440,this)">1 ngày</button>
            </div>

            <!-- Combined chart -->
            <div class="chart-box">
                <h3>📈 Nhiệt độ & Tải theo thời gian</h3>
                <canvas id="combinedChart"></canvas>
            </div>

            <button class="download-btn" onclick="downloadImage()">📸 Tải ảnh về máy</button>
        </div>

        <!-- ════ CHAT BOX ════ -->
        <div id="chatBox">
            <div id="chatMessages">
                <div class="chat-default">👋 Xin chào! Tôi là <b style="color:#4ecdc4">Friday</b>.<br>Hỏi tôi bất cứ điều gì về máy CNC...</div>
            </div>
            <div class="chat-input-row">
                <input id="chatInput" type="text" placeholder="Nhập tin nhắn..."
                       onkeypress="if(event.key==='Enter' && !event.shiftKey) sendChat()">
                <button class="send-btn" id="sendBtn" onclick="sendChat()">GỬI ➤</button>
            </div>
        </div>

    </div><!-- /container -->

    <script>
    // ══════════════════════════════════════
    //  CHART
    // ══════════════════════════════════════
    const combinedChart = new Chart(document.getElementById('combinedChart').getContext('2d'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: '🌡️ Nhiệt độ (°C)',
                    data: [],
                    borderColor: '#ff6b6b',
                    backgroundColor: 'rgba(255,107,107,0.08)',
                    borderWidth: 2.5,
                    pointRadius: 0, pointHoverRadius: 6,
                    tension: 0.4, fill: true,
                    yAxisID: 'yTemp'
                },
                {
                    label: '⚙️ Tải (%)',
                    data: [],
                    borderColor: '#4ecdc4',
                    backgroundColor: 'rgba(78,205,196,0.08)',
                    borderWidth: 2.5,
                    pointRadius: 0, pointHoverRadius: 6,
                    tension: 0.4, fill: true,
                    yAxisID: 'yLoad'
                }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            animation: { duration: 200 },
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: {
                    ticks: { color:'#888', maxTicksLimit:8, font:{size:10} },
                    grid:  { color:'#2d2d2d' }
                },
                yTemp: {
                    type:'linear', position:'left',
                    min:30, max:80,
                    ticks: { color:'#ff6b6b', font:{size:10} },
                    grid:  { color:'#2d2d2d' },
                    title: { display:true, text:'°C', color:'#ff6b6b' }
                },
                yLoad: {
                    type:'linear', position:'right',
                    min:0, max:100,
                    ticks: { color:'#4ecdc4', font:{size:10} },
                    grid:  { drawOnChartArea:false },
                    title: { display:true, text:'%', color:'#4ecdc4' }
                }
            },
            plugins: {
                legend: { display:true, labels:{ color:'#ddd', font:{size:12}, boxWidth:20 } },
                tooltip: { enabled:true }
            }
        }
    });

    function pushToChart(label, temp, load) {
        combinedChart.data.labels.push(label);
        combinedChart.data.datasets[0].data.push(temp || 0);
        combinedChart.data.datasets[1].data.push(load || 0);
    }
    function shiftChart() {
        combinedChart.data.labels.shift();
        combinedChart.data.datasets[0].data.shift();
        combinedChart.data.datasets[1].data.shift();
    }
    function clearChart() {
        combinedChart.data.labels = [];
        combinedChart.data.datasets[0].data = [];
        combinedChart.data.datasets[1].data = [];
    }

    // ══════════════════════════════════════
    //  LIVE MODE
    // ══════════════════════════════════════
    const MAX_LIVE = 60;
    let liveTimer = null;

    function startLive() {
        fetchLatest();
        fetchLiveChart();
        liveTimer = setInterval(() => { fetchLatest(); fetchLiveChart(); }, 5000);
    }

    function fetchLatest() {
        fetch('/api/latest?_t=' + Date.now()).then(r => r.json()).then(d => {
            document.getElementById('tempValue').textContent   = d.temp  ? d.temp.toFixed(1) + '°C' : '--°C';
            document.getElementById('loadValue').textContent   = d.load  ? d.load + '%' : '--%';
            document.getElementById('statusValue').innerHTML   =
                '<span class="status-badge ' + (d.status||'') + '">' + (d.status||'--').toUpperCase() + '</span>';
        });
    }

    function fetchLiveChart() {
        fetch('/api/latest?_t=' + Date.now()).then(r => r.json()).then(d => {
            if (d.temp === 0 && d.load === 0) return;
            const now = new Date().toLocaleTimeString('vi-VN', {hour:'2-digit', minute:'2-digit', second:'2-digit'});
            pushToChart(now, d.temp, d.load);
            if (combinedChart.data.labels.length > MAX_LIVE) shiftChart();
            combinedChart.update('none');
            document.getElementById('infoRight').textContent = '🔄 ' + now + ' | ' + combinedChart.data.labels.length + ' điểm';
        });
    }

    // ══════════════════════════════════════
    //  HISTORY MODE
    // ══════════════════════════════════════
    let historyTimer   = null;
    let historyMinutes = 10;

    function startHistory() {
        fetchHistory();
        historyTimer = setInterval(fetchHistory, 30000);
    }

    function changeTime(minutes, btn) {
        historyMinutes = minutes;
        document.querySelectorAll('#histBtns .btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        fetchHistory();
    }

    function fetchHistory() {
        document.getElementById('infoRight').textContent = '🔄 Đang tải...';
        fetch('/api/history?minutes=' + historyMinutes + '&_t=' + Date.now())
            .then(r => r.json()).then(data => {
                clearChart();
                data.forEach(d => {
                    let t = '';
                    try { t = new Date(d.time).toLocaleTimeString('vi-VN', {hour:'2-digit', minute:'2-digit'}); }
                    catch(e) { t = d.time || ''; }
                    pushToChart(t, d.temp, d.load);
                });
                combinedChart.update();
                document.getElementById('infoRight').textContent =
                    '🔄 ' + new Date().toLocaleTimeString('vi-VN') + ' | ' + data.length + ' điểm';
            });
    }

    // ══════════════════════════════════════
    //  TAB SWITCHING
    // ══════════════════════════════════════
    function switchTab(tab, btn) {
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        clearInterval(liveTimer);
        clearInterval(historyTimer);
        clearChart();

        const dash     = document.getElementById('dashboardContent');
        const chatBox  = document.getElementById('chatBox');
        const infoBar  = document.getElementById('infoBar');
        const histBtns = document.getElementById('histBtns');

        dash.style.display    = tab !== 'chat' ? 'block' : 'none';
        chatBox.style.display = tab === 'chat' ? 'block' : 'none';
        infoBar.style.display = tab !== 'chat' ? 'flex'  : 'none';
        histBtns.style.display = 'none';

        if (tab === 'live') {
            document.getElementById('infoLeft').innerHTML = '<span class="live-dot"></span> REAL-TIME';
            startLive();
        } else if (tab === 'history') {
            document.getElementById('infoLeft').textContent = '📅 LỊCH SỬ';
            histBtns.style.display = 'flex';
            startHistory();
        }
        // tab === 'chat' → không cần làm gì thêm
    }

    // ══════════════════════════════════════
    //  CHAT
    // ══════════════════════════════════════
    let conversationId = null;
    let chatPolling    = null;

    function sendChat() {
        const input  = document.getElementById('chatInput');
        const sendBtn = document.getElementById('sendBtn');
        const msg    = input.value.trim();
        if (!msg) return;

        appendMsg('user', msg);
        input.value = '';
        sendBtn.disabled = true;

        // Hiện typing indicator
        appendTyping();

        fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({ message: msg, conversation_id: conversationId })
        })
        .then(r => r.json())
        .then(data => {
            conversationId = data.conversation_id;
            startPolling(conversationId);
        })
        .catch(() => {
            removeTyping();
            appendMsg('ai', '❌ Lỗi kết nối server.');
            sendBtn.disabled = false;
        });
    }

    function appendMsg(role, text) {
        const box = document.getElementById('chatMessages');
        // Xóa default greeting nếu còn
        const def = box.querySelector('.chat-default');
        if (def) def.remove();

        const div = document.createElement('div');
        div.className = 'chat-row ' + role;
        div.innerHTML =
            '<div class="chat-name">' + (role === 'user' ? 'Bạn' : '🤖 Friday') + '</div>' +
            '<div class="chat-bubble">' + escHtml(text) + '</div>';
        box.appendChild(div);
        box.scrollTop = box.scrollHeight;
    }

    function appendTyping() {
        const box = document.getElementById('chatMessages');
        const div = document.createElement('div');
        div.className = 'chat-row ai';
        div.id = 'typingRow';
        div.innerHTML =
            '<div class="chat-name">🤖 Friday</div>' +
            '<div class="chat-bubble"><div class="typing-dots"><span></span><span></span><span></span></div></div>';
        box.appendChild(div);
        box.scrollTop = box.scrollHeight;
    }

    function removeTyping() {
        const el = document.getElementById('typingRow');
        if (el) el.remove();
    }

    function escHtml(s) {
        return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\\n/g,'<br>');
    }

    function startPolling(convId) {
        if (chatPolling) clearInterval(chatPolling);
        let lastCount = 0;
        let ticks = 0;

        chatPolling = setInterval(() => {
            ticks++;
            if (ticks > 60) { // timeout 90s
                clearInterval(chatPolling);
                removeTyping();
                appendMsg('ai', '⏰ Friday không phản hồi. Thử lại sau nhé!');
                document.getElementById('sendBtn').disabled = false;
                return;
            }

            fetch('/api/chat/messages/' + convId)
            .then(r => r.json())
            .then(data => {
                const aiMsgs = data.messages.filter(m => m.role === 'ai');
                if (aiMsgs.length > lastCount) {
                    removeTyping();
                    aiMsgs.slice(lastCount).forEach(m => appendMsg('ai', m.message));
                    lastCount = aiMsgs.length;
                }
                if (data.done) {
                    clearInterval(chatPolling);
                    chatPolling = null;
                    document.getElementById('sendBtn').disabled = false;
                }
            });
        }, 1500);
    }

    // ══════════════════════════════════════
    //  DOWNLOAD
    // ══════════════════════════════════════
    function downloadImage() {
        html2canvas(document.getElementById('dashboard'), { backgroundColor:'#1a1a2e', scale:2 })
        .then(canvas => {
            const a = document.createElement('a');
            a.download = 'CNC_' + new Date().toISOString().slice(0,19).replace(/:/g,'-') + '.png';
            a.href = canvas.toDataURL('image/png');
            a.click();
        });
    }

    // ══════════════════════════════════════
    //  KHỞI ĐỘNG
    // ══════════════════════════════════════
    fetchLatest();
    startLive();
    setInterval(fetchLatest, 3000);
    </script>
    </body>
    </html>
    """

# ─────────────────────────────────────────────
#  API: SENSOR
# ─────────────────────────────────────────────
@app.route("/api/latest")
def api_latest():
    if collection is None:
        return jsonify({"temp":0,"load":0,"status":"db_error"})
    try:
        doc = collection.find_one(sort=[("mqtt_timestamp", -1)])
        if doc:
            return jsonify({
                "temp":   doc.get("temp", 0),
                "load":   doc.get("load", 0),
                "status": doc.get("status", "unknown")
            })
        return jsonify({"temp":0,"load":0,"status":"no_data"})
    except:
        return jsonify({"temp":0,"load":0,"status":"error"})

@app.route("/api/history")
def api_history():
    if collection is None:
        return jsonify([])
    try:
        minutes    = int(request.args.get("minutes", 10))
        now        = datetime.utcnow() + timedelta(hours=7)   # giờ Việt Nam
        start_time = now - timedelta(minutes=minutes)

        start_str = start_time.strftime("%Y-%m-%dT%H:%M:%S.000000")
        now_str   = now.strftime("%Y-%m-%dT%H:%M:%S.999999")

        print(f"📅 Giờ VN: {now.strftime('%H:%M:%S')}  |  Từ: {start_str} → Đến: {now_str}")

        docs = list(collection.find({
            "mqtt_timestamp": {"$gte": start_str, "$lte": now_str}
        }).sort("mqtt_timestamp", 1))

        print(f"📊 Tìm được: {len(docs)} bản ghi")

        if len(docs) > 2000:
            step = len(docs) // 2000
            docs = docs[::step]

        return jsonify([{
            "time": d.get("mqtt_timestamp",""),
            "temp": d.get("temp", 0),
            "load": d.get("load", 0)
        } for d in docs])

    except Exception as e:
        print(f"❌ History error: {e}")
        return jsonify([])

# ─────────────────────────────────────────────
#  API: CHAT
# ─────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    WebUI gửi tin nhắn → lưu vào Chat_Jobs (pending)
    Worker (VS Code) sẽ đọc job này, gọi AI, lưu kết quả
    """
    if db is None:
        return jsonify({"error": "DB không kết nối"}), 500

    data    = request.json or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "Tin nhắn trống"}), 400

    conv_id = data.get("conversation_id") or str(ObjectId())

    # Lưu tin nhắn user
    db["Chat_Messages"].insert_one({
        "conversation_id": conv_id,
        "role":            "user",
        "message":         message,
        "timestamp":       (datetime.utcnow() + timedelta(hours=7)).isoformat()
    })

    # Tạo job cho worker VS Code
    db["Chat_Jobs"].insert_one({
        "conversation_id": conv_id,
        "question":        message,
        "status":          "pending",
        "created_at":      (datetime.utcnow() + timedelta(hours=7)).isoformat()
    })

    return jsonify({
        "status":          "ok",
        "conversation_id": conv_id,
        "message":         "Friday đang xử lý..."
    })

@app.route("/api/chat/messages/<conv_id>")
def api_chat_messages(conv_id):
    """WebUI poll → lấy tất cả tin nhắn + kiểm tra job xong chưa"""
    if db is None:
        return jsonify({"messages":[], "done": False})
    try:
        messages = list(
            db["Chat_Messages"]
            .find({"conversation_id": conv_id})
            .sort("timestamp", 1)
        )
        job_done = db["Chat_Jobs"].find_one({
            "conversation_id": conv_id,
            "status":          "done"
        })
        return jsonify({
            "messages": [{
                "role":    m["role"],
                "message": m["message"],
                "time":    m.get("timestamp","")
            } for m in messages],
            "done": job_done is not None
        })
    except Exception as e:
        print(f"❌ Chat poll error: {e}")
        return jsonify({"messages":[], "done": False})

# ─────────────────────────────────────────────
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
