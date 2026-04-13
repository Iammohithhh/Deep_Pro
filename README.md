# 🤖 Friday AI Assistant - Iron Man Inspired Personal AI

> "Your personal AI assistant that lives on your laptop, ready to help with voice commands, screen awareness, and intelligent suggestions."

**Friday** is a next-generation AI assistant inspired by JARVIS/Friday from Iron Man. It combines local offline capability with cloud AI power, wraps you in an intelligent HUD overlay, and understands your screen context to offer proactive help.

## ⭐ Key Features

### 🎤 Voice Interaction
- **Wake Word Detection**: Say "Friday" to activate instantly
- **Offline Speech Recognition**: Uses Faster-Whisper for local STT (no audio sent anywhere)
- **Smart Voice Activity Detection**: Automatically detects when you stop speaking (1.2s silence)
- **Natural Text-to-Speech**: Speaks responses using pyttsx3 (fully offline)

### 🧠 Dual LLM Brain
- **Local Ollama** (free, offline): Tinyllama (600MB) or Phi-3-mini (2.3GB) for fast responses
- **Claude API** (cloud, powerful): Fallback for complex reasoning
- **Smart Routing**: Automatically uses the right engine for each query
- **Conversation Memory**: Remembers context across sessions

### 💾 Long-Term Memory
- **Learns Your Name**: Asks on first run, remembers forever
- **Remembers Facts**: Extracts and stores information you tell it
- **Conversation History**: SQLite database of all chats across sessions
- **Preference Learning**: Detects if you prefer concise or detailed responses
- **Work Tracking**: Monitors work sessions and suggests breaks

### 👀 Screen Awareness
- **Knows What You're Doing**: Monitors active window and detects app type
- **Clipboard Intelligence**: Watches what you copy (code? links? text?)
- **Mood Detection**: Analyzes typing patterns to detect stress/frustration
- **OCR Capability**: Can read text from your screen (with permission)
- **Proactive Help**: Offers help when it detects errors or frustration

### 🎨 Visual Interface
- **Iron Man HUD**: Sleek overlay with news ticker, clock, battery, system stats
- **Animated Avatar**: Cute emoji-based character that pops up when you say "Friday"
- **Status Indicators**: Shows listening, thinking, speaking, sleeping states
- **System Tray**: Quick access menu and minimization

### 📰 News & Weather
- **Morning Briefing**: Wakes you with news and weather on startup
- **Live News Ticker**: BBC, Reuters, Hacker News, TechCrunch feeds
- **Weather Updates**: Free location-based weather (no API key needed)
- **Customizable Sources**: Edit config to choose your news sources

### ⏰ Intelligent Scheduling
- **Time-Aware**: Understands morning vs evening and adjusts tone
- **Break Reminders**: Suggests breaks after 90+ minutes of work
- **Morning Greeting**: Gets you up to speed each day
- **Proactive Suggestions**: Offers help based on detected activity

## 🚀 Getting Started

### Requirements
- **Windows, macOS, or Linux** with Python 3.10+
- **RAM**: 4GB minimum (6GB+ recommended for better models)
- **Microphone**: Any USB mic or built-in will work
- **Internet**: Only needed for Claude API (optional), all else is offline

### Installation

```bash
# Clone the project
cd Deep_Pro
cd friday

# Install dependencies
pip install -r requirements.txt

# (Windows only) Install microphone support
pip install pywin32 pypiwin32 comtypes

# Download AI model (Ollama)
# First, install Ollama from https://ollama.ai
ollama pull phi3:mini  # ~2.3GB, recommended
# OR
ollama pull tinyllama  # ~600MB, for low RAM

# Start Ollama service
ollama serve  # In a separate terminal
```

### First Run

```bash
# Full GUI mode (HUD + voice)
python main.py

# Terminal-only mode (type instead of speaking)
python main.py --cli

# Setup wizard
python main.py --setup

# Get morning briefing
python main.py --briefing

# Check system status
python main.py status
```

### Keyboard Shortcuts
- **Ctrl+Shift+F**: Activate Friday (hotkey, configurable)
- **Ctrl+C**: Clean shutdown (works in any mode)

## 🎯 How to Use

### Basic Voice Commands

**Wake Friday up:**
```
"Hey Friday"
"Friday, are you there?"
"Okay Friday"
```

**Ask questions:**
```
"What's the weather?"
"Show me the news"
"What time is it?"
"How are you?"
"Clear my history"
```

**Coding help:**
```
"Can you explain this code?"
"Why am I getting this error?"
"How do I do X in Python?"
```

**Writing help:**
```
"Proofread this for me"
"Make this more concise"
"What do you think about this?"
```

### Learning Your Name

On first startup, Friday asks: **"Good morning, sir. What shall I call you?"**

- Say your name → Friday remembers it forever
- All future greetings use your name
- Responses address you respectfully

### Teaching Friday Your Preferences

**Response style:**
- "Be concise" → Friday learns you prefer short answers
- "Tell me more" → Friday learns you like detailed responses

**Topics:**
- Mention what you're interested in → Friday tracks topics
- Builds a profile of your interests over time

## ⚙️ Configuration

Edit `friday/config/settings.yaml` to customize:

```yaml
friday:
  name: "Friday"
  personality: "professional"  # or casual, sarcastic, friendly
  voice_gender: "female"
  voice_speed: 1.0

brain:
  primary: "auto"  # auto, ollama, or claude
  ollama:
    model: "phi3:mini"  # tinyllama (600MB) or phi3:mini (2.3GB)

wake_word:
  sensitivity: 0.6  # 0.0-1.0, higher = more sensitive

hud:
  enabled: true
  theme: "iron_man"  # minimal, neon
  position: "top-right"  # or top-left, bottom-right, bottom-left

morning_briefing:
  enabled: true
  time: "09:00"  # When to trigger
  include_top_news: 5  # Number of headlines
```

### Environment Variables

```bash
# Use Claude API (optional)
export ANTHROPIC_API_KEY="sk-..."

# Custom Ollama host
export OLLAMA_HOST="http://localhost:11434"
```

## 📊 What Friday Learns About You

Over time, Friday builds a profile:

- ✅ Your name and location
- ✅ What you work on (coding, writing, design, etc.)
- ✅ Your response preferences (concise vs detailed)
- ✅ Your mood patterns (detects frustration)
- ✅ Your work patterns (when you're productive)
- ✅ Your interests (topics you ask about)

All stored locally in `data/friday_memory.db` — **you own your data**.

## 🔧 Advanced Features

### CLI Mode (Perfect for Testing)

```bash
python main.py --cli
```

Type messages instead of speaking. Great for:
- Testing without microphone
- Debugging responses
- Fast iteration

### Custom Commands

Friday recognizes special commands:

```
"Clear history"          → Clears conversation memory
"Switch to Claude"       → Uses Claude API for next query
"Switch to local"        → Goes back to Ollama
"News briefing"          → Gets morning briefing on demand
"System status"          → Shows what's running
"Break time"             → Ends work session, suggests break
```

### Debug Logging

```bash
python main.py --debug
```

Shows detailed logs in `data/friday.log` and terminal.

## 🎮 Performance Expectations

### Response Times

| Model | RAM | Speed | Quality |
|-------|-----|-------|---------|
| Tinyllama | 600MB | 3-5s | Basic |
| Phi-3-mini | 2.3GB | 3-8s | Good |
| Mistral | 4.5GB | 5-10s | Excellent |
| Claude API | Cloud | 2-3s | Best |

### Audio Quality

- **STT Accuracy**: ~95% for clear speech (depends on background noise)
- **TTS Naturalness**: Moderate (pyttsx3 offline) or Very Natural (edge-tts online)
- **Latency**: <200ms from wake word to acknowledgment (after initial setup)

## 🐛 Troubleshooting

### "Ollama isn't running"
```bash
ollama serve  # Start Ollama in another terminal
```

### "Model not found"
```bash
ollama pull phi3:mini  # Download the model
```

### "No microphone detected"
- Check system sound settings
- Try USB microphone
- Use `--cli` mode for testing without audio

### "Can't hear Friday speaking"
- Check speaker volume
- Check OS volume settings
- Try `python main.py status` to verify TTS engine

### "Wake word too sensitive/insensitive"
Edit `friday/config/settings.yaml`:
```yaml
wake_word:
  sensitivity: 0.6  # Lower = stricter, higher = more sensitive
```

## 🚀 Future Enhancements

Planned features for upcoming versions:

- 🎬 **VRM Avatar**: 3D anime character with lip-sync
- 🗣️ **Natural Voices**: Integration with edge-tts for natural speech
- 🎨 **Custom Themes**: More HUD styles and customization
- 📱 **Mobile Sync**: Friday available on phone
- 🔗 **Integrations**: Slack, Discord, GitHub, Jira
- 🧠 **Semantic Search**: Search memories by meaning, not keywords
- 📈 **Analytics Dashboard**: Personal insights about your work
- 🎓 **Learning Mode**: Friday can learn new tasks and skills

## 📜 License

This project is part of Deep_Pro. See LICENSE file for details.

## 🤝 Contributing

Found a bug? Have a feature idea? PRs welcome!

## 💡 Tips for Best Results

1. **Use headphones**: Better audio quality and isolation
2. **Quiet environment**: Friday hears better without background noise
3. **Clear speech**: Speak naturally and clearly for best recognition
4. **Teach Friday**: Tell it your preferences, it learns over time
5. **Morning briefing**: Read the news while Friday handles interruptions
6. **Regular breaks**: Use Friday's break reminders to stay healthy

## 🎉 Enjoy Your AI Assistant!

Friday is designed to be helpful, not intrusive. It only listens for the wake word or responds to hotkeys. All your data stays local unless you configure Claude API.

Say "Friday, what can you do?" to get started!

---

**Made with ❤️ for productive people who need an intelligent assistant at their fingertips.**
