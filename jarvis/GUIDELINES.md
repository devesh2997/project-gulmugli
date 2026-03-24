# Project JARVIS — ET's Learning Guidelines

**These rules apply to EVERY module, every document, every code snippet in this project.**

---

## ET's Background

ET is an experienced backend + frontend developer. He knows how to build applications, understands HTTP/REST/APIs, is comfortable writing Python, and can work with Linux at a basic level. He does NOT need explanations for:
- How HTTP servers, APIs, or ports work
- What `pip install`, `brew`, `curl`, REST endpoints, JSON parsing, etc. do
- How to structure code, write classes, handle errors, etc.
- General programming concepts

**What ET DOES need explained in depth:**
- **AI/ML concepts** — LLMs, quantization, inference, tokens, embeddings, model architectures, training vs fine-tuning, system prompts, how Whisper transcribes speech, how wake word detection works under the hood, what CUDA does for inference, etc.
- **AI-specific tools** — What Ollama does that's AI-specific, why model X beats model Y, etc.
- **Hardware concepts (ALL of them)** — ET is NOT a hardware person. Explain everything: what a GPIO pin is, what I2S means, how NeoPixel strips communicate, what a Jetson even is vs a Raspberry Pi at the board level, what "shared memory" means for CPU/GPU, how Bluetooth audio protocols work, what a mic array does differently from a single mic, how beamforming works, what soldering is and when it's needed, power delivery (PD) basics, thermal management, enclosure ventilation, etc. Treat hardware like how AI is treated — deep explanations, no assumptions.
- **Decision rationale** — Why we chose tool A over tool B, with alternatives listed

## Rule 1: Deep-Dive on AI, Skim on Software

Explain AI and hardware concepts thoroughly. Skip explanations of standard software engineering concepts.

Bad: "`requests.post()` sends an HTTP POST request to the URL..."
Good: Just write the code. ET knows what `requests.post()` does.

Bad: "JSON is a data format..."
Good: Skip this. ET uses JSON daily.

Good: "Quantization shrinks a model from 6GB to 2GB by storing each parameter in 4 bits instead of 16. Here's what that means for quality..."
Good: "The `format: json` flag in Ollama constrains the model's token generation to only produce valid JSON tokens — it modifies the sampling probability distribution at each step to zero out any token that would break JSON syntax."

## Rule 2: Justify Every AI/Tool Decision

Every AI model, AI tool, or hardware choice must include:
- What it is (one line)
- Why we picked it over alternatives (comparison table)
- When you'd reconsider

Standard software libraries (requests, subprocess, etc.) don't need justification.

## Rule 3: Document Decisions in Each Module

Every module README must include a "Decision Log" section for the non-obvious choices.

## Rule 4: Build AI & Hardware Intuition

The goal is for ET to understand two domains deeply:
1. **AI layer** — well enough to debug, swap models, tune prompts, and make architectural decisions independently
2. **Hardware layer** — well enough to confidently order parts, connect them, understand what's plugged into what, and troubleshoot physical issues

The software layer is just plumbing — ET can handle that. AI and hardware are where the learning happens.

## Summary: What to Explain vs What to Skip

| Domain | Explain in depth? | Example |
|--------|-------------------|---------|
| AI/ML concepts | YES | How Whisper transcribes audio, what attention layers do, why Q4 quantization works |
| Hardware/electronics | YES | What GPIO pins are, how Bluetooth A2DP works, why the Jetson needs a heatsink |
| Software engineering | NO | How to make HTTP requests, what async/await does, how to structure a Python project |
| Linux commands | BRIEFLY | One-liner explanation if non-obvious, skip for basics like `cd`, `ls`, `pip install` |
