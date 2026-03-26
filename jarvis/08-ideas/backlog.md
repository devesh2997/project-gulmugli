# Ideas Backlog

Ideas are grouped by *why Alexa can't do this*. Each idea has a rough effort tag:
- **[weekend]** — Could prototype in a weekend
- **[week]** — Needs a week of focused work
- **[project]** — Multi-week, needs research first

---

## Memory & Context (Alexa is stateless — yours isn't)

### Persistent conversation memory
Jarvis remembers what you talked about yesterday, last week, last month. "What was that song you recommended?" works. Store conversations in a local SQLite DB, embed them with a small model, retrieve by semantic similarity.
**[week]**

### Personal knowledge base
Tell Jarvis facts about your life once: "My mom's birthday is March 12", "I'm allergic to peanuts", "My flight is on the 15th". It remembers forever. Alexa forgets everything the moment the conversation ends.
**[weekend]**

### Mood/pattern awareness
Over time, Jarvis notices patterns: you always play sad songs on Sunday nights, you ask about weather before leaving for work, you dim lights at 10pm. It can proactively suggest things. "It's Sunday night — want me to play your usual playlist?"
**[project]**

---

## Reasoning & Multi-step (Alexa is a keyword matcher — yours thinks)

### Complex music requests
"Play something like what I was listening to last week but more upbeat" — requires memory + reasoning + search. Already partially working with the enrichment pipeline, but can go much further.
**[week]**

### Morning briefing
"Good morning" triggers a personalized briefing: weather, calendar, reminders, news topics YOU care about (not what Amazon wants to sell), any messages overnight. The LLM composes this naturally, not as a robotic list.
**[weekend]**

### Multi-device orchestration
"Movie time" — dims lights to 20% warm, plays a specific playlist at low volume for 2 minutes, then fades out. Requires chaining multiple actions with timing. Alexa routines can sort of do this but they're rigid and can't reason about context.
**[weekend]** (the infra for chained commands already exists)

### Contextual follow-ups
"Turn on the bedroom light" → "Make it warmer" → "A bit brighter" — Alexa handles this poorly because each command is independent. Jarvis keeps conversational context so "it" and "a bit" resolve correctly.
**[weekend]** (mostly works already via LLM context)

---

## Local Integration (Alexa is cloud-locked — yours talks to anything)

### File assistant
"Summarize that PDF on my desktop" or "What's in the spreadsheet I downloaded?" — Jarvis has local filesystem access. It can read, summarize, search your files. Alexa has zero access to your computer.
**[week]**

### Coding companion
"What's that git command for interactive rebase?" or "Explain this error message" — voice in, voice out. A desk-side coding assistant that doesn't need you to open a browser or type. Particularly useful when your hands are busy (soldering, cooking, etc).
**[weekend]**

### Local network scanner
"What devices are on my network?" or "Is the NAS running?" — Jarvis can scan the local network, ping devices, check services. It becomes a voice-controlled network monitor.
**[weekend]**

### Calendar/task integration
Connect to your Google Calendar, Todoist, or whatever you use. "What's on my schedule tomorrow?" or "Remind me to buy groceries at 6pm". The key difference from Alexa: the LLM can reason about conflicts, suggest rescheduling, and give you a natural summary instead of reading a robotic list.
**[week]**

### Clipboard bridge
"Save that to my clipboard" or "Read what's on my clipboard" — the assistant bridges voice and your computer's clipboard. Useful when you're across the room.
**[weekend]**

---

## Personality & Companionship (Alexa is corporate — yours has soul)

### Dynamic personality evolution
Personalities aren't just a static system prompt — they develop. Jarvis learns your humor preferences, your girlfriend's favorite topics, what makes each person laugh. The personality adapts over weeks.
**[project]**

### Storytelling mode (dedicated module — high priority)
A first-class storytelling experience, not just "chat that happens to be a story." Dedicated intent (`story_tell`), separate from chat, with its own LLM prompting strategy optimized for narrative. Key requirements:
- **Long-form generation**: Stories should be genuinely long and interesting (not 2 sentences). May need streaming TTS — generate and speak in chunks rather than waiting for the full story.
- **Calming narrator voice**: A specific TTS voice/speed tuned for narration — slower, warmer, soothing. Separate from the personality's conversational voice. Think audiobook narrator, not assistant.
- **Story memory**: Remember characters and plot threads from previous stories. "Continue the story from last night" works. Stored in the memory system with a `story` category.
- **Ongoing narratives**: Your girlfriend gets a personalized serialized narrative that develops over days/weeks.
- **Genre/mood control**: "Tell me something spooky" vs "a romantic fairy tale" vs "something funny."
- **Bilingual**: Stories in Hindi, English, or Hinglish based on the request language.
- **Interruption-friendly**: "Hey Jarvis, pause the story" mid-narration works naturally.
Alexa reads from a fixed library. Jarvis creates unique stories that remember who's listening.
**[week]**

### Conversation games
20 questions, word association, trivia tailored to your interests, Antakshari (Hindi song game — perfect for the music system). An LLM can play these games naturally. Alexa's games are rigid skills.
**[weekend]**

### Voice journaling
"Jarvis, journal entry" — speak your thoughts, Jarvis transcribes, summarizes, tags by mood/topic, stores locally. Over time you have a searchable voice diary. Completely private, never leaves your device.
**[week]**

---

## Smart Home Beyond Basics (Alexa does on/off — yours reasons)

### Presence-based automation
With the mic array + speaker recognition (already planned), Jarvis knows WHO is in the room. Different people get different defaults: your music preferences, her light preferences. No explicit switching needed.
**[project]** (depends on speaker recognition in 02-the-ears)

### Energy-aware scheduling
"Turn off everything when I leave" or time-based rules: lights dim gradually as bedtime approaches, heating adjusts to schedule. The LLM can handle natural language rules instead of rigid IF-THEN automations.
**[week]**

### Ambient mode
When nobody's talking to it, Jarvis isn't silent — it's an ambient presence. Soft color cycling on the LED ring, a clock on the screen, maybe ambient sounds. It feels alive, not dormant.
**[weekend]**

### IR blaster — control AC, TV, and non-smart devices
An IR transmitter + receiver module on the Jetson's GPIO lets Jarvis control any device with an IR remote: AC, TV, set-top box, fans. Learn remote codes by pointing the original remote at the receiver, then replay them on command. "Jarvis, set AC to 24 degrees" or "switch to HDMI 2." This is huge — it brings non-smart appliances into Jarvis's control without replacing them with smart ones. Hardware: IR LED + TSOP38238 receiver, ~₹100. Software: LIRC or a custom GPIO driver, plus an `IRProvider` in the provider pattern.
**[week]**

---

## Screen-specific ideas (Phase 2 — Alexa Show territory but smarter)

### Photo frame mode
When idle, show a rotating slideshow from a local photos folder. But unlike a dumb frame, you can say "Show me photos from Manali" and it filters by metadata/faces. The LLM describes what it sees if asked.
**[week]** (depends on screen + basic vision model)

### Visual recipe assistant
"Show me a paneer butter masala recipe" — displays steps on screen, reads them aloud one at a time, waits for "next step". Hands-free cooking. Alexa Show does this but only from Amazon's recipe partners.
**[weekend]**

### Dashboard mode
Show a custom dashboard: weather, calendar, music now playing, smart home status, reminders. Fully customizable, not locked to Amazon's layout. Built as a local web UI.
**[week]**

### Video call display
Use the screen + a USB webcam for video calls. "Call Mom on WhatsApp" — routes through the computer. Unusual but possible since Jarvis has full system access.
**[project]**

---

## Wild ideas (probably hard, but fun to think about)

### Voice cloning for TTS
Use a voice cloning model to make Jarvis speak in a familiar voice — a celebrity, a loved one (with consent), or a custom trained voice. Local TTS means no API restrictions.
**[project]**

### Multi-room with cheap satellite speakers
Raspberry Pi Zero + speaker + mic in each room, all connecting to the main Jetson brain. Distributed Jarvis. Each room has presence, but one central brain. Much cheaper than buying multiple Alexas.
**[project]**

### Local vision (with USB camera)
"What's on my desk?" or "Is the door closed?" — a small vision model on the Jetson processes camera input. Completely local, no cloud. Privacy-first home monitoring.
**[project]**

### Skill marketplace (for yourself)
Build a framework where adding new capabilities is as simple as dropping a Python file into a skills/ folder. Each skill defines its intent patterns and handler. You become your own Alexa skill developer, but with zero bureaucracy.
**[week]** (the provider pattern already supports this conceptually)

---

## Not ideas yet, just questions

- Can we make Jarvis work as a Bluetooth speaker too? Play phone audio through it?
- Can the screen show notifications from your phone (like a smart watch)?
- Can Jarvis control a TV via HDMI-CEC?
- Can we add a gesture sensor (wave to dismiss, swipe to skip song)?
- What about a panic button mode? "Jarvis, emergency" calls a preset number and shares location?

---

*Last updated: March 26, 2026*
*Add ideas anytime — no filter, no judgment. We'll sort them later.*
