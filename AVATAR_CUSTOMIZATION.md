# Friday Avatar Customization Guide

## Quick Start: Add Custom Avatar Character Images

Friday's avatar system now supports **PNG image-based avatars** while falling back to emoji if images aren't provided.

### Directory Structure

Create an `assets/avatar/` folder in your project root:

```
Deep_Pro/
├── assets/
│   └── avatar/
│       ├── idle_1.png
│       ├── idle_2.png
│       ├── thinking_1.png
│       ├── thinking_2.png
│       ├── speaking_1.png
│       └── speaking_2.png
├── friday/
├── main.py
└── ...
```

### Image Requirements

#### Size & Format
- **Format:** PNG (with transparency support recommended)
- **Resolution:** 200x200 to 400x400 pixels (scales automatically)
- **Aspect Ratio:** Square (1:1) works best
- **Background:** Transparent or matching your theme

#### Animation Frames
Friday looks for animation frames in this order:

1. **Per-State Numbered Frames** (recommended for smooth animation)
   - `idle_1.png`, `idle_2.png`, `idle_3.png`, `idle_4.png`
   - `thinking_1.png`, `thinking_2.png`, `thinking_3.png`, `thinking_4.png`
   - `speaking_1.png`, `speaking_2.png`, `speaking_3.png`, `speaking_4.png`

2. **Single-State Images** (fallback)
   - `idle.png`
   - `thinking.png`
   - `speaking.png`

### States & Their Meaning

| State | When Used | Suggested Animation |
|-------|-----------|-------------------|
| **idle** | Greeting user, waiting for input | Subtle breathing, blinking |
| **thinking** | Processing question, generating response | Thinking pose, loading spinner effect |
| **speaking** | Speaking the response | Mouth movements, lip-sync animation |

### Example: Convert Emoji to PNG

If you want to create frames from scratch, you can:

1. **Use an online emoji-to-PNG converter** and save as individual frames
2. **Create in design software** (Photoshop, GIMP, Figma, Krita)
3. **Download character assets** from:
   - [Open Game Art](https://opengameart.org/)
   - [itch.io - Character Assets](https://itch.io/game-assets/tag-character)
   - [VRoid Studio](https://vroid.com/en/studio) - Create custom anime characters

### Recommended: VRoid Studio (Free!)

**Best option for anime-style avatars:**

1. Download [VRoid Studio](https://vroid.com/en/studio)
2. Create/customize your avatar character
3. Export screenshots or use in-game recording
4. Convert video frames to PNG sequence (see below)

#### Convert Video/GIF to PNG Frames

Using FFmpeg:

```bash
# From video (MP4, MOV, etc.)
ffmpeg -i avatar_animation.mp4 -vf scale=300:-1 assets/avatar/idle_%d.png

# From GIF
ffmpeg -i avatar_idle.gif -vf scale=300:-1 assets/avatar/idle_%d.png

# Rename frames (Linux/Mac)
for f in assets/avatar/idle_*.png; do
  num=$(echo "$f" | grep -o '[0-9]\+' | head -1)
  mv "$f" "assets/avatar/idle_${num}.png"
done
```

### Troubleshooting

#### Images Not Loading?
1. Check file names match exactly: `idle_1.png`, `thinking_1.png`, etc. (lowercase)
2. Verify `assets/avatar/` directory exists in project root
3. Check Friday logs for asset loading messages
4. PNG files should be readable (not corrupted)

#### Avatar Still Shows Emoji?
This is normal! It means no PNG assets were found. The system automatically falls back to emoji. Once you add PNG files, it will use them.

#### Image Quality Issues?
- Try higher resolution images (400x400 or larger)
- Ensure transparent backgrounds match the avatar widget's background
- Avoid too much detail (will be scaled down)

### Example: Minimal Test Setup

If you want to test with simple images:

```bash
# Create test images using ImageMagick
convert -size 300x300 xc:cyan assets/avatar/idle_1.png
convert -size 300x300 xc:yellow assets/avatar/thinking_1.png
convert -size 300x300 xc:magenta assets/avatar/speaking_1.png
```

### Advanced: Live2D Integration (Future)

For even more impressive avatars with real-time lip-sync:

- **Tool:** live2d-py (Python SDK for Live2D Cubism)
- **Timeline:** Planned for Phase 2B (this weekend)
- **Character Source:** VRoid Studio exports + Live2D rigging

---

## Fallback Behavior

If no PNG assets are found, Friday displays an **emoji-based avatar** with the following animations:

- **Idle:** 🤖 with breathing effect (✨)
- **Thinking:** 🤔 with spinner animation
- **Speaking:** 🤖 with mouth movements (💬 / 👄)

This ensures Friday always has a visible avatar, even without custom images.

---

## Next Steps

1. **Quick Win:** Use emoji avatar as-is (already looks much better with size improvements)
2. **Weekend:** Add custom PNG assets or Live2D avatar
3. **Advanced:** Implement real-time lip-sync with viseme mapping

**Questions?** Check the avatar implementation in `friday/ui/avatar.py` or the orchestrator streaming code for how avatars are triggered.
