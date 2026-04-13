#!/usr/bin/env python3
"""
╔═══════════════════════════════════════════════════════╗
║           FRIDAY AI ASSISTANT - v1.0                  ║
║     Iron Man inspired personal AI for your laptop     ║
║                                                       ║
║  Wake word: "Friday"  |  Hotkey: Ctrl+Shift+F        ║
║  Local LLM + Claude API | Voice + HUD + News         ║
╚═══════════════════════════════════════════════════════╝

Entry point. Supports:
  python main.py            → full GUI mode
  python main.py --cli      → terminal-only mode
  python main.py --minimized → tray only (no HUD popup)
  python main.py --setup    → first-time setup wizard
  python main.py --briefing → morning briefing then exit
"""

import sys
import os
import threading
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

app = typer.Typer(add_completion=False, invoke_without_command=True)
console = Console()

# ──────────────────────────────────────────────────────────────
# Logging setup
# ──────────────────────────────────────────────────────────────

def setup_logging(level: str = "INFO", log_to_file: bool = True):
    from config.loader import get as cfg
    level = cfg("logging.level", level)
    logger.remove()
    logger.add(sys.stderr, level=level, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")
    if log_to_file:
        log_path = ROOT / cfg("logging.log_path", "data/friday.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(str(log_path), level="DEBUG", rotation="5 MB", retention="7 days")


# ──────────────────────────────────────────────────────────────
# Banner
# ──────────────────────────────────────────────────────────────

def print_banner():
    banner = Text()
    banner.append("◈ FRIDAY AI ASSISTANT ◈\n", style="bold yellow")
    banner.append("Iron Man inspired personal AI for your laptop\n", style="dim yellow")
    banner.append("─" * 40 + "\n", style="dark_orange")
    banner.append("Wake word:  ", style="dim")
    banner.append('"Friday"\n', style="bold cyan")
    banner.append("Hotkey:     ", style="dim")
    banner.append("Ctrl+Shift+F\n", style="bold cyan")
    banner.append("Brain:      ", style="dim")
    banner.append("Ollama (local) + Claude API\n", style="bold green")

    console.print(Panel(banner, border_style="yellow", padding=(0, 2)))


# ──────────────────────────────────────────────────────────────
# CLI Commands
# ──────────────────────────────────────────────────────────────

@app.callback()
def main(
    ctx: typer.Context,
    cli: bool = typer.Option(False, "--cli", help="Run in terminal-only mode (no GUI)"),
    minimized: bool = typer.Option(False, "--minimized", help="Start minimized to tray"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """
    Friday AI Assistant - Iron Man inspired personal AI for your laptop.

    Run with no arguments to start in full mode (HUD + voice).
    Use --cli to chat by typing instead of speaking.
    """
    # Only run if no subcommand was invoked (e.g. status, briefing, setup)
    if ctx.invoked_subcommand is not None:
        return

    setup_logging("DEBUG" if debug else "INFO")
    print_banner()

    if cli:
        _run_cli_mode()
        return

    _run_full_mode(minimized=minimized)


@app.command()
def start(
    cli: bool = typer.Option(False, "--cli", help="Run in terminal-only mode (no GUI)"),
    minimized: bool = typer.Option(False, "--minimized", help="Start minimized to tray"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Explicitly start Friday AI Assistant (same as running with no subcommand)."""
    setup_logging("DEBUG" if debug else "INFO")
    print_banner()

    if cli:
        _run_cli_mode()
        return

    _run_full_mode(minimized=minimized)


@app.command()
def setup():
    """First-time setup wizard."""
    setup_logging()
    console.print("\n[bold yellow]◈ Friday Setup Wizard[/bold yellow]\n")

    console.print("Checking dependencies...")
    _check_dependencies()

    console.print("\nChecking Ollama...")
    _check_ollama()

    console.print("\n[bold green]Setup complete! Run: python main.py[/bold green]\n")


@app.command()
def briefing():
    """Get an immediate news + weather briefing and exit."""
    setup_logging()
    from features.news import get_news, get_weather
    from core.voice import get_voice

    news = get_news()
    weather = get_weather()
    voice = get_voice()

    console.print("[yellow]Fetching your morning briefing...[/yellow]")
    weather_spoken = weather.spoken()
    news_text = news.morning_briefing_text(n=5)
    full = f"{weather_spoken} {news_text}"

    console.print(Panel(full, title="Morning Briefing", border_style="yellow"))
    voice.say_sync(full)


@app.command()
def status():
    """Show Friday's current system status."""
    setup_logging()
    from core.brain import get_brain

    brain = get_brain()
    s = brain.engine_status

    console.print(f"\n[bold yellow]◈ Friday Status[/bold yellow]")
    console.print(f"  Ollama:      {'[green]✓ Online[/green]' if s['ollama'] else '[red]✗ Offline[/red]'}")
    console.print(f"  Claude API:  {'[green]✓ Ready[/green]' if s['claude'] else '[dim]Not configured[/dim]'}")
    console.print(f"  Primary:     [cyan]{s['primary']}[/cyan]")


# ──────────────────────────────────────────────────────────────
# Full Mode (HUD + voice) — Qt MUST run in main thread on Windows
# ──────────────────────────────────────────────────────────────

def _run_full_mode(minimized: bool = False):
    """
    Start Friday with HUD overlay + voice.

    Architecture (required by Qt on Windows):
      Main thread  → QApplication + HUD widget (Qt event loop)
      Background   → Orchestrator (wake word, voice, news, memory…)
    """
    from core.orchestrator import FridayOrchestrator
    from ui.hud import get_hud
    from config.loader import get as cfg

    friday = FridayOrchestrator()
    hud = get_hud()

    # Step 1: Init Qt widget in main thread BEFORE starting orchestrator
    qt_app = hud.init_in_main_thread()

    # Step 2: Start all background systems in a daemon thread
    def _bg():
        try:
            friday.start()
            # Block the background thread — HUD shutdown will stop the loop
            friday.run_forever()
        except Exception as e:
            logger.error(f"Orchestrator error: {e}")

    bg = threading.Thread(target=_bg, daemon=True, name="FridayMain")
    bg.start()

    # Step 3: Block main thread on Qt event loop (or plain loop if no Qt)
    if qt_app is not None:
        logger.info("Friday HUD running — close window or use tray to quit")
        qt_app.exec()
        friday.shutdown()
    else:
        # No GUI available — fall back to blocking loop
        logger.info("No GUI — running headless. Ctrl+C to quit.")
        friday.run_forever()


# ──────────────────────────────────────────────────────────────
# CLI Mode (no GUI)
# ──────────────────────────────────────────────────────────────

def _run_cli_mode():
    """
    Terminal-only mode. Type to Friday instead of speaking.
    Great for testing or when audio isn't available.
    """
    from core.brain import get_brain
    from core.memory import get_memory
    from core.eyes import get_eyes

    brain = get_brain()
    memory = get_memory()
    eyes = get_eyes()
    eyes.start_all()

    console.print("\n[bold yellow]Friday CLI Mode[/bold yellow] - Type your message, Enter to send. 'quit' to exit.\n")

    while True:
        try:
            user_input = input("[You] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "bye"):
            console.print("[dim]Friday offline.[/dim]")
            break

        context = eyes.full_context() + " " + memory.context_summary()
        response = brain.chat(user_input, extra_context=context)

        memory.conversation.save_turn("user", user_input)
        memory.conversation.save_turn("assistant", response)

        console.print(f"[bold yellow][Friday][/bold yellow] {response}\n")

    eyes.stop_all()


# ──────────────────────────────────────────────────────────────
# Dependency Checks
# ──────────────────────────────────────────────────────────────

def _check_dependencies():
    """Check all required Python packages."""
    checks = [
        ("faster_whisper", "faster-whisper"),
        ("openwakeword", "openwakeword"),
        ("pyttsx3", "pyttsx3"),
        ("sounddevice", "sounddevice"),
        ("feedparser", "feedparser"),
        ("PyQt6", "PyQt6"),
        ("pystray", "pystray"),
        ("PIL", "Pillow"),
        ("mss", "mss"),
        ("pyperclip", "pyperclip"),
        ("apscheduler", "apscheduler"),
        ("ollama", "ollama"),
    ]
    all_ok = True
    for module, package in checks:
        try:
            __import__(module)
            console.print(f"  [green]✓[/green] {package}")
        except ImportError:
            console.print(f"  [red]✗[/red] {package} - [dim]pip install {package}[/dim]")
            all_ok = False

    if not all_ok:
        console.print("\n[yellow]Install missing packages:[/yellow]")
        console.print("  pip install -r requirements.txt")

    return all_ok


def _check_ollama():
    """Check if Ollama is running and has a model."""
    try:
        import ollama
        models = ollama.list()
        model_names = [m.model for m in models.models] if hasattr(models, 'models') else []
        if model_names:
            console.print(f"  [green]✓[/green] Ollama running | Models: {', '.join(model_names[:3])}")
        else:
            console.print("  [yellow]⚠[/yellow] Ollama running but no models found")
            console.print("  Run: [cyan]ollama pull mistral[/cyan]")
    except Exception:
        console.print("  [red]✗[/red] Ollama not running")
        console.print("  Install: [cyan]https://ollama.ai[/cyan]")
        console.print("  Start:   [cyan]ollama serve[/cyan]")
        console.print("  Model:   [cyan]ollama pull mistral[/cyan]")


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
