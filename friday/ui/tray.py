"""
Friday System Tray
------------------
Lives in the system tray at all times.
Provides quick controls, status indicator, and menu.
"""

import sys
import threading
from pathlib import Path
from typing import Callable

from loguru import logger

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False
    logger.warning("pystray or Pillow not installed - tray icon disabled")


def _create_icon_image(state: str = "sleeping") -> "Image.Image":
    """
    Generate a dynamic tray icon based on Friday's state.
    Returns a PIL Image.
    """
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Circle background
    colors = {
        "sleeping":  ((30, 20, 5), (180, 130, 0)),     # Dark gold
        "listening": ((0, 40, 30), (0, 200, 160)),     # Teal
        "thinking":  ((0, 20, 50), (0, 140, 255)),     # Blue
        "speaking":  ((40, 20, 0), (255, 180, 0)),     # Bright gold
    }
    bg_color, ring_color = colors.get(state, colors["sleeping"])

    draw.ellipse([2, 2, size - 2, size - 2], fill=bg_color, outline=ring_color, width=3)

    # "F" letter in center
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf", 28)
    except Exception:
        font = ImageFont.load_default()

    draw.text((size // 2, size // 2), "F", fill=ring_color, font=font, anchor="mm")
    return img


class FridayTray:
    """
    System tray icon with context menu.
    Provides status indication and quick controls.
    """

    def __init__(self):
        self._icon: pystray.Icon | None = None
        self._state = "sleeping"
        self._thread: threading.Thread | None = None
        self._callbacks: dict[str, list[Callable]] = {
            "activate": [],
            "quit": [],
            "toggle_hud": [],
            "news_briefing": [],
        }

    def on(self, event: str, fn: Callable):
        """Register a callback for a tray event."""
        self._callbacks.setdefault(event, []).append(fn)

    def _fire(self, event: str):
        for cb in self._callbacks.get(event, []):
            threading.Thread(target=cb, daemon=True).start()

    def _build_menu(self):
        """Build the right-click context menu."""
        if not HAS_TRAY:
            return None

        return pystray.Menu(
            pystray.MenuItem("Friday AI Assistant", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Activate (Ctrl+Shift+F)", lambda: self._fire("activate")),
            pystray.MenuItem("News Briefing", lambda: self._fire("news_briefing")),
            pystray.MenuItem("Toggle HUD", lambda: self._fire("toggle_hud")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Status: " + self._state.capitalize(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit Friday", lambda: self._fire("quit")),
        )

    def start(self):
        """Start the system tray icon."""
        if not HAS_TRAY:
            logger.warning("System tray not available")
            return

        img = _create_icon_image("sleeping")
        self._icon = pystray.Icon(
            name="Friday",
            icon=img,
            title="Friday AI Assistant",
            menu=self._build_menu(),
        )
        self._thread = threading.Thread(target=self._icon.run, daemon=True, name="FridayTray")
        self._thread.start()
        logger.info("System tray icon started")

    def update_state(self, state: str):
        """Update the tray icon to reflect current state."""
        self._state = state
        if self._icon and HAS_TRAY:
            try:
                self._icon.icon = _create_icon_image(state)
                self._icon.title = f"Friday AI - {state.capitalize()}"
                self._icon.menu = self._build_menu()
            except Exception as e:
                logger.warning(f"Tray update failed: {e}")

    def notify(self, title: str, message: str):
        """Show a system notification."""
        if self._icon and HAS_TRAY:
            try:
                self._icon.notify(message, title)
            except Exception as e:
                logger.warning(f"Notification failed: {e}")

    def stop(self):
        """Stop the tray icon."""
        if self._icon:
            self._icon.stop()
        logger.info("Tray icon stopped")


# ──────────────────────────────────────────────────────────────
# Auto-Startup Registration
# ──────────────────────────────────────────────────────────────

def register_startup(script_path: Path):
    """
    Register Friday to auto-start on system boot.
    Supports Linux (systemd user service) and basic autostart.
    """
    import platform
    system = platform.system()

    if system == "Linux":
        _register_linux_autostart(script_path)
    elif system == "Windows":
        _register_windows_startup(script_path)
    elif system == "Darwin":
        _register_macos_launchagent(script_path)
    else:
        logger.warning(f"Auto-startup not supported on {system}")


def _register_linux_autostart(script_path: Path):
    """Create a .desktop autostart entry."""
    autostart_dir = Path.home() / ".config" / "autostart"
    autostart_dir.mkdir(parents=True, exist_ok=True)

    desktop_file = autostart_dir / "friday-ai.desktop"
    python_exec = sys.executable

    content = f"""[Desktop Entry]
Type=Application
Name=Friday AI Assistant
Comment=Always-on AI personal assistant
Exec={python_exec} {script_path} --minimized
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
StartupNotify=false
"""
    desktop_file.write_text(content)
    logger.info(f"Linux autostart registered: {desktop_file}")


def _register_windows_startup(script_path: Path):
    """Add to Windows registry startup."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(
            key, "FridayAI", 0, winreg.REG_SZ,
            f'"{sys.executable}" "{script_path}"'
        )
        winreg.CloseKey(key)
        logger.info("Windows startup registered")
    except Exception as e:
        logger.error(f"Windows startup registration failed: {e}")


def _register_macos_launchagent(script_path: Path):
    """Create a macOS LaunchAgent plist."""
    agents_dir = Path.home() / "Library" / "LaunchAgents"
    agents_dir.mkdir(parents=True, exist_ok=True)

    plist_path = agents_dir / "com.friday.ai.plist"
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.friday.ai</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>{script_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""
    plist_path.write_text(content)
    logger.info(f"macOS LaunchAgent registered: {plist_path}")


# Global singleton
_tray_instance: FridayTray | None = None


def get_tray() -> FridayTray:
    global _tray_instance
    if _tray_instance is None:
        _tray_instance = FridayTray()
    return _tray_instance
