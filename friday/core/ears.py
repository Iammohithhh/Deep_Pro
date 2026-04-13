"""
Friday Wake Word Engine
-----------------------
Always-listening wake word detection using OpenWakeWord.
Runs as a background thread. When "Friday" is detected,
fires callbacks so the rest of the system wakes up.

Also supports a global hotkey as an alternative trigger.
"""

import threading
import time
from typing import Callable

import numpy as np
from loguru import logger

from config.loader import get as cfg


class FridayEars:
    """
    Listens 24/7 for the wake word "Friday".
    Ultra-low CPU footprint - only activates on detection.
    """

    def __init__(self):
        self._enabled = cfg("wake_word.enabled", True)
        self._sensitivity = cfg("wake_word.sensitivity", 0.6)
        self._chunk_size = cfg("wake_word.chunk_size", 1280)
        self._sample_rate = cfg("wake_word.sample_rate", 16000)
        self._device_index = cfg("wake_word.device_index", None)

        self._running = False
        self._thread: threading.Thread | None = None
        self._oww_model = None
        self._callbacks: list[Callable] = []
        self._cooldown_sec = 2.0  # seconds between detections
        self._last_detection = 0.0

        logger.info("Ears initialized | always-listening wake word engine ready")

    def on_wake(self, fn: Callable):
        """Register a callback triggered when 'Friday' is detected."""
        self._callbacks.append(fn)
        logger.debug(f"Wake callback registered: {fn.__name__}")

    def _load_model(self):
        """Load OpenWakeWord model (lazy)."""
        try:
            from openwakeword.model import Model
            # Use built-in "hey jarvis" as base or closest to "friday"
            # OpenWakeWord supports custom models - using pre-trained for now
            self._oww_model = Model(
                wakeword_models=["hey_jarvis"],  # closest built-in
                inference_framework="onnx",
            )
            logger.info("OpenWakeWord model loaded (hey_jarvis as Friday stand-in)")
        except Exception as e:
            logger.warning(f"OpenWakeWord not available ({e}), falling back to energy-based detection")
            self._oww_model = None

    def _fire_wake(self):
        """Fire all registered wake callbacks."""
        now = time.time()
        if now - self._last_detection < self._cooldown_sec:
            return  # Cooldown to prevent double triggers
        self._last_detection = now
        logger.info("WAKE WORD DETECTED - activating Friday!")
        for cb in self._callbacks:
            threading.Thread(target=cb, daemon=True).start()

    def _listen_loop_oww(self):
        """Main listen loop using OpenWakeWord."""
        import sounddevice as sd

        logger.info("Wake word listener started (OpenWakeWord)")
        chunk_size = self._chunk_size
        sr = self._sample_rate

        with sd.InputStream(
            samplerate=sr,
            channels=1,
            dtype="int16",
            blocksize=chunk_size,
            device=self._device_index,
        ) as stream:
            while self._running:
                try:
                    chunk, _ = stream.read(chunk_size)
                    chunk = chunk.flatten()
                    preds = self._oww_model.predict(chunk)

                    for model_name, score in preds.items():
                        if score >= self._sensitivity:
                            logger.debug(f"Wake score: {model_name}={score:.3f}")
                            self._fire_wake()
                            break
                except Exception as e:
                    logger.error(f"Wake word loop error: {e}")
                    time.sleep(0.5)

    def _listen_loop_energy(self):
        """
        Fallback: simple energy-based voice activity detection.
        Triggers on loud sustained audio (manual trigger by clapping 3x or hotkey).
        """
        import sounddevice as sd
        logger.info("Wake word listener started (energy/VAD fallback)")

        sr = self._sample_rate
        chunk_size = 1600  # 100ms
        ENERGY_THRESHOLD = 0.03
        TRIGGER_CHUNKS = 5  # 500ms sustained above threshold

        above_count = 0
        with sd.InputStream(samplerate=sr, channels=1, dtype="float32", blocksize=chunk_size) as stream:
            while self._running:
                try:
                    chunk, _ = stream.read(chunk_size)
                    rms = float(np.sqrt(np.mean(chunk.flatten() ** 2)))
                    if rms > ENERGY_THRESHOLD:
                        above_count += 1
                        if above_count >= TRIGGER_CHUNKS:
                            self._fire_wake()
                            above_count = 0
                    else:
                        above_count = max(0, above_count - 1)
                except Exception as e:
                    logger.error(f"Energy listener error: {e}")
                    time.sleep(0.5)

    def _setup_hotkey(self):
        """Register global hotkey as alternative wake trigger."""
        hotkey = cfg("system.hotkey", "ctrl+shift+f")
        try:
            import keyboard
            keyboard.add_hotkey(hotkey, self._fire_wake, suppress=False)
            logger.info(f"Global hotkey registered: {hotkey}")
        except Exception as e:
            logger.warning(f"Hotkey registration failed: {e}")

    def start(self):
        """Start the always-listening wake word detector."""
        if not self._enabled:
            logger.info("Wake word disabled in config, using hotkey only")
            self._setup_hotkey()
            return

        self._running = True
        self._load_model()

        if self._oww_model:
            target = self._listen_loop_oww
        else:
            target = self._listen_loop_energy

        self._thread = threading.Thread(target=target, daemon=True, name="FridayEars")
        self._thread.start()
        self._setup_hotkey()
        logger.info("Friday is listening...")

    def stop(self):
        """Stop the wake word listener."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        try:
            import keyboard
            keyboard.unhook_all()
        except Exception:
            pass
        logger.info("Wake word listener stopped")

    @property
    def is_listening(self) -> bool:
        return self._running and (self._thread is not None and self._thread.is_alive())


# ──────────────────────────────────────────────────────────────
# Interaction State Machine
# ──────────────────────────────────────────────────────────────

class FridayInteractionState:
    """
    Manages the state of a Friday interaction.

    States: sleeping → listening → thinking → speaking → sleeping
    """

    SLEEPING = "sleeping"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"

    def __init__(self):
        self._state = self.SLEEPING
        self._callbacks: dict[str, list[Callable]] = {
            self.SLEEPING: [],
            self.LISTENING: [],
            self.THINKING: [],
            self.SPEAKING: [],
        }

    def transition(self, new_state: str):
        """Transition to a new state and fire callbacks."""
        if new_state == self._state:
            return
        old = self._state
        self._state = new_state
        logger.debug(f"State: {old} → {new_state}")
        for cb in self._callbacks.get(new_state, []):
            cb()

    def on(self, state: str, fn: Callable):
        """Register callback for a state transition."""
        self._callbacks.setdefault(state, []).append(fn)

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_sleeping(self) -> bool:
        return self._state == self.SLEEPING


# Global singletons
_ears_instance: FridayEars | None = None
_state_instance: FridayInteractionState | None = None


def get_ears() -> FridayEars:
    global _ears_instance
    if _ears_instance is None:
        _ears_instance = FridayEars()
    return _ears_instance


def get_state() -> FridayInteractionState:
    global _state_instance
    if _state_instance is None:
        _state_instance = FridayInteractionState()
    return _state_instance
