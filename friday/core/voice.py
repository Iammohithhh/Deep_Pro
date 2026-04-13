"""
Friday Voice Engine
-------------------
Handles:
  - Speech-to-Text  : Faster-Whisper (offline, fast)
  - Text-to-Speech  : pyttsx3 (offline) or edge-tts (online, natural)
  - Voice Activity Detection (VAD) for clean audio capture
"""

import io
import queue
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Callable

import numpy as np
import sounddevice as sd
from loguru import logger

from config.loader import get as cfg


# ──────────────────────────────────────────────────────────────
# Speech-to-Text (STT)
# ──────────────────────────────────────────────────────────────

class FridaySTT:
    """
    Offline speech recognition using Faster-Whisper.
    Captures audio from mic, detects silence, returns transcript.
    """

    def __init__(self):
        self._model_name = cfg("stt.model", "base")
        self._device = cfg("stt.device", "cpu")
        self._language = cfg("stt.language", "en")
        self._silence_threshold = cfg("stt.silence_threshold", 0.5)
        self._max_seconds = cfg("stt.max_record_seconds", 15)
        self._sample_rate = 16000
        self._model = None
        logger.info(f"STT initialized | model={self._model_name} | device={self._device}")

    def _load_model(self):
        """Lazy-load Whisper model on first use."""
        if self._model is None:
            logger.info("Loading Whisper model (first use, may take a moment)...")
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self._model_name,
                device=self._device,
                compute_type="int8" if self._device == "cpu" else "float16",
            )
            logger.info("Whisper model loaded.")

    def record(self, max_seconds: int | None = None) -> np.ndarray:
        """
        Record audio from microphone with smart voice-activity detection.
        Waits for speech to start, then stops after sustained silence.
        Returns numpy array of audio samples.
        """
        max_sec = max_seconds or self._max_seconds
        sample_rate = self._sample_rate
        chunk_duration = 0.1  # 100ms per chunk
        chunk_size = int(sample_rate * chunk_duration)

        # Calibrate: read 0.3s of ambient noise to set threshold
        audio_chunks = []
        noise_samples = []
        with sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            blocksize=chunk_size,
        ) as stream:
            # Phase 0: Calibrate noise floor (300ms)
            for _ in range(3):
                chunk, _ = stream.read(chunk_size)
                flat = chunk.flatten()
                noise_samples.append(np.sqrt(np.mean(flat ** 2)))

            noise_floor = max(np.mean(noise_samples) * 2.5, 0.003)
            logger.debug(f"Noise floor calibrated: {noise_floor:.4f}")

            speech_started = False
            silence_chunks = 0
            # Need 1.2s of silence AFTER speech to stop
            silence_limit = int(1.2 / chunk_duration)

            max_chunks = int(max_sec / chunk_duration)
            for i in range(max_chunks):
                chunk, _ = stream.read(chunk_size)
                flat = chunk.flatten()
                audio_chunks.append(flat)

                rms = np.sqrt(np.mean(flat ** 2))

                if rms > noise_floor:
                    speech_started = True
                    silence_chunks = 0
                elif speech_started:
                    silence_chunks += 1
                    if silence_chunks >= silence_limit:
                        logger.debug(f"Speech ended after {i * chunk_duration:.1f}s")
                        break

        if not audio_chunks:
            return np.array([], dtype=np.float32)

        audio = np.concatenate(audio_chunks)
        duration = len(audio) / sample_rate
        logger.debug(f"Recorded {duration:.1f}s of audio (speech_detected={speech_started})")
        return audio

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe numpy audio array to text."""
        self._load_model()

        # Save to temp WAV file (faster-whisper needs file path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(self._sample_rate)
                wf.writeframes((audio * 32767).astype(np.int16).tobytes())

        try:
            segments, info = self._model.transcribe(
                tmp_path,
                language=self._language,
                vad_filter=True,  # Skip silent parts
                beam_size=3,
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()
            logger.info(f"Transcribed: '{text}' (lang={info.language}, prob={info.language_probability:.2f})")
            return text
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def listen_once(self) -> str:
        """Record one utterance and return transcript."""
        audio = self.record()
        if len(audio) < self._sample_rate * 0.3:
            return ""
        return self.transcribe(audio)


# ──────────────────────────────────────────────────────────────
# Text-to-Speech (TTS)
# ──────────────────────────────────────────────────────────────

class FridayTTS:
    """
    Text-to-speech engine for Friday's voice.
    Uses pyttsx3 for offline, edge-tts for natural online voice.
    """

    def __init__(self):
        self._engine_name = cfg("tts.engine", "pyttsx3")
        self._rate = cfg("tts.rate", 180)
        self._volume = cfg("tts.volume", 0.9)
        self._is_speaking = False
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._engine = None
        self._stop_flag = threading.Event()
        logger.info(f"TTS initialized | engine={self._engine_name}")

    def _init_pyttsx3(self):
        """Initialize pyttsx3 engine."""
        if self._engine is None:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self._rate)
            self._engine.setProperty("volume", self._volume)

            # Try to use a natural-sounding female voice
            voices = self._engine.getProperty("voices")
            female_voice = None
            for v in voices:
                if any(kw in v.name.lower() for kw in ["female", "zira", "hazel", "samantha", "victoria"]):
                    female_voice = v.id
                    break
            if female_voice:
                self._engine.setProperty("voice", female_voice)
                logger.debug(f"TTS voice set to: {female_voice}")

    def speak(self, text: str, interrupt: bool = False):
        """
        Speak text aloud. Runs in background thread.
        interrupt=True stops current speech first.
        """
        if not text or not text.strip():
            return
        if interrupt:
            self.stop()
        self._queue.put(text)
        if self._thread is None or not self._thread.is_alive():
            self._stop_flag.clear()
            self._thread = threading.Thread(target=self._speak_worker, daemon=True)
            self._thread.start()

    def speak_sync(self, text: str):
        """Speak text and block until done."""
        if not text or not text.strip():
            return
        self._speak_text(text)

    def _speak_text(self, text: str):
        """Internal: speak text using configured engine."""
        self._is_speaking = True
        try:
            if self._engine_name == "pyttsx3":
                self._init_pyttsx3()
                self._engine.say(text)
                self._engine.runAndWait()
            else:
                # Fallback to pyttsx3 if edge-tts not available
                self._init_pyttsx3()
                self._engine.say(text)
                self._engine.runAndWait()
        except Exception as e:
            logger.error(f"TTS error: {e}")
        finally:
            self._is_speaking = False

    def _speak_worker(self):
        """Background thread that drains the speech queue."""
        while not self._stop_flag.is_set():
            try:
                text = self._queue.get(timeout=0.5)
                self._speak_text(text)
                self._queue.task_done()
            except queue.Empty:
                break

    def stop(self):
        """Stop current speech immediately."""
        self._stop_flag.set()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        if self._engine and self._engine_name == "pyttsx3":
            try:
                self._engine.stop()
            except Exception:
                pass
        self._is_speaking = False
        logger.debug("TTS stopped")

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking


# ──────────────────────────────────────────────────────────────
# Combined Voice Interface
# ──────────────────────────────────────────────────────────────

class FridayVoice:
    """High-level voice interface combining STT and TTS."""

    def __init__(self):
        self.stt = FridaySTT()
        self.tts = FridayTTS()
        self._on_listening_callbacks: list[Callable] = []
        self._on_done_callbacks: list[Callable] = []

    def on_listening(self, fn: Callable):
        """Register callback when Friday starts listening."""
        self._on_listening_callbacks.append(fn)

    def on_done(self, fn: Callable):
        """Register callback when Friday is done speaking."""
        self._on_done_callbacks.append(fn)

    def listen(self) -> str:
        """Listen for user speech and return transcript."""
        for cb in self._on_listening_callbacks:
            cb()
        text = self.stt.listen_once()
        return text

    def say(self, text: str, interrupt: bool = False):
        """Speak a response."""
        logger.info(f"Friday says: '{text[:60]}...' " if len(text) > 60 else f"Friday says: '{text}'")
        self.tts.speak(text, interrupt=interrupt)

    def say_sync(self, text: str):
        """Speak synchronously (blocks)."""
        logger.info(f"Friday says (sync): '{text[:60]}'" if len(text) > 60 else f"Friday says (sync): '{text}'")
        self.tts.speak_sync(text)

    def stop_speaking(self):
        """Interrupt Friday's current speech."""
        self.tts.stop()

    def greet(self, user_name: str = "sir"):
        """Friday's greeting with user's name."""
        import datetime
        hour = datetime.datetime.now().hour
        if hour < 12:
            time_greeting = "Good morning"
        elif hour < 17:
            time_greeting = "Good afternoon"
        else:
            time_greeting = "Good evening"
        self.say(f"{time_greeting}, {user_name}. Friday online. How can I help?")


# Global singleton
_voice_instance: FridayVoice | None = None


def get_voice() -> FridayVoice:
    """Get or create the global voice instance."""
    global _voice_instance
    if _voice_instance is None:
        _voice_instance = FridayVoice()
    return _voice_instance
