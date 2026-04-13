# Live2D Integration Plan - Phase 2B (Weekend Work)

Based on research of 6,800+ GitHub projects and current state-of-the-art solutions, this document outlines the technical plan to integrate a professional Live2D anime avatar with real-time lip-sync.

## Overview

**Goal:** Replace emoji/PNG avatar with a smooth, professional Live2D character that:
- Animates in real-time with lip-sync
- Responds to interaction states (thinking, speaking, listening)
- Has natural breathing/idle animations
- Feels like talking to a real AI assistant

**Timeline:** 3-4 hours of development (Friday evening/Saturday morning)

---

## Recommended Stack

### 1. Avatar System: `live2d-py` (Official Python SDK)

**Why:** Native Python bindings, zero configuration, official support from Live2D

```
Package: live2d-py
PyPI: pip install live2d-py
GitHub: EasyLive2D/live2d-py
Status: Production-ready, actively maintained
Python Support: 3.8+
```

#### Installation

```bash
# Easiest - pre-built wheel
pip install live2d-py

# Or from source (requires C++ 17 compiler)
git clone https://github.com/EasyLive2D/live2d-py.git
cd live2d-py
cmake -B build && cmake --build build
pip install ./dist/*.whl
```

#### Key Capabilities

- ✅ Load Live2D Cubism 3.0+ models (.model3.json)
- ✅ Real-time parameter manipulation (facial expressions, mouth, eyes)
- ✅ Built-in lip-sync support with audio
- ✅ Motion playback (animations like "idle", "talk", "smile")
- ✅ Eye tracking / gaze animation
- ✅ Click detection for interactive UI

---

### 2. Avatar Character: VRoid Studio Export + Live2D Rigging

**Why:** Free to create, anime-style (matches user's aesthetic), proven workflow

**Process:**

```
VRoid Studio (Create/Customize) 
    ↓
    Export → FBX/VRM
    ↓
    Blender (Import + rig for Live2D)
    ↓
    Live2D Cubism Editor (Build 2D rig)
    ↓
    Export → model3.json (ready for live2d-py)
```

**Alternative (Faster):** Use pre-made Live2D models:
- [live2d.com/en/download/sample-model](https://live2d.com/en/download/sample-model/)
- [GitHub: Live2D Sample Models](https://github.com/live2d/sample_model)

---

### 3. Text-to-Speech with Viseme: HeadTTS

**Why:** Free, generates mouth shape data alongside audio, real-time capable

```
Package: python-head-tts (or headtts)
Status: New (2024) but very effective
Output: Audio + viseme timing data
```

#### Integration Flow

```
Text Input
    ↓
    HeadTTS.generate(text)
    ↓
    ├─→ audio_data (WAV/MP3)
    └─→ viseme_data [{phoneme, start_ms, end_ms}, ...]
    ↓
    Lip Sync Mapper (phoneme → Live2D mouth parameters)
    ↓
    live2d-py renders with animated mouth
```

---

## Implementation Steps

### Step 1: Set Up Environment

**Time:** 15-20 minutes

```bash
cd Deep_Pro

# Install dependencies
pip install live2d-py head-tts pygame  # pygame for rendering

# Or add to requirements.txt:
# live2d-py>=0.3.0
# head-tts>=0.1.0
# pygame>=2.1.0
```

#### Test Installation

```python
import live2d_py
from headtts import HeadTTS

print("✓ live2d-py available")
print("✓ HeadTTS available")
```

---

### Step 2: Create Avatar Loader Module

**Time:** 30-40 minutes

**File:** `friday/ui/live2d_avatar.py`

```python
"""Live2D Avatar Renderer"""

import time
from pathlib import Path
from typing import Optional

import live2d_py
from loguru import logger


class Live2DAvatar:
    """
    Live2D-based animated avatar with lip-sync support.
    """

    def __init__(self, model_path: str):
        """
        Initialize Live2D avatar.
        
        Args:
            model_path: Path to model3.json file
                Example: "assets/avatar/model.model3.json"
        """
        self.model_path = Path(model_path)
        self.model = None
        self.motion_manager = None
        self._load_model()

        # Lip-sync parameters
        self._mouth_open_param = None
        self._mouth_form_param = None
        self._init_mouth_parameters()

        logger.info(f"Live2D Avatar loaded: {model_path}")

    def _load_model(self):
        """Load Live2D model from file."""
        try:
            self.model = live2d_py.cubism.Model.from_file(str(self.model_path))
            logger.info(f"Model loaded: {self.model_path.name}")
        except Exception as e:
            logger.error(f"Failed to load Live2D model: {e}")
            self.model = None

    def _init_mouth_parameters(self):
        """Initialize mouth animation parameters."""
        if not self.model:
            return

        # Common Live2D mouth parameter names
        mouth_params = [
            "ParamMouthOpenY",  # Mouth open/close
            "ParamMouthForm",   # Mouth shape (A/I/U/E/O)
        ]

        for param_name in mouth_params:
            try:
                param = self.model.get_parameter(param_name)
                if param:
                    if "Open" in param_name:
                        self._mouth_open_param = param
                    elif "Form" in param_name:
                        self._mouth_form_param = param
            except Exception:
                pass

        logger.debug(f"Mouth parameters initialized: "
                    f"open={self._mouth_open_param is not None}, "
                    f"form={self._mouth_form_param is not None}")

    def update_mouth_from_viseme(self, viseme_code: int, blend: float = 1.0):
        """
        Update mouth shape based on viseme code.
        
        Viseme codes (SAPI standard):
        0: Silence, 1: AE, 2: AA, 3: IY, 4: EH, 5: AH,
        6: OW, 7: UW, 8: ER, 9: AX, 10: S, 11: Z, 12: SH, etc.
        
        Map to mouth shapes:
        A(1,2,5), E(4), I(3), O(6,7), U(7)
        """
        if not self._mouth_form_param:
            return

        # Simplified viseme → mouth open/shape mapping
        viseme_map = {
            0: 0.0,     # Silence
            1: 0.3,     # AE → 30% open
            2: 0.5,     # AA → 50% open (wide)
            3: 0.2,     # IY → 20% open
            4: 0.25,    # EH → 25% open
            5: 0.4,     # AH → 40% open
            6: 0.6,     # OW → 60% open
            7: 0.7,     # UW → 70% open
            8: 0.35,    # ER → 35% open
            9: 0.3,     # AX → 30% open
            10: 0.1,    # S → 10% open
            11: 0.1,    # Z → 10% open
            12: 0.15,   # SH → 15% open
        }

        mouth_open = viseme_map.get(viseme_code, 0.0) * blend

        try:
            self._mouth_open_param.value = mouth_open
            if self._mouth_form_param:
                self._mouth_form_param.value = viseme_code / 32.0  # Normalize
        except Exception as e:
            logger.warning(f"Failed to set mouth viseme {viseme_code}: {e}")

    def render_frame(self) -> Optional[bytes]:
        """
        Render current frame and return as image bytes.
        Returns None if model not loaded.
        """
        if not self.model:
            return None

        try:
            # Update model physics
            self.model.update()

            # Render to texture (implementation depends on rendering backend)
            # This would integrate with PyQt6 or pygame for display
            return self.model.draw()
        except Exception as e:
            logger.error(f"Render error: {e}")
            return None

    def set_expression(self, expression_name: str):
        """Set avatar facial expression."""
        if not self.model:
            return

        try:
            self.model.set_expression(expression_name)
            logger.debug(f"Expression set: {expression_name}")
        except Exception as e:
            logger.warning(f"Failed to set expression {expression_name}: {e}")

    def play_motion(self, motion_name: str, priority: int = 0):
        """Play a motion animation."""
        if not self.model:
            return

        try:
            self.model.play_motion(motion_name, priority=priority)
            logger.debug(f"Motion started: {motion_name}")
        except Exception as e:
            logger.warning(f"Failed to play motion {motion_name}: {e}")

    def stop(self):
        """Clean up resources."""
        if self.model:
            self.model.destroy()
            self.model = None
        logger.info("Live2D Avatar stopped")
```

---

### Step 3: Integrate Lip-Sync with HeadTTS

**Time:** 20-30 minutes

**File:** `friday/core/tts_lipsync.py`

```python
"""TTS with Live2D Lip-Sync Integration"""

from typing import Iterator, Tuple
import wave
import io


class LipSyncTTS:
    """
    Text-to-Speech with real-time viseme data for avatar mouth animation.
    """

    def __init__(self):
        try:
            from headtts import HeadTTS
            self.engine = HeadTTS()
            self.available = True
        except ImportError:
            self.available = False
            logger.warning("HeadTTS not available — lip-sync disabled")

    def generate_with_visemes(self, text: str) -> Tuple[bytes, list]:
        """
        Generate speech and return (audio_bytes, viseme_data).
        
        Returns:
            audio_bytes: WAV audio data
            visemes: [{time_ms, viseme_code, duration_ms}, ...]
        """
        if not self.available:
            return None, []

        try:
            result = self.engine.generate(text)

            # HeadTTS returns:
            # result['audio']: WAV bytes
            # result['visemes']: List of viseme events

            audio = result.get('audio', b'')
            visemes = result.get('visemes', [])

            logger.info(f"Generated speech: {len(audio)} bytes, "
                       f"{len(visemes)} viseme events")

            return audio, visemes

        except Exception as e:
            logger.error(f"HeadTTS generation failed: {e}")
            return None, []

    def stream_with_visemes(self, text: str) -> Iterator[Tuple[bytes, int]]:
        """
        Stream speech audio in chunks with corresponding viseme codes.
        
        Yields:
            (audio_chunk, viseme_code)
        """
        audio, visemes = self.generate_with_visemes(text)
        if not audio:
            return

        # Simple streaming: chunk audio + sync with viseme timing
        chunk_size = 1024
        for i in range(0, len(audio), chunk_size):
            chunk = audio[i : i + chunk_size]

            # Find corresponding viseme
            current_time_ms = (i // 2) * 1000 / 16000  # Convert to ms @ 16kHz

            viseme_code = self._find_viseme_at_time(current_time_ms, visemes)
            yield chunk, viseme_code

    @staticmethod
    def _find_viseme_at_time(time_ms: float, visemes: list) -> int:
        """Find viseme code at specific time."""
        for viseme in visemes:
            start = viseme.get('start_ms', 0)
            end = viseme.get('end_ms', 0)
            if start <= time_ms <= end:
                return viseme.get('viseme_code', 0)
        return 0  # Silence


# Global instance
_tts_lipsync_instance = None


def get_tts_lipsync() -> LipSyncTTS:
    """Get or create TTS with lip-sync."""
    global _tts_lipsync_instance
    if _tts_lipsync_instance is None:
        _tts_lipsync_instance = LipSyncTTS()
    return _tts_lipsync_instance
```

---

### Step 4: Integrate Live2D into Orchestrator

**Time:** 30-40 minutes

**Modify:** `friday/core/orchestrator.py`

Add to `_handle_streaming_response()`:

```python
def _handle_streaming_response(self, text: str, extra_context: str = ""):
    """Stream response token-by-token with Live2D avatar mouth sync."""
    self.state.transition(FridayInteractionState.SPEAKING)

    # Get streaming generator
    token_stream = self.brain.chat(text, extra_context=extra_context, stream=True)

    # Get TTS with lip-sync
    from core.tts_lipsync import get_tts_lipsync
    lipsync = get_tts_lipsync()

    full_response = ""
    spoken_buffer = ""

    try:
        for token in token_stream:
            full_response += token
            spoken_buffer += token

            self.hud.set_speech(full_response)

            # Trigger avatar animations
            if self.avatar and self.avatar.available:
                self.avatar.controller.speaking.emit()

            # Stream with mouth animation
            if len(spoken_buffer) > 50:
                audio, visemes = lipsync.generate_with_visemes(spoken_buffer)
                if audio and self.avatar:
                    # Play audio with live2d mouth sync
                    for chunk, viseme_code in lipsync.stream_with_visemes(spoken_buffer):
                        # Update avatar mouth in real-time
                        try:
                            self.avatar_renderer.update_mouth_from_viseme(viseme_code)
                        except Exception:
                            pass
                        self.voice.play_audio_chunk(chunk)

                spoken_buffer = ""

    except Exception as e:
        logger.error(f"Streaming error: {e}")
        full_response = f"I encountered an error: {e}"

    if spoken_buffer.strip():
        audio, visemes = lipsync.generate_with_visemes(spoken_buffer)
        if audio:
            self.voice.play_audio_sync(audio)

    self.memory.conversation.save_turn("assistant", full_response)
```

---

### Step 5: Test & Iterate

**Time:** 20-30 minutes

```bash
# Test import
python -c "import live2d_py; print('✓ live2d-py installed')"

# Test with sample model
python friday/core/orchestrator.py --test-live2d

# Check logs for avatar loading
tail -f data/friday.log | grep -i "live2d\|avatar"
```

---

## Model Resources

### Pre-Made Live2D Models

1. **Official Samples** (Free)
   - https://live2d.com/en/download/sample-model/
   - Multiple anime character models ready to use
   - Includes idle, smile, sad animations

2. **Community Models** (GitHub)
   - Nanami Amakaze (anime girl)
   - Tororo (cute character)
   - Search: "live2d model free" on GitHub

### Create Custom Model

1. **VRoid Studio** (Free, anime)
   - https://vroid.com/en/studio
   - Create anime character
   - Export → Blender + Live2D pipeline

2. **Blender** (Free, professional)
   - Import VRM/FBX from VRoid
   - Rig for Live2D
   - Export model3.json

---

## Estimated Complexity

```
Component              | Complexity | Time
─────────────────────────────────────────
live2d-py setup        | Low        | 15m
Model acquisition      | Low        | 15m  
Avatar loader          | Medium     | 40m
Viseme mapping         | Medium     | 30m
Orchestrator integration | Medium   | 40m
Testing & debugging    | Low        | 20m
─────────────────────────────────────────
TOTAL                                  2.5 hours
```

---

## Success Criteria

✅ Avatar appears on screen with smooth animations
✅ Mouth moves during speech (lip-sync)  
✅ Avatar transitions between idle/thinking/speaking
✅ First audio output within 200-400ms (streaming)
✅ No performance degradation (30+ FPS avatar)
✅ Works offline with local models

---

## Fallback Plan

If Live2D proves too complex:

1. **Upgrade emoji avatar** with larger size + better animations
2. **Use PNG sequences** for professional look (simpler than Live2D)
3. **Simple viseme animation** with emoji mouth shapes
4. **Retry Live2D** after more research

---

## Weekend Roadmap

```
Friday Evening (2 hours):
├─ Install live2d-py + dependencies
├─ Create avatar loader module
└─ Download sample Live2D model

Saturday Morning (2 hours):
├─ Integrate lip-sync TTS
├─ Update orchestrator for Live2D
├─ Test end-to-end
└─ Fix bugs & polish

Saturday Evening (1 hour):
├─ Create custom avatar (optional)
├─ Fine-tune mouth animation
└─ Make production-ready
```

---

## Resources & References

- **Live2D SDK:** https://docs.live2d.com/en/cubism-sdk-manual/top/
- **live2d-py Docs:** https://github.com/EasyLive2D/live2d-py/wiki
- **HeadTTS:** https://github.com/ZyqGitHub1/HeadTTS
- **Rhubarb Lip-Sync:** https://github.com/DanielSWolf/rhubarb-lip-sync (alternative)

---

## Next: Monday Integration

Once Live2D is working:

1. **Advanced Interactions**
   - Eye tracking / gaze animation
   - Eyebrow movement for emotions
   - Hand gestures on emphasis

2. **Custom Expressions**
   - Happy when user compliments
   - Thinking pose for complex queries
   - Concerned when errors detected

3. **Voice Variety**
   - Multiple voice personalities
   - Emotion-aware speech (sad, excited, etc.)
   - Background music sync

---

This plan will make Friday truly "awe-inspiring" with a professional, anime-style Live2D character that responds naturally in real-time.
