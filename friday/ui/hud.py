"""
Friday Iron Man HUD Overlay
---------------------------
A transparent, always-on-top overlay that displays:
  - Digital clock (Iron Man style)
  - News ticker (scrolling headlines)
  - System status (CPU, RAM, battery)
  - Listening indicator (pulsing when active)
  - Chat bubble for Friday's responses
  - Weather summary

Built with PyQt6 for smooth, hardware-accelerated rendering.
Theme: Iron Man gold/red palette on dark background.
"""

import sys
import threading
import time
from typing import Callable

from loguru import logger

try:
    from PyQt6.QtCore import (
        Qt, QTimer, QPropertyAnimation, QEasingCurve,
        QPoint, QRect, QSize, pyqtSignal, QObject, QThread
    )
    from PyQt6.QtGui import (
        QColor, QFont, QFontDatabase, QPainter, QPen,
        QBrush, QLinearGradient, QPainterPath, QPixmap,
        QScreen, QGuiApplication
    )
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QLabel, QVBoxLayout,
        QHBoxLayout, QFrame, QSizePolicy
    )
    HAS_QT = True
except ImportError:
    HAS_QT = False
    logger.warning("PyQt6 not available - HUD disabled")

from config.loader import get as cfg


# ──────────────────────────────────────────────────────────────
# Color Theme (Iron Man)
# ──────────────────────────────────────────────────────────────

class IronManTheme:
    BG_DARK        = QColor(8, 12, 20, 210)       # Near-black with opacity
    GOLD_PRIMARY   = QColor(255, 180, 0)            # Tony's gold
    GOLD_LIGHT     = QColor(255, 220, 80)
    RED_ACCENT     = QColor(180, 30, 30)
    BLUE_GLOW      = QColor(0, 180, 255, 200)       # Arc reactor blue
    TEXT_PRIMARY   = QColor(220, 200, 120)          # Gold text
    TEXT_DIM       = QColor(120, 100, 60)
    TEXT_WHITE     = QColor(230, 230, 230)
    PANEL_BORDER   = QColor(180, 130, 0, 160)
    LISTENING_CLR  = QColor(0, 220, 180, 200)       # Teal when listening
    SUCCESS_CLR    = QColor(80, 220, 80)
    BORDER_RADIUS  = 8


if HAS_QT:
    class FridayHUDWidget(QWidget):
        """
        The main HUD overlay widget.
        Transparent window, always on top, click-through capable.
        """

        # Signals for thread-safe UI updates
        update_speech_signal = pyqtSignal(str)
        update_state_signal = pyqtSignal(str)  # sleeping | listening | thinking | speaking
        update_news_signal = pyqtSignal(str)

        def __init__(self):
            super().__init__()
            self._theme = IronManTheme()
            self._ticker_text = "Fetching news..."
            self._ticker_offset = 0
            self._speech_text = ""
            self._state = "sleeping"
            self._pulse_alpha = 0
            self._pulse_dir = 1
            self._weather_text = ""
            self._cpu_pct = 0.0
            self._ram_pct = 0.0
            self._battery_pct = -1

            self._setup_window()
            self._setup_timers()
            self._connect_signals()

        def _setup_window(self):
            pos = cfg("hud.position", "top-right")
            width = cfg("hud.width", 340)
            opacity = cfg("hud.opacity", 0.85)

            self.setWindowTitle("Friday HUD")
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
                | Qt.WindowType.WindowTransparentForInput  # Click-through!
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            self.setWindowOpacity(opacity)

            # Position based on config
            screen = QGuiApplication.primaryScreen().geometry()
            height = 380
            margin = 16

            positions = {
                "top-right":     QRect(screen.width() - width - margin, margin, width, height),
                "top-left":      QRect(margin, margin, width, height),
                "bottom-right":  QRect(screen.width() - width - margin, screen.height() - height - margin, width, height),
                "bottom-left":   QRect(margin, screen.height() - height - margin, width, height),
            }
            geom = positions.get(pos, positions["top-right"])
            self.setGeometry(geom)

        def _setup_timers(self):
            # Clock update every second
            self._clock_timer = QTimer(self)
            self._clock_timer.timeout.connect(self._tick_clock)
            self._clock_timer.start(1000)

            # News ticker scroll every 60ms
            self._ticker_timer = QTimer(self)
            self._ticker_timer.timeout.connect(self._tick_ticker)
            self._ticker_timer.start(60)

            # Listening pulse animation every 50ms
            self._pulse_timer = QTimer(self)
            self._pulse_timer.timeout.connect(self._tick_pulse)
            self._pulse_timer.start(50)

            # System stats every 3s
            self._stats_timer = QTimer(self)
            self._stats_timer.timeout.connect(self._update_stats)
            self._stats_timer.start(3000)

        def _connect_signals(self):
            self.update_speech_signal.connect(self._on_speech_update)
            self.update_state_signal.connect(self._on_state_update)
            self.update_news_signal.connect(self._on_news_update)

        # ── Timer callbacks ─────────────────────────────────

        def _tick_clock(self):
            self.update()  # Trigger repaint

        def _tick_ticker(self):
            if self._ticker_text:
                self._ticker_offset -= 2
                text_width = len(self._ticker_text) * 7
                if self._ticker_offset < -text_width:
                    self._ticker_offset = self.width()
            self.update()

        def _tick_pulse(self):
            if self._state in ("listening", "thinking"):
                self._pulse_alpha += 8 * self._pulse_dir
                if self._pulse_alpha >= 255 or self._pulse_alpha <= 0:
                    self._pulse_dir *= -1
                    self._pulse_alpha = max(0, min(255, self._pulse_alpha))
                self.update()

        def _update_stats(self):
            try:
                import psutil
                self._cpu_pct = psutil.cpu_percent()
                self._ram_pct = psutil.virtual_memory().percent
                batt = psutil.sensors_battery()
                self._battery_pct = batt.percent if batt else -1
            except Exception:
                pass
            self.update()

        # ── Signal slots ────────────────────────────────────

        def _on_speech_update(self, text: str):
            self._speech_text = text
            self.update()

        def _on_state_update(self, state: str):
            self._state = state
            if state == "sleeping":
                self._pulse_alpha = 0
            self.update()

        def _on_news_update(self, text: str):
            self._ticker_text = text
            self._ticker_offset = self.width()

        # ── Paint ───────────────────────────────────────────

        def paintEvent(self, event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            w, h = self.width(), self.height()

            # Main panel background
            self._draw_panel(painter, w, h)
            # Header with Friday logo
            self._draw_header(painter, w)
            # Clock
            self._draw_clock(painter, w)
            # Status indicator
            self._draw_status(painter, w)
            # System stats
            self._draw_stats(painter, w)
            # Weather
            self._draw_weather(painter, w)
            # Speech/response area
            self._draw_speech(painter, w)
            # News ticker
            self._draw_ticker(painter, w, h)

            painter.end()

        def _draw_panel(self, p: QPainter, w: int, h: int):
            """Dark semi-transparent panel with gold border."""
            path = QPainterPath()
            path.addRoundedRect(0, 0, w, h, IronManTheme.BORDER_RADIUS, IronManTheme.BORDER_RADIUS)

            # Background
            p.fillPath(path, QBrush(IronManTheme.BG_DARK))

            # Border
            pen = QPen(IronManTheme.PANEL_BORDER, 1.5)
            p.setPen(pen)
            p.drawPath(path)

            # Top accent line (gold)
            p.setPen(QPen(IronManTheme.GOLD_PRIMARY, 2))
            p.drawLine(IronManTheme.BORDER_RADIUS, 1, w - IronManTheme.BORDER_RADIUS, 1)

        def _draw_header(self, p: QPainter, w: int):
            """Draw 'FRIDAY' logo text at top."""
            p.setPen(QPen(IronManTheme.GOLD_PRIMARY))
            font = QFont("Courier New", 11, QFont.Weight.Bold)
            p.setFont(font)
            p.drawText(QRect(12, 8, w - 24, 20), Qt.AlignmentFlag.AlignLeft, "◈ FRIDAY AI")

            # Version / mode on right
            p.setPen(QPen(IronManTheme.TEXT_DIM))
            font2 = QFont("Courier New", 7)
            p.setFont(font2)
            p.drawText(QRect(12, 8, w - 24, 20), Qt.AlignmentFlag.AlignRight, "v1.0 ◈")

            # Separator
            p.setPen(QPen(IronManTheme.PANEL_BORDER, 1))
            p.drawLine(12, 30, w - 12, 30)

        def _draw_clock(self, p: QPainter, w: int):
            """Large digital clock display."""
            import datetime
            now = datetime.datetime.now()
            time_str = now.strftime("%H:%M:%S")
            date_str = now.strftime("%a, %b %d %Y")

            font = QFont("Courier New", 24, QFont.Weight.Bold)
            p.setFont(font)
            p.setPen(QPen(IronManTheme.GOLD_LIGHT))
            p.drawText(QRect(0, 36, w, 38), Qt.AlignmentFlag.AlignCenter, time_str)

            font2 = QFont("Courier New", 8)
            p.setFont(font2)
            p.setPen(QPen(IronManTheme.TEXT_DIM))
            p.drawText(QRect(0, 74, w, 14), Qt.AlignmentFlag.AlignCenter, date_str)

        def _draw_status(self, p: QPainter, w: int):
            """Listening/thinking/speaking status indicator."""
            state_colors = {
                "sleeping": IronManTheme.TEXT_DIM,
                "listening": IronManTheme.LISTENING_CLR,
                "thinking": IronManTheme.BLUE_GLOW,
                "speaking": IronManTheme.GOLD_PRIMARY,
            }
            state_labels = {
                "sleeping": "● STANDBY",
                "listening": "◉ LISTENING...",
                "thinking": "⟳ PROCESSING...",
                "speaking": "♪ SPEAKING",
            }
            color = state_colors.get(self._state, IronManTheme.TEXT_DIM)
            label = state_labels.get(self._state, "● STANDBY")

            if self._state in ("listening", "thinking"):
                color = QColor(color.red(), color.green(), color.blue(), self._pulse_alpha)

            p.setPen(QPen(color))
            font = QFont("Courier New", 8, QFont.Weight.Bold)
            p.setFont(font)
            p.drawText(QRect(0, 90, w, 14), Qt.AlignmentFlag.AlignCenter, label)

            # Separator
            p.setPen(QPen(IronManTheme.PANEL_BORDER, 1))
            p.drawLine(12, 107, w - 12, 107)

        def _draw_stats(self, p: QPainter, w: int):
            """CPU / RAM / Battery mini stats."""
            font = QFont("Courier New", 7)
            p.setFont(font)
            y = 112

            stats = [
                ("CPU", f"{self._cpu_pct:.0f}%", self._cpu_pct / 100),
                ("RAM", f"{self._ram_pct:.0f}%", self._ram_pct / 100),
            ]
            if self._battery_pct >= 0:
                stats.append(("BAT", f"{self._battery_pct:.0f}%", self._battery_pct / 100))

            bar_width = (w - 24 - (len(stats) - 1) * 8) // len(stats)
            x = 12

            for label, val_str, pct in stats:
                # Label
                p.setPen(QPen(IronManTheme.TEXT_DIM))
                p.drawText(QRect(x, y, bar_width, 10), Qt.AlignmentFlag.AlignCenter, f"{label}: {val_str}")

                # Bar background
                p.fillRect(x, y + 11, bar_width, 4, QBrush(QColor(40, 30, 10)))
                # Bar fill
                color = IronManTheme.SUCCESS_CLR if pct < 0.7 else (IronManTheme.GOLD_PRIMARY if pct < 0.9 else IronManTheme.RED_ACCENT)
                fill_w = int(bar_width * pct)
                if fill_w > 0:
                    p.fillRect(x, y + 11, fill_w, 4, QBrush(color))

                x += bar_width + 8

            # Separator
            p.setPen(QPen(IronManTheme.PANEL_BORDER, 1))
            p.drawLine(12, y + 18, w - 12, y + 18)

        def _draw_weather(self, p: QPainter, w: int):
            """Weather display."""
            y = 140
            font = QFont("Courier New", 8)
            p.setFont(font)
            p.setPen(QPen(IronManTheme.TEXT_PRIMARY))
            weather_display = self._weather_text or "☁ Weather loading..."
            p.drawText(QRect(12, y, w - 24, 14), Qt.AlignmentFlag.AlignLeft, f"☁ {weather_display}")

            # Separator
            p.setPen(QPen(IronManTheme.PANEL_BORDER, 1))
            p.drawLine(12, y + 18, w - 12, y + 18)

        def _draw_speech(self, p: QPainter, w: int):
            """Friday's last response displayed in a speech box."""
            if not self._speech_text:
                return

            y = 165
            box_h = 100
            padding = 10

            # Box border
            p.setPen(QPen(QColor(180, 130, 0, 100), 1))
            p.drawRoundedRect(12, y, w - 24, box_h, 4, 4)

            # "FRIDAY:" label
            font_label = QFont("Courier New", 7, QFont.Weight.Bold)
            p.setFont(font_label)
            p.setPen(QPen(IronManTheme.GOLD_PRIMARY))
            p.drawText(QRect(16, y + 4, w - 32, 12), Qt.AlignmentFlag.AlignLeft, "FRIDAY:")

            # Response text (word-wrapped)
            font_text = QFont("Arial", 8)
            p.setFont(font_text)
            p.setPen(QPen(IronManTheme.TEXT_WHITE))
            text_rect = QRect(16, y + 18, w - 32, box_h - 24)
            p.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, self._speech_text)

        def _draw_ticker(self, p: QPainter, w: int, h: int):
            """Scrolling news ticker at the bottom."""
            if not cfg("hud.show_news_ticker", True):
                return

            ticker_y = h - 28
            ticker_h = 22

            # Ticker background
            p.fillRect(0, ticker_y, w, ticker_h, QBrush(QColor(20, 10, 0, 200)))
            p.setPen(QPen(IronManTheme.PANEL_BORDER, 1))
            p.drawLine(0, ticker_y, w, ticker_y)

            # Clip to ticker area
            p.setClipRect(0, ticker_y, w, ticker_h)

            font = QFont("Courier New", 7)
            p.setFont(font)
            p.setPen(QPen(IronManTheme.GOLD_PRIMARY))
            p.drawText(
                self._ticker_offset,
                ticker_y + 14,
                self._ticker_text,
            )

            p.setClipping(False)

        # ── Public API (thread-safe) ─────────────────────────

        def set_state(self, state: str):
            """Update listening state (thread-safe)."""
            self.update_state_signal.emit(state)

        def set_speech(self, text: str):
            """Update displayed response (thread-safe)."""
            self.update_speech_signal.emit(text)

        def set_news_ticker(self, text: str):
            """Update news ticker text (thread-safe)."""
            self.update_news_signal.emit(text)

        def set_weather(self, text: str):
            """Update weather display (thread-safe)."""
            self._weather_text = text
            self.update()


# ──────────────────────────────────────────────────────────────
# HUD Manager (runs the Qt event loop in a thread)
# ──────────────────────────────────────────────────────────────

class HUDManager:
    """
    Manages the HUD overlay lifecycle.

    IMPORTANT: Qt requires QApplication to run in the main thread.
    Use init_in_main_thread() from your main thread before starting
    the orchestrator loop.  start() is kept for compatibility but
    will only work if called from the main thread.
    """

    def __init__(self):
        self._app: "QApplication | None" = None
        self._widget: "FridayHUDWidget | None" = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()

    def init_in_main_thread(self):
        """
        Create QApplication + widget in the CURRENT (main) thread.
        Call this before starting the orchestrator background threads.
        Returns the QApplication so caller can call app.exec() to block.
        """
        if not HAS_QT:
            logger.warning("PyQt6 not installed - HUD unavailable")
            return None
        if not cfg("hud.enabled", True):
            logger.info("HUD disabled in config")
            return None
        try:
            app = QApplication.instance() or QApplication(sys.argv)
            self._app = app
            self._widget = FridayHUDWidget()
            self._widget.show()
            self._ready.set()
            logger.info("HUD initialized in main thread")
            return app
        except Exception as e:
            logger.error(f"HUD init error: {e}")
            self._ready.set()
            return None

    def start(self):
        """
        Legacy start method — only works correctly when called from
        the main thread.  Prefer init_in_main_thread() + app.exec().
        """
        if not HAS_QT or not cfg("hud.enabled", True):
            return
        # If already initialized (e.g. by init_in_main_thread), skip
        if self._widget is not None:
            return
        logger.warning(
            "HUD.start() called — creating widget in current thread. "
            "For full GUI use init_in_main_thread() from main.py instead."
        )
        self.init_in_main_thread()

    def stop(self):
        """Cleanly shut down HUD."""
        if self._app:
            self._app.quit()

    # Forwarded update methods

    def set_state(self, state: str):
        if self._widget:
            self._widget.set_state(state)

    def set_speech(self, text: str):
        if self._widget:
            self._widget.set_speech(text)

    def set_news_ticker(self, text: str):
        if self._widget:
            self._widget.set_news_ticker(text)

    def set_weather(self, text: str):
        if self._widget:
            self._widget.set_weather(text)

    @property
    def available(self) -> bool:
        return HAS_QT and self._widget is not None


# Global singleton
_hud_instance: HUDManager | None = None


def get_hud() -> HUDManager:
    global _hud_instance
    if _hud_instance is None:
        _hud_instance = HUDManager()
    return _hud_instance
