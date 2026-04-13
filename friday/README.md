# ◈ Friday AI Assistant

> One step above every JARVIS project online. An advanced Iron Man-inspired personal AI assistant for your laptop.

## What Makes Friday Different

| Feature | Others | Friday |
|---------|--------|--------|
| Wake word | Needs browser tab | System-level, always listening |
| AI Engine | Cloud only | **Dual: Ollama local + Claude API** |
| Screen awareness | None | Sees your screen, knows what you're doing |
| Clipboard intelligence | None | Offers help when you copy code/text/URLs |
| Mood detection | None | Detects frustration from typing patterns |
| Iron Man HUD | None | Transparent overlay with news ticker |
| Memory | Session only | Long-term SQLite memory |
| Cost | API fees | **FREE** (local Ollama) |

---

## Quick Start

```bash
chmod +x setup.sh && ./setup.sh
source .venv/bin/activate
python main.py
```

---

## Requirements

- Python 3.10+
- [Ollama](https://ollama.ai) (free, local LLM)
- Microphone + speakers
- Linux / macOS / Windows

### Optional
- `ANTHROPIC_API_KEY` in `.env` for Claude API (advanced queries)

---

## Usage

```bash
# Full mode (HUD + voice + wake word)
python main.py

# CLI mode (type instead of speak)
python main.py --cli

# Morning briefing only
python main.py briefing

# Check system status
python main.py status

# First-time setup wizard
python main.py setup
```

---

## How It Works

```
You say "Friday" → Wake word detected
    ↓
Friday listens (Whisper STT)
    ↓
Friday thinks (Ollama local LLM or Claude API)
    ↓
Friday speaks (pyttsx3 TTS)
    ↓
HUD overlay updates with response + news ticker
```

---

## Features

### Voice Activation
Say **"Friday"** anywhere on your laptop. No browser needed. No tab open. Just speaks.

### Dual Brain
- **Ollama** (default): 100% local, free, offline
- **Claude API**: For complex queries (needs API key)
- **Auto mode**: Routes based on query complexity

### Iron Man HUD
Transparent overlay showing:
- Digital clock
- Listening/thinking indicator
- System stats (CPU/RAM/battery)
- Scrolling news ticker
- Friday's responses

### News Briefing
Aggregates from BBC, Reuters, Hacker News, TechCrunch, Ars Technica - no API key needed (RSS).

### Screen Intelligence
Friday knows what app you're using and offers relevant help.

### Clipboard Intelligence
Copy code → Friday offers to explain it. Copy a URL → Friday offers to summarize.

### Memory
Remembers conversations, facts you tell it, your work patterns - across reboots.

---

## Configuration

Edit `config/settings.yaml` or use `.env`:

```yaml
brain:
  primary: "ollama"    # ollama | claude | auto

friday:
  personality: "professional"  # professional | casual | friendly
```

---

## Commands (by voice or CLI)

| Say | Action |
|-----|--------|
| "Friday, what's the news?" | Morning briefing |
| "Friday, what's the weather?" | Weather report |
| "Friday, system status" | Check system |
| "Friday, switch to Claude" | Use Claude API |
| "Friday, switch to local" | Use Ollama |
| "Friday, clear history" | Reset memory |
| "Friday, I'll take a break" | End work session |

---

## Project Structure

```
friday/
├── main.py              # Entry point + CLI
├── core/
│   ├── brain.py         # Dual LLM (Ollama + Claude)
│   ├── ears.py          # Wake word detection
│   ├── voice.py         # STT (Whisper) + TTS
│   ├── eyes.py          # Screen + clipboard + mood
│   ├── memory.py        # Long-term SQLite memory
│   └── orchestrator.py  # Central coordinator
├── features/
│   └── news.py          # News + weather (free APIs)
├── ui/
│   ├── hud.py           # Iron Man HUD overlay
│   └── tray.py          # System tray + auto-startup
└── config/
    ├── settings.yaml    # All configuration
    └── loader.py        # Config loader
```

---

Built with: Python · Faster-Whisper · OpenWakeWord · Ollama · Claude API · PyQt6 · SQLite
