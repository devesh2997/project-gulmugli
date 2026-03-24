# Module 4: The Hands — Music, Lights & Actions

**What this is:** The skills layer — everything JARVIS can actually DO. Playing music, controlling lights, and executing real-world actions.

**Why it matters:** The Brain thinks, the Ears listen, the Voice speaks — but the Hands act. This is where the assistant becomes useful, not just a chatbot.

**Time estimate:** 5–7 hours across Weeks 3–4

**Prerequisites:** Module 1 (The Brain) should be done. Modules 2 & 3 are helpful but not blocking.

---

## What You'll Learn

1. YouTube Music API (ytmusicapi) — search, play, control
2. Spotify API (spotipy) — setup, limitations, and why YouTube is primary
3. Audio streaming with mpv
4. Wipro/Tuya smart bulb protocol — how local IoT control works
5. tinytuya library — controlling your actual lights from Python
6. Building a skill/action framework that's easy to extend

---

## Learning Path

### 4.1 — YouTube Music API Setup

This is your primary music backend — no restrictions, no Premium requirement.

```bash
pip install ytmusicapi
```

**Authentication (one-time):**

```bash
# This opens a browser for Google OAuth
ytmusicapi oauth
# Follow the prompts → creates oauth.json
```

```python
# experiments/ytmusic_basics.py
from ytmusicapi import YTMusic

ytm = YTMusic("oauth.json")

# Search for a song
results = ytm.search("Tum Hi Ho Arijit Singh", filter="songs", limit=5)
for r in results:
    print(f"  {r['title']} — {r['artists'][0]['name']}")
    print(f"  Video ID: {r['videoId']}")
    print()

# Search for something vague
results = ytm.search("sad bollywood rain song", filter="songs", limit=5)
for r in results:
    print(f"  {r['title']} — {r['artists'][0]['name']}")
```

**Exercise:** Search for 20 different queries — specific songs, vague moods, artist names, movie soundtracks. How good are YouTube Music's search results? Write findings in `notes/ytmusic-search-quality.md`.

### 4.2 — Audio Streaming with mpv

mpv is a command-line media player that can stream YouTube URLs directly.

```bash
# Install mpv
brew install mpv   # Mac
# sudo apt install mpv  # Later on Jetson
```

```python
# experiments/music_player.py
import subprocess
import signal
from ytmusicapi import YTMusic

ytm = YTMusic("oauth.json")

class MusicPlayer:
    def __init__(self):
        self.process = None

    def play(self, query: str) -> str:
        """Search and play a song."""
        # Stop current playback
        self.stop()

        # Search
        results = ytm.search(query, filter="songs", limit=3)
        if not results:
            return f"Couldn't find anything for '{query}'"

        song = results[0]
        title = song["title"]
        artist = song["artists"][0]["name"]
        video_id = song["videoId"]
        url = f"https://music.youtube.com/watch?v={video_id}"

        # Play with mpv (audio only, no video window)
        self.process = subprocess.Popen(
            ["mpv", "--no-video", "--really-quiet", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        return f"Playing {title} by {artist}"

    def stop(self):
        """Stop current playback."""
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None
            return "Stopped"
        return "Nothing is playing"

    def pause(self):
        """Pause/resume — mpv doesn't support this easily via subprocess.
        For proper control, we'll use mpv's IPC socket later."""
        # TODO: Implement via mpv --input-ipc-server
        return "Pause/resume requires mpv IPC (we'll add this in the build phase)"

# Test
player = MusicPlayer()
print(player.play("Tum Hi Ho Arijit Singh"))
input("Press Enter to stop...")
player.stop()

print(player.play("Kun Faya Kun"))
input("Press Enter to stop...")
player.stop()
```

**Exercise:** Play 10 different songs. Does mpv stream reliably? How long before audio starts? Test with your Bluetooth speaker paired to Mac.

### 4.3 — mpv IPC for Playback Control

For pause/resume/skip, mpv has a JSON IPC interface:

```python
# experiments/mpv_ipc_control.py
import subprocess
import socket
import json
import time
import os

IPC_SOCKET = "/tmp/mpv-jarvis.sock"

class MusicPlayerAdvanced:
    def __init__(self):
        self.process = None

    def play(self, url: str):
        self.stop()
        # Remove old socket
        if os.path.exists(IPC_SOCKET):
            os.unlink(IPC_SOCKET)

        self.process = subprocess.Popen([
            "mpv", "--no-video", "--really-quiet",
            f"--input-ipc-server={IPC_SOCKET}",
            url
        ])
        time.sleep(1)  # Wait for socket to be created

    def _send_command(self, command: list):
        """Send a command to mpv via IPC socket."""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(IPC_SOCKET)
            msg = json.dumps({"command": command}) + "\n"
            sock.send(msg.encode())
            response = sock.recv(1024).decode()
            sock.close()
            return json.loads(response)
        except Exception as e:
            return {"error": str(e)}

    def pause(self):
        return self._send_command(["set_property", "pause", True])

    def resume(self):
        return self._send_command(["set_property", "pause", False])

    def volume_up(self):
        return self._send_command(["add", "volume", 10])

    def volume_down(self):
        return self._send_command(["add", "volume", -10])

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None

# Test
player = MusicPlayerAdvanced()
player.play("https://music.youtube.com/watch?v=YOUR_VIDEO_ID")
time.sleep(5)
player.pause()
time.sleep(2)
player.resume()
```

**Exercise:** Test all controls — play, pause, resume, volume up/down, stop. This is the full music control interface JARVIS will use.

### 4.4 — Spotify (Optional — Know the Limitations)

Spotify is heavily restricted for hobby projects since 2025. Set it up only if you have Premium and want it as a secondary option.

```bash
pip install spotipy
```

```python
# experiments/spotify_basics.py
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# You need to create an app at https://developer.spotify.com/dashboard
# Development mode: max 25 users, requires Premium
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    redirect_uri="http://localhost:8888/callback",
    scope="user-modify-playback-state user-read-playback-state"
))

# Search
results = sp.search(q="Tum Hi Ho", type="track", limit=5)
for track in results["tracks"]["items"]:
    print(f"{track['name']} — {track['artists'][0]['name']}")

# Note: Playback control requires an active Spotify device
# (phone app open, desktop app, or web player)
```

**Decision point:** Is Spotify worth the hassle for demo day? YouTube Music has no restrictions and covers the same songs. Write your decision in `notes/spotify-decision.md`.

### 4.5 — Wipro Smart Light Control

This is one of the coolest demo moments — "JARVIS, set the lights to romantic mode" and the room transforms.

**Step 1: Tuya IoT Platform Setup (free)**

1. Go to [iot.tuya.com](https://iot.tuya.com) and create a free account
2. Create a "Cloud Project" → select "Smart Home" → select your data center (India)
3. Subscribe to these APIs: "IoT Core", "Authorization Token Management"
4. Note your **Access ID** and **Access Secret**
5. Link your Tuya Smart / Wipro app account to the Cloud Project

**Step 2: Get Device Credentials**

```bash
pip install tinytuya

# Run the setup wizard
python -m tinytuya wizard
# Enter your Tuya API credentials when prompted
# It will scan your network and list all devices with their:
#   - Device ID
#   - IP Address
#   - Local Key
```

**Step 3: Control Your Light**

```python
# experiments/light_control.py
import tinytuya
import time

# Values from the tinytuya wizard output
light = tinytuya.BulbDevice(
    dev_id="YOUR_DEVICE_ID",
    address="YOUR_DEVICE_IP",      # e.g., 192.168.1.105
    local_key="YOUR_LOCAL_KEY",
    version=3.3
)

# Basic controls
print("Turning on...")
light.turn_on()
time.sleep(2)

print("Setting to warm white, 50% brightness...")
light.set_brightness(500)  # 10-1000
light.set_colourtemp(500)  # warm
time.sleep(2)

print("Setting to blue...")
light.set_colour(0, 0, 255)
time.sleep(2)

print("Setting to romantic purple, dim...")
light.set_colour(128, 0, 128)
light.set_brightness(200)
time.sleep(2)

print("Turning off...")
light.turn_off()
```

**Exercise:** Test every capability of your Wipro bulb — colors, brightness levels, color temperature. Find out what range your specific bulb supports. Some Wipro bulbs are RGB, some are just warm/cool white. Document in `notes/wipro-bulb-capabilities.md`.

### 4.6 — Scene Presets (The Demo Wow Factor)

Pre-define scenes that combine multiple light settings:

```python
# experiments/light_scenes.py
import tinytuya
import time

light = tinytuya.BulbDevice(
    dev_id="YOUR_DEVICE_ID",
    address="YOUR_DEVICE_IP",
    local_key="YOUR_LOCAL_KEY",
    version=3.3
)

SCENES = {
    "romantic": {"color": (255, 50, 80), "brightness": 200},
    "movie": {"color": (255, 150, 50), "brightness": 150},
    "focus": {"color": (255, 255, 255), "brightness": 800},
    "party": {"color": (0, 100, 255), "brightness": 600},
    "sleep": {"color": (255, 100, 30), "brightness": 50},
    "sunrise": {"color": (255, 200, 100), "brightness": 400},
}

def set_scene(scene_name: str):
    scene = SCENES.get(scene_name.lower())
    if not scene:
        return f"Unknown scene: {scene_name}. Available: {', '.join(SCENES.keys())}"

    light.turn_on()
    light.set_colour(*scene["color"])
    light.set_brightness(scene["brightness"])
    return f"Scene set to {scene_name}"

# Demo all scenes
for name in SCENES:
    print(set_scene(name))
    time.sleep(3)
```

**Exercise:** Create scenes that will impress on demo day. "Romantic mode" is the obvious one for a birthday gift. Test each scene in your actual room. Adjust colors until they look perfect.

### 4.7 — Putting the Hands Together

Build the unified action executor that the Brain's intent router will call:

```python
# experiments/action_executor.py
"""
Unified action executor — takes an intent from the Brain
and executes the right action.
"""
import json

# Import your player and light controller
# from music_player import MusicPlayer
# from light_control import LightController

class ActionExecutor:
    def __init__(self):
        # self.music = MusicPlayer()
        # self.lights = LightController()
        pass

    def execute(self, intent: dict) -> str:
        """Execute an action based on the classified intent."""
        action = intent.get("intent")
        params = intent.get("params", {})

        if action == "music_play":
            query = params.get("query", "")
            # return self.music.play(query)
            return f"[MOCK] Would play: {query}"

        elif action == "music_control":
            ctrl = params.get("action", "")
            # return getattr(self.music, ctrl, lambda: "Unknown control")()
            return f"[MOCK] Would {ctrl} music"

        elif action == "light_control":
            act = params.get("action", "")
            value = params.get("value", "")
            # return self.lights.control(act, value)
            return f"[MOCK] Would set light {act} to {value}"

        elif action == "chat":
            message = params.get("message", "")
            # return self.brain.chat(message)
            return f"[MOCK] Would chat about: {message}"

        else:
            return "I'm not sure how to do that."

# Test with sample intents from Module 1
test_intents = [
    {"intent": "music_play", "params": {"query": "Atlas Coldplay"}, "response": "Playing Atlas"},
    {"intent": "light_control", "params": {"action": "color", "value": "purple"}, "response": "Setting lights to purple"},
    {"intent": "music_control", "params": {"action": "pause"}, "response": "Pausing"},
    {"intent": "chat", "params": {"message": "what is quantum computing"}, "response": ""},
]

executor = ActionExecutor()
for intent in test_intents:
    result = executor.execute(intent)
    print(f"Intent: {intent['intent']} → {result}")
```

---

## Checkpoint — You're Ready When:

- [ ] ytmusicapi searches and finds songs accurately
- [ ] mpv streams YouTube Music audio reliably
- [ ] mpv IPC controls work (pause/resume/volume)
- [ ] You have Tuya credentials and can control your Wipro bulb from Python
- [ ] You've created and tested 5+ light scenes
- [ ] The "romantic" scene looks genuinely good in your room
- [ ] You understand why YouTube Music is primary over Spotify
- [ ] The action executor framework is ready to wire up

---

## Buy Decision: Wipro Smart Bulb

If you don't already own a Wipro smart bulb, this is the **first purchase** to make.
It's cheap (~₹800-1200 on Amazon.in), you can test it immediately on your Mac,
and it gives you the most impressive demo moment.

**Search:** "Wipro smart bulb RGB" on Amazon.in

---

## Files You Should Have Created

```
04-the-hands/
├── notes/
│   ├── ytmusic-search-quality.md
│   ├── spotify-decision.md
│   └── wipro-bulb-capabilities.md
├── experiments/
│   ├── ytmusic_basics.py
│   ├── music_player.py
│   ├── mpv_ipc_control.py
│   ├── spotify_basics.py (optional)
│   ├── light_control.py
│   ├── light_scenes.py
│   └── action_executor.py
└── README.md (this file)
```
