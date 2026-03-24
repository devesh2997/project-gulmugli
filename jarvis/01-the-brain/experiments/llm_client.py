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

    def generate_json(self, prompt: str, model: str, system: str = "", temperature: float = 0.3) -> tuple[dict, LLMResponse]:
        """Generate and parse a JSON response. Lower temperature for consistency."""
        resp = self.generate(prompt, model, system=system, json_mode=True, temperature=temperature)
        return json.loads(resp.text), resp

    def list_models(self) -> list[str]:
        """List all locally available models."""
        response = requests.get(f"{self.base_url}/api/tags")
        return [m["name"] for m in response.json().get("models", [])]


# Singleton for convenience — import this in other scripts
client = LLMClient()
