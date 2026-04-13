#!/usr/bin/env python3
"""
Friday Diagnostic Tool
Tests each component independently to identify issues quickly.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

def test_pyttsx3():
    """Test pyttsx3 TTS engine."""
    console.print("\n[bold cyan]Testing pyttsx3 TTS...[/bold cyan]")
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty('rate', 150)
        engine.setProperty('volume', 0.9)

        # Try to speak
        engine.say("Testing text to speech. If you hear this, pyttsx3 works.")
        engine.runAndWait()
        console.print("[green]✓ pyttsx3 working![/green]")
        return True
    except Exception as e:
        console.print(f"[red]✗ pyttsx3 failed: {e}[/red]")
        return False


def test_gtts():
    """Test gTTS fallback engine."""
    console.print("\n[bold cyan]Testing gTTS fallback...[/bold cyan]")
    try:
        from gtts import gTTS
        import tempfile
        import subprocess
        import platform

        # Generate speech
        tts = gTTS(text="Testing Google Text to Speech fallback.", lang='en')
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
            tts.save(tmp_path)
            console.print(f"[yellow]Saved to: {tmp_path}[/yellow]")

            # Try to play
            if platform.system() == "Windows":
                import os
                os.startfile(tmp_path)
                console.print("[green]✓ gTTS audio file created and opened[/green]")
            else:
                console.print("[yellow]Note: Can't auto-play on this platform, but file created[/yellow]")
        return True
    except ImportError:
        console.print("[yellow]⚠ gTTS not installed: pip install gtts[/yellow]")
        return False
    except Exception as e:
        console.print(f"[red]✗ gTTS failed: {e}[/red]")
        return False


def test_microphone():
    """Test microphone input."""
    console.print("\n[bold cyan]Testing microphone...[/bold cyan]")
    try:
        import sounddevice as sd
        import numpy as np

        # Quick test: record 1 second
        sample_rate = 16000
        duration = 1

        console.print("[yellow]Recording 1 second... speak now![/yellow]")
        audio = sd.rec(int(sample_rate * duration), samplerate=sample_rate, channels=1, dtype='float32')
        sd.wait()

        # Check if any sound was recorded
        rms = np.sqrt(np.mean(audio ** 2))
        if rms > 0.01:
            console.print(f"[green]✓ Microphone working! (volume: {rms:.3f})[/green]")
            return True
        else:
            console.print("[yellow]⚠ Microphone detected but very quiet[/yellow]")
            return False
    except Exception as e:
        console.print(f"[red]✗ Microphone test failed: {e}[/red]")
        return False


def test_ollama():
    """Test Ollama connection."""
    console.print("\n[bold cyan]Testing Ollama...[/bold cyan]")
    try:
        import ollama

        # Check if Ollama is running
        models = ollama.list()
        model_names = [m.model for m in models.models] if hasattr(models, 'models') else []

        if not model_names:
            console.print("[yellow]⚠ Ollama running but no models found[/yellow]")
            console.print("[dim]Run: ollama pull phi3:mini[/dim]")
            return False

        console.print(f"[green]✓ Ollama online | Models: {', '.join(model_names[:3])}[/green]")

        # Quick test: simple query
        console.print("[yellow]Testing model response... (this may take a moment)[/yellow]")
        response = ollama.chat(
            model=model_names[0],
            messages=[{"role": "user", "content": "Say 'Friday ready' in one word"}],
            stream=False
        )
        console.print(f"[green]✓ Model response: {response['message']['content'][:50]}[/green]")
        return True
    except Exception as e:
        console.print(f"[red]✗ Ollama test failed: {e}[/red]")
        return False


def test_opencv():
    """Test screen capture."""
    console.print("\n[bold cyan]Testing screen capture...[/bold cyan]")
    try:
        import mss

        with mss.mss() as sct:
            screenshot = sct.grab(sct.monitors[1])
            if screenshot.width > 0 and screenshot.height > 0:
                console.print(f"[green]✓ Screen capture working ({screenshot.width}x{screenshot.height})[/green]")
                return True
        return False
    except Exception as e:
        console.print(f"[red]✗ Screen capture failed: {e}[/red]")
        return False


def test_database():
    """Test SQLite database."""
    console.print("\n[bold cyan]Testing SQLite database...[/bold cyan]")
    try:
        from core.memory import get_memory

        memory = get_memory()
        # Try to store and retrieve a fact
        memory.facts.remember("test_key", "test_value", confidence=1.0)
        retrieved = memory.facts.recall("test_key")

        if retrieved == "test_value":
            console.print("[green]✓ Database working (read/write OK)[/green]")
            memory.facts.forget("test_key")
            return True
        return False
    except Exception as e:
        console.print(f"[red]✗ Database test failed: {e}[/red]")
        return False


def run_all_tests():
    """Run all diagnostic tests."""
    console.print(Panel("[bold yellow]Friday AI Assistant - Diagnostic Tool[/bold yellow]", border_style="yellow"))

    results = {
        "pyttsx3 TTS": test_pyttsx3(),
        "gTTS Fallback": test_gtts(),
        "Microphone": test_microphone(),
        "Ollama LLM": test_ollama(),
        "Screen Capture": test_opencv(),
        "Database": test_database(),
    }

    # Summary table
    table = Table(title="[bold]Diagnostic Results[/bold]")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="magenta")

    for component, passed in results.items():
        status = "[green]✓ Working[/green]" if passed else "[red]✗ Failed[/red]"
        table.add_row(component, status)

    console.print(table)

    # Summary
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    console.print(f"\n[bold]Summary:[/bold] {passed}/{total} components working")

    if passed == total:
        console.print("[green bold]✓ All systems go! Friday is ready to run.[/green bold]")
    else:
        console.print("[yellow bold]⚠ Some components need attention. See details above.[/yellow bold]")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
