"""
Friday Brain - Dual LLM Engine
-------------------------------
Seamlessly switches between:
  - Ollama  (local, free, offline, fast for quick queries)
  - Claude API (Anthropic, richer reasoning for complex queries)

Smart routing:
  - "auto" mode: short/simple → Ollama, complex/creative → Claude
  - Manual override: force one or the other per call
"""

import asyncio
import time
from enum import Enum
from typing import AsyncGenerator, Generator

from loguru import logger

from config.loader import get as cfg


class BrainMode(str, Enum):
    OLLAMA = "ollama"
    CLAUDE = "claude"
    AUTO = "auto"


# Friday's core system prompt - her personality
FRIDAY_SYSTEM_PROMPT = """You are Friday, an advanced AI personal assistant inspired by Iron Man's Friday.
You are running directly on the user's laptop as a local system daemon.

Personality traits:
- Professional yet warm, like a trusted colleague who knows you well
- Concise and direct - never pad responses with fluff
- Proactive - offer relevant suggestions without being asked
- Witty but not over the top - occasional dry humor is fine
- Adaptive - match the user's energy and formality level

Key rules:
- Keep responses SHORT for voice (under 3 sentences for simple queries)
- For complex topics, use bullet points with short entries
- NEVER say "As an AI" or "I cannot" - just answer or say you'll find out
- Always refer to yourself as "Friday"
- When giving news or facts, cite the source briefly
- If unsure, say so - don't hallucinate

Current context will be injected before this message."""


def _complexity_score(prompt: str) -> float:
    """
    Heuristic to decide if a query needs Claude vs Ollama.
    Returns 0.0 (simple) → 1.0 (complex).
    """
    keywords_complex = [
        "analyze", "explain in detail", "write a", "code", "debug",
        "compare", "pros and cons", "summarize", "translate", "research",
        "draft", "review", "strategy", "plan"
    ]
    prompt_lower = prompt.lower()
    hits = sum(1 for kw in keywords_complex if kw in prompt_lower)
    length_score = min(len(prompt) / 500, 1.0)
    keyword_score = min(hits / 3, 1.0)
    return (length_score + keyword_score) / 2


class FridayBrain:
    """
    The core intelligence of Friday.
    Manages conversation history and routes to the right LLM.
    """

    def __init__(self):
        self._history: list[dict] = []
        self._primary = cfg("brain.primary", "ollama")
        self._ollama_enabled = cfg("brain.ollama.enabled", True)
        self._claude_enabled = cfg("brain.claude.enabled", False)
        self._ollama_host = cfg("brain.ollama.host", "http://localhost:11434")
        self._ollama_model = cfg("brain.ollama.model", "mistral")
        self._claude_model = cfg("brain.claude.model", "claude-haiku-4-5-20251001")
        self._claude_max_tokens = cfg("brain.claude.max_tokens", 1024)
        self._context_summary = ""  # Rolling summary of older history

        logger.info(f"Brain initialized | primary={self._primary} | ollama={self._ollama_enabled} | claude={self._claude_enabled}")

    def _choose_engine(self, prompt: str, force: BrainMode | None = None) -> BrainMode:
        """Decide which engine to use for this prompt."""
        if force:
            return force
        if self._primary == BrainMode.AUTO:
            score = _complexity_score(prompt)
            if score > 0.55 and self._claude_enabled:
                logger.debug(f"Auto routing → Claude (complexity={score:.2f})")
                return BrainMode.CLAUDE
            logger.debug(f"Auto routing → Ollama (complexity={score:.2f})")
            return BrainMode.OLLAMA
        if self._primary == BrainMode.CLAUDE and self._claude_enabled:
            return BrainMode.CLAUDE
        return BrainMode.OLLAMA

    def _build_context(self, extra_context: str = "") -> str:
        """Build context string injected before system prompt."""
        import datetime
        now = datetime.datetime.now()
        parts = [
            f"Current time: {now.strftime('%A, %B %d %Y, %I:%M %p')}",
        ]
        if self._context_summary:
            parts.append(f"Session summary: {self._context_summary}")
        if extra_context:
            parts.append(f"Current context: {extra_context}")
        return "\n".join(parts)

    def _get_system_prompt(self, extra_context: str = "") -> str:
        context = self._build_context(extra_context)
        return f"{context}\n\n{FRIDAY_SYSTEM_PROMPT}"

    def add_to_history(self, role: str, content: str):
        """Add a message to conversation history."""
        self._history.append({"role": role, "content": content})
        max_hist = cfg("memory.max_history", 100)
        summarize_after = cfg("memory.summarize_after", 20)
        if len(self._history) > summarize_after * 2:
            self._trim_history()

    def _trim_history(self):
        """Keep only the last N turns, summarize older ones."""
        keep = cfg("memory.max_history", 100)
        if len(self._history) > keep:
            old = self._history[: len(self._history) - keep]
            self._context_summary = f"[{len(old)} earlier messages summarized]"
            self._history = self._history[-keep:]
            logger.debug("History trimmed and summarized")

    def reset_history(self):
        """Clear conversation history."""
        self._history.clear()
        self._context_summary = ""
        logger.info("Conversation history reset")

    # ──────────────────────────────────────────────────────────
    # Ollama (local)
    # ──────────────────────────────────────────────────────────

    def _query_ollama(self, prompt: str, extra_context: str = "") -> str:
        """Send query to local Ollama and return response."""
        try:
            import ollama
            messages = [{"role": "system", "content": self._get_system_prompt(extra_context)}]
            messages.extend(self._history[-10:])  # Last 10 turns for context
            messages.append({"role": "user", "content": prompt})

            t0 = time.perf_counter()
            response = ollama.chat(
                model=self._ollama_model,
                messages=messages,
            )
            elapsed = time.perf_counter() - t0
            reply = response["message"]["content"].strip()
            logger.info(f"Ollama replied in {elapsed:.2f}s ({len(reply)} chars)")
            return reply
        except Exception as e:
            err_str = str(e).lower()
            logger.error(f"Ollama error: {e}")
            if self._claude_enabled:
                logger.info("Falling back to Claude API...")
                return self._query_claude(prompt, extra_context)
            # Give specific advice based on error type
            if "memory" in err_str or "ram" in err_str:
                return (
                    f"Not enough RAM to run '{self._ollama_model}'. "
                    f"Run: ollama pull tinyllama  then set model: tinyllama in config/settings.yaml"
                )
            if "connection" in err_str or "refused" in err_str or "connect" in err_str:
                return "Ollama isn't running. Open a terminal and run: ollama serve"
            if "not found" in err_str or "no such" in err_str:
                return f"Model '{self._ollama_model}' not downloaded. Run: ollama pull {self._ollama_model}"
            return f"Ollama error: {e}"

    def _stream_ollama(self, prompt: str, extra_context: str = "") -> Generator[str, None, None]:
        """Stream response from Ollama token by token."""
        try:
            import ollama
            messages = [{"role": "system", "content": self._get_system_prompt(extra_context)}]
            messages.extend(self._history[-10:])
            messages.append({"role": "user", "content": prompt})

            stream = ollama.chat(model=self._ollama_model, messages=messages, stream=True)
            for chunk in stream:
                token = chunk["message"]["content"]
                if token:
                    yield token
        except Exception as e:
            logger.error(f"Ollama stream error: {e}")
            yield "Connection to local brain failed."

    # ──────────────────────────────────────────────────────────
    # Claude API
    # ──────────────────────────────────────────────────────────

    def _query_claude(self, prompt: str, extra_context: str = "") -> str:
        """Send query to Claude API and return response."""
        try:
            import anthropic
            import os

            api_key = cfg("brain.claude.api_key") or os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                return "Claude API key not configured. Set ANTHROPIC_API_KEY in .env file."

            client = anthropic.Anthropic(api_key=api_key)

            messages = list(self._history[-10:])
            messages.append({"role": "user", "content": prompt})

            t0 = time.perf_counter()
            response = client.messages.create(
                model=self._claude_model,
                max_tokens=self._claude_max_tokens,
                system=self._get_system_prompt(extra_context),
                messages=messages,
            )
            elapsed = time.perf_counter() - t0
            reply = response.content[0].text.strip()
            logger.info(f"Claude replied in {elapsed:.2f}s ({len(reply)} chars)")
            return reply
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            if self._ollama_enabled:
                logger.info("Falling back to Ollama...")
                return self._query_ollama(prompt, extra_context)
            return f"Sorry, both brains are unavailable right now. Error: {e}"

    def _stream_claude(self, prompt: str, extra_context: str = "") -> Generator[str, None, None]:
        """Stream response from Claude API."""
        try:
            import anthropic
            import os

            api_key = cfg("brain.claude.api_key") or os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                yield "Claude API key not set."
                return

            client = anthropic.Anthropic(api_key=api_key)
            messages = list(self._history[-10:])
            messages.append({"role": "user", "content": prompt})

            with client.messages.stream(
                model=self._claude_model,
                max_tokens=self._claude_max_tokens,
                system=self._get_system_prompt(extra_context),
                messages=messages,
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Claude stream error: {e}")
            yield "Claude connection failed."

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────

    def chat(
        self,
        prompt: str,
        extra_context: str = "",
        force_engine: BrainMode | None = None,
        stream: bool = False,
    ) -> str | Generator[str, None, None]:
        """
        Main interface: send a prompt, get a response.
        Handles history, engine selection, and fallback.
        """
        engine = self._choose_engine(prompt, force=force_engine)

        if stream:
            if engine == BrainMode.CLAUDE and self._claude_enabled:
                gen = self._stream_claude(prompt, extra_context)
            else:
                gen = self._stream_ollama(prompt, extra_context)
            # Record to history after streaming (caller must consume generator)
            self.add_to_history("user", prompt)
            return gen

        # Non-streaming
        self.add_to_history("user", prompt)
        if engine == BrainMode.CLAUDE and self._claude_enabled:
            reply = self._query_claude(prompt, extra_context)
        else:
            reply = self._query_ollama(prompt, extra_context)

        self.add_to_history("assistant", reply)
        return reply

    def quick(self, prompt: str) -> str:
        """
        Force a quick local Ollama response (no history, no context).
        Used for internal tasks like news summarization.
        """
        try:
            import ollama
            response = ollama.chat(
                model=self._ollama_model,
                messages=[
                    {"role": "system", "content": "You are a concise summarizer. Keep all answers under 2 sentences."},
                    {"role": "user", "content": prompt},
                ],
            )
            return response["message"]["content"].strip()
        except Exception as e:
            logger.warning(f"Quick query failed: {e}")
            return ""

    def switch_engine(self, engine: str):
        """Dynamically switch primary engine at runtime."""
        self._primary = engine
        logger.info(f"Brain switched to: {engine}")

    @property
    def engine_status(self) -> dict:
        """Return current engine availability."""
        ollama_ok = False
        try:
            import ollama
            ollama.list()
            ollama_ok = True
        except Exception:
            pass

        claude_ok = bool(cfg("brain.claude.api_key") or __import__("os").environ.get("ANTHROPIC_API_KEY"))

        return {
            "ollama": ollama_ok,
            "claude": claude_ok and self._claude_enabled,
            "primary": self._primary,
        }


# Global singleton
_brain_instance: FridayBrain | None = None


def get_brain() -> FridayBrain:
    """Get or create the global brain instance."""
    global _brain_instance
    if _brain_instance is None:
        _brain_instance = FridayBrain()
    return _brain_instance
