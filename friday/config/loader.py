"""
Friday Config Loader
--------------------
Loads and validates configuration from settings.yaml
Supports environment variable overrides.
"""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from loguru import logger

# Load .env file if present
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

_CONFIG_PATH = Path(__file__).parent / "settings.yaml"
_config_cache: dict | None = None


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base dict."""
    result = base.copy()
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_config(config_path: Path | None = None) -> dict:
    """Load and return the full config dict. Cached after first load."""
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    path = config_path or _CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r") as f:
        cfg = yaml.safe_load(f)

    # Apply environment variable overrides
    _apply_env_overrides(cfg)

    _config_cache = cfg
    logger.info(f"Config loaded from {path}")
    return cfg


def _apply_env_overrides(cfg: dict) -> None:
    """Apply environment variable overrides to config."""
    env_map = {
        "ANTHROPIC_API_KEY": ("brain", "claude", "api_key"),
        "FRIDAY_MODEL": ("brain", "ollama", "model"),
        "FRIDAY_PRIMARY_BRAIN": ("brain", "primary"),
        "FRIDAY_PERSONALITY": ("friday", "personality"),
        "FRIDAY_HUD_ENABLED": ("hud", "enabled"),
        "FRIDAY_WAKE_SENSITIVITY": ("wake_word", "sensitivity"),
    }
    for env_var, key_path in env_map.items():
        val = os.environ.get(env_var)
        if val is not None:
            # Navigate to nested key and set
            d = cfg
            for k in key_path[:-1]:
                d = d.setdefault(k, {})
            # Handle type coercion
            final_key = key_path[-1]
            existing = d.get(final_key)
            if isinstance(existing, bool):
                d[final_key] = val.lower() in ("true", "1", "yes")
            elif isinstance(existing, float):
                d[final_key] = float(val)
            elif isinstance(existing, int):
                d[final_key] = int(val)
            else:
                d[final_key] = val
            logger.debug(f"Config override from env: {env_var}")


def get(key_path: str, default: Any = None) -> Any:
    """
    Get a config value by dot-notation path.
    Example: get("brain.ollama.model") → "mistral"
    """
    cfg = load_config()
    keys = key_path.split(".")
    val = cfg
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return default
        if val is None:
            return default
    return val


def reload() -> dict:
    """Force reload config from disk."""
    global _config_cache
    _config_cache = None
    return load_config()
