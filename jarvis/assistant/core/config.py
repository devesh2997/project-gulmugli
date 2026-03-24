"""
Configuration loader.

Reads config.yaml once at startup. Every module imports `config` from here
instead of reading the YAML file directly.

The assistant name, model choice, music platform, etc. all come from config.
Nothing is hardcoded anywhere else.
"""

import yaml
from pathlib import Path


def load_config(config_path: str = None) -> dict:
    """
    Load configuration from YAML file.

    Search order:
      1. Explicit path if provided
      2. config.yaml in the assistant directory
      3. config.yaml in current working directory
    """
    if config_path:
        path = Path(config_path)
    else:
        # Look relative to this file's location (assistant/core/config.py → assistant/config.yaml)
        path = Path(__file__).parent.parent / "config.yaml"
        if not path.exists():
            path = Path("config.yaml")

    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found at {path}. "
            f"Copy config.example.yaml to config.yaml and edit it."
        )

    with open(path) as f:
        return yaml.safe_load(f)


# Load once at import time. Every module does:
#   from core.config import config
#   name = config["assistant"]["name"]
config = load_config()
