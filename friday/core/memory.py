"""
Friday Memory System
--------------------
Long-term SQLite-backed memory.
Stores:
  - Conversation history (full turns)
  - User preferences (learned over time)
  - Named facts ("My name is...", "I work at...")
  - Work sessions (time tracking)
  - Mood logs

Friday remembers across reboots and sessions.
"""

import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

from config.loader import get as cfg


DB_PATH = Path(cfg("memory.db_path", "data/friday_memory.db"))


@contextmanager
def _db():
    """Context manager for DB connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"DB error: {e}")
        raise
    finally:
        conn.close()


def init_db():
    """Create all tables on first run."""
    with _db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                engine TEXT DEFAULT 'unknown'
            );

            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS work_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time REAL NOT NULL,
                end_time REAL,
                duration_minutes REAL,
                activity TEXT DEFAULT 'general'
            );

            CREATE TABLE IF NOT EXISTS mood_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                mood TEXT NOT NULL,
                score INTEGER DEFAULT 5,
                notes TEXT DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id);
            CREATE INDEX IF NOT EXISTS idx_conv_time ON conversations(timestamp);
        """)
    logger.info(f"Memory DB initialized: {DB_PATH}")


# ──────────────────────────────────────────────────────────────
# Conversation Memory
# ──────────────────────────────────────────────────────────────

class ConversationMemory:
    """Stores and retrieves conversation history."""

    def __init__(self, session_id: str):
        self._session_id = session_id
        self._max_history = cfg("memory.max_history", 100)

    def save_turn(self, role: str, content: str, engine: str = "unknown"):
        """Save a conversation turn."""
        with _db() as conn:
            conn.execute(
                "INSERT INTO conversations (session_id, timestamp, role, content, engine) VALUES (?, ?, ?, ?, ?)",
                (self._session_id, time.time(), role, content, engine),
            )

    def get_recent(self, n: int | None = None) -> list[dict]:
        """Get the N most recent conversation turns."""
        n = n or self._max_history
        with _db() as conn:
            rows = conn.execute(
                "SELECT role, content, timestamp FROM conversations WHERE session_id=? ORDER BY timestamp DESC LIMIT ?",
                (self._session_id, n),
            ).fetchall()
        return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in reversed(rows)]

    def get_all_sessions(self) -> list[str]:
        """Get all session IDs."""
        with _db() as conn:
            rows = conn.execute(
                "SELECT DISTINCT session_id FROM conversations ORDER BY MIN(timestamp) DESC"
            ).fetchall()
        return [r["session_id"] for r in rows]

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Keyword search in conversation history."""
        with _db() as conn:
            rows = conn.execute(
                "SELECT role, content, timestamp FROM conversations WHERE content LIKE ? ORDER BY timestamp DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def clear_session(self):
        """Delete this session's history."""
        with _db() as conn:
            conn.execute("DELETE FROM conversations WHERE session_id=?", (self._session_id,))
        logger.info(f"Session {self._session_id} cleared")

    def summary_stats(self) -> dict:
        """Return stats about conversation history."""
        with _db() as conn:
            total = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
            sessions = conn.execute("SELECT COUNT(DISTINCT session_id) FROM conversations").fetchone()[0]
            oldest = conn.execute("SELECT MIN(timestamp) FROM conversations").fetchone()[0]
        return {
            "total_turns": total,
            "total_sessions": sessions,
            "oldest": datetime.fromtimestamp(oldest).isoformat() if oldest else None,
        }


# ──────────────────────────────────────────────────────────────
# Facts (Long-term knowledge about the user)
# ──────────────────────────────────────────────────────────────

class FactMemory:
    """
    Stores facts Friday learns about you.
    Examples:
      - "user_name" → "Alex"
      - "user_works_at" → "Anthropic"
      - "user_wakeup_time" → "7:30am"
    """

    def remember(self, key: str, value: Any, confidence: float = 1.0):
        """Store or update a fact."""
        with _db() as conn:
            conn.execute(
                """INSERT INTO facts (key, value, confidence, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, confidence=excluded.confidence, updated_at=excluded.updated_at""",
                (key, json.dumps(value), confidence, time.time()),
            )
        logger.debug(f"Fact stored: {key} = {value}")

    def recall(self, key: str, default: Any = None) -> Any:
        """Retrieve a fact by key."""
        with _db() as conn:
            row = conn.execute("SELECT value FROM facts WHERE key=?", (key,)).fetchone()
        if row:
            return json.loads(row["value"])
        return default

    def forget(self, key: str):
        """Delete a fact."""
        with _db() as conn:
            conn.execute("DELETE FROM facts WHERE key=?", (key,))

    def all_facts(self) -> dict:
        """Get all stored facts."""
        with _db() as conn:
            rows = conn.execute("SELECT key, value FROM facts").fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}

    def extract_from_text(self, text: str):
        """
        Simple rule-based fact extraction from user speech.
        Learns user's name, preferences etc. from conversation.
        """
        import re
        text_lower = text.lower()

        # Name extraction
        name_patterns = [
            r"(?:my name is|i'm|i am|call me)\s+([A-Z][a-z]+)",
            r"([A-Z][a-z]+) here[,\.]",
        ]
        for pattern in name_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                self.remember("user_name", m.group(1), confidence=0.9)
                logger.info(f"Learned user name: {m.group(1)}")
                break

        # Location
        if "i'm in " in text_lower or "i live in " in text_lower:
            m = re.search(r"(?:i'm in|i live in)\s+([A-Z][a-z\s]+)", text, re.IGNORECASE)
            if m:
                self.remember("user_location", m.group(1).strip(), confidence=0.8)


# ──────────────────────────────────────────────────────────────
# Preferences
# ──────────────────────────────────────────────────────────────

class PreferenceMemory:
    """User preferences that Friday learns over time."""

    def set(self, key: str, value: Any):
        with _db() as conn:
            conn.execute(
                """INSERT INTO preferences (key, value, updated_at) VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (key, json.dumps(value), time.time()),
            )

    def get(self, key: str, default: Any = None) -> Any:
        with _db() as conn:
            row = conn.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def all(self) -> dict:
        with _db() as conn:
            rows = conn.execute("SELECT key, value FROM preferences").fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}

    def learn_from_interaction(self, text: str, response_quality: str = "good"):
        """
        Learn preferences from user interactions.
        Track what topics user asks about, preferred response style, etc.
        """
        text_lower = text.lower()

        # Learn response style preferences
        if any(kw in text_lower for kw in ["concise", "short", "brief", "quick", "tl;dr"]):
            self.set("preferred_response_style", "concise")
        elif any(kw in text_lower for kw in ["explain", "detailed", "elaborate", "tell me more"]):
            self.set("preferred_response_style", "detailed")

        # Learn common topics
        topics = self.get("common_topics", [])
        if any(kw in text_lower for kw in ["code", "coding", "python", "javascript", "debug"]):
            if "coding" not in topics:
                topics.append("coding")
        if any(kw in text_lower for kw in ["write", "writing", "article", "doc", "email"]):
            if "writing" not in topics:
                topics.append("writing")
        if any(kw in text_lower for kw in ["data", "analysis", "statistics", "math"]):
            if "data" not in topics:
                topics.append("data")
        if len(topics) > 5:
            topics = topics[-5:]  # Keep only 5 most recent
        self.set("common_topics", topics)

    def get_learning_summary(self) -> str:
        """Get a summary of learned preferences for context."""
        prefs = []
        style = self.get("preferred_response_style")
        if style:
            prefs.append(f"Preferred response style: {style}")
        topics = self.get("common_topics", [])
        if topics:
            prefs.append(f"Interested in: {', '.join(topics)}")
        mood = self.get("user_mood")
        if mood:
            prefs.append(f"Current mood: {mood}")
        return ". ".join(prefs) if prefs else ""


# ──────────────────────────────────────────────────────────────
# Work Session Tracker (for mood & break reminders)
# ──────────────────────────────────────────────────────────────

class WorkSessionTracker:
    """Tracks work sessions for mood intelligence."""

    def __init__(self):
        self._current_start: float | None = None
        self._activity: str = "general"

    def start_session(self, activity: str = "general"):
        self._current_start = time.time()
        self._activity = activity
        with _db() as conn:
            conn.execute(
                "INSERT INTO work_sessions (start_time, activity) VALUES (?, ?)",
                (self._current_start, activity),
            )
        logger.info(f"Work session started: {activity}")

    def end_session(self) -> float:
        """End current session, return duration in minutes."""
        if not self._current_start:
            return 0
        duration = (time.time() - self._current_start) / 60
        with _db() as conn:
            conn.execute(
                "UPDATE work_sessions SET end_time=?, duration_minutes=? WHERE start_time=? AND end_time IS NULL",
                (time.time(), duration, self._current_start),
            )
        self._current_start = None
        logger.info(f"Work session ended: {duration:.1f}m")
        return duration

    @property
    def current_duration_minutes(self) -> float:
        if not self._current_start:
            return 0
        return (time.time() - self._current_start) / 60

    def needs_break(self) -> bool:
        threshold = cfg("mood.break_reminder_minutes", 90)
        return self.current_duration_minutes >= threshold

    def today_stats(self) -> dict:
        today_start = datetime.now().replace(hour=0, minute=0, second=0).timestamp()
        with _db() as conn:
            rows = conn.execute(
                "SELECT SUM(duration_minutes) as total, COUNT(*) as sessions FROM work_sessions WHERE start_time >= ?",
                (today_start,),
            ).fetchone()
        return {
            "total_minutes": rows["total"] or 0,
            "sessions": rows["sessions"] or 0,
        }


# ──────────────────────────────────────────────────────────────
# Unified Memory Interface
# ──────────────────────────────────────────────────────────────

class FridayMemory:
    """Single access point for all memory systems."""

    def __init__(self, session_id: str | None = None):
        import uuid
        self._session_id = session_id or str(uuid.uuid4())[:8]
        init_db()

        self.conversation = ConversationMemory(self._session_id)
        self.facts = FactMemory()
        self.preferences = PreferenceMemory()
        self.work = WorkSessionTracker()

        logger.info(f"Memory initialized | session={self._session_id}")

    @property
    def session_id(self) -> str:
        return self._session_id

    def get_user_name(self) -> str:
        return self.facts.recall("user_name", "there")

    def context_summary(self) -> str:
        """
        Build a short context string for the LLM system prompt.
        Includes key facts Friday knows about the user.
        """
        parts = []
        name = self.facts.recall("user_name")
        if name:
            parts.append(f"User's name: {name}")
        location = self.facts.recall("user_location")
        if location:
            parts.append(f"User is in: {location}")
        work_today = self.work.today_stats()
        if work_today["total_minutes"] > 0:
            parts.append(f"User worked {work_today['total_minutes']:.0f} min today")
        return ". ".join(parts)


# Global singleton
_memory_instance: FridayMemory | None = None


def get_memory() -> FridayMemory:
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = FridayMemory()
    return _memory_instance
