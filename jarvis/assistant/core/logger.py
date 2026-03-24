"""
Centralized logging for the assistant.

Reads from config.yaml's debug section and sets up Python's logging module.
Every module does:
    from core.logger import log

    log.info("Something happened")
    log.debug("Detailed debug info")

Log levels map directly to config.yaml:
    debug.log_level: "DEBUG"   → see everything (raw queries, enriched queries, search results)
    debug.log_level: "INFO"    → see what's happening (playing X, paused, volume set)
    debug.log_level: "WARNING" → only problems (provider not available, search mismatch)
    debug.log_level: "ERROR"   → only failures (playback failed, JSON parse failed)

The user-facing output (the assistant's spoken response) always prints to stdout
regardless of log level. Logging is for the developer/debugger, not the user.
"""

import logging
import sys
import os

from core.config import config


# ═══════════════════════════════════════════════════════════════
# ANSI colors — auto-disabled if output isn't a terminal
# (e.g., piped to a file: python main.py 2>debug.log)
# ═══════════════════════════════════════════════════════════════

_USE_COLOR = hasattr(sys.stderr, "isatty") and sys.stderr.isatty() and os.environ.get("NO_COLOR") is None


class _Colors:
    """ANSI escape codes. All empty strings when color is disabled."""

    RESET   = "\033[0m"  if _USE_COLOR else ""
    BOLD    = "\033[1m"  if _USE_COLOR else ""
    DIM     = "\033[2m"  if _USE_COLOR else ""

    # Level colors
    GRAY    = "\033[90m" if _USE_COLOR else ""  # DEBUG — dim, stay out of the way
    BLUE    = "\033[94m" if _USE_COLOR else ""  # INFO  — calm, informational
    YELLOW  = "\033[93m" if _USE_COLOR else ""  # WARN  — attention
    RED     = "\033[91m" if _USE_COLOR else ""  # ERROR — problem
    RED_BG  = "\033[41m" if _USE_COLOR else ""  # CRITICAL — screaming

    # Semantic colors for log content
    CYAN    = "\033[96m" if _USE_COLOR else ""  # quoted values ("Sajni", "Arijit Singh")
    GREEN   = "\033[92m" if _USE_COLOR else ""  # success indicators


C = _Colors


def _setup_logger() -> logging.Logger:
    """
    Create and configure the assistant logger from config.yaml.

    Uses a custom formatter designed for terminal readability:
    - Color-coded by level (gray debug, blue info, yellow warn, red error)
    - Fixed-width level tags so messages align vertically
    - Module origin shown in DEBUG mode for tracing
    - Quoted strings highlighted in cyan for quick scanning
    - No timestamps (you're running this interactively, not parsing server logs)

    Example output at DEBUG level:

        ┊ DEBUG brain.ollama  │ Enriched "Sajni" → "Sajni Arijit Singh"
        ┊ DEBUG music.youtube │ Both searches agree: "Sajni"
        ┊ INFO                │ Playing "Sajni" by Arijit Singh
        ┊ WARN                │ Search mismatch: enriched → "Saajan", raw → "Sajni"
    """
    debug_cfg = config.get("debug", {})
    level_str = debug_cfg.get("log_level", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)

    logger = logging.getLogger("assistant")
    logger.setLevel(level)

    # Don't add handlers if they already exist (e.g., module reloaded)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    formatter = _AssistantFormatter()
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    # Don't propagate to root logger (avoids duplicate output)
    logger.propagate = False

    return logger


class _AssistantFormatter(logging.Formatter):
    """
    Pretty terminal formatter with color and alignment.

    Layout:
        ┊ LEVEL module.name │ message text here
        ┊ LEVEL             │ message text here  (when no module needed)

    The ┊ gutter and │ separator create a clean visual column,
    and the fixed-width level+module field keeps messages aligned.
    """

    # (color, tag, width)
    LEVEL_STYLES = {
        logging.DEBUG:    (C.GRAY,   "DEBUG",    5),
        logging.INFO:     (C.BLUE,   "INFO",     5),
        logging.WARNING:  (C.YELLOW, "WARN",     5),
        logging.ERROR:    (C.RED,    "ERROR",    5),
        logging.CRITICAL: (C.RED_BG, "CRITICAL", 8),
    }

    # How wide the "LEVEL module" column is (for alignment)
    _TAG_WIDTH = 22

    def format(self, record):
        color, tag, _ = self.LEVEL_STYLES.get(
            record.levelno,
            (C.RESET, record.levelname, len(record.levelname)),
        )

        # Build the level + module label
        module = record.name.replace("assistant.", "")
        if record.levelno <= logging.DEBUG and module != "assistant":
            label = f"{tag} {module}"
        else:
            label = tag

        # Pad for alignment
        padded_label = label.ljust(self._TAG_WIDTH)

        # Colorize the message — highlight quoted strings in cyan
        msg = record.getMessage()
        msg = _highlight_quotes(msg, color)

        # Build the final line
        gutter = f"{C.DIM}┊{C.RESET}"
        sep = f"{C.DIM}│{C.RESET}"

        return f"  {gutter} {color}{padded_label}{C.RESET} {sep} {msg}"


def _highlight_quotes(text: str, base_color: str) -> str:
    """
    Highlight "quoted strings" in cyan within a log message.

    Turns:  Enriched "Sajni" → "Sajni Arijit Singh"
    Into:   Enriched [cyan]"Sajni"[/cyan] → [cyan]"Sajni Arijit Singh"[/cyan]

    Only activates when color is enabled. Handles unmatched quotes gracefully
    by just returning the original text.
    """
    if not _USE_COLOR or '"' not in text:
        return text

    parts = text.split('"')
    # Odd-indexed parts are inside quotes
    if len(parts) < 3:
        return text

    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:  # inside quotes
            result.append(f'{C.CYAN}"{part}"{base_color}')
        else:
            result.append(part)

    return base_color.join("").join("") + "".join(result)


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

# The main logger. Every module imports this.
log = _setup_logger()


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger for a specific module.

    Usage:
        from core.logger import get_logger
        log = get_logger("brain.ollama")

    This creates a child of the "assistant" logger, so it inherits
    the level and handlers. The name shows up in DEBUG output.
    """
    return logging.getLogger(f"assistant.{name}")
