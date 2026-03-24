# Module 1: The Brain — Local LLM & Intent Routing

**What this is:** The intelligence layer. A language model running locally that understands what the user wants and decides what action to take.

**Time estimate:** 6–8 hours across Weeks 1–2

**Design principle:** Model-agnostic. Every piece of code in this module treats the model as a swappable config value. You'll build an evaluation framework to objectively compare models, and the intent router will work with any model you throw at it. No model is "chosen" until your own benchmarks prove it's the best for YOUR use case.

---

## AI Concepts You Need

### How LLMs Actually Work

An LLM is a neural network trained to predict "what token comes next." Given "The capital of France is ___", it predicts "Paris" because it's seen that pattern billions of times during training.

**Parameters** are the numbers (weights) inside the network that encode knowledge. They're the result of training — the model "learned" them by reading vast amounts of text. More parameters = more knowledge capacity = smarter, but also bigger file = more RAM = slower.

| Size | Parameters | Capability | Q4 RAM |
|------|-----------|-----------|--------|
| Tiny | 1B | Basic language, simple tasks | ~0.7 GB |
| Small | 3B | Good reasoning, follows structured instructions | ~2 GB |
| Medium | 7-8B | Very capable, nuanced understanding | ~5 GB |
| Large | 70B+ | Near-human reasoning | ~40 GB |

### Tokens ≠ Words

LLMs process **tokens**, not words. A token is a chunk of text, roughly ¾ of a word. "Playing" might be two tokens: "Play" + "ing". The model generates one token at a time, each time running the entire neural network forward.

**Inference speed** is measured in tokens/second (tok/s). At 30 tok/s, the model generates ~22 words/second — fast enough for short assistant responses to feel instant.

### Quantization — Why Models Fit on Small Devices

A raw 3B model stores each parameter as a 16-bit float: `3B × 2 bytes = 6 GB`. Quantization compresses this by using fewer bits per parameter:

| Quant | Bits | 3B Size | Quality Impact |
|-------|------|---------|---------------|
| FP16 | 16 | ~6 GB | Baseline (full quality) |
| Q8 | 8 | ~3 GB | Imperceptible loss |
| Q4 | 4 | ~2 GB | Slight loss, fine for intent classification |
| Q2 | 2 | ~1 GB | Noticeable degradation |

Q4 doesn't literally store 4-bit floats — it groups parameters into blocks of 32, computes a scaling factor per block, and stores each parameter as a 4-bit integer + shared scale. This preserves more accuracy than naive rounding. The format Ollama uses is **GGUF** (GPT-Generated Unified Format), developed by the llama.cpp project.

### How the Model "Thinks" (Transformer Architecture — 60-second version)

When you send "play that sad Coldplay song from the space movie":

1. **Tokenizer** breaks it into tokens: ["play", "that", "sad", "Cold", "play", "song", ...]
2. Each token gets converted to a **vector** (list of numbers representing meaning in context)
3. **Self-attention layers** let each token "look at" every other token to understand relationships. "sad" attends to "Coldplay" and "space movie", building the association.
4. This runs through ~30+ layers of attention + feedforward networks, each refining the understanding
5. The final layer outputs a probability distribution over all possible next tokens
6. The model samples a token based on that distribution (controlled by `temperature`)
7. Repeat until done

The "knowledge" lives in those attention weights — that's what the billions of parameters encode. There's no database; it's patterns of association.

### What is CUDA and Why Does It Matter?

CUDA is NVIDIA's framework that lets you run computations on the GPU instead of the CPU. Why this matters for LLMs:

- **CPU inference:** Each token runs through 3 billion multiplications, one after another. Like one person doing all the math.
- **GPU inference:** The GPU has thousands of small cores that do the multiplications in parallel. Like 1000 people splitting the work.

This is why the same model might run at 15 tok/s on CPU and 30+ tok/s on an NVIDIA GPU. AMD and Apple Silicon have their own equivalents (ROCm and Metal, respectively). Ollama auto-detects your hardware and uses whatever acceleration is available.

**Hardware note:** This matters when choosing hardware later. NVIDIA GPUs use CUDA, Apple Silicon uses Metal, and some ARM boards have no GPU acceleration at all. We'll note per-model what acceleration they support.

---

## Decision Log: Why Ollama as the Model Server?

| Tool | What it is | Verdict |
|------|-----------|---------|
| **Ollama** ✅ | Local model server wrapping llama.cpp. Downloads, manages, and serves models via REST API. | **Chosen as starting point.** One-command install, works on Mac (Metal) + Linux ARM + NVIDIA, dead simple API, supports hot-swapping models. |
| **llama.cpp** | The C++ inference engine Ollama wraps | More control, slightly faster. We might drop down to this for optimization later. Same model format (GGUF). |
| **vLLM** | High-throughput production serving | Designed for hundreds of concurrent users. Overkill for single-user assistant. |
| **LocalAI** | Ollama alternative, OpenAI-compatible API | Smaller community, rougher ARM support. |
| **HuggingFace Transformers** | Direct Python model loading | Most flexible, most boilerplate. Good for fine-tuning, not for getting started. |
| **LM Studio** | GUI desktop app | No headless mode. Not suitable for always-on assistant on any hardware. |

**Key point:** Ollama serves models over a standard REST API. Our code talks to that API. If we ever swap Ollama for something else (llama.cpp server, vLLM, etc.), we only change the HTTP endpoint — all our intent routing, evaluation, and benchmarking code stays the same. The abstraction layer we build below makes this trivial.

---

## Model Registry — The Candidates

Instead of picking one model, we maintain a **registry** of candidates. Each entry documents what the model is, its size, its strengths, and hardware constraints. You'll pull several of these and benchmark them against each other.

This registry lives in `models.yaml` and the evaluation framework reads from it.

### Current Candidates (March 2026)

| Model | Params | Q4 Size | Strengths | Weaknesses | Hardware Notes |
|-------|--------|---------|-----------|-----------|---------------|
| **qwen2.5:3b** | 3B | ~2 GB | Best-in-class JSON/function-calling output. Specifically trained for tool use. | Weaker at creative writing than Llama. | Tested on: Mac Metal, NVIDIA Jetson ARM, x86 CUDA. Works everywhere. |
| **llama3.2:3b** | 3B | ~2 GB | Strong general-purpose. Huge community. | JSON output less reliable — sometimes wraps in markdown or adds explanations. | Same compatibility as Qwen. |
| **phi4-mini** | 3.8B | ~2.4 GB | Best reasoning in class (52% AIME math). | Slightly larger. ONNX-optimized ecosystem (Microsoft), less native Ollama love. | Works on Mac/CUDA. Less tested on ARM Linux without ONNX runtime. |
| **gemma3:4b** | 4B | ~2.5 GB | Google's edge-optimized. Good vision support. | Reported compatibility bugs on some NVIDIA ARM boards. | Mac/x86 fine. ARM NVIDIA: test before committing. |
| **deepseek-r1:8b** | 8B | ~5 GB | Incredible reasoning. | Too large for 8GB shared-memory devices alongside other models (Whisper, TTS, OS). | Needs 8GB+ free RAM. Fine on Mac (16-64GB). Tight on small boards. |
| **llama3.2:1b** | 1B | ~0.7 GB | Ultra-fast, ultra-small. | Not smart enough for vague music interpretation. | Runs on anything, including Raspberry Pi. |
| **qwen3:1b** | 1B | ~0.7 GB | Newer architecture than Qwen 2.5. | 1B limits reasoning depth. | Same as above. |
| **mistral-small** | 3B | ~2 GB | Apache 2.0 license. Good instruction following. | Newer, less community testing. | Standard compatibility. |

**The point:** You don't need to decide now. Pull 3-4 of these, run the evaluation framework below, and let the data decide.

---

## Step 1.1 — Setup

```bash
brew install ollama
ollama serve  # In a separate tab, or check if already running: curl http://localhost:11434

# Pull your first model to start experimenting
ollama pull qwen2.5:3b

# Pull 2-3 more for comparison (do this while working on other steps)
ollama pull llama3.2:3b
ollama pull phi4-mini
# Optional extras:
# ollama pull gemma3:4b
# ollama pull mistral-small
```

Interactive test with any model:
```bash
ollama run qwen2.5:3b    # Ctrl+D or /bye to exit
ollama run llama3.2:3b   # Try the same questions, compare
```

Spend 15 minutes with each model you pulled. Ask the same questions to each. Write raw impressions in `notes/first-impressions.md` — which felt smarter? Which gave cleaner outputs?

---

## Step 1.2 — The Model Abstraction Layer

Before writing any experiments, we build a thin abstraction so every piece of code in this project can swap models with one config change.

Create `experiments/llm_client.py`:

```python
"""
Model-agnostic LLM client.

Every script in this project imports from here instead of calling Ollama directly.
To swap models: change the model name. To swap backends: change this file.

Future-proofing:
- If we switch from Ollama to llama.cpp server → change the URL and response parsing here
- If we add OpenAI API as a fallback → add another backend class here
- If we go multi-model → the router calls this with different model names per task
"""

import requests
import json
import time
from dataclasses import dataclass

@dataclass
class LLMResponse:
    text: str
    model: str
    latency: float           # seconds
    tokens_generated: int    # output tokens
    tokens_per_second: float

class LLMClient:
    """
    Unified interface to a local LLM.
    Currently backed by Ollama. Backend is swappable.
    """

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    def generate(
        self,
        prompt: str,
        model: str,
        system: str = "",
        json_mode: bool = False,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            prompt: The user's input
            model: Ollama model tag (e.g., "qwen2.5:3b", "llama3.2:3b")
            system: System prompt (instructions for the model's behavior)
            json_mode: If True, constrains output to valid JSON.
                       Uses Ollama's format flag which modifies token sampling
                       to zero out probabilities of tokens that would break JSON syntax.
            temperature: Controls randomness. 0 = deterministic, 1 = creative.
                        Lower is better for intent classification (we want consistency).
                        Higher is better for conversation (we want variety).
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }

        if system:
            payload["system"] = system

        if json_mode:
            payload["format"] = "json"

        start = time.time()
        response = requests.post(f"{self.base_url}/api/generate", json=payload)
        latency = time.time() - start

        data = response.json()
        text = data.get("response", "")

        # Ollama returns token counts in the response metadata
        eval_count = data.get("eval_count", 0)
        eval_duration = data.get("eval_duration", 1)  # nanoseconds
        tok_per_sec = eval_count / (eval_duration / 1e9) if eval_duration > 0 else 0

        return LLMResponse(
            text=text.strip(),
            model=model,
            latency=latency,
            tokens_generated=eval_count,
            tokens_per_second=tok_per_sec,
        )

    def generate_json(self, prompt: str, model: str, system: str = "", temperature: float = 0.3) -> dict:
        """Generate and parse a JSON response. Lower temperature for consistency."""
        resp = self.generate(prompt, model, system=system, json_mode=True, temperature=temperature)
        return json.loads(resp.text), resp

    def list_models(self) -> list[str]:
        """List all locally available models."""
        response = requests.get(f"{self.base_url}/api/tags")
        return [m["name"] for m in response.json().get("models", [])]


# Singleton for convenience — import this in other scripts
client = LLMClient()
```

This is the only file that knows about Ollama's API. Everything else imports `client` from here.

---

## Step 1.3 — The Model Registry

Create `models.yaml`:

```yaml
# Model Registry — candidates for JARVIS's brain
# Add new models here as they're released. The eval framework reads this file.

models:
  qwen2.5:3b:
    family: "Qwen (Alibaba)"
    params: "3B"
    q4_size_gb: 2.0
    strengths:
      - "Best-in-class structured JSON / function-calling output"
      - "Specifically trained for tool use"
      - "Good multilingual support"
    weaknesses:
      - "Weaker at creative/conversational writing than Llama"
    hardware_constraints:
      min_ram_gb: 4
      gpu_acceleration: ["cuda", "metal", "vulkan"]
      tested_on: ["macOS ARM", "Jetson Orin Nano", "x86 Linux"]
      known_issues: []

  llama3.2:3b:
    family: "Llama (Meta)"
    params: "3B"
    q4_size_gb: 2.0
    strengths:
      - "Strong general-purpose model"
      - "Huge community, lots of fine-tunes available"
      - "Good conversational quality"
    weaknesses:
      - "JSON output less reliable — sometimes adds markdown or explanations"
      - "Needs more prompt engineering for structured output"
    hardware_constraints:
      min_ram_gb: 4
      gpu_acceleration: ["cuda", "metal", "vulkan"]
      tested_on: ["macOS ARM", "Jetson Orin Nano", "x86 Linux"]
      known_issues: []

  phi4-mini:
    family: "Phi (Microsoft)"
    params: "3.8B"
    q4_size_gb: 2.4
    strengths:
      - "Best reasoning in the 3-4B class (52% AIME 2024)"
      - "Excellent at complex, multi-step logic"
    weaknesses:
      - "Slightly larger than 3B models"
      - "Microsoft ecosystem bias — best with ONNX, less Ollama optimization"
    hardware_constraints:
      min_ram_gb: 5
      gpu_acceleration: ["cuda", "metal", "directml"]
      tested_on: ["macOS ARM", "x86 Linux"]
      known_issues:
        - "Less tested on ARM Linux without ONNX runtime"

  gemma3:4b:
    family: "Gemma (Google)"
    params: "4B"
    q4_size_gb: 2.5
    strengths:
      - "Purpose-built for edge/mobile deployment"
      - "Multimodal (text + vision) in same model"
    weaknesses:
      - "Reported compatibility bugs on some NVIDIA ARM boards"
    hardware_constraints:
      min_ram_gb: 5
      gpu_acceleration: ["cuda", "metal"]
      tested_on: ["macOS ARM", "x86 Linux"]
      known_issues:
        - "Errors reported on Jetson Orin Nano Super with JetPack 6.2.1"

  deepseek-r1:8b:
    family: "DeepSeek"
    params: "8B"
    q4_size_gb: 5.0
    strengths:
      - "Incredible reasoning capability for its size"
      - "Surpasses many 14B models on benchmarks"
    weaknesses:
      - "At 5GB, leaves little room for Whisper + TTS on 8GB devices"
      - "Slower inference due to size"
    hardware_constraints:
      min_ram_gb: 8
      gpu_acceleration: ["cuda", "metal"]
      tested_on: ["macOS ARM", "x86 Linux"]
      known_issues:
        - "Too large for 8GB shared-memory boards if running alongside STT+TTS"

  llama3.2:1b:
    family: "Llama (Meta)"
    params: "1B"
    q4_size_gb: 0.7
    strengths:
      - "Ultra-fast, ultra-small"
      - "Runs on almost anything including Raspberry Pi"
    weaknesses:
      - "Limited reasoning depth"
      - "Struggles with vague/creative music requests"
    hardware_constraints:
      min_ram_gb: 2
      gpu_acceleration: ["cuda", "metal", "vulkan", "cpu-only"]
      tested_on: ["macOS ARM", "Raspberry Pi 5", "Jetson Orin Nano", "x86 Linux"]
      known_issues: []

# To add a new model:
# 1. Add entry here
# 2. Run: ollama pull <model_name>
# 3. Run: python experiments/eval_framework.py
# 4. Check results in notes/eval-results/
```

---

## Step 1.4 — The Evaluation Framework

This is what lets you objectively compare models instead of guessing. It runs the same test suite against every model and produces a scored report.

Create `experiments/eval_framework.py`:

```python
"""
Model Evaluation Framework for JARVIS.

Runs a standardized test suite against one or more models and produces
a comparison report. Use this to:
  1. Pick the best model for JARVIS
  2. Re-evaluate when new models are released
  3. Validate that a model swap doesn't break anything
  4. Compare multi-model setups later

Usage:
  python eval_framework.py                    # Evaluate all locally available models
  python eval_framework.py qwen2.5:3b         # Evaluate one model
  python eval_framework.py qwen2.5:3b llama3.2:3b  # Compare two models
"""

import sys
import json
import time
import os
from datetime import datetime
from llm_client import client, LLMResponse

# ─── Test Cases ───────────────────────────────────────────────────
# Each test case has:
#   - input: what the user said
#   - task: what we're testing (intent_classification, song_resolution, json_reliability, conversation)
#   - expected_intent: the correct intent (for intent tests)
#   - expected_contains: strings that should appear in the output (for song/chat tests)
#   - notes: why this test exists

TEST_CASES = [
    # ── Intent Classification: Music Play (specific) ──
    {
        "input": "play Tum Hi Ho",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": ["Tum Hi Ho"],
        "notes": "Direct song request, should be trivial",
    },
    {
        "input": "play Bohemian Rhapsody by Queen",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": ["Bohemian Rhapsody", "Queen"],
        "notes": "Specific song + artist",
    },

    # ── Intent Classification: Music Play (vague — the hard ones) ──
    {
        "input": "play that sad Coldplay song from the space movie",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],  # We'll check this manually or with song resolution
        "notes": "Requires cultural knowledge: Interstellar → Atlas",
    },
    {
        "input": "play something chill for studying",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Mood-based request, no specific song",
    },
    {
        "input": "play that Arijit Singh song everyone cries to",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Requires Bollywood knowledge: probably Tum Hi Ho",
    },

    # ── Intent Classification: Music Control ──
    {
        "input": "pause",
        "task": "intent_classification",
        "expected_intent": "music_control",
        "expected_contains": ["pause"],
        "notes": "Single word command",
    },
    {
        "input": "skip this song",
        "task": "intent_classification",
        "expected_intent": "music_control",
        "expected_contains": ["skip"],
        "notes": "Simple control",
    },
    {
        "input": "turn the volume up",
        "task": "intent_classification",
        "expected_intent": "music_control",
        "expected_contains": ["volume_up"],
        "notes": "Volume control",
    },
    {
        "input": "stop the music",
        "task": "intent_classification",
        "expected_intent": "music_control",
        "expected_contains": ["stop"],
        "notes": "Stop command",
    },

    # ── Intent Classification: Light Control ──
    {
        "input": "turn off the lights",
        "task": "intent_classification",
        "expected_intent": "light_control",
        "expected_contains": ["off"],
        "notes": "Basic light toggle",
    },
    {
        "input": "set the lights to purple",
        "task": "intent_classification",
        "expected_intent": "light_control",
        "expected_contains": ["purple"],
        "notes": "Color command",
    },
    {
        "input": "brightness 30 percent",
        "task": "intent_classification",
        "expected_intent": "light_control",
        "expected_contains": ["30"],
        "notes": "Brightness with number",
    },
    {
        "input": "make the room romantic",
        "task": "intent_classification",
        "expected_intent": "light_control",
        "expected_contains": ["romantic"],
        "notes": "Scene-based — model should map 'romantic' to a scene",
    },
    {
        "input": "movie mode",
        "task": "intent_classification",
        "expected_intent": "light_control",
        "expected_contains": ["movie"],
        "notes": "Scene shorthand",
    },

    # ── Intent Classification: Chat ──
    {
        "input": "what is the meaning of life",
        "task": "intent_classification",
        "expected_intent": "chat",
        "expected_contains": [],
        "notes": "General knowledge question",
    },
    {
        "input": "tell me a joke",
        "task": "intent_classification",
        "expected_intent": "chat",
        "expected_contains": [],
        "notes": "Entertainment request",
    },
    {
        "input": "who won the 2023 cricket world cup",
        "task": "intent_classification",
        "expected_intent": "chat",
        "expected_contains": [],
        "notes": "Factual question",
    },

    # ── Intent Classification: System ──
    {
        "input": "what time is it",
        "task": "intent_classification",
        "expected_intent": "system",
        "expected_contains": ["time"],
        "notes": "System info",
    },

    # ── Edge Cases (ambiguous) ──
    {
        "input": "never gonna give you up",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Song title that sounds like a statement. Should recognize it as a Rick Astley song.",
    },
    {
        "input": "light me up",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Ambiguous: 'light' + 'me up'. This is more likely a song request than a light command.",
    },
    {
        "input": "I'm feeling blue",
        "task": "intent_classification",
        "expected_intent": "chat",
        "expected_contains": [],
        "notes": "Ambiguous: 'blue' could mean light color, but 'feeling blue' is an emotional statement.",
    },
    {
        "input": "make it brighter in here",
        "task": "intent_classification",
        "expected_intent": "light_control",
        "expected_contains": ["brightness"],
        "notes": "Indirect phrasing for brightness up",
    },

    # ── JSON Reliability (does the model return parseable JSON?) ──
    {
        "input": "play some jazz",
        "task": "json_reliability",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Simple request — JSON should be clean",
    },
    {
        "input": "set an alarm for 7 AM tomorrow and also make the lights warm",
        "task": "json_reliability",
        "expected_intent": None,  # Compound request — tricky
        "expected_contains": [],
        "notes": "Multi-intent in one sentence. Does it handle gracefully or break?",
    },

    # ── Song Resolution Quality ──
    {
        "input": "the Coldplay song from Interstellar",
        "task": "song_resolution",
        "expected_contains": ["Atlas"],
        "notes": "Should resolve to Atlas by Coldplay",
    },
    {
        "input": "that song from the end of Fast and Furious 7",
        "task": "song_resolution",
        "expected_contains": ["See You Again"],
        "notes": "Should resolve to See You Again by Wiz Khalifa",
    },
    {
        "input": "that Punjabi song that goes tunak tunak",
        "task": "song_resolution",
        "expected_contains": ["Tunak Tunak Tun"],
        "notes": "Should resolve to Tunak Tunak Tun by Daler Mehndi",
    },
]


# ─── System Prompts ───────────────────────────────────────────────

INTENT_SYSTEM_PROMPT = """You are JARVIS, a smart voice assistant. Classify the user's spoken request into a structured action.

Respond with valid JSON only. No explanation. No markdown.

## Intents

1. "music_play" — Play a song/artist/playlist/genre
   Params: {"query": "search terms", "platform": "youtube|spotify|any"}
   Resolve vague descriptions into specific search terms.

2. "music_control" — Control current playback
   Params: {"action": "pause|resume|skip|stop|volume_up|volume_down"}

3. "light_control" — Change room lights
   Params: {"action": "on|off|brightness|color|scene", "value": "..."}

4. "chat" — General question or conversation
   Params: {"message": "the user's question"}

5. "system" — System info
   Params: {"action": "time|date|weather|alarm|reminder"}

## Format
{"intent": "...", "params": {...}, "response": "Brief spoken acknowledgment. Empty for chat."}

## Examples
User: "play that sad Coldplay song from the space movie"
{"intent": "music_play", "params": {"query": "Atlas Coldplay Interstellar", "platform": "any"}, "response": "Playing Atlas by Coldplay."}

User: "turn the lights blue"
{"intent": "light_control", "params": {"action": "color", "value": "blue"}, "response": "Setting the lights to blue."}

User: "pause"
{"intent": "music_control", "params": {"action": "pause"}, "response": "Paused."}

User: "what's the meaning of life"
{"intent": "chat", "params": {"message": "what is the meaning of life"}, "response": ""}

User: "make the room romantic"
{"intent": "light_control", "params": {"action": "scene", "value": "romantic"}, "response": "Setting the mood."}
"""

SONG_RESOLUTION_PROMPT = """You are a music expert. The user describes a song vaguely.
Figure out which song they mean and return the best search query.
Consider: titles, artists, soundtracks, lyrics, Bollywood, Indian music, viral songs.
Return ONLY the search query. Nothing else."""


# ─── Evaluation Engine ────────────────────────────────────────────

def evaluate_model(model: str, test_cases: list[dict]) -> dict:
    """Run all test cases against a single model and score the results."""

    results = {
        "model": model,
        "timestamp": datetime.now().isoformat(),
        "scores": {
            "intent_accuracy": 0,
            "json_reliability": 0,
            "song_resolution": 0,
            "avg_latency": 0,
            "avg_tok_per_sec": 0,
        },
        "details": [],
    }

    intent_correct = 0
    intent_total = 0
    json_valid = 0
    json_total = 0
    song_correct = 0
    song_total = 0
    latencies = []
    tps_values = []

    for tc in test_cases:
        detail = {"input": tc["input"], "task": tc["task"], "notes": tc.get("notes", "")}

        try:
            if tc["task"] in ("intent_classification", "json_reliability"):
                parsed, resp = client.generate_json(
                    prompt=tc["input"],
                    model=model,
                    system=INTENT_SYSTEM_PROMPT,
                    temperature=0.3,
                )
                detail["output"] = parsed
                detail["latency"] = resp.latency
                detail["tok_per_sec"] = resp.tokens_per_second
                latencies.append(resp.latency)
                tps_values.append(resp.tokens_per_second)

                # JSON reliability — did it parse at all?
                json_total += 1
                json_valid += 1  # If we got here, JSON was valid
                detail["json_valid"] = True

                # Intent accuracy
                if tc["task"] == "intent_classification" and tc.get("expected_intent"):
                    intent_total += 1
                    got_intent = parsed.get("intent", "")
                    detail["expected_intent"] = tc["expected_intent"]
                    detail["got_intent"] = got_intent
                    if got_intent == tc["expected_intent"]:
                        intent_correct += 1
                        detail["intent_correct"] = True
                    else:
                        detail["intent_correct"] = False

                # Check expected_contains in params
                if tc.get("expected_contains"):
                    params_str = json.dumps(parsed.get("params", {})).lower()
                    found = [kw for kw in tc["expected_contains"] if kw.lower() in params_str]
                    detail["expected_keywords"] = tc["expected_contains"]
                    detail["found_keywords"] = found

            elif tc["task"] == "song_resolution":
                resp = client.generate(
                    prompt=f'User: "{tc["input"]}"',
                    model=model,
                    system=SONG_RESOLUTION_PROMPT,
                    temperature=0.3,
                )
                detail["output"] = resp.text
                detail["latency"] = resp.latency
                detail["tok_per_sec"] = resp.tokens_per_second
                latencies.append(resp.latency)
                tps_values.append(resp.tokens_per_second)

                song_total += 1
                if tc.get("expected_contains"):
                    found = any(kw.lower() in resp.text.lower() for kw in tc["expected_contains"])
                    detail["expected"] = tc["expected_contains"]
                    detail["song_correct"] = found
                    if found:
                        song_correct += 1

        except json.JSONDecodeError as e:
            detail["error"] = f"JSON parse failed: {e}"
            detail["json_valid"] = False
            json_total += 1
            if tc["task"] == "intent_classification":
                intent_total += 1
            latencies.append(0)

        except Exception as e:
            detail["error"] = str(e)
            latencies.append(0)

        results["details"].append(detail)

    # Calculate scores
    results["scores"]["intent_accuracy"] = round(intent_correct / max(intent_total, 1) * 100, 1)
    results["scores"]["json_reliability"] = round(json_valid / max(json_total, 1) * 100, 1)
    results["scores"]["song_resolution"] = round(song_correct / max(song_total, 1) * 100, 1)
    results["scores"]["avg_latency"] = round(sum(latencies) / max(len(latencies), 1), 2)
    results["scores"]["avg_tok_per_sec"] = round(sum(tps_values) / max(len(tps_values), 1), 1)

    return results


def print_summary(all_results: list[dict]):
    """Print a comparison table across all evaluated models."""
    print(f"\n{'='*80}")
    print(f"JARVIS Brain — Model Evaluation Report")
    print(f"{'='*80}\n")

    # Header
    header = f"{'Model':<20} {'Intent %':>10} {'JSON %':>10} {'Songs %':>10} {'Latency':>10} {'Tok/s':>10}"
    print(header)
    print("─" * 80)

    for r in all_results:
        s = r["scores"]
        print(f"{r['model']:<20} {s['intent_accuracy']:>9}% {s['json_reliability']:>9}% "
              f"{s['song_resolution']:>9}% {s['avg_latency']:>9}s {s['avg_tok_per_sec']:>9}")

    print("─" * 80)

    # Find best per category
    if len(all_results) > 1:
        print("\nBest per category:")
        for cat, label in [
            ("intent_accuracy", "Intent Classification"),
            ("json_reliability", "JSON Reliability"),
            ("song_resolution", "Song Resolution"),
            ("avg_latency", "Fastest (lowest latency)"),
            ("avg_tok_per_sec", "Throughput (highest tok/s)"),
        ]:
            if cat == "avg_latency":
                best = min(all_results, key=lambda r: r["scores"][cat] if r["scores"][cat] > 0 else 999)
            else:
                best = max(all_results, key=lambda r: r["scores"][cat])
            print(f"  {label}: {best['model']} ({best['scores'][cat]})")


def save_results(all_results: list[dict]):
    """Save detailed results to JSON for later analysis."""
    os.makedirs("../notes/eval-results", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"../notes/eval-results/eval_{timestamp}.json"
    with open(path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nDetailed results saved to: {path}")


# ─── Main ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Determine which models to evaluate
    if len(sys.argv) > 1:
        models_to_eval = sys.argv[1:]
    else:
        # Evaluate all locally available models
        available = client.list_models()
        print(f"Found {len(available)} local models: {', '.join(available)}")
        models_to_eval = available

    all_results = []
    for model in models_to_eval:
        print(f"\n{'─'*40}")
        print(f"Evaluating: {model}")
        print(f"{'─'*40}")
        result = evaluate_model(model, TEST_CASES)
        all_results.append(result)
        s = result["scores"]
        print(f"  Intent: {s['intent_accuracy']}% | JSON: {s['json_reliability']}% | "
              f"Songs: {s['song_resolution']}% | Latency: {s['avg_latency']}s")

    print_summary(all_results)
    save_results(all_results)
```

**How to use it:**

```bash
cd jarvis/01-the-brain/experiments

# Evaluate all models you've pulled
python eval_framework.py

# Or compare specific models
python eval_framework.py qwen2.5:3b llama3.2:3b

# Or test just one
python eval_framework.py phi4-mini
```

It outputs a comparison table and saves detailed per-test results to `notes/eval-results/` so you can track performance over time or dig into specific failures.

---

## Step 1.5 — The Intent Router (Model-Agnostic)

This is the actual component JARVIS uses at runtime. It imports the LLM client and takes the model name as config.

Create `experiments/intent_router.py`:

```python
"""
Model-agnostic intent router.

The model is a parameter, not a hardcoded choice.
In production, this reads from config.yaml.
In testing, the eval framework passes different models in.
"""

import json
from llm_client import client

# Default system prompt — this is your prompt engineering playground.
# Save your best version to best_system_prompt.txt
DEFAULT_SYSTEM_PROMPT = """You are JARVIS, a smart voice assistant. Classify the user's spoken request into a structured action.

Respond with valid JSON only. No explanation. No markdown.

## Intents

1. "music_play" — Play a song/artist/playlist/genre
   Params: {"query": "search terms", "platform": "youtube|spotify|any"}
   Resolve vague descriptions into specific search terms.

2. "music_control" — Control current playback
   Params: {"action": "pause|resume|skip|stop|volume_up|volume_down"}

3. "light_control" — Change room lights
   Params: {"action": "on|off|brightness|color|scene", "value": "..."}

4. "chat" — General question or conversation
   Params: {"message": "the user's question"}

5. "system" — System info
   Params: {"action": "time|date|weather|alarm|reminder"}

## Format
{"intent": "...", "params": {...}, "response": "Brief spoken acknowledgment. Empty for chat."}

## Examples
User: "play that sad Coldplay song from the space movie"
{"intent": "music_play", "params": {"query": "Atlas Coldplay Interstellar", "platform": "any"}, "response": "Playing Atlas by Coldplay."}

User: "turn the lights blue"
{"intent": "light_control", "params": {"action": "color", "value": "blue"}, "response": "Setting the lights to blue."}

User: "pause"
{"intent": "music_control", "params": {"action": "pause"}, "response": "Paused."}

User: "what's the meaning of life"
{"intent": "chat", "params": {"message": "what is the meaning of life"}, "response": ""}

User: "make the room romantic"
{"intent": "light_control", "params": {"action": "scene", "value": "romantic"}, "response": "Setting the mood."}
"""


class IntentRouter:
    def __init__(self, model: str, system_prompt: str = DEFAULT_SYSTEM_PROMPT):
        self.model = model
        self.system_prompt = system_prompt

    def classify(self, user_input: str) -> dict:
        """Classify a voice command into a structured intent."""
        parsed, response_meta = client.generate_json(
            prompt=user_input,
            model=self.model,
            system=self.system_prompt,
            temperature=0.3,
        )
        # Attach metadata for debugging/logging
        parsed["_meta"] = {
            "model": self.model,
            "latency": response_meta.latency,
            "tok_per_sec": response_meta.tokens_per_second,
        }
        return parsed

    def swap_model(self, new_model: str):
        """Hot-swap the model. Useful for A/B testing or multi-model setups."""
        self.model = new_model


# ─── Interactive Testing ──────────────────────────────────────────

if __name__ == "__main__":
    import sys

    model = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:3b"
    router = IntentRouter(model=model)

    print(f"Intent Router — using model: {model}")
    print(f"Type a command (or 'quit' to exit, 'swap <model>' to change model)\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() == "quit":
            break
        if user_input.lower().startswith("swap "):
            new_model = user_input.split(" ", 1)[1]
            router.swap_model(new_model)
            print(f"Swapped to: {new_model}\n")
            continue

        try:
            result = router.classify(user_input)
            meta = result.pop("_meta", {})
            print(f"  Intent:   {result.get('intent')}")
            print(f"  Params:   {json.dumps(result.get('params', {}))}")
            print(f"  Response: {result.get('response', '')}")
            print(f"  [{meta.get('model')} | {meta.get('latency', 0):.2f}s | {meta.get('tok_per_sec', 0):.0f} tok/s]\n")
        except Exception as e:
            print(f"  Error: {e}\n")
```

**Usage:**
```bash
# Start with qwen
python intent_router.py qwen2.5:3b

# Or start with llama
python intent_router.py llama3.2:3b

# Swap models live during the session:
# You: swap phi4-mini
# You: play something chill
```

---

## Step 1.6 — Add Your Own Test Cases

The eval framework's power comes from YOUR test cases. The ones I provided are a starting point. As you test, you'll find failures — add those as test cases.

Create `experiments/my_test_cases.py`:

```python
"""
Your custom test cases. Add every failure you discover here.
The eval framework can import this alongside the default test suite.

Pattern:
  - Found a command that model X gets wrong? Add it here.
  - Found an edge case? Add it here.
  - Found something that works on Qwen but not Llama? Add it here.
  - These become your regression tests when you swap models.
"""

MY_TEST_CASES = [
    # Add your own test cases here as you discover them.
    # Copy the format from eval_framework.py TEST_CASES.
    #
    # Example:
    # {
    #     "input": "the command that failed",
    #     "task": "intent_classification",
    #     "expected_intent": "music_play",
    #     "expected_contains": ["expected", "keywords"],
    #     "notes": "Why this test exists — what broke",
    # },
]
```

---

## Exercises

1. **Pull 3 models** (`qwen2.5:3b`, `llama3.2:3b`, and one other). Run `eval_framework.py`. See which wins.
2. **Find 5 failures.** Use the interactive `intent_router.py`, try weird inputs, find things that break. Add them to `my_test_cases.py`.
3. **Iterate the system prompt.** Tweak it, re-run the eval, see if scores improve. Save your best version in `best_system_prompt.txt`.
4. **Read the detailed JSON results** in `notes/eval-results/`. Look at which specific tests each model fails. Patterns emerge.

---

## Checkpoint — Ready for Module 2 When:

- [ ] You can explain quantization, tokens, transformer attention, and CUDA acceleration
- [ ] Ollama running, 2-3 models pulled
- [ ] Eval framework runs and produces a comparison report
- [ ] You've identified which model scores best on intent classification
- [ ] You've identified which model scores best on song resolution
- [ ] You've found at least 5 edge-case failures and added them to `my_test_cases.py`
- [ ] You have a leading model candidate (but haven't committed to it as final)
- [ ] `best_system_prompt.txt` saved with your iterated prompt

---

## Files You Should Have

```
01-the-brain/
├── models.yaml                 # Model registry with hardware constraints
├── notes/
│   ├── first-impressions.md
│   ├── eval-results/
│   │   └── eval_YYYYMMDD_HHMMSS.json
│   └── ... (your notes)
├── experiments/
│   ├── llm_client.py           # Model-agnostic LLM client (THE abstraction layer)
│   ├── eval_framework.py       # Cross-model evaluation & scoring
│   ├── intent_router.py        # The actual intent router (model is config)
│   ├── my_test_cases.py        # Your custom regression tests
│   └── best_system_prompt.txt  # Your best prompt so far
└── README.md (this file)
```

---

## Future: Multi-Model Architecture

When you're ready (post-MVP), the abstraction layer supports this naturally:

```python
# Different models for different tasks
intent_model = "qwen2.5:3b"     # Best at JSON/structured output
chat_model = "llama3.2:3b"      # Best at natural conversation
song_model = "phi4-mini"         # Best at reasoning through vague requests

# The router picks the right model per task
router = IntentRouter(model=intent_model)
intent = router.classify(user_input)

if intent["intent"] == "chat":
    response = client.generate(intent["params"]["message"], model=chat_model)
elif intent["intent"] == "music_play":
    query = client.generate(f"Resolve: {intent['params']['query']}", model=song_model)
```

This is a one-afternoon change because the abstraction is already there. But don't do this until single-model is solid and you have eval data showing multi-model actually helps.
