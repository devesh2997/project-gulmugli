# Module 3: The Voice — Text-to-Speech & Audio Output

**What this is:** The output layer — converting the assistant's text responses into natural-sounding speech and playing them through a speaker.

**Why it matters:** This is what makes JARVIS feel alive. Bad TTS = robotic and annoying. Good TTS = charming and impressive. On demo day, the voice IS the product.

**Time estimate:** 3–4 hours across Week 2–3

**Prerequisites:** Module 1 (The Brain) recommended but not required.

---

## What You'll Learn

1. How neural TTS works (Piper's VITS architecture)
2. How to install and run Piper TTS locally on Mac
3. Choosing and testing different voices
4. Audio playback in Python
5. Bluetooth audio routing (conceptual on Mac, real on Jetson later)
6. Streaming TTS for faster perceived response time

---

## Learning Path

### 3.1 — Install Piper TTS on Mac

```bash
# Install Piper
pip install piper-tts

# Test it immediately
echo "Hello, I am JARVIS, your personal assistant." | piper \
  --model en_US-amy-medium \
  --output_file test_voice.wav

# Play it
afplay test_voice.wav  # macOS built-in player
```

If the pip install doesn't work on Mac (Piper has ARM Linux binaries), use the Python API instead:

```bash
# Alternative: use piper directly via Python
pip install piper-tts

# Or use the pre-built binaries
# Download from: https://github.com/rhasspy/piper/releases
```

### 3.2 — Explore Voice Models

Piper has dozens of voices. The voice you pick will define JARVIS's personality.

**Voice models catalog:** https://github.com/rhasspy/piper/blob/master/VOICES.md

```python
# experiments/voice_sampler.py
"""Download and test multiple voices to find the right one for JARVIS."""
import subprocess
import os

# Test phrase — use something that sounds natural for an assistant
TEST_PHRASES = [
    "Hello! I'm JARVIS, your personal assistant. How can I help you today?",
    "Playing Tum Hi Ho by Arijit Singh. Great choice.",
    "I've set the lights to warm orange at 60 percent brightness.",
    "The answer to your question is: approximately 42.",
    "I'm sorry, I didn't quite catch that. Could you say that again?",
]

# Good voice options to try (download from Piper releases):
# - en_US-amy-medium     (female, American, warm)
# - en_US-ryan-medium    (male, American, clear)
# - en_US-lessac-medium  (male, American, professional)
# - en_GB-alan-medium    (male, British, sophisticated — very JARVIS-like)
# - en_GB-cori-medium    (female, British, friendly)

VOICE = "en_GB-alan-medium"  # Start with the British male — feels like JARVIS

for i, phrase in enumerate(TEST_PHRASES):
    output_file = f"voice_test_{i}.wav"
    subprocess.run([
        "piper",
        "--model", VOICE,
        "--output_file", output_file
    ], input=phrase.encode(), check=True)
    print(f"Generated: {output_file} — '{phrase[:50]}...'")

print("\nPlay each file and decide which voice feels right!")
```

**Exercise:** Test at least 3 different voices. Play them to someone (a friend, not the girlfriend — no spoilers). Ask which one sounds most like a personal AI assistant. Document your choice in `notes/voice-selection.md`.

### 3.3 — Python TTS Wrapper

Build a reusable TTS function:

```python
# experiments/tts_wrapper.py
import subprocess
import tempfile
import os
import time

class TextToSpeech:
    def __init__(self, model: str = "en_GB-alan-medium"):
        self.model = model

    def speak(self, text: str):
        """Convert text to speech and play it."""
        start = time.time()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            # Generate audio
            subprocess.run(
                ["piper", "--model", self.model, "--output_file", f.name],
                input=text.encode(),
                check=True,
                capture_output=True
            )

            gen_time = time.time() - start
            print(f"[TTS generated in {gen_time:.2f}s]")

            # Play audio (macOS)
            subprocess.run(["afplay", f.name])

            # Clean up
            os.unlink(f.name)

    def speak_to_file(self, text: str, output_path: str):
        """Generate speech and save to file."""
        subprocess.run(
            ["piper", "--model", self.model, "--output_file", output_path],
            input=text.encode(),
            check=True,
            capture_output=True
        )

# Test
tts = TextToSpeech()
tts.speak("Playing Tum Hi Ho by Arijit Singh. Beautiful song choice.")
tts.speak("I've set the lights to warm purple at forty percent brightness.")
tts.speak("The time is currently 3:45 PM. You have no upcoming reminders.")
```

**Exercise:** Measure the latency — how long from calling `speak()` to hearing the first audio? On Mac this will be slower than on Jetson, but note it down. Anything under 2 seconds total (generation + playback start) will feel responsive.

### 3.4 — Audio Playback Alternatives

`afplay` is Mac-only. On the Jetson, we'll use PipeWire. Get familiar with cross-platform options:

```python
# experiments/playback_options.py
import sounddevice as sd
import numpy as np
import wave

def play_wav(filepath: str):
    """Cross-platform WAV playback using sounddevice."""
    with wave.open(filepath, 'rb') as wf:
        sample_rate = wf.getframerate()
        audio_data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)

    sd.play(audio_data, samplerate=sample_rate)
    sd.wait()  # Block until playback finishes

# Test
play_wav("voice_test_0.wav")
```

This approach works on both Mac and Linux/Jetson. On the Jetson, `sounddevice` will route through PipeWire to the Bluetooth speaker.

### 3.5 — Bluetooth Speaker (Conceptual)

You can't fully test BT audio routing on Mac the way it'll work on the Jetson, but understand the concept:

**On Mac:** Audio → macOS audio system → Bluetooth speaker (automatic if paired)
**On Jetson:** Audio → PipeWire → BlueZ → Bluetooth speaker

The key thing to set up later (Module 5) is:
1. Pair the speaker via `bluetoothctl`
2. Set it as the default PipeWire output sink
3. All `sounddevice` / `pw-play` output automatically routes there

**Exercise:** If you have a Bluetooth speaker, pair it with your Mac and verify that `afplay` and `sounddevice` playback goes to it. Note: this "just works" on Mac. It'll need more setup on Jetson.

### 3.6 — Response Personality

This is where JARVIS starts feeling like a character, not a tool. The Brain generates text, but HOW it sounds depends on what text you feed to TTS.

```python
# experiments/personality_test.py
"""
Compare flat responses vs. personality-rich responses.
The difference in user experience is MASSIVE.
"""

# Flat (boring)
flat_responses = [
    "Playing Tum Hi Ho.",
    "Lights set to blue.",
    "The time is 3 PM.",
]

# With personality (engaging)
personality_responses = [
    "Ah, Tum Hi Ho — excellent taste. Playing it now.",
    "Blue it is. The room looks gorgeous.",
    "It's 3 in the afternoon. Perfect time for chai, if you ask me.",
]

tts = TextToSpeech()
for flat, personal in zip(flat_responses, personality_responses):
    print(f"\n--- Flat ---")
    tts.speak(flat)
    print(f"\n--- With personality ---")
    tts.speak(personal)
    input("Press Enter to continue...")
```

**Exercise:** Listen to both versions. The personality version is what makes this a gift, not just a gadget. This personality will come from the LLM's system prompt (Module 1), but hearing it spoken makes it real. Start thinking about how you want JARVIS to sound personality-wise. Write thoughts in `notes/personality-direction.md`.

---

## Checkpoint — You're Ready When:

- [ ] Piper TTS is installed and generating speech on your Mac
- [ ] You've chosen a voice that feels right for JARVIS
- [ ] Your TTS wrapper function works reliably
- [ ] You understand the generation latency on your Mac
- [ ] You've thought about JARVIS's personality and tone
- [ ] Audio playback works via sounddevice (cross-platform approach)

---

## Files You Should Have Created

```
03-the-voice/
├── notes/
│   ├── voice-selection.md
│   └── personality-direction.md
├── experiments/
│   ├── voice_sampler.py
│   ├── tts_wrapper.py
│   ├── playback_options.py
│   ├── personality_test.py
│   ├── voice_test_0.wav
│   ├── voice_test_1.wav
│   └── ...
└── README.md (this file)
```
