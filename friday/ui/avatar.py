"""
Friday Avatar - Animated AI Assistant Character
-----------------------------------------------
Displays an animated character that:
- Pops up when Friday is activated (wake word detected)
- Shows thinking/speaking animations
- Can use image-based PNGs or fallback to emoji
- Disappears when done or minimized

Character assets should be placed in: assets/avatar/
  - idle.png / idle_1.png, idle_2.png (idle animations)
  - thinking.png / thinking_1.png, thinking_2.png (processing)
  - speaking.png / speaking_1.png, speaking_2.png (speaking mouth)
"""

import threading
import time
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QLabel, QApplication
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize
    from PyQt6.QtGui import QFont, QColor, QPixmap
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    logger.warning("PyQt6 not available — avatar disabled")


class AvatarAnimationController(QObject):
    """Emits signals for avatar animations."""

    # Signals for avatar state changes
    activated = pyqtSignal()      # Wake word detected
    thinking = pyqtSignal()       # Processing query
    speaking = pyqtSignal()       # Speaking (no args needed)
    idle = pyqtSignal()           # Resting
    minimize = pyqtSignal()       # Hide avatar


class SimpleAvatar(QWidget):
    """
    Animated avatar character with image/emoji support.
    - Loads PNG images from assets/avatar/ if available
    - Falls back to emoji animations if PNGs not found
    - Smooth frame-by-frame animations
    - Synced with speech and processing states
    """

    def __init__(self):
        if not QT_AVAILABLE:
            self.available = False
            return

        super().__init__()
        self.available = True
        self._state = "idle"
        self._animation_frame = 0
        self._is_visible = False
        self.controller = AvatarAnimationController()

        # Load avatar assets
        self._load_avatar_assets()

        # Setup UI
        self._setup_ui()
        self._setup_animations()
        self._connect_signals()

        logger.info("Avatar initialized")

    def _load_avatar_assets(self):
        """Load PNG avatar images if available, otherwise use emoji."""
        self._use_images = False
        self._image_cache = {}  # Cache loaded images

        # Try to load PNG assets
        assets_dir = Path(__file__).parent.parent.parent / "assets" / "avatar"
        if assets_dir.exists():
            self._load_png_assets(assets_dir)
        else:
            logger.info("No assets/avatar directory found — using emoji avatar")

    def _load_png_assets(self, assets_dir: Path):
        """Load PNG images from assets directory."""
        states = ["idle", "thinking", "speaking"]

        for state in states:
            self._image_cache[state] = []

            # Try to load numbered frames (idle_1.png, idle_2.png, etc.)
            frame_num = 1
            while True:
                png_file = assets_dir / f"{state}_{frame_num}.png"
                if not png_file.exists():
                    break

                try:
                    pixmap = QPixmap(str(png_file))
                    if not pixmap.isNull():
                        self._image_cache[state].append(pixmap)
                        logger.debug(f"Loaded: {png_file.name}")
                except Exception as e:
                    logger.warning(f"Failed to load {png_file.name}: {e}")

                frame_num += 1

            # Fallback: try single image file
            if not self._image_cache[state]:
                png_file = assets_dir / f"{state}.png"
                if png_file.exists():
                    try:
                        pixmap = QPixmap(str(png_file))
                        if not pixmap.isNull():
                            self._image_cache[state].append(pixmap)
                            logger.debug(f"Loaded: {png_file.name}")
                    except Exception as e:
                        logger.warning(f"Failed to load {png_file.name}: {e}")

        # Check if any assets loaded successfully
        if any(self._image_cache[state] for state in states):
            self._use_images = True
            logger.info(f"Avatar using PNG images (idle: {len(self._image_cache['idle'])}, "
                       f"thinking: {len(self._image_cache['thinking'])}, "
                       f"speaking: {len(self._image_cache['speaking'])} frames)")
        else:
            logger.info("No valid PNG assets found — using emoji fallback")

    def _setup_ui(self):
        """Create avatar UI."""
        self.setWindowTitle("Friday")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SplashScreen
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Increased size for better visibility (was 200x300)
        self.setFixedSize(QSize(320, 420))

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Character display (larger, supports both emoji and images)
        self.character_label = QLabel()
        self.character_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Bigger font for emoji/character (was 80)
        self.character_label.setFont(QFont("Arial", 120))
        # Set minimum size for image display
        self.character_label.setMinimumHeight(200)
        # Add glow effect with minimal CSS
        self.character_label.setStyleSheet("""
            QLabel {
                color: #00D4FF;
                text-shadow: 0px 0px 10px #00D4FF;
                background: rgba(0, 20, 40, 180);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.character_label)

        # Status text (larger)
        self.status_label = QLabel("Friday")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setFont(QFont("Arial", 14))
        self.status_label.setStyleSheet("""
            QLabel {
                color: #00D4FF;
                font-weight: bold;
                background: rgba(0, 20, 40, 160);
                border-radius: 5px;
                padding: 5px;
            }
        """)
        layout.addWidget(self.status_label)

        self.setLayout(layout)

        # Position: top-right corner
        screen = QApplication.primaryScreen()
        geom = screen.geometry()
        self.move(geom.width() - 340, 50)

    def _setup_animations(self):
        """Setup animation timer."""
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._animate_frame)
        # Faster animation: 150ms per frame for smoother motion
        self.animation_timer.setInterval(150)

    def _connect_signals(self):
        """Connect avatar state signals."""
        self.controller.activated.connect(self._on_activated)
        self.controller.thinking.connect(self._on_thinking)
        self.controller.speaking.connect(self._on_speaking)
        self.controller.idle.connect(self._on_idle)
        self.controller.minimize.connect(self.hide)

    # ──────────────────────────────────────────────────────────────
    # Animation States
    # ──────────────────────────────────────────────────────────────

    def _animate_frame(self):
        """Animate avatar based on current state."""
        self._animation_frame = (self._animation_frame + 1) % 8

        if self._use_images:
            self._animate_frame_images()
        else:
            self._animate_frame_emoji()

    def _animate_frame_images(self):
        """Animate using PNG images."""
        state_frames = self._image_cache.get(self._state, [])

        if not state_frames:
            # Fallback to emoji if this state has no images
            self._animate_frame_emoji()
            return

        idx = self._animation_frame % len(state_frames)
        pixmap = state_frames[idx]
        # Scale to fit label while maintaining aspect ratio
        scaled = pixmap.scaledToHeight(200, Qt.TransformationMode.SmoothTransformation)
        self.character_label.setPixmap(scaled)

        # Update status text
        if self._state == "idle":
            self.status_label.setText("Friday • Ready")
        elif self._state == "thinking":
            self.status_label.setText("Processing...")
        elif self._state == "speaking":
            self.status_label.setText("Speaking...")

    def _animate_frame_emoji(self):
        """Animate using emoji (fallback)."""
        if self._state == "idle":
            # Breathing/relaxed idle animation (subtle)
            characters = ["🤖", "✨🤖✨", "🤖", "✨🤖✨"]
            idx = self._animation_frame % len(characters)
            self.character_label.setText(characters[idx])
            self.status_label.setText("Friday • Ready")

        elif self._state == "thinking":
            # Thinking/loading animation - more dynamic
            chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧"]
            idx = self._animation_frame % len(chars)
            # Use multiple thinking characters for more visual interest
            self.character_label.setText(f"🤔\n{chars[idx]}")
            self.status_label.setText("Processing...")

        elif self._state == "speaking":
            # Speaking animation - mouth movements
            mouths = ["💬", "👄", "💬", "👄"]
            idx = self._animation_frame % len(mouths)
            self.character_label.setText(f"🤖\n{mouths[idx]}")
            self.status_label.setText("Speaking...")

    def _on_activated(self):
        """Wake word detected — pop up with greeting."""
        self._state = "idle"
        self.show()
        self._is_visible = True
        self.animation_timer.start()
        self.character_label.setText("🤖")
        self.status_label.setText("Friday • Listening")
        logger.debug("Avatar activated")

    def _on_thinking(self):
        """Start thinking animation."""
        self._state = "thinking"
        self._animation_frame = 0
        if not self.animation_timer.isActive():
            self.animation_timer.start()
        logger.debug("Avatar thinking")

    def _on_speaking(self, text: str = ""):
        """Start speaking animation."""
        self._state = "speaking"
        self._animation_frame = 0
        if not self.animation_timer.isActive():
            self.animation_timer.start()
        logger.debug("Avatar speaking")

    def _on_idle(self):
        """Return to idle state."""
        self._state = "idle"
        self._animation_frame = 0
        logger.debug("Avatar idle")

    # ──────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────

    def show_popup(self):
        """Pop up the avatar on screen."""
        if QT_AVAILABLE:
            self.show()
            self._is_visible = True

    def hide(self):
        """Hide the avatar."""
        super().hide()
        self._is_visible = False
        self.animation_timer.stop()
        logger.debug("Avatar hidden")

    def stop(self):
        """Stop all animations and clean up."""
        self.animation_timer.stop()
        self.hide()
        logger.debug("Avatar stopped")

    @property
    def is_visible(self) -> bool:
        return self._is_visible


# Global singleton
_avatar_instance: Optional[SimpleAvatar] = None


def get_avatar() -> Optional[SimpleAvatar]:
    """Get or create the global avatar instance."""
    global _avatar_instance
    if _avatar_instance is None and QT_AVAILABLE:
        _avatar_instance = SimpleAvatar()
    return _avatar_instance
