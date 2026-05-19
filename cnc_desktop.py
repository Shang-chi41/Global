"""
CNC Monitor - Desktop App (PyQt6)
Kết nối vào Flask API tại localhost:5000
Cài đặt: pip install PyQt6 requests
Chạy:    python cnc_desktop.py
"""

import sys
import math
from collections import deque
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QButtonGroup, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPointF, QRectF
)
from PyQt6.QtGui import (
    QColor, QPainter, QPainterPath, QPen, QBrush,
    QLinearGradient, QFont, QPalette
)
import requests

# ── Cấu hình ──────────────────────────────────────────────────────────────────
FLASK_URL    = "http://localhost:5000"
LIVE_INTERVAL_MS    = 5000   # refresh live data
CARD_INTERVAL_MS    = 3000   # refresh cards
HISTORY_INTERVAL_MS = 30000
MAX_LIVE_POINTS     = 60

# ── Màu sắc ───────────────────────────────────────────────────────────────────
BG_DARK   = "#1a1a2e"
BG_CARD   = "#16213e"
COL_TEAL  = "#4ecdc4"
COL_RED   = "#ff6b6b"
COL_GREEN = "#00b894"
COL_GRID  = "#252540"


# ══════════════════════════════════════════════════════════════════════════════
#  Worker thread – gọi API không block UI
# ══════════════════════════════════════════════════════════════════════════════
class ApiWorker(QThread):
    data_ready    = pyqtSignal(dict)   # latest
    history_ready = pyqtSignal(list)   # history
    error         = pyqtSignal(str)

    def __init__(self, mode="latest", minutes=10):
        super().__init__()
        self.mode    = mode
        self.minutes = minutes

    def run(self):
        try:
            if self.mode == "latest":
                r = requests.get(f"{FLASK_URL}/api/latest", timeout=5)
                self.data_ready.emit(r.json())
            else:
                r = requests.get(f"{FLASK_URL}/api/history?minutes={self.minutes}", timeout=10)
                self.history_ready.emit(r.json())
        except Exception as e:
            self.error.emit(str(e))


# ══════════════════════════════════════════════════════════════════════════════
#  Widget vẽ line chart bằng QPainter
# ══════════════════════════════════════════════════════════════════════════════
class LineChart(QWidget):
    def __init__(self, color: str, y_min: float, y_max: float, unit: str):
        super().__init__()
        self.color  = QColor(color)
        self.y_min  = y_min
        self.y_max  = y_max
        self.unit   = unit
        self.data   : list[float] = []
        self.labels : list[str]   = []
        self.setMinimumHeight(130)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self._hover_idx = -1

    def set_data(self, data: list[float], labels: list[str]):
        self.data   = data
        self.labels = labels
        self.update()

    # ── vẽ ─────────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        W, H   = self.width(), self.height()
        PAD_L  = 8
        PAD_R  = 8
        PAD_T  = 8
        PAD_B  = 22   # chỗ cho nhãn trục X

        chart_w = W - PAD_L - PAD_R
        chart_h = H - PAD_T - PAD_B

        # Nền
        p.fillRect(0, 0, W, H, QColor(BG_CARD))

        n = len(self.data)
        if n < 2:
            p.end()
            return

        def xs(i): return PAD_L + (i / (n - 1)) * chart_w
        def ys(v): return PAD_T + chart_h - max(0, min(1, (v - self.y_min) / (self.y_max - self.y_min))) * chart_h

        pts = [QPointF(xs(i), ys(v)) for i, v in enumerate(self.data)]

        # Grid lines (4 ngang)
        grid_pen = QPen(QColor(COL_GRID), 1)
        p.setPen(grid_pen)
        for g in range(5):
            y = PAD_T + (g / 4) * chart_h
            p.drawLine(QPointF(PAD_L, y), QPointF(W - PAD_R, y))

        # Build smooth bezier path
        path = QPainterPath()
        path.moveTo(pts[0])
        for i in range(1, n):
            mx = (pts[i-1].x() + pts[i].x()) / 2
            path.cubicTo(
                QPointF(mx, pts[i-1].y()),
                QPointF(mx, pts[i].y()),
                pts[i]
            )

        # Fill gradient
        fill_path = QPainterPath(path)
        fill_path.lineTo(pts[-1].x(), PAD_T + chart_h)
        fill_path.lineTo(pts[0].x(),  PAD_T + chart_h)
        fill_path.closeSubpath()

        grad = QLinearGradient(0, PAD_T, 0, PAD_T + chart_h)
        c_top = QColor(self.color); c_top.setAlphaF(0.4)
        c_bot = QColor(self.color); c_bot.setAlphaF(0.03)
        grad.setColorAt(0, c_top)
        grad.setColorAt(1, c_bot)
        p.fillPath(fill_path, QBrush(grad))

        # Đường line
        p.setPen(QPen(self.color, 2.5, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawPath(path)

        # Nhãn trục X (5 điểm)
        p.setPen(QColor("#555555"))
        p.setFont(QFont("Arial", 8))
        idxs = [0, n//4, n//2, 3*n//4, n-1]
        for i in idxs:
            if i < len(self.labels):
                lx = xs(i)
                p.drawText(QRectF(lx - 30, H - PAD_B + 4, 60, 16),
                           Qt.AlignmentFlag.AlignHCenter, self.labels[i])

        # Hover dot + tooltip
        if 0 <= self._hover_idx < n:
            hi = self._hover_idx
            hx, hy = pts[hi].x(), pts[hi].y()

            # chấm trắng
            p.setPen(QPen(self.color, 2.5))
            p.setBrush(QBrush(QColor("white")))
            p.drawEllipse(QPointF(hx, hy), 5, 5)

            # tooltip box
            txt_time = self.labels[hi] if hi < len(self.labels) else ""
            txt_val  = f"{self.data[hi]:.1f} {self.unit}"
            tt_w, tt_h = 110, 46
            tx = max(4, min(hx - tt_w // 2, W - tt_w - 4))
            ty = max(4, hy - tt_h - 10)

            p.setBrush(QBrush(QColor(0, 0, 0, 220)))
            p.setPen(QPen(self.color, 1.5))
            p.drawRoundedRect(QRectF(tx, ty, tt_w, tt_h), 7, 7)

            p.setPen(QColor(COL_TEAL))
            p.setFont(QFont("Arial", 8))
            p.drawText(QRectF(tx, ty + 5, tt_w, 16),
                       Qt.AlignmentFlag.AlignHCenter, f"🕐 {txt_time}")

            p.setPen(self.color)
            p.setFont(QFont("Arial", 13, QFont.Weight.Bold))
            p.drawText(QRectF(tx, ty + 22, tt_w, 20),
                       Qt.AlignmentFlag.AlignHCenter, txt_val)

        p.end()

    def mouseMoveEvent(self, e):
        n = len(self.data)
        if n < 2: return
        PAD_L, PAD_R = 8, 8
        chart_w = self.width() - PAD_L - PAD_R
        rx = (e.position().x() - PAD_L) / chart_w
        self._hover_idx = max(0, min(n - 1, round(rx * (n - 1))))
        self.update()

    def leaveEvent(self, _):
        self._hover_idx = -1
        self.update()


# ══════════════════════════════════════════════════════════════════════════════
#  Card số liệu (Temp / Load / Status)
# ══════════════════════════════════════════════════════════════════════════════
class MetricCard(QWidget):
    def __init__(self, icon: str, label: str, value_color: str):
        super().__init__()
        self.setStyleSheet(f"background:{BG_CARD}; border-radius:12px;")
        ly = QVBoxLayout(self)
        ly.setContentsMargins(12, 10, 12, 10)
        ly.setSpacing(4)

        lbl = QLabel(f"{icon}  {label}")
        lbl.setStyleSheet("color:#888; font-size:10px; letter-spacing:1px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(lbl)

        self.val = QLabel("--")
        self.val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.val.setStyleSheet(f"color:{value_color}; font-size:26px; font-weight:700;")
        ly.addWidget(self.val)

    def set_value(self, text: str, extra_style: str = ""):
        self.val.setText(text)
        if extra_style:
            self.val.setStyleSheet(extra_style)


# ══════════════════════════════════════════════════════════════════════════════
#  Cửa sổ chính
# ══════════════════════════════════════════════════════════════════════════════
class CNCMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CNC Machine Monitor")
        self.setMinimumSize(680, 600)
        self.setStyleSheet(f"background:{BG_DARK};")

        self._mode          = "live"
        self._history_mins  = 10
        self._t_data  : list[float] = []
        self._l_data  : list[float] = []
        self._labels  : list[str]   = []
        self._workers : list[ApiWorker] = []

        self._build_ui()
        self._start_live()

    # ── Build UI ────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(16, 12, 16, 12)
        main.setSpacing(10)

        # Title
        title = QLabel("🏭  CNC Machine Monitor")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color:{COL_TEAL}; font-size:18px; font-weight:600;")
        main.addWidget(title)

        # Mode switch
        mode_row = QHBoxLayout()
        mode_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        pill = QFrame()
        pill.setStyleSheet(f"background:{BG_CARD}; border-radius:18px;")
        pill_ly = QHBoxLayout(pill)
        pill_ly.setContentsMargins(4, 4, 4, 4)
        pill_ly.setSpacing(0)

        self.btn_live = QPushButton("🔴  LIVE")
        self.btn_hist = QPushButton("📅  LỊCH SỬ")
        for btn in (self.btn_live, self.btn_hist):
            btn.setCheckable(True)
            btn.setStyleSheet(self._btn_style(False))
            btn.setFixedHeight(34)
            pill_ly.addWidget(btn)
        self.btn_live.setChecked(True)
        self.btn_live.setStyleSheet(self._btn_style(True))
        self.btn_live.clicked.connect(lambda: self._switch_mode("live"))
        self.btn_hist.clicked.connect(lambda: self._switch_mode("history"))
        mode_row.addWidget(pill)
        main.addLayout(mode_row)

        # Info bar
        info_row = QHBoxLayout()
        self.lbl_left  = QLabel("● REAL-TIME")
        self.lbl_right = QLabel("Đang tải...")
        self.lbl_left.setStyleSheet(f"color:{COL_GREEN}; font-size:11px;")
        self.lbl_right.setStyleSheet("color:#888; font-size:11px;")
        info_row.addWidget(self.lbl_left)
        info_row.addStretch()
        info_row.addWidget(self.lbl_right)
        main.addLayout(info_row)

        # Gauge cards
        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)
        self.card_temp   = MetricCard("🌡️", "NHIỆT ĐỘ",   COL_RED)
        self.card_load   = MetricCard("⚙️", "TẢI",         COL_TEAL)
        self.card_status = MetricCard("📌", "TRẠNG THÁI", "white")
        for c in (self.card_temp, self.card_load, self.card_status):
            cards_row.addWidget(c)
        main.addLayout(cards_row)

        # History time buttons (ẩn mặc định)
        self.hist_frame = QFrame()
        hist_ly = QHBoxLayout(self.hist_frame)
        hist_ly.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        hist_ly.setSpacing(6)
        self.hist_frame.hide()
        self._hist_btns = []
        for label, mins in [("10 phút", 10), ("30 phút", 30), ("1 giờ", 60), ("6 giờ", 360), ("1 ngày", 1440)]:
            b = QPushButton(label)
            b.setCheckable(True)
            b.setStyleSheet(self._hbtn_style(mins == 10))
            b.clicked.connect(lambda _, m=mins, btn=b: self._change_time(m, btn))
            hist_ly.addWidget(b)
            self._hist_btns.append((b, mins))
        main.addWidget(self.hist_frame)

        # Charts
        for title_str, attr, color, ymin, ymax, unit in [
            ("📈  Nhiệt độ (°C)", "chart_temp", COL_RED,  30, 70,  "°C"),
            ("📈  Tải (%)",       "chart_load", COL_TEAL,  0, 100, "%"),
        ]:
            box = QFrame()
            box.setStyleSheet(f"background:{BG_CARD}; border-radius:12px;")
            box_ly = QVBoxLayout(box)
            box_ly.setContentsMargins(12, 10, 12, 10)
            box_ly.setSpacing(4)
            lbl = QLabel(title_str)
            lbl.setStyleSheet("color:#ccc; font-size:12px;")
            box_ly.addWidget(lbl)
            chart = LineChart(color, ymin, ymax, unit)
            box_ly.addWidget(chart)
            setattr(self, attr, chart)
            main.addWidget(box)

        # Download button
        dl = QPushButton("📸  Tải ảnh về máy")
        dl.setStyleSheet(f"""
            QPushButton {{ background:{COL_RED}; color:white; border:none;
                          border-radius:16px; padding:10px 24px; font-size:13px; font-weight:600; }}
            QPushButton:hover {{ background:#e05555; }}
        """)
        dl.clicked.connect(self._save_screenshot)
        main.addWidget(dl, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Timers
        self.timer_live    = QTimer(self); self.timer_live.timeout.connect(self._fetch_live)
        self.timer_cards   = QTimer(self); self.timer_cards.timeout.connect(self._fetch_latest)
        self.timer_history = QTimer(self); self.timer_history.timeout.connect(self._fetch_history)

    # ── Styles ──────────────────────────────────────────────────────────────
    def _btn_style(self, active: bool) -> str:
        if active:
            return f"QPushButton {{ background:{COL_TEAL}; color:#1a1a2e; border:none; border-radius:14px; padding:6px 22px; font-size:13px; font-weight:700; }}"
        return f"QPushButton {{ background:transparent; color:#888; border:none; border-radius:14px; padding:6px 22px; font-size:13px; }}"

    def _hbtn_style(self, active: bool) -> str:
        if active:
            return f"QPushButton {{ background:{COL_TEAL}; color:#1a1a2e; border:1.5px solid {COL_TEAL}; border-radius:12px; padding:5px 13px; font-size:11px; font-weight:700; }}"
        return f"QPushButton {{ background:{BG_CARD}; color:#ccc; border:1.5px solid {COL_TEAL}; border-radius:12px; padding:5px 13px; font-size:11px; }}"

    # ── Mode switching ───────────────────────────────────────────────────────
    def _switch_mode(self, mode: str):
        self._mode = mode
        self.timer_live.stop(); self.timer_history.stop()
        self._t_data.clear(); self._l_data.clear(); self._labels.clear()
        self.chart_temp.set_data([], []); self.chart_load.set_data([], [])

        is_live = mode == "live"
        self.btn_live.setStyleSheet(self._btn_style(is_live))
        self.btn_hist.setStyleSheet(self._btn_style(not is_live))
        self.hist_frame.setVisible(not is_live)

        if is_live:
            self.lbl_left.setText("●  REAL-TIME")
            self.lbl_left.setStyleSheet(f"color:{COL_GREEN}; font-size:11px;")
            self._start_live()
        else:
            self.lbl_left.setText("📅  LỊCH SỬ")
            self.lbl_left.setStyleSheet("color:#4ecdc4; font-size:11px;")
            self._start_history()

    def _start_live(self):
        self._fetch_live()
        self.timer_live.start(LIVE_INTERVAL_MS)
        self.timer_cards.start(CARD_INTERVAL_MS)

    def _start_history(self):
        self._fetch_history()
        self.timer_history.start(HISTORY_INTERVAL_MS)

    def _change_time(self, mins: int, clicked_btn: QPushButton):
        self._history_mins = mins
        for b, m in self._hist_btns:
            b.setStyleSheet(self._hbtn_style(m == mins))
        self._fetch_history()

    # ── API calls ────────────────────────────────────────────────────────────
    def _fetch_latest(self):
        w = ApiWorker("latest")
        w.data_ready.connect(self._on_latest)
        w.error.connect(lambda e: self.lbl_right.setText(f"❌ {e}"))
        self._workers.append(w)
        w.start()

    def _fetch_live(self):
        w = ApiWorker("latest")
        w.data_ready.connect(self._on_live_data)
        w.error.connect(lambda e: self.lbl_right.setText(f"❌ {e}"))
        self._workers.append(w)
        w.start()

    def _fetch_history(self):
        self.lbl_right.setText("🔄 Đang tải...")
        w = ApiWorker("history", self._history_mins)
        w.history_ready.connect(self._on_history_data)
        w.error.connect(lambda e: self.lbl_right.setText(f"❌ {e}"))
        self._workers.append(w)
        w.start()

    # ── Data handlers ────────────────────────────────────────────────────────
    def _on_latest(self, d: dict):
        self._update_cards(d)

    def _on_live_data(self, d: dict):
        self._update_cards(d)
        if d.get("temp", 0) == 0 and d.get("load", 0) == 0:
            return
        now = datetime.now().strftime("%H:%M:%S")
        self._t_data.append(d.get("temp", 0))
        self._l_data.append(d.get("load", 0))
        self._labels.append(now)
        if len(self._t_data) > MAX_LIVE_POINTS:
            self._t_data.pop(0); self._l_data.pop(0); self._labels.pop(0)
        self.chart_temp.set_data(self._t_data, self._labels)
        self.chart_load.set_data(self._l_data, self._labels)
        self.lbl_right.setText(f"🔄 {now}  |  {len(self._t_data)} điểm")

    def _on_history_data(self, data: list):
        self._t_data.clear(); self._l_data.clear(); self._labels.clear()
        for d in data:
            try: t = datetime.fromisoformat(d["time"]).strftime("%H:%M")
            except: t = str(d.get("time", ""))
            self._labels.append(t)
            self._t_data.append(d.get("temp", 0))
            self._l_data.append(d.get("load", 0))
        self.chart_temp.set_data(self._t_data, self._labels)
        self.chart_load.set_data(self._l_data, self._labels)
        now = datetime.now().strftime("%H:%M:%S")
        self.lbl_right.setText(f"🔄 {now}  |  {len(data)} điểm")

    def _update_cards(self, d: dict):
        temp   = d.get("temp", None)
        load   = d.get("load", None)
        status = d.get("status", "--")
        self.card_temp.set_value(f"{temp:.1f}°C" if temp else "--°C",
                                  f"color:{COL_RED}; font-size:26px; font-weight:700;")
        self.card_load.set_value(f"{load}%" if load is not None else "--%",
                                  f"color:{COL_TEAL}; font-size:26px; font-weight:700;")

        # Màu badge theo trạng thái
        colors = {
            "running":     ("#00b894", "white"),
            "idle":        ("#fdcb6e", "#333"),
            "maintenance": ("#e17055", "white"),
            "error":       ("#d63031", "white"),
        }
        bg, fg = colors.get(status, ("#444", "white"))
        self.card_status.set_value(
            status.upper(),
            f"color:{fg}; background:{bg}; font-size:13px; font-weight:700;"
            f" border-radius:10px; padding:4px 10px;"
        )

    # ── Screenshot ───────────────────────────────────────────────────────────
    def _save_screenshot(self):
        from PyQt6.QtGui import QPixmap
        px = self.centralWidget().grab()
        fname = f"CNC_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        px.save(fname)
        self.lbl_right.setText(f"✅ Đã lưu: {fname}")


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette để các widget hệ thống cũng tối
    pal = app.palette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(BG_DARK))
    pal.setColor(QPalette.ColorRole.WindowText,       QColor("white"))
    pal.setColor(QPalette.ColorRole.Base,             QColor(BG_CARD))
    pal.setColor(QPalette.ColorRole.AlternateBase,    QColor(BG_DARK))
    pal.setColor(QPalette.ColorRole.Text,             QColor("white"))
    pal.setColor(QPalette.ColorRole.Button,           QColor(BG_CARD))
    pal.setColor(QPalette.ColorRole.ButtonText,       QColor("white"))
    app.setPalette(pal)

    win = CNCMonitor()
    win.show()
    sys.exit(app.exec())