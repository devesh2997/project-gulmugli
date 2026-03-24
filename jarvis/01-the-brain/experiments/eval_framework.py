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

# ─── System Prompts ───────────────────────────────────────────────

INTENT_SYSTEM_PROMPT = """You are JARVIS, a smart voice assistant used in India. Classify the user's spoken request into a structured action.

The user speaks in English, Hindi, or Hinglish (mixed Hindi-English). You must understand all three.

Respond with valid JSON only. No explanation. No markdown.

## Intents

1. "music_play" — Play a song/artist/playlist/genre
   Params: {"query": "search terms for YouTube/Spotify", "platform": "youtube|spotify|any"}
   Resolve vague descriptions into specific search terms. If user describes a song without naming it, figure out the song.
   For Hindi/Hinglish: translate the intent but keep song/artist names as-is.

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

User: "woh Arijit Singh ka dard bhara gaana laga do"
{"intent": "music_play", "params": {"query": "Tum Hi Ho Arijit Singh", "platform": "any"}, "response": "Playing Tum Hi Ho by Arijit Singh."}

User: "turn the lights blue"
{"intent": "light_control", "params": {"action": "color", "value": "blue"}, "response": "Setting the lights to blue."}

User: "pause"
{"intent": "music_control", "params": {"action": "pause"}, "response": "Paused."}

User: "what's the meaning of life"
{"intent": "chat", "params": {"message": "what is the meaning of life"}, "response": ""}

User: "make the room romantic"
{"intent": "light_control", "params": {"action": "scene", "value": "romantic"}, "response": "Setting the mood."}

User: "light band karo"
{"intent": "light_control", "params": {"action": "off"}, "response": "Lights off."}
"""

SONG_RESOLUTION_PROMPT = """You are a music expert with deep knowledge of Bollywood, Indian indie, Punjabi, and Western music.
The user describes a song vaguely — sometimes in Hindi, Hinglish, or English.
Figure out which song they mean and return the best YouTube search query.
Consider: titles, artists, soundtracks, lyrics, Bollywood movies, viral songs, Indian music culture.
Return ONLY the search query. Nothing else."""


# ─── Test Cases ───────────────────────────────────────────────────
# Each test case has:
#   - input: what the user said (as transcribed by STT)
#   - task: what we're testing
#   - expected_intent: the correct intent (for intent tests)
#   - expected_contains: strings that should appear in the output
#   - notes: why this test exists

TEST_CASES = [
    # ═══════════════════════════════════════════════════════════════
    # ENGLISH — Direct commands
    # ═══════════════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════════════
    # ENGLISH — Vague/descriptive music requests
    # ═══════════════════════════════════════════════════════════════
    {
        "input": "play that sad Coldplay song from the space movie",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Requires cultural knowledge: Interstellar → Atlas or A Sky Full of Stars",
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
        "notes": "Requires Bollywood knowledge: probably Tum Hi Ho or Channa Mereya",
    },
    {
        "input": "play that song that goes I'm just a kid and life is a nightmare",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Lyric-based reference: I'm Just a Kid by Simple Plan",
    },

    # ═══════════════════════════════════════════════════════════════
    # HINDI — Pure Hindi commands (as Whisper might transcribe them)
    # ═══════════════════════════════════════════════════════════════
    {
        "input": "woh Arijit Singh ka dard bhara gaana laga do",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Hindi: 'play that painful Arijit Singh song' → Tum Hi Ho / Channa Mereya",
    },
    {
        "input": "kuch romantic sa bajao",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Hindi: 'play something romantic'. Mood request in Hindi.",
    },
    {
        "input": "gaana band karo",
        "task": "intent_classification",
        "expected_intent": "music_control",
        "expected_contains": ["stop"],
        "notes": "Hindi: 'stop the song'. Direct control in Hindi.",
    },
    {
        "input": "light band karo",
        "task": "intent_classification",
        "expected_intent": "light_control",
        "expected_contains": ["off"],
        "notes": "Hindi: 'turn off the light'",
    },
    {
        "input": "awaaz badha do thoda",
        "task": "intent_classification",
        "expected_intent": "music_control",
        "expected_contains": ["volume_up"],
        "notes": "Hindi: 'increase the volume a bit'",
    },
    {
        "input": "awaaz kam karo",
        "task": "intent_classification",
        "expected_intent": "music_control",
        "expected_contains": ["volume_down"],
        "notes": "Hindi: 'reduce the volume'",
    },
    {
        "input": "woh gaana laga do jisme woh bolta hai senorita",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Hindi: 'play that song where he says senorita' → Señorita by Shawn Mendes & Camila Cabello",
    },
    {
        "input": "neeli light kar do",
        "task": "intent_classification",
        "expected_intent": "light_control",
        "expected_contains": ["blue"],
        "notes": "Hindi: 'make the light blue'. 'neeli' = blue in Hindi.",
    },
    {
        "input": "aaj ka din kaisa hai",
        "task": "intent_classification",
        "expected_intent": "chat",
        "expected_contains": [],
        "notes": "Hindi: 'how is today' — general chat, NOT system/weather.",
    },

    # ═══════════════════════════════════════════════════════════════
    # HINGLISH — Mixed Hindi-English (most realistic for Indian users)
    # ═══════════════════════════════════════════════════════════════
    {
        "input": "yaar woh sad wala song play kar do na",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Hinglish: 'bro play that sad song'. Extremely vague but common.",
    },
    {
        "input": "woh KK ka last concert wala gaana play karo",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Hinglish: 'play that song from KK's last concert' → Pal by KK (his last performance). Tests Indian pop culture knowledge.",
    },
    {
        "input": "bhai kuch Punjabi bajao party wala",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Hinglish: 'bro play some Punjabi party song'. Genre + mood in Hinglish.",
    },
    {
        "input": "room ka mood change karo romantic wala",
        "task": "intent_classification",
        "expected_intent": "light_control",
        "expected_contains": ["romantic"],
        "notes": "Hinglish: 'change the room mood to romantic'. Scene request.",
    },
    {
        "input": "next song laga do",
        "task": "intent_classification",
        "expected_intent": "music_control",
        "expected_contains": ["skip"],
        "notes": "Hinglish: 'play the next song' → skip intent.",
    },
    {
        "input": "lights thoda dim karo",
        "task": "intent_classification",
        "expected_intent": "light_control",
        "expected_contains": ["brightness"],
        "notes": "Hinglish: 'dim the lights a bit'. Brightness control.",
    },
    {
        "input": "woh movie wala gaana laga do jisme Ranbir Kapoor pagal ho jaata hai",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Hinglish: 'play that movie song where Ranbir Kapoor goes crazy' → likely Ae Dil Hai Mushkil or Badtameez Dil",
    },
    {
        "input": "Atif Aslam ka woh gaana jisme woh rota hai chhod ke jaane ke baad",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Hinglish: 'that Atif Aslam song where he cries after being left' → Tere Sang Yaara / Pehli Nazar Mein",
    },
    {
        "input": "woh old Bollywood wala romantic song, woh Shahrukh Khan movie se hai",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Hinglish: vague SRK movie song. Tests if model generates a reasonable search query even when it can't pin down ONE song.",
    },

    # ═══════════════════════════════════════════════════════════════
    # ENGLISH — Music Control
    # ═══════════════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════════════
    # ENGLISH — Light Control
    # ═══════════════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════════════
    # Chat & System
    # ═══════════════════════════════════════════════════════════════
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
    {
        "input": "what time is it",
        "task": "intent_classification",
        "expected_intent": "system",
        "expected_contains": ["time"],
        "notes": "System info",
    },

    # ═══════════════════════════════════════════════════════════════
    # Edge Cases — Ambiguous inputs
    # ═══════════════════════════════════════════════════════════════
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
    {
        "input": "woh dhoop wala gaana, Agar Tum Saath Ho nahi, woh doosra wala",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Hinglish: 'that sunshine song, NOT Agar Tum Saath Ho, the other one'. Negation + vague = very hard.",
    },
    {
        "input": "kuch bhi laga do mujhe kya pata",
        "task": "intent_classification",
        "expected_intent": "music_play",
        "expected_contains": [],
        "notes": "Hinglish: 'play anything, I don't care'. Should still be music_play with a generic query.",
    },

    # ═══════════════════════════════════════════════════════════════
    # JSON Reliability
    # ═══════════════════════════════════════════════════════════════
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
        "expected_intent": None,
        "expected_contains": [],
        "notes": "Multi-intent in one sentence. Does it handle gracefully or break?",
    },
    {
        "input": "bhai gaana laga aur light bhi dim kar thodi",
        "task": "json_reliability",
        "expected_intent": None,
        "expected_contains": [],
        "notes": "Hinglish multi-intent: 'play a song AND dim the lights'. Compound request in Hindi.",
    },

    # ═══════════════════════════════════════════════════════════════
    # Song Resolution — can the model figure out which song?
    # ═══════════════════════════════════════════════════════════════
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
    {
        "input": "woh gaana jisme ladka train ke peechhe bhaagta hai",
        "task": "song_resolution",
        "expected_contains": ["Chaiyya Chaiyya"],
        "notes": "Hindi: 'the song where the guy runs behind/on the train' → Chaiyya Chaiyya from Dil Se",
    },
    {
        "input": "that song from YJHD when they're in the mountains",
        "task": "song_resolution",
        "expected_contains": ["Kabira"],
        "notes": "YJHD = Yeh Jawaani Hai Deewani. Mountain scene → Kabira or Dilliwaali Girlfriend",
    },
    {
        "input": "Honey Singh ka woh gaana brown rang wala",
        "task": "song_resolution",
        "expected_contains": ["Brown Rang"],
        "notes": "Hinglish: Should resolve to Brown Rang by Yo Yo Honey Singh",
    },
    {
        "input": "that viral song from Money Heist, the Spanish one",
        "task": "song_resolution",
        "expected_contains": ["Bella Ciao"],
        "notes": "Should resolve to Bella Ciao",
    },
    {
        "input": "Arijit ka woh breakup song, Ae Dil nahi, doosra wala",
        "task": "song_resolution",
        "expected_contains": [],
        "notes": "Hinglish: 'Arijit's breakup song, NOT Ae Dil, the other one' → Channa Mereya / Tum Hi Ho. Hard — tests negation comprehension.",
    },
]


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
            "hindi_intent_accuracy": 0,
            "avg_latency": 0,
            "avg_tok_per_sec": 0,
        },
        "details": [],
    }

    intent_correct = 0
    intent_total = 0
    hindi_correct = 0
    hindi_total = 0
    json_valid = 0
    json_total = 0
    song_correct = 0
    song_total = 0
    latencies = []
    tps_values = []

    # Detect Hindi/Hinglish tests by checking for Hindi words
    hindi_markers = [
        "woh", "karo", "laga", "bajao", "gaana", "bhai", "yaar",
        "kuch", "thoda", "band", "awaaz", "neeli", "aaj", "mujhe",
        "doosra", "dhoop", "pata",
    ]

    def is_hindi_input(text: str) -> bool:
        words = text.lower().split()
        return any(w in hindi_markers for w in words)

    for i, tc in enumerate(test_cases):
        detail = {
            "index": i,
            "input": tc["input"],
            "task": tc["task"],
            "notes": tc.get("notes", ""),
            "is_hindi": is_hindi_input(tc["input"]),
        }

        try:
            if tc["task"] in ("intent_classification", "json_reliability"):
                parsed, resp = client.generate_json(
                    prompt=tc["input"],
                    model=model,
                    system=INTENT_SYSTEM_PROMPT,
                    temperature=0.3,
                )
                detail["output"] = parsed
                detail["raw_text"] = resp.text
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

                    # Track Hindi accuracy separately
                    if detail["is_hindi"]:
                        hindi_total += 1
                        if got_intent == tc["expected_intent"]:
                            hindi_correct += 1

                # Check expected_contains in params
                if tc.get("expected_contains"):
                    params_str = json.dumps(parsed.get("params", {})).lower()
                    response_str = parsed.get("response", "").lower()
                    search_str = params_str + " " + response_str
                    found = [kw for kw in tc["expected_contains"] if kw.lower() in search_str]
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
                if detail.get("is_hindi"):
                    hindi_total += 1
            latencies.append(0)

        except Exception as e:
            detail["error"] = str(e)
            latencies.append(0)

        results["details"].append(detail)

        # Progress indicator
        status = "✓" if detail.get("intent_correct") or detail.get("song_correct") or detail.get("json_valid") else "✗"
        if "error" in detail:
            status = "✗"
        print(f"  [{i+1}/{len(test_cases)}] {status} {tc['input'][:60]}...")

    # Calculate scores
    results["scores"]["intent_accuracy"] = round(intent_correct / max(intent_total, 1) * 100, 1)
    results["scores"]["json_reliability"] = round(json_valid / max(json_total, 1) * 100, 1)
    results["scores"]["song_resolution"] = round(song_correct / max(song_total, 1) * 100, 1)
    results["scores"]["hindi_intent_accuracy"] = round(hindi_correct / max(hindi_total, 1) * 100, 1)
    results["scores"]["avg_latency"] = round(sum(latencies) / max(len(latencies), 1), 2)
    results["scores"]["avg_tok_per_sec"] = round(sum(tps_values) / max(len(tps_values), 1), 1)
    results["scores"]["total_tests"] = len(test_cases)
    results["scores"]["intent_tests"] = intent_total
    results["scores"]["hindi_tests"] = hindi_total
    results["scores"]["song_tests"] = song_total

    return results


def print_summary(all_results: list[dict]):
    """Print a comparison table across all evaluated models."""
    print(f"\n{'='*90}")
    print(f"JARVIS Brain — Model Evaluation Report")
    print(f"{'='*90}\n")

    # Header
    header = f"{'Model':<20} {'Intent %':>10} {'Hindi %':>10} {'JSON %':>10} {'Songs %':>10} {'Latency':>10} {'Tok/s':>10}"
    print(header)
    print("─" * 90)

    for r in all_results:
        s = r["scores"]
        print(f"{r['model']:<20} {s['intent_accuracy']:>9}% {s['hindi_intent_accuracy']:>9}% "
              f"{s['json_reliability']:>9}% {s['song_resolution']:>9}% "
              f"{s['avg_latency']:>9}s {s['avg_tok_per_sec']:>9}")

    print("─" * 90)

    # Find best per category
    if len(all_results) > 1:
        print("\nBest per category:")
        for cat, label in [
            ("intent_accuracy", "Intent Classification"),
            ("hindi_intent_accuracy", "Hindi/Hinglish Understanding"),
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

    # Print failures for debugging
    print(f"\n{'='*90}")
    print("FAILURES & INTERESTING RESULTS")
    print(f"{'='*90}")
    for r in all_results:
        failures = [d for d in r["details"] if d.get("intent_correct") == False or d.get("song_correct") == False or "error" in d]
        if failures:
            print(f"\n  {r['model']} — {len(failures)} issues:")
            for f in failures:
                print(f"    Input: {f['input']}")
                if "error" in f:
                    print(f"    Error: {f['error']}")
                elif f.get("intent_correct") == False:
                    print(f"    Expected: {f.get('expected_intent')} | Got: {f.get('got_intent')}")
                elif f.get("song_correct") == False:
                    print(f"    Expected: {f.get('expected')} | Got: {f.get('output', '')[:80]}")
                print()


def save_results(all_results: list[dict]):
    """Save detailed results to JSON for later analysis."""
    os.makedirs("../notes/eval-results", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"../notes/eval-results/eval_{timestamp}.json"
    with open(path, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\nDetailed results saved to: {path}")


# ─── Main ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Optionally import custom test cases
    try:
        from my_test_cases import MY_TEST_CASES
        if MY_TEST_CASES:
            all_tests = TEST_CASES + MY_TEST_CASES
            print(f"Loaded {len(MY_TEST_CASES)} custom test cases + {len(TEST_CASES)} default = {len(all_tests)} total")
        else:
            all_tests = TEST_CASES
            print(f"Running {len(all_tests)} default test cases")
    except ImportError:
        all_tests = TEST_CASES
        print(f"Running {len(all_tests)} default test cases")

    # Determine which models to evaluate
    if len(sys.argv) > 1:
        models_to_eval = sys.argv[1:]
    else:
        # Evaluate all locally available models
        available = client.list_models()
        print(f"Found {len(available)} local models: {', '.join(available)}")
        models_to_eval = available

    if not models_to_eval:
        print("No models found! Pull some models first:")
        print("  ollama pull qwen2.5:3b")
        print("  ollama pull llama3.2:3b")
        sys.exit(1)

    all_results = []
    for model in models_to_eval:
        print(f"\n{'━'*60}")
        print(f"  Evaluating: {model}")
        print(f"{'━'*60}")
        result = evaluate_model(model, all_tests)
        all_results.append(result)
        s = result["scores"]
        print(f"\n  Summary: Intent={s['intent_accuracy']}% | Hindi={s['hindi_intent_accuracy']}% | "
              f"JSON={s['json_reliability']}% | Songs={s['song_resolution']}% | "
              f"Latency={s['avg_latency']}s | {s['avg_tok_per_sec']} tok/s")

    print_summary(all_results)
    save_results(all_results)
