"""
Friday Eyes - Screen Awareness & Clipboard Intelligence
-------------------------------------------------------
UNIQUE FEATURES that make Friday one step above:

1. Screen Vision   - Takes periodic screenshots, reads visible text via OCR
                     → Friday knows what you're working on
2. App Detection   - Detects active window (VS Code? YouTube? Google Docs?)
                     → Offers relevant contextual help
3. Clipboard Watch - Monitors clipboard changes
                     → "I see you copied code - want me to explain it?"
4. Mood Detection  - Analyzes typing patterns from keyboard activity
                     → Detects stress/frustration, adjusts tone
5. Proactive Push  - Periodically offers help based on screen context
"""

import platform
import threading
import time
from typing import Callable

from loguru import logger

from config.loader import get as cfg


# ──────────────────────────────────────────────────────────────
# Screen Capture & OCR
# ──────────────────────────────────────────────────────────────

class ScreenWatcher:
    """
    Periodically captures screen and extracts visible text.
    Understands what the user is currently working on.
    """

    def __init__(self):
        self._enabled = cfg("screen.enabled", True)
        self._interval = cfg("screen.capture_interval_seconds", 5)
        self._ocr_enabled = cfg("screen.ocr_enabled", True)
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_text: str = ""
        self._last_app: str = ""
        self._on_context_callbacks: list[Callable] = []

    def on_context_change(self, fn: Callable):
        """Register callback when screen context changes significantly."""
        self._on_context_callbacks.append(fn)

    def _get_active_window_title(self) -> str:
        """Get the title of the currently focused window."""
        system = platform.system()
        try:
            if system == "Linux":
                import subprocess
                result = subprocess.run(
                    ["xdotool", "getactivewindow", "getwindowname"],
                    capture_output=True, text=True, timeout=2
                )
                return result.stdout.strip()
            elif system == "Windows":
                import ctypes
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(length + 1)
                ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                return buf.value
            elif system == "Darwin":
                import subprocess
                script = 'tell application "System Events" to name of first application process whose frontmost is true'
                result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=2)
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f"Window title fetch failed: {e}")
        return ""

    def _classify_app(self, window_title: str) -> str:
        """Classify what the user is doing based on window title."""
        title_lower = window_title.lower()
        categories = {
            "coding": ["vs code", "pycharm", "vim", "neovim", "sublime", "atom", "intellij", "xcode", ".py", ".js", "terminal", "bash", "zsh"],
            "writing": ["word", "docs", "notion", "obsidian", "typora", ".docx", "libreoffice writer", "markdown"],
            "browsing": ["firefox", "chrome", "safari", "edge", "browser"],
            "email": ["thunderbird", "outlook", "gmail", "mail"],
            "video": ["youtube", "netflix", "vlc", "mpv", "plex"],
            "spreadsheet": ["excel", "sheets", "calc", "csv"],
            "design": ["figma", "photoshop", "gimp", "inkscape", "canva"],
            "communication": ["slack", "discord", "teams", "zoom", "telegram", "whatsapp"],
        }
        for category, keywords in categories.items():
            if any(kw in title_lower for kw in keywords):
                return category
        return "general"

    def _capture_screen_text(self) -> str:
        """Take a screenshot and OCR visible text."""
        if not self._ocr_enabled:
            return ""
        try:
            import mss
            import pytesseract
            from PIL import Image

            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

                # Downscale for faster OCR
                w, h = img.size
                img = img.resize((w // 2, h // 2), Image.LANCZOS)

                # OCR
                text = pytesseract.image_to_string(img, config="--psm 6")
                return text[:2000]  # Limit
        except ImportError:
            logger.debug("mss or pytesseract not available - screen OCR disabled")
        except Exception as e:
            logger.debug(f"Screen capture error: {e}")
        return ""

    def _watch_loop(self):
        """Main screen watching loop."""
        logger.info("Screen watcher started")
        while self._running:
            try:
                window_title = self._get_active_window_title()
                app_category = self._classify_app(window_title)

                if app_category != self._last_app:
                    self._last_app = app_category
                    logger.debug(f"App context changed: {app_category} ({window_title})")
                    for cb in self._on_context_callbacks:
                        threading.Thread(
                            target=cb,
                            args=(app_category, window_title),
                            daemon=True,
                        ).start()

                time.sleep(self._interval)
            except Exception as e:
                logger.error(f"Screen watcher error: {e}")
                time.sleep(5)

    def start(self):
        if not self._enabled:
            return
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True, name="FridayEyes")
        self._thread.start()

    def stop(self):
        self._running = False

    @property
    def current_app(self) -> str:
        return self._last_app

    @property
    def current_window(self) -> str:
        return self._get_active_window_title()

    def describe_current_screen(self) -> str:
        """
        Return a description of what's currently on screen.
        Used for context injection into LLM prompts.
        """
        window = self.current_window
        app = self._last_app or "general"
        if window:
            return f"User is currently in '{window}' (category: {app})"
        return f"User is doing: {app}"

    def capture_for_query(self) -> str:
        """Capture current screen text for a direct user query."""
        return self._capture_screen_text()


# ──────────────────────────────────────────────────────────────
# Clipboard Intelligence
# ──────────────────────────────────────────────────────────────

class ClipboardWatcher:
    """
    Monitors clipboard for changes.
    When something is copied, Friday can offer smart assistance.
    """

    def __init__(self):
        self._enabled = cfg("clipboard.enabled", True)
        self._watch = cfg("clipboard.watch", True)
        self._auto_suggest = cfg("clipboard.auto_suggest", True)
        self._running = False
        self._thread: threading.Thread | None = None
        self._last_content: str = ""
        self._on_copy_callbacks: list[Callable] = []

    def on_copy(self, fn: Callable):
        """Register callback when clipboard content changes."""
        self._on_copy_callbacks.append(fn)

    def _get_clipboard(self) -> str:
        try:
            import pyperclip
            return pyperclip.paste() or ""
        except Exception:
            return ""

    def _classify_content(self, text: str) -> str:
        """Classify what kind of content was copied."""
        import re
        text_stripped = text.strip()

        if re.match(r"^https?://", text_stripped):
            return "url"
        if len(text_stripped.split("\n")) > 3 or any(kw in text_stripped for kw in ["def ", "function ", "class ", "import ", "const ", "var ", "let "]):
            return "code"
        if re.match(r"^\d+[\d\s\+\-\*\/\(\)\.]+$", text_stripped):
            return "math"
        if len(text_stripped.split()) > 20:
            return "paragraph"
        return "text"

    def _watch_loop(self):
        """Poll clipboard every second for changes."""
        logger.info("Clipboard watcher started")
        while self._running:
            try:
                content = self._get_clipboard()
                if content and content != self._last_content and len(content) > 3:
                    content_type = self._classify_content(content)
                    self._last_content = content
                    logger.debug(f"Clipboard changed: type={content_type}, len={len(content)}")

                    if self._auto_suggest:
                        for cb in self._on_copy_callbacks:
                            threading.Thread(
                                target=cb,
                                args=(content, content_type),
                                daemon=True,
                            ).start()
            except Exception as e:
                logger.debug(f"Clipboard watch error: {e}")
            time.sleep(1)

    def start(self):
        if not self._enabled or not self._watch:
            return
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True, name="FridayClipboard")
        self._thread.start()

    def stop(self):
        self._running = False

    @property
    def current_content(self) -> str:
        return self._last_content

    @property
    def current_type(self) -> str:
        if self._last_content:
            return self._classify_content(self._last_content)
        return "empty"


# ──────────────────────────────────────────────────────────────
# Mood / Stress Detector
# ──────────────────────────────────────────────────────────────

class MoodDetector:
    """
    Detects user stress/frustration from typing patterns.
    Frustration signals: rapid backspacing, capslock usage,
    repeated typing-deleting-retyping patterns.
    """

    def __init__(self):
        self._enabled = cfg("mood.detect_typing_stress", True)
        self._running = False
        self._thread: threading.Thread | None = None
        self._backspace_count = 0
        self._key_count = 0
        self._window_start = time.time()
        self._current_mood = "neutral"
        self._on_mood_callbacks: list[Callable] = []

    def on_mood_change(self, fn: Callable):
        self._on_mood_callbacks.append(fn)

    def _analyze_mood(self) -> str:
        """Analyze recent typing data to determine mood."""
        if self._key_count == 0:
            return "neutral"
        error_rate = self._backspace_count / max(self._key_count, 1)
        if error_rate > 0.3:
            return "frustrated"
        elif error_rate > 0.15:
            return "mildly_stressed"
        return "focused"

    def _watch_loop(self):
        """Monitor keyboard patterns."""
        try:
            import keyboard

            def on_key(event):
                self._key_count += 1
                if event.name == "backspace":
                    self._backspace_count += 1

                # Analyze every 30 seconds
                if time.time() - self._window_start > 30:
                    new_mood = self._analyze_mood()
                    if new_mood != self._current_mood:
                        self._current_mood = new_mood
                        for cb in self._on_mood_callbacks:
                            threading.Thread(target=cb, args=(new_mood,), daemon=True).start()
                    # Reset window
                    self._backspace_count = 0
                    self._key_count = 0
                    self._window_start = time.time()

            keyboard.on_press(on_key)
            logger.info("Mood detector started (keyboard pattern analysis)")

            while self._running:
                time.sleep(1)

            keyboard.unhook_all()
        except ImportError:
            logger.debug("keyboard module not available - mood detection disabled")
        except Exception as e:
            logger.error(f"Mood detector error: {e}")

    def start(self):
        if not self._enabled:
            return
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True, name="FridayMood")
        self._thread.start()

    def stop(self):
        self._running = False

    @property
    def mood(self) -> str:
        return self._current_mood


# ──────────────────────────────────────────────────────────────
# Unified Ambient Intelligence
# ──────────────────────────────────────────────────────────────

class FridayEyes:
    """
    Combines screen awareness, clipboard intelligence, and mood detection.
    The ambient intelligence layer of Friday.
    """

    def __init__(self):
        self.screen = ScreenWatcher()
        self.clipboard = ClipboardWatcher()
        self.mood = MoodDetector()

    def start_all(self):
        """Start all ambient sensors."""
        self.screen.start()
        self.clipboard.start()
        self.mood.start()
        logger.info("Friday ambient intelligence active")

    def stop_all(self):
        """Stop all ambient sensors."""
        self.screen.stop()
        self.clipboard.stop()
        self.mood.stop()

    def full_context(self) -> str:
        """
        Build a full context string for the LLM.
        Combines screen, clipboard, and mood awareness.
        """
        parts = []

        screen_desc = self.screen.describe_current_screen()
        if screen_desc:
            parts.append(screen_desc)

        if self.clipboard.current_content:
            clip_type = self.clipboard.current_type
            parts.append(f"User recently copied {clip_type}: '{self.clipboard.current_content[:100]}...'")

        mood = self.mood.mood
        if mood != "neutral":
            parts.append(f"User appears to be {mood} based on typing patterns")

        return ". ".join(parts)


# Global singleton
_eyes_instance: FridayEyes | None = None


def get_eyes() -> FridayEyes:
    global _eyes_instance
    if _eyes_instance is None:
        _eyes_instance = FridayEyes()
    return _eyes_instance
