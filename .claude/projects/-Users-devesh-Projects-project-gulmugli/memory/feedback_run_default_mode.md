---
name: Always run assistant in default mode
description: Don't use --text flag unless specifically scoping tests. Run the assistant as it's meant to be used.
type: feedback
---

Don't use `--text` flag when starting the assistant unless specifically testing a text-only workflow.

**Why:** The user wants to always test the assistant in its full default state (wake word + voice + STT + TTS). Using `--text` bypasses wake word detection and other critical features. Special flags should only be used when deliberately scoping testing to a specific workflow.

**How to apply:** In launch.json and when running the assistant, use `python main.py` with no flags. The auto-detect logic in main() will pick the right mode (wake word > voice > text) based on available hardware/providers.
