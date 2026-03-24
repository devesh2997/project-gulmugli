# Module 6: The Soul — Integration, Personality & Reliability

**What this is:** The final assembly — wiring all modules together into one seamless experience, adding JARVIS's personality, and making it bulletproof for demo day.

**Why it matters:** Individual components working ≠ a working assistant. This module turns 5 separate experiments into one smooth, reliable product that won't crash when your girlfriend says "Hey Jarvis" on her birthday.

**Time estimate:** 8–10 hours across Weeks 6–7

**Prerequisites:** All previous modules complete. Hardware assembled (Module 5).

---

## What You'll Learn

1. Async event-driven architecture for a voice assistant
2. Error handling and graceful recovery
3. Personality engineering via system prompts
4. Auto-start on boot (systemd service)
5. Stress testing and reliability hardening
6. The personal touch — making JARVIS sound like you

---

## 6.1 — The Main Loop

This is the production version of `main.py` — the one that runs on the Jetson.

```
jarvis/06-the-soul/
├── src/
│   ├── main.py              # Entry point
│   ├── config.yaml           # All settings in one place
│   ├── audio/
│   │   ├── wake_word.py      # OpenWakeWord listener
│   │   ├── recorder.py       # VAD-based recording
│   │   ├── stt.py            # faster-whisper transcription
│   │   └── tts.py            # Piper TTS + playback
│   ├── brain/
│   │   ├── llm.py            # Ollama client
│   │   ├── intent_router.py  # Intent classification
│   │   └── prompts.py        # System prompts (personality lives here)
│   ├── skills/
│   │   ├── music.py          # YouTube Music + mpv
│   │   ├── lights.py         # Wipro/Tuya control
│   │   └── chat.py           # General conversation
│   ├── hardware/
│   │   ├── leds.py           # NeoPixel + ReSpeaker LEDs
│   │   └── bluetooth.py      # BT speaker management
│   └── utils/
│       ├── logger.py         # Logging for debugging
│       └── errors.py         # Error handling
├── config/
│   └── jarvis.yaml           # Configuration file
└── tests/
    ├── test_intent_router.py # Automated intent tests
    └── test_reliability.py   # Stress tests
```

The key architectural principle: **every component failure should be caught and produce a friendly spoken error, never a crash.**

```python
# Example pattern for every action:
async def execute_safely(self, intent):
    try:
        result = await self.execute(intent)
        return result
    except MusicError as e:
        return "I had trouble playing that song. Could you try again?"
    except LightError as e:
        return "I couldn't reach the lights. They might be offline."
    except Exception as e:
        self.logger.error(f"Unexpected error: {e}")
        return "Something went wrong on my end. Give me a moment."
```

---

## 6.2 — Configuration File

One file to rule them all — no hardcoded values scattered across modules.

```yaml
# config/jarvis.yaml

jarvis:
  name: "JARVIS"
  wake_word: "hey_jarvis"
  wake_word_threshold: 0.5

audio:
  sample_rate: 16000
  silence_threshold: 500
  silence_duration: 1.5
  max_recording_duration: 15

stt:
  model: "medium"
  device: "cuda"        # "cpu" for Mac testing
  compute_type: "float16"
  language: "en"

llm:
  model: "qwen2.5:3b"
  base_url: "http://localhost:11434"
  temperature: 0.7

tts:
  voice: "en_GB-alan-medium"
  speed: 1.0

music:
  default_platform: "youtube"
  mpv_ipc_socket: "/tmp/mpv-jarvis.sock"

lights:
  devices:
    - name: "bedroom"
      dev_id: "YOUR_DEVICE_ID"
      address: "192.168.1.105"
      local_key: "YOUR_LOCAL_KEY"
      version: 3.3
  scenes:
    romantic: {color: [255, 50, 80], brightness: 200}
    movie: {color: [255, 150, 50], brightness: 150}
    focus: {color: [255, 255, 255], brightness: 800}
    party: {color: [0, 100, 255], brightness: 600}
    sleep: {color: [255, 100, 30], brightness: 50}

bluetooth:
  speaker_mac: "XX:XX:XX:XX:XX:XX"
  auto_reconnect: true
  reconnect_interval: 10

leds:
  num_pixels: 30
  brightness: 0.3
  gpio_pin: 18
```

---

## 6.3 — Personality Engineering

This is the most important part for the birthday gift. JARVIS shouldn't sound like a generic assistant — it should have warmth, wit, and eventually sound like you.

**Phase 1: Charming assistant personality (for the demo)**

```python
# brain/prompts.py

JARVIS_PERSONALITY = """You are JARVIS, a personal AI assistant created by ET as
a birthday gift. You are warm, witty, and slightly playful. You speak concisely
(1-2 sentences max for actions, 2-3 for questions).

Personality traits:
- You're genuinely helpful, not robotic
- You have a dry sense of humor when appropriate
- You compliment good taste in music
- You make light control feel magical ("The room transforms...")
- You never say "I'm just an AI" or apologize excessively
- You refer to yourself as JARVIS, never "the assistant"

Response style examples:
- Playing a song: "Excellent choice. Playing Tum Hi Ho — this one's a classic."
- Setting lights: "Going romantic. The room looks beautiful now."
- Answering a question: Give a warm, conversational answer
- Didn't understand: "Hmm, I didn't catch that. Could you say it differently?"
- Error: "I'm having a moment. Let me try that again."
"""
```

**Phase 2: Sounds-like-you personality (post-birthday, the real gift)**

This is what you'll add later — fine-tune the personality prompt to match how you actually talk. Collect examples of your texting style, pet names, inside jokes. This turns JARVIS from "cool tech" into "this is so us."

---

## 6.4 — Auto-Start on Boot

JARVIS should start the moment the Jetson powers on — no keyboard, no monitor needed.

```bash
# Create systemd service
sudo tee /etc/systemd/system/jarvis.service << 'EOF'
[Unit]
Description=JARVIS Voice Assistant
After=network.target bluetooth.target
Wants=bluetooth.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/jarvis
ExecStart=/usr/bin/python3 src/main.py
Restart=always
RestartSec=5
Environment=DISPLAY=:0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable jarvis
sudo systemctl start jarvis

# Check status
sudo systemctl status jarvis

# View logs
journalctl -u jarvis -f
```

---

## 6.5 — Demo Day Reliability Checklist

**One week before May 14th, run through this:**

- [ ] Cold boot test: Unplug Jetson → plug in → JARVIS starts automatically within 60 seconds
- [ ] Bluetooth reconnect: Turn speaker off and on → audio recovers automatically
- [ ] 30-minute soak test: Leave it running for 30 minutes, give 20+ commands, zero crashes
- [ ] Music test: Play 10 different songs via voice → all play correctly
- [ ] Light test: Change color 10 times → all changes apply
- [ ] Conversation test: Ask 10 random questions → all get spoken answers
- [ ] Error recovery: Unplug Ethernet during music → handles gracefully
- [ ] Volume test: Commands recognized while music is playing at medium volume
- [ ] Edge case: Say something really weird → doesn't crash, gives friendly response
- [ ] Battery test (if using portable speaker): How long does the speaker last?

---

## 6.6 — Demo Script

Plan the exact sequence for the birthday reveal:

```
1. Room is dark. JARVIS is powered on (enclosure glowing idle blue).
2. You: "Hey Jarvis"
   → LED ring turns bright blue, NeoPixel pulses
3. You: "Set the lights to romantic mode"
   → Lights transform. Room goes warm pink/purple.
   → JARVIS: "Going romantic. Happy birthday."
4. You: "Play her favorite song" (whatever that is)
   → Music starts from BT speaker
   → JARVIS: "Playing [song]. Great choice for tonight."
5. You: "Jarvis, say happy birthday to [her name]"
   → JARVIS speaks a personalized birthday message
   → (Pre-craft this in the system prompt)
6. Let her interact with it:
   → "Hey Jarvis, change the lights to blue"
   → "Hey Jarvis, play something romantic"
   → "Hey Jarvis, tell me a joke"
```

**Exercise:** Write the full demo script in `07-presentation/demo-scripts/birthday-demo.md`. Practice it 5 times. Time it. Make sure every step works.

---

## Checkpoint — You're Ready When:

- [ ] All components are wired together in one main.py
- [ ] Config file controls everything (no hardcoded values)
- [ ] Every error produces a friendly spoken message (never a crash)
- [ ] JARVIS auto-starts on boot
- [ ] 30-minute soak test passes with zero crashes
- [ ] The demo script runs flawlessly 3 times in a row
- [ ] The personality feels warm, not robotic
- [ ] You've practiced the birthday reveal

---

## Files You Should Have Created

```
06-the-soul/
├── src/
│   ├── main.py
│   ├── config.yaml
│   ├── audio/ ...
│   ├── brain/ ...
│   ├── skills/ ...
│   ├── hardware/ ...
│   └── utils/ ...
├── config/
│   └── jarvis.yaml
└── tests/
    ├── test_intent_router.py
    └── test_reliability.py
```
