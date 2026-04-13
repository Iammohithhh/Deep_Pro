"""
Friday Orchestrator
-------------------
The central nervous system. Connects all components:
  - Ears (wake word) → triggers listen
  - Voice (STT) → transcribes
  - Brain (LLM) → generates response
  - Memory → stores + retrieves context
  - Eyes → provides ambient context
  - Voice (TTS) → speaks response
  - HUD → displays everything
  - News → feeds ticker + briefings

Also handles:
  - Morning briefing on startup
  - Clipboard suggestions
  - Mood-based responses
  - Break reminders
  - Proactive news suggestions
"""

import threading
import time
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from loguru import logger

from config.loader import get as cfg
from core.brain import get_brain, BrainMode
from core.ears import get_ears, get_state, FridayInteractionState
from core.eyes import get_eyes
from core.memory import get_memory
from core.voice import get_voice
from features.news import get_news, get_weather
from ui.hud import get_hud
from ui.tray import get_tray
from ui.avatar import get_avatar


class FridayOrchestrator:
    """
    The heart of Friday.
    Wires all systems together into a coherent experience.
    """

    def __init__(self):
        # Core components
        self.brain = get_brain()
        self.ears = get_ears()
        self.voice = get_voice()
        self.memory = get_memory()
        self.eyes = get_eyes()
        self.news = get_news()
        self.weather = get_weather()
        self.hud = get_hud()
        self.tray = get_tray()
        self.avatar = get_avatar()
        self.state = get_state()

        # Scheduler for periodic tasks
        self.scheduler = BackgroundScheduler(daemon=True)

        # Flags
        self._running = False
        self._last_clipboard_suggestion = 0
        self._last_proactive = 0

        logger.info("Friday Orchestrator initialized")

    def _setup_callbacks(self):
        """Wire all event callbacks together."""

        # Wake word → start listening
        self.ears.on_wake(self._on_wake)

        # State transitions → HUD updates
        self.state.on(FridayInteractionState.LISTENING, lambda: self.hud.set_state("listening"))
        self.state.on(FridayInteractionState.THINKING, lambda: self.hud.set_state("thinking"))
        self.state.on(FridayInteractionState.SPEAKING, lambda: self.hud.set_state("speaking"))
        self.state.on(FridayInteractionState.SLEEPING, lambda: self.hud.set_state("sleeping"))

        # State transitions → tray updates
        self.state.on(FridayInteractionState.LISTENING, lambda: self.tray.update_state("listening"))
        self.state.on(FridayInteractionState.SLEEPING, lambda: self.tray.update_state("sleeping"))

        # State transitions → Avatar animations (if available)
        if self.avatar:
            self.state.on(FridayInteractionState.LISTENING, self.avatar.controller.activated.emit)
            self.state.on(FridayInteractionState.THINKING, self.avatar.controller.thinking.emit)
            self.state.on(FridayInteractionState.SPEAKING, self.avatar.controller.speaking.emit)
            self.state.on(FridayInteractionState.SLEEPING, self.avatar.controller.idle.emit)

        # Screen context changes → proactive help
        self.eyes.screen.on_context_change(self._on_app_change)

        # Clipboard changes → smart suggestions
        self.eyes.clipboard.on_copy(self._on_clipboard_copy)

        # Mood changes → adjust responses
        self.eyes.mood.on_mood_change(self._on_mood_change)

        # Tray menu actions
        self.tray.on("activate", self._on_wake)
        self.tray.on("news_briefing", self._do_morning_briefing)
        self.tray.on("toggle_hud", self._toggle_hud)
        self.tray.on("quit", self.shutdown)

    def _setup_scheduler(self):
        """Set up periodic background tasks."""

        # News refresh every 30 minutes
        self.scheduler.add_job(
            self._refresh_news_ticker,
            "interval",
            minutes=cfg("news.refresh_interval_minutes", 30),
            id="news_refresh",
        )

        # Break reminder check every 5 minutes
        self.scheduler.add_job(
            self._check_break_reminder,
            "interval",
            minutes=5,
            id="break_check",
        )

        # Proactive suggestion every hour
        self.scheduler.add_job(
            self._proactive_check,
            "interval",
            minutes=60,
            id="proactive",
        )

        # Morning briefing at configured time
        briefing_time = cfg("morning_briefing.time", "09:00")
        hour, minute = map(int, briefing_time.split(":"))
        self.scheduler.add_job(
            self._do_morning_briefing,
            "cron",
            hour=hour,
            minute=minute,
            id="morning_briefing",
        )

        # Update weather in HUD every hour
        self.scheduler.add_job(
            self._update_weather_display,
            "interval",
            minutes=60,
            id="weather_update",
        )

    # ──────────────────────────────────────────────────────────
    # Main Interaction Loop
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _strip_wake_words(text: str) -> str:
        """Remove wake word artifacts from transcript."""
        import re
        # Remove leading "friday", "hey friday", "okay friday", etc.
        cleaned = re.sub(
            r'^(?:hey\s+|okay?\s+|yo\s+)?friday[,!.\s]*',
            '', text, flags=re.IGNORECASE
        ).strip()
        return cleaned

    def _on_wake(self):
        """Triggered when wake word 'Friday' is detected."""
        if not self.state.is_sleeping:
            return  # Already active

        logger.info("Friday activated by wake word")
        self.state.transition(FridayInteractionState.LISTENING)

        # Play a short confirmation response with user's name
        user_name = self.memory.get_user_name()
        acknowledgment = f"Yes, {user_name}?" if user_name != "there" else "At your service, sir?"
        self.voice.say_sync(acknowledgment)

        # Now listen for the actual command
        text = self.voice.listen()
        text = self._strip_wake_words(text) if text else ""

        if not text or len(text.strip()) < 2:
            self.state.transition(FridayInteractionState.SLEEPING)
            return

        self._process_query(text)

    @staticmethod
    def _truncate_for_voice(text: str, max_sentences: int = 3) -> str:
        """Truncate response for voice output — keep first N sentences, improve naturalness."""
        import re
        # Remove markdown formatting for speech
        text = text.replace("**", "").replace("__", "").replace("`", "").replace("```", "")

        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())

        # Filter out headers, code blocks, bullet lists
        spoken = [
            s for s in sentences
            if not any(s.startswith(prefix) for prefix in ['#', '- ', '* ', '| ', '> ', '```'])
        ]

        # Use markdown sentences if we filtered too much
        if not spoken or len(spoken) < 2:
            spoken = sentences

        # Combine first N sentences, add period if missing
        result = " ".join(spoken[:max_sentences]).strip()
        if result and not result.endswith(('.', '!', '?')):
            result += "."

        # Limit to reasonable length for TTS
        if len(result) > 400:
            result = result[:397] + "..."

        return result

    def _process_query(self, text: str):
        """Process a user query end-to-end."""
        logger.info(f"Processing query: '{text}'")

        # Check for special commands first
        if self._handle_command(text):
            self.state.transition(FridayInteractionState.SLEEPING)
            return

        # Extract any facts from the query
        self.memory.facts.extract_from_text(text)

        # Learn from user interaction
        self.memory.preferences.learn_from_interaction(text)

        # Build ambient context
        screen_context = self.eyes.full_context()
        user_context = self.memory.context_summary()
        learning_summary = self.memory.preferences.get_learning_summary()
        combined_context = ". ".join(filter(None, [user_context, screen_context, learning_summary]))

        # Generate response
        self.state.transition(FridayInteractionState.THINKING)
        response = self.brain.chat(text, extra_context=combined_context)

        # Save to memory
        self.memory.conversation.save_turn("user", text)
        self.memory.conversation.save_turn("assistant", response)

        # Respond — truncate for voice (first 3 sentences max)
        spoken_text = self._truncate_for_voice(response)
        self.state.transition(FridayInteractionState.SPEAKING)
        self.hud.set_speech(response)  # Show full text on HUD
        self.voice.say_sync(spoken_text)  # Speak truncated version, BLOCK until done

        self.state.transition(FridayInteractionState.SLEEPING)

    def _handle_command(self, text: str) -> bool:
        """
        Handle built-in commands without going to LLM.
        Returns True if command was handled.
        """
        text_lower = text.lower().strip()

        # News briefing
        if any(kw in text_lower for kw in ["news", "briefing", "headlines", "what's happening"]):
            self._do_morning_briefing()
            return True

        # Weather
        if any(kw in text_lower for kw in ["weather", "temperature", "forecast"]):
            self.state.transition(FridayInteractionState.THINKING)
            weather_text = self.weather.spoken()
            self.state.transition(FridayInteractionState.SPEAKING)
            self.voice.say(weather_text)
            self.hud.set_speech(weather_text)
            return True

        # Status
        if any(kw in text_lower for kw in ["system status", "how are you", "status"]):
            status = self.brain.engine_status
            engine_txt = "Ollama" if status["ollama"] else "Claude API"
            msg = f"All systems operational. Running on {engine_txt}. Session started this session."
            self.state.transition(FridayInteractionState.SPEAKING)
            self.voice.say(msg)
            self.hud.set_speech(msg)
            return True

        # Clear / reset
        if any(kw in text_lower for kw in ["clear history", "forget everything", "reset"]):
            self.memory.conversation.clear_session()
            self.brain.reset_history()
            response = "Memory cleared. Starting fresh."
            self.voice.say(response)
            self.hud.set_speech(response)
            return True

        # Switch brain
        if "switch to claude" in text_lower or "use claude" in text_lower:
            self.brain.switch_engine("claude")
            self.voice.say("Switched to Claude API mode.")
            return True
        if "switch to local" in text_lower or "use ollama" in text_lower or "go offline" in text_lower:
            self.brain.switch_engine("ollama")
            self.voice.say("Switched to local Ollama mode.")
            return True

        # Break reminder dismiss
        if any(kw in text_lower for kw in ["i'll take a break", "break time", "stopping now"]):
            self.memory.work.end_session()
            self.voice.say("Enjoy your break. I'll be here when you're back.")
            return True

        return False

    # ──────────────────────────────────────────────────────────
    # Ambient Intelligence Callbacks
    # ──────────────────────────────────────────────────────────

    def _on_app_change(self, category: str, window_title: str):
        """React to user switching apps."""
        suggestions = {
            "coding": None,  # Don't interrupt coding sessions
            "writing": None,
            "video": "Looks like you're watching something. I'll stay quiet.",
            "browsing": None,
        }
        # Only notify for significant changes, not every switch
        logger.debug(f"App changed to: {category}")

    def _on_clipboard_copy(self, content: str, content_type: str):
        """React to clipboard content."""
        now = time.time()
        # Don't suggest too frequently (at least 30 seconds between suggestions)
        if now - self._last_clipboard_suggestion < 30:
            return
        if not cfg("clipboard.auto_suggest", True):
            return

        self._last_clipboard_suggestion = now

        suggestions = {
            "url": "I see you copied a link. Want me to summarize what's there?",
            "code": "I noticed some code in your clipboard. Want me to explain or review it?",
            "math": "Looks like a math expression. Want me to calculate or explain it?",
            "paragraph": "You copied some text. Want a quick summary or translation?",
        }
        msg = suggestions.get(content_type)
        if msg and self.state.is_sleeping:
            self.tray.notify("Friday", msg)
            # Don't voice-speak unless activated - that would be intrusive
            self.hud.set_speech(f"[Clipboard] {msg}")

    def _on_mood_change(self, mood: str):
        """Adapt Friday's behavior based on detected user mood."""
        if mood == "frustrated":
            logger.info("User appears frustrated - Friday will be more concise and supportive")
            # Just update internal state - affects next response automatically
            self.memory.preferences.set("user_mood", mood)
        elif mood == "focused":
            self.memory.preferences.set("user_mood", mood)

    # ──────────────────────────────────────────────────────────
    # Scheduled Tasks
    # ──────────────────────────────────────────────────────────

    def _do_morning_briefing(self):
        """Speak a morning briefing with news + weather."""
        logger.info("Starting morning briefing")
        self.state.transition(FridayInteractionState.SPEAKING)

        # Weather
        weather_spoken = self.weather.spoken()

        # News
        n_items = cfg("morning_briefing.include_top_news", 5)
        briefing = self.news.morning_briefing_text(n=n_items)

        full_briefing = f"{weather_spoken} {briefing}"
        self.hud.set_speech("Morning Briefing - listen for news headlines...")
        self.voice.say_sync(full_briefing)

        self.state.transition(FridayInteractionState.SLEEPING)

    def _refresh_news_ticker(self):
        """Refresh news and update HUD ticker."""
        try:
            ticker = self.news.get_ticker_text()
            self.hud.set_news_ticker(ticker)
            logger.debug("News ticker updated")
        except Exception as e:
            logger.warning(f"News ticker refresh failed: {e}")

    def _update_weather_display(self):
        """Update weather in HUD."""
        try:
            w = self.weather.get()
            weather_text = f"{w['city']}: {w['temp_c']}°C, {w['condition']}"
            self.hud.set_weather(weather_text)
        except Exception as e:
            logger.warning(f"Weather update failed: {e}")

    def _check_break_reminder(self):
        """Check if user needs a break."""
        if self.memory.work.needs_break() and self.state.is_sleeping:
            duration = self.memory.work.current_duration_minutes
            msg = f"You've been working for {duration:.0f} minutes. Consider taking a short break."
            self.tray.notify("Friday - Break Reminder", msg)
            self.hud.set_speech(f"Break reminder: {duration:.0f} min session. Rest your eyes!")
            logger.info(f"Break reminder sent after {duration:.0f}m")

    def _proactive_check(self):
        """Periodically offer proactive help based on activity and mood."""
        if not self.state.is_sleeping:
            return  # Only when Friday is idle

        # Check if user appears frustrated (mood detection)
        mood = self.memory.preferences.get("user_mood")
        if mood == "frustrated":
            suggestions = [
                "I notice you might be dealing with something tricky. Want some help?",
                "Looks like you could use a hand. What can I do?",
                "I'm here if you need assistance with anything.",
            ]
            import random
            msg = random.choice(suggestions)
            self.tray.notify("Friday - Proactive Help", msg)
            self.hud.set_speech(f"[Proactive] {msg}")
            logger.info("Proactive help offered for frustrated user")
            return

        # Check screen context for opportunities to help
        screen_context = self.eyes.full_context()
        if not screen_context:
            return

        # Detect if user is coding and might have issues
        if any(kw in screen_context.lower() for kw in ["error", "exception", "syntax", "traceback", "debug"]):
            msg = "I see an error in your code. Want me to take a look?"
            self.tray.notify("Friday - Code Help", msg)
            self.hud.set_speech(f"[Proactive] {msg}")
            logger.info("Proactive code help offered")
            return

        # Detect long work sessions and suggest breaks
        work_duration = self.memory.work.current_duration_minutes
        if work_duration > 120 and not self.memory.preferences.get("break_offered_today"):
            msg = f"You've been working for {work_duration:.0f} minutes. How about a quick break?"
            self.tray.notify("Friday - Break Reminder", msg)
            self.hud.set_speech(f"[Proactive] {msg}")
            self.memory.preferences.set("break_offered_today", True)
            logger.info("Proactive break suggestion offered")

    def _toggle_hud(self):
        """Show/hide HUD overlay."""
        if self.hud.available:
            widget = self.hud._widget
            if widget:
                if widget.isVisible():
                    widget.hide()
                else:
                    widget.show()

    # ──────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────

    def start(self):
        """
        Start all Friday background systems.
        NOTE: HUD must be initialized BEFORE calling start() via
        hud.init_in_main_thread() in main.py — Qt requires the main thread.
        """
        logger.info("Starting Friday AI Assistant...")
        self._running = True

        # HUD is already initialized by main.py in the main thread.
        # Only start tray here (it uses its own thread safely).
        self.tray.start()

        # Wire callbacks
        self._setup_callbacks()

        # Initial news + weather load
        threading.Thread(target=self._initial_data_load, daemon=True).start()

        # Start ambient intelligence
        self.eyes.start_all()

        # Start wake word listener
        self.ears.start()

        # Start work session
        self.memory.work.start_session()

        # Start scheduler
        self._setup_scheduler()
        self.scheduler.start()

        # Startup greeting
        if cfg("morning_briefing.auto_on_startup", True):
            threading.Thread(target=self._startup_sequence, daemon=True).start()

        logger.info("Friday is ONLINE.")

    def _initial_data_load(self):
        """Load news and weather on startup in background."""
        try:
            time.sleep(2)  # Let UI initialize
            ticker = self.news.get_ticker_text()
            self.hud.set_news_ticker(ticker)

            w = self.weather.get()
            weather_text = f"{w['city']}: {w['temp_c']}°C, {w['condition']}"
            self.hud.set_weather(weather_text)
            logger.info("Initial data loaded")
        except Exception as e:
            logger.warning(f"Initial data load failed: {e}")

    def _startup_sequence(self):
        """Startup greeting sequence with name learning."""
        time.sleep(3)  # Wait for everything to initialize
        user_name = self.memory.get_user_name()

        # If we don't know the user's name, ask for it
        if user_name == "there":
            self.state.transition(FridayInteractionState.SPEAKING)
            greeting = "Good morning, sir. I am Friday. What shall I call you?"
            self.hud.set_speech(greeting)
            self.voice.say_sync(greeting)

            # Listen for name
            self.state.transition(FridayInteractionState.LISTENING)
            response = self.voice.listen()
            if response and len(response.strip()) > 1:
                # Extract name from response
                self.memory.facts.extract_from_text(f"Call me {response}")
                user_name = self.memory.get_user_name()
                reply = f"Pleasure to meet you, {user_name}. I will remember that."
                self.voice.say_sync(reply)
                self.hud.set_speech(reply)
            self.state.transition(FridayInteractionState.SLEEPING)

        # Standard greeting with user's name
        hour = __import__("datetime").datetime.now().hour
        if hour < 12:
            time_greeting = "Good morning"
        elif hour < 17:
            time_greeting = "Good afternoon"
        else:
            time_greeting = "Good evening"

        greeting = f"{time_greeting}, {user_name}. Friday is online."
        self.state.transition(FridayInteractionState.SPEAKING)
        self.hud.set_speech(greeting)
        self.voice.say_sync(greeting)
        self.state.transition(FridayInteractionState.SLEEPING)

    def run_forever(self):
        """Block and run the event loop."""
        try:
            logger.info("Friday running. Press Ctrl+C to quit.")
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.shutdown()

    def shutdown(self):
        """Gracefully shut down all systems."""
        logger.info("Friday shutting down...")
        self._running = False

        self.voice.say_sync("Shutting down. Goodbye.")
        self.memory.work.end_session()

        self.scheduler.shutdown(wait=False)
        self.ears.stop()
        self.eyes.stop_all()
        self.hud.stop()
        if self.avatar:
            self.avatar.stop()
        self.tray.stop()

        logger.info("Friday offline.")
