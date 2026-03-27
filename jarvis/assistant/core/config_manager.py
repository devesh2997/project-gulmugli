"""
Runtime configuration management — read, validate, and update config.yaml.

This is the bridge between the running assistant and its configuration file.
Used by:
  - Dashboard settings UI (browser → WebSocket → ConfigManager → config.yaml)
  - Natural language config updates ("change the model to gemma:2b")
  - Future: API endpoints for companion mobile app

Design principles:
  - Every setting has a schema: type, allowed values, description, restart requirement
  - Changes are validated BEFORE writing to disk
  - Some changes take effect immediately (volume, personality, TTS speed)
  - Some require a provider restart (model change, STT model size)
  - Some require a full restart (port changes, hardware config)
  - The running `config` dict is updated in-place for immediate-effect settings
  - config.yaml is always written so changes survive restarts

Usage:
    from core.config_manager import config_manager

    # Get all settings the UI should show
    settings = config_manager.get_settings()

    # Update a setting
    result = config_manager.update("brain.model", "gemma:2b")
    # → {"ok": True, "restart_required": True, "message": "Model changed to gemma:2b. Restart required."}
"""

import copy
from pathlib import Path
from typing import Any

import yaml

from core.config import config, load_config
from core.logger import get_logger

log = get_logger("config_manager")


# ── Setting Schema ────────────────────────────────────────────────
# Each entry describes one configurable setting.
# Fields:
#   path:         dot-notation path in config.yaml (e.g., "brain.model")
#   type:         "string", "int", "float", "bool", "choice", "list"
#   label:        human-readable name for the UI
#   description:  what this setting does
#   choices:      for type "choice" — allowed values
#   min/max:      for numeric types — valid range
#   restart:      "none" (immediate), "provider" (restart that provider), "full" (restart assistant)
#   category:     grouping for the settings UI
#   editable:     whether the UI should allow changing this (false for secrets, hardware IDs, etc.)

SETTINGS_SCHEMA: list[dict] = [
    # ── Brain ──
    {
        "path": "brain.model",
        "type": "string",
        "label": "LLM Model",
        "description": "Ollama model tag for intent classification and chat",
        "restart": "provider",
        "category": "brain",
    },
    {
        "path": "brain.temperature",
        "type": "float",
        "label": "Temperature",
        "description": "Lower = more consistent, higher = more creative",
        "min": 0.0,
        "max": 2.0,
        "restart": "none",
        "category": "brain",
    },
    {
        "path": "brain.endpoint",
        "type": "string",
        "label": "Ollama Endpoint",
        "description": "URL where Ollama is running",
        "restart": "provider",
        "category": "brain",
    },

    # ── Voice ──
    {
        "path": "voice.enabled",
        "type": "bool",
        "label": "Text-to-Speech",
        "description": "Enable or disable voice output",
        "restart": "none",
        "category": "voice",
    },
    {
        "path": "voice.speed",
        "type": "float",
        "label": "Speech Speed",
        "description": "TTS playback speed multiplier",
        "min": 0.5,
        "max": 2.0,
        "restart": "none",
        "category": "voice",
    },
    {
        "path": "voice.fallback_provider",
        "type": "choice",
        "label": "Fallback Voice Provider",
        "description": "TTS provider to use when personality's preferred provider is unavailable",
        "choices": ["kokoro", "piper", "xtts", "edge"],
        "restart": "none",
        "category": "voice",
    },

    # ── Ears ──
    {
        "path": "ears.model_size",
        "type": "choice",
        "label": "STT Model Size",
        "description": "Larger = more accurate, slower. Medium recommended for Hindi.",
        "choices": ["tiny", "base", "small", "medium", "large-v3"],
        "restart": "provider",
        "category": "ears",
    },
    {
        "path": "ears.language",
        "type": "string",
        "label": "STT Language",
        "description": "Language code (auto, en, hi) or auto-detect",
        "restart": "none",
        "category": "ears",
    },

    # ── Music ──
    {
        "path": "music.search_results",
        "type": "int",
        "label": "Search Results",
        "description": "Number of YouTube Music results to consider",
        "min": 1,
        "max": 20,
        "restart": "none",
        "category": "music",
    },
    {
        "path": "music.auto_play_first",
        "type": "bool",
        "label": "Auto-play First Result",
        "description": "Play first search result automatically",
        "restart": "none",
        "category": "music",
    },

    # ── Knowledge ──
    {
        "path": "knowledge.enabled",
        "type": "bool",
        "label": "Web Search",
        "description": "Enable web search for factual questions (needs internet)",
        "restart": "none",
        "category": "knowledge",
    },
    {
        "path": "knowledge.max_results",
        "type": "int",
        "label": "Max Search Results",
        "description": "Number of web results to feed to the LLM",
        "min": 1,
        "max": 10,
        "restart": "none",
        "category": "knowledge",
    },

    # ── Wake Word ──
    {
        "path": "wake_word.sensitivity",
        "type": "float",
        "label": "Wake Word Sensitivity",
        "description": "0.0 = never triggers, 1.0 = triggers on everything",
        "min": 0.0,
        "max": 1.0,
        "restart": "none",
        "category": "wake_word",
    },
    {
        "path": "wake_word.cooldown",
        "type": "float",
        "label": "Wake Word Cooldown",
        "description": "Seconds between wake word detections",
        "min": 0.5,
        "max": 10.0,
        "restart": "none",
        "category": "wake_word",
    },

    # ── Memory ──
    {
        "path": "memory.enabled",
        "type": "bool",
        "label": "Memory",
        "description": "Log interactions for later recall",
        "restart": "none",
        "category": "memory",
    },

    # ── UI ──
    {
        "path": "ui.port",
        "type": "int",
        "label": "Dashboard Port",
        "description": "WebSocket port for the dashboard",
        "min": 1024,
        "max": 65535,
        "restart": "full",
        "category": "ui",
    },

    # ── Debug ──
    {
        "path": "debug.log_level",
        "type": "choice",
        "label": "Log Level",
        "description": "Logging verbosity",
        "choices": ["DEBUG", "INFO", "WARNING", "ERROR"],
        "restart": "none",
        "category": "debug",
    },

    # ── Personalities (default) ──
    {
        "path": "personalities.default",
        "type": "string",
        "label": "Default Personality",
        "description": "Which personality to start with",
        "restart": "none",
        "category": "personalities",
    },
]


def _get_nested(d: dict, path: str, default: Any = None) -> Any:
    """Get a value from a nested dict using dot notation."""
    keys = path.split(".")
    current = d
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _set_nested(d: dict, path: str, value: Any) -> None:
    """Set a value in a nested dict using dot notation."""
    keys = path.split(".")
    current = d
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


class ConfigManager:
    """
    Runtime configuration manager.

    Reads/writes config.yaml and validates changes against the schema.
    Thread-safe for concurrent reads; writes are sequential (config changes
    are infrequent enough that locking isn't needed).
    """

    def __init__(self):
        self._schema = {s["path"]: s for s in SETTINGS_SCHEMA}
        # Find the config.yaml path (same logic as config.py)
        self._config_path = Path(__file__).parent.parent / "config.yaml"
        if not self._config_path.exists():
            self._config_path = Path("config.yaml")

    def get_settings(self) -> list[dict]:
        """
        Get all configurable settings with their current values.

        Returns a list of setting dicts, each with the schema fields
        plus a "value" field containing the current config value.
        """
        settings = []
        for schema in SETTINGS_SCHEMA:
            entry = copy.copy(schema)
            entry["value"] = _get_nested(config, schema["path"])
            settings.append(entry)
        return settings

    def get_settings_by_category(self) -> dict[str, list[dict]]:
        """Get settings grouped by category, for the UI."""
        settings = self.get_settings()
        grouped: dict[str, list[dict]] = {}
        for s in settings:
            cat = s.get("category", "other")
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(s)
        return grouped

    def get_value(self, path: str) -> Any:
        """Get the current value of a setting."""
        return _get_nested(config, path)

    def update(self, path: str, value: Any) -> dict:
        """
        Update a setting.

        Validates the value, updates the running config dict, and writes
        to config.yaml. Returns a result dict:
            {"ok": True/False, "message": str, "restart_required": str}
        """
        schema = self._schema.get(path)
        if not schema:
            return {"ok": False, "message": f"Unknown setting: {path}"}

        # Validate type
        validation = self._validate(schema, value)
        if not validation["ok"]:
            return validation

        # Coerce type
        value = self._coerce(schema, value)

        old_value = _get_nested(config, path)
        if old_value == value:
            return {"ok": True, "message": "No change.", "restart_required": "none"}

        # Update the running config dict (for immediate-effect settings)
        _set_nested(config, path, value)

        # Write to disk
        try:
            self._write_config()
        except Exception as e:
            # Rollback in-memory change
            _set_nested(config, path, old_value)
            return {"ok": False, "message": f"Failed to write config: {e}"}

        restart = schema.get("restart", "none")
        label = schema.get("label", path)
        log.info('Config updated: %s = %s (was: %s, restart: %s)', path, value, old_value, restart)

        return {
            "ok": True,
            "message": f"{label} changed to {value}.",
            "restart_required": restart,
            "old_value": old_value,
            "new_value": value,
        }

    def _validate(self, schema: dict, value: Any) -> dict:
        """Validate a value against its schema."""
        stype = schema.get("type", "string")

        if stype == "bool":
            if not isinstance(value, bool):
                if isinstance(value, str):
                    if value.lower() in ("true", "yes", "on", "1"):
                        return {"ok": True}
                    elif value.lower() in ("false", "no", "off", "0"):
                        return {"ok": True}
                return {"ok": False, "message": f"Expected boolean, got {type(value).__name__}"}

        elif stype == "int":
            try:
                v = int(value)
            except (TypeError, ValueError):
                return {"ok": False, "message": f"Expected integer, got {value!r}"}
            if "min" in schema and v < schema["min"]:
                return {"ok": False, "message": f"Minimum is {schema['min']}"}
            if "max" in schema and v > schema["max"]:
                return {"ok": False, "message": f"Maximum is {schema['max']}"}

        elif stype == "float":
            try:
                v = float(value)
            except (TypeError, ValueError):
                return {"ok": False, "message": f"Expected number, got {value!r}"}
            if "min" in schema and v < schema["min"]:
                return {"ok": False, "message": f"Minimum is {schema['min']}"}
            if "max" in schema and v > schema["max"]:
                return {"ok": False, "message": f"Maximum is {schema['max']}"}

        elif stype == "choice":
            choices = schema.get("choices", [])
            if str(value) not in [str(c) for c in choices]:
                return {"ok": False, "message": f"Must be one of: {', '.join(str(c) for c in choices)}"}

        return {"ok": True}

    def _coerce(self, schema: dict, value: Any) -> Any:
        """Coerce a value to the schema's type."""
        stype = schema.get("type", "string")
        if stype == "bool":
            if isinstance(value, str):
                return value.lower() in ("true", "yes", "on", "1")
            return bool(value)
        elif stype == "int":
            return int(value)
        elif stype == "float":
            return float(value)
        return value

    def _write_config(self) -> None:
        """Write the current config dict to config.yaml."""
        if not self._config_path.exists():
            log.warning("Config file not found at %s — skipping write.", self._config_path)
            return

        with open(self._config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


# ═══════════════════════════════════════════════════════════════
# Singleton
# ═══════════════════════════════════════════════════════════════

config_manager = ConfigManager()
