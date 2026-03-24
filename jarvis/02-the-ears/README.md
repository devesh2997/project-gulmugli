# Module 2: The Ears — Speech-to-Text & Wake Word

**What this is:** The audio input pipeline — capturing your voice, detecting the wake word, and converting speech to text that the Brain can process.

**Why it matters:** The entire user experience starts here. If the mic doesn't hear you, or the transcription is wrong, nothing else matters.

**Time estimate:** 4–6 hours across Weeks 2–3

**Prerequisites:** Complete Module 1 (The Brain) first.

---

## What You'll Learn

1. How speech-to-text models work (Whisper architecture basics)
2. How to run faster-whisper locally on your Mac
3. What wake word detection is and how OpenWakeWord works
4. Audio recording in Python (PyAudio / sounddevice)
5. Voice Activity Detection (VAD) — knowing when someone stopped talking
6. The full pipeline: always-listening → wake word → record → transcribe

---

## Learning Path

### 2.1 — Install Dependencies on Mac

```bash
# Install PortAudio (required for PyAudio)
brew install portaudio

# Python packages
pip install faster-whisper pyaudio sounddevice numpy openwakeword
```

If PyAudio gives trouble on Mac, use sounddevice instead — it's more Mac-friendly.

### 2.2 — Record Your Own Voice

Before any AI, just make sure you can capture audio in Python.

```python
# experiments/basic_recording.py
import sounddevice as sd
import numpy as np
import wave

SAMPLE_RATE = 16000  # 16kHz is standard for speech
DURATION = 5  # seconds

print("Recording for 5 seconds... speak now!")
audio = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE,
               channels=1, dtype='int16')
sd.wait()
print("Done!")

# Save to WAV file
with wave.open("test_recording.wav", "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)  # 16-bit = 2 bytes
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(audio.tobytes())

print("Saved to test_recording.wav — play it back to verify")
```

**Exercise:** Record yourself saying 5 different commands ("play some music", "turn the lights blue", etc.). Play them back. Are they clear? Save them in `experiments/test_recordings/` — you'll use these throughout this module.

### 2.3 — Speech-to-Text with faster-whisper

Now transcribe those recordings.

```python
# experiments/stt_basics.py
from faster_whisper import WhisperModel

# On Mac, use CPU. On Jetson later, we'll switch to CUDA.
# "base" is fast for testing. "medium" is what we'll use in production.
model = WhisperModel("base", device="cpu", compute_type="int8")

def transcribe(audio_path: str) -> str:
    segments, info = model.transcribe(audio_path, language="en")
    text = " ".join(segment.text for segment in segments)
    return text.strip()

# Test with your recordings
import glob
for wav_file in sorted(glob.glob("test_recordings/*.wav")):
    result = transcribe(wav_file)
    print(f"{wav_file}: {result}")
```

**Exercise:** Test with different model sizes. The key trade-off is speed vs. accuracy:

```python
# experiments/stt_model_comparison.py
import time

for model_size in ["tiny", "base", "small", "medium"]:
    print(f"\n--- {model_size} ---")
    m = WhisperModel(model_size, device="cpu", compute_type="int8")

    start = time.time()
    text = transcribe_with_model(m, "test_recordings/sample.wav")
    elapsed = time.time() - start

    print(f"Time: {elapsed:.2f}s")
    print(f"Text: {text}")
```

Note: On your Mac (CPU), "medium" will be slow (5-10 seconds). On the Jetson with GPU, it'll be under 1 second. Don't worry about speed on Mac — focus on accuracy.

**Write your findings in `notes/model-size-comparison.md`.**

### 2.4 — Test with Indian English

This is critical. Record yourself speaking naturally — the way you actually talk, not "perfect" English. Include:
- Hinglish phrases ("play that gaana from the movie")
- Indian names (Arijit Singh, A.R. Rahman)
- Mixed commands ("lights ko blue kar do" if you want Hindi support)

**Exercise:** Create 10 recordings with natural Indian English speech. Test transcription accuracy. Note which model size gets Indian accents right. Save in `notes/indian-english-accuracy.md`.

### 2.5 — Wake Word Detection

The assistant should only activate when you say the trigger phrase — not when you're having a random conversation nearby.

```python
# experiments/wake_word_basics.py
from openwakeword.model import Model
import sounddevice as sd
import numpy as np

# Load a pre-trained wake word model
# Available built-in models: "hey_jarvis", "alexa", "hey_mycroft", etc.
oww_model = Model(inference_framework="onnx")

# Print available models
print("Available models:", oww_model.models.keys())

SAMPLE_RATE = 16000
CHUNK_SIZE = 1280  # 80ms chunks (OpenWakeWord expects this)

print("Listening for wake words... say 'Hey Jarvis' or 'Alexa'")

def audio_callback(indata, frames, time, status):
    audio_chunk = np.frombuffer(indata, dtype=np.int16)
    predictions = oww_model.predict(audio_chunk)

    for model_name, confidence in predictions.items():
        if confidence > 0.5:
            print(f"\n*** WAKE WORD DETECTED: {model_name} (confidence: {confidence:.2f}) ***")

with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16',
                     blocksize=CHUNK_SIZE, callback=audio_callback):
    print("Press Ctrl+C to stop...")
    import time
    while True:
        time.sleep(0.1)
```

**Exercise:** Test wake word detection in different conditions:
1. Quiet room, speaking directly
2. From 2 meters away
3. With music playing in background
4. While someone else is talking nearby

Note the false positive and false negative rates. Write in `notes/wake-word-accuracy.md`.

### 2.6 — Voice Activity Detection (Silence Detection)

After the wake word triggers, you need to record the user's command and know when they've stopped talking. This is called VAD (Voice Activity Detection).

```python
# experiments/vad_recording.py
import sounddevice as sd
import numpy as np
import wave

SAMPLE_RATE = 16000
CHUNK_DURATION = 0.1  # 100ms chunks
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)
SILENCE_THRESHOLD = 500  # Adjust based on your mic
SILENCE_DURATION = 1.5  # seconds of silence before stopping
MAX_DURATION = 10  # max recording length

def record_until_silence():
    """Record audio, stop when silence is detected."""
    print("Listening... speak now!")

    frames = []
    silent_chunks = 0
    max_silent_chunks = int(SILENCE_DURATION / CHUNK_DURATION)
    max_chunks = int(MAX_DURATION / CHUNK_DURATION)

    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                            dtype='int16', blocksize=CHUNK_SIZE)
    stream.start()

    for i in range(max_chunks):
        data, _ = stream.read(CHUNK_SIZE)
        frames.append(data.copy())

        # Check volume level
        volume = np.abs(data).mean()

        if volume < SILENCE_THRESHOLD:
            silent_chunks += 1
        else:
            silent_chunks = 0

        # Stop if enough silence
        if silent_chunks >= max_silent_chunks and len(frames) > 10:
            print(f"Silence detected after {len(frames) * CHUNK_DURATION:.1f}s")
            break

    stream.stop()
    stream.close()

    # Combine frames
    audio = np.concatenate(frames)
    return audio

# Test it
audio = record_until_silence()
print(f"Recorded {len(audio) / SAMPLE_RATE:.1f} seconds")

# Save for inspection
with wave.open("vad_test.wav", "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(SAMPLE_RATE)
    wf.writeframes(audio.tobytes())
```

**Exercise:** Tune the `SILENCE_THRESHOLD` for your Mac's built-in mic. Too low = it never stops. Too high = it cuts you off mid-sentence. Find the sweet spot. This value will be different on the Jetson with the ReSpeaker mic — that's fine.

### 2.7 — Wire It All Together (The Full Ear Pipeline)

```python
# experiments/full_ear_pipeline.py
"""
Complete audio input pipeline:
1. Listen for wake word (always running, low CPU)
2. On detection → start recording
3. Record until silence
4. Transcribe the recording
5. Print the text (later: send to Brain)
"""

from openwakeword.model import Model
from faster_whisper import WhisperModel
import sounddevice as sd
import numpy as np
import wave
import tempfile

# Initialize models (do this ONCE at startup)
print("Loading models...")
oww = Model(inference_framework="onnx")
whisper = WhisperModel("base", device="cpu", compute_type="int8")
print("Models loaded!")

SAMPLE_RATE = 16000
CHUNK_SIZE = 1280
SILENCE_THRESHOLD = 500
SILENCE_SECONDS = 1.5

def listen_for_wake_word():
    """Block until wake word is detected."""
    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                            dtype='int16', blocksize=CHUNK_SIZE)
    stream.start()

    while True:
        data, _ = stream.read(CHUNK_SIZE)
        audio_chunk = data.flatten()
        predictions = oww.predict(audio_chunk)

        for name, confidence in predictions.items():
            if confidence > 0.5:
                stream.stop()
                stream.close()
                print(f"[Wake word: {name} ({confidence:.2f})]")
                return name

def record_command():
    """Record until silence, return audio array."""
    frames = []
    silent_chunks = 0
    max_silent = int(SILENCE_SECONDS / 0.1)

    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                            dtype='int16', blocksize=int(SAMPLE_RATE * 0.1))
    stream.start()

    for _ in range(100):  # Max 10 seconds
        data, _ = stream.read(int(SAMPLE_RATE * 0.1))
        frames.append(data.copy())

        if np.abs(data).mean() < SILENCE_THRESHOLD:
            silent_chunks += 1
        else:
            silent_chunks = 0

        if silent_chunks >= max_silent and len(frames) > 5:
            break

    stream.stop()
    stream.close()
    return np.concatenate(frames)

def transcribe(audio: np.ndarray) -> str:
    """Save audio to temp file and transcribe."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        with wave.open(f.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())

        segments, _ = whisper.transcribe(f.name, language="en")
        return " ".join(s.text for s in segments).strip()

# Main loop
print("\n🎤 JARVIS Ears active. Say the wake word to begin...\n")
while True:
    listen_for_wake_word()
    print("👂 Listening for your command...")

    audio = record_command()
    print("🧠 Transcribing...")

    text = transcribe(audio)
    print(f"📝 You said: \"{text}\"\n")
    print("Waiting for wake word again...\n")
```

**Exercise:** Run this pipeline for 15 minutes. Give it real commands. Note every failure — wrong transcription, missed wake word, cut-off recording. These are the bugs you'll fix before demo day.

---

## Checkpoint — You're Ready When:

- [ ] You can record clear audio from your Mac's mic
- [ ] Whisper transcribes your voice accurately (especially Indian English)
- [ ] Wake word detection works reliably (>90% detection, <5% false positive)
- [ ] VAD correctly detects when you stop speaking
- [ ] The full pipeline (wake word → record → transcribe) works end-to-end
- [ ] You know which Whisper model size gives the best speed/accuracy trade-off

---

## Files You Should Have Created

```
02-the-ears/
├── notes/
│   ├── model-size-comparison.md
│   ├── indian-english-accuracy.md
│   └── wake-word-accuracy.md
├── experiments/
│   ├── basic_recording.py
│   ├── stt_basics.py
│   ├── stt_model_comparison.py
│   ├── wake_word_basics.py
│   ├── vad_recording.py
│   ├── full_ear_pipeline.py
│   └── test_recordings/
│       ├── command_01.wav
│       ├── command_02.wav
│       └── ...
└── README.md (this file)
```
