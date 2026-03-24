# Project JARVIS — Master Roadmap

**Start:** March 22, 2026 | **Deadline:** May 14, 2026 (her birthday)
**Total time:** 7.5 weeks × 5–10 hrs/week ≈ 40–75 hours

---

## Philosophy

```
LEARN on Mac → SIMULATE on Mac → BUY with confidence → BUILD on Jetson → POLISH for demo day
```

No purchases until you understand what you're buying and why.
No hardware until software works on your Mac.
No integration until individual pieces are solid.
Reliability over features — a smooth 4-feature demo beats a buggy 8-feature one.

---

## Project Modules

The project is split into 7 modules, named after the parts of JARVIS:

| # | Module | What It Is | Where You Work | Purchases Needed |
|---|--------|-----------|----------------|-----------------|
| 01 | **The Brain** | LLM + intent routing | Mac | None |
| 02 | **The Ears** | Wake word + speech-to-text | Mac | None |
| 03 | **The Voice** | Text-to-speech + audio output | Mac | None |
| 04 | **The Hands** | Music, lights, actions | Mac | Wipro bulb (~₹1,000) |
| 05 | **The Body** | Hardware setup + enclosure | Jetson | Everything else |
| 06 | **The Soul** | Integration + personality | Jetson | None |
| 07 | **Presentation** | Demo prep + birthday reveal | Both | None |

---

## Week-by-Week Timeline

### Week 1: March 22 – March 28
**Theme: Get your hands dirty with the LLM**

| Day | Task | Module | Hours |
|-----|------|--------|-------|
| Sat-Sun | Install Ollama, play with Qwen 2.5 3B, understand basics | 01 | 3-4 |
| Weekday | Read about quantization, run comparison experiments | 01 | 1-2 |
| Weekday | Build intent router v1, test with 20+ inputs | 01 | 2-3 |

**Deliverables:**
- Working intent router on Mac
- `best_system_prompt.txt`
- `notes/first-impressions.md`

**Buy:** Nothing

---

### Week 2: March 29 – April 4
**Theme: Audio pipeline — ears and voice**

| Day | Task | Module | Hours |
|-----|------|--------|-------|
| Sat-Sun | Set up faster-whisper, test STT accuracy with your voice | 02 | 3-4 |
| Weekday | Install Piper TTS, test voices, pick JARVIS's voice | 03 | 1-2 |
| Weekday | Wake word detection experiments, VAD tuning | 02 | 2-3 |

**Deliverables:**
- STT working on Mac mic
- Voice selected for JARVIS
- Wake word → record → transcribe pipeline working
- `notes/voice-selection.md`

**Buy:** Wipro smart bulb (~₹1,000) — needed for Module 4 next week

---

### Week 3: April 5 – April 11
**Theme: Skills — music and lights**

| Day | Task | Module | Hours |
|-----|------|--------|-------|
| Sat-Sun | Set up ytmusicapi, mpv streaming, music player class | 04 | 3-4 |
| Weekday | Set up tinytuya, control Wipro bulb, create scenes | 04 | 2-3 |
| Weekday | Build song resolver (LLM → search query), test 30 queries | 01+04 | 1-2 |

**Deliverables:**
- Music plays via voice command on Mac
- Lights change via Python script
- 5+ light scenes defined and tested
- `notes/wipro-bulb-capabilities.md`

**Buy:** Nothing (bulb ordered last week)

---

### Week 4: April 12 – April 18
**Theme: Full Mac prototype + hardware order**

| Day | Task | Module | Hours |
|-----|------|--------|-------|
| Sat-Sun | Wire everything together on Mac: wake word → STT → LLM → action → TTS | All | 4-5 |
| Weekday | Test end-to-end, find and fix bugs | All | 2-3 |
| Wed/Thu | **ORDER HARDWARE** (Jetson, ReSpeaker, SSD, cables) | 05 | 1 |

**Deliverables:**
- Complete working prototype on Mac (slower but functional)
- End-to-end: say command → hear response + action happens
- Hardware ordered

**Buy:** Jetson Orin Nano Super, ReSpeaker Mic, NVMe SSD, cables, charger (~₹45,000–50,000)

**Why now:** You've proven the software works. You know exactly which components you need. No wasted money.

---

### Week 5: April 19 – April 25
**Theme: Hardware setup + porting**

| Day | Task | Module | Hours |
|-----|------|--------|-------|
| Sat-Sun | Set up Jetson (JetPack, CUDA, Ollama, Python packages) | 05 | 4-5 |
| Mon-Tue | Pair BT speaker, set up ReSpeaker mic, test audio I/O | 05 | 2-3 |
| Wed-Thu | Port all Mac code to Jetson, fix platform differences | 05 | 2-3 |

**Deliverables:**
- Jetson running with all software
- Bluetooth speaker paired and playing audio
- ReSpeaker mic recording and transcribing
- All Mac code working on Jetson

**Buy:** NeoPixel LED strip, enclosure materials (~₹1,500–2,000)

---

### Week 6: April 26 – May 2
**Theme: Integration + enclosure**

| Day | Task | Module | Hours |
|-----|------|--------|-------|
| Sat-Sun | Build main.py — full integration, error handling, config file | 06 | 4-5 |
| Weekday | Set up NeoPixel LEDs, build/order enclosure | 05 | 2-3 |
| Weekday | Personality prompt engineering, auto-start on boot | 06 | 2-3 |

**Deliverables:**
- Fully integrated JARVIS running on Jetson
- LED feedback working (idle/listening/thinking/speaking)
- Enclosure built or ordered
- Auto-starts on boot

**Buy:** Nothing (enclosure materials ordered)

---

### Week 7: May 3 – May 9
**Theme: Polish + reliability**

| Day | Task | Module | Hours |
|-----|------|--------|-------|
| Sat-Sun | Soak test (30 mins continuous), fix all bugs found | 06 | 3-4 |
| Weekday | Assemble enclosure, final hardware build | 05 | 2-3 |
| Weekday | Write and practice demo script, rehearse birthday reveal | 07 | 1-2 |

**Deliverables:**
- Zero crashes in 30-minute soak test
- Enclosure assembled, looks great
- Demo script written and practiced 3x

**Buy:** Nothing

---

### Week 7.5: May 10 – May 13
**Theme: Final prep**

| Day | Task | Hours |
|-----|------|-------|
| May 10-11 | Full dress rehearsal — run through the birthday demo exactly as planned | 2 |
| May 12 | Fix any last issues. Charge speaker. | 1 |
| May 13 | Final test. Place JARVIS in position. Relax. | 0.5 |
| **May 14** | **Her birthday. Demo day. You've got this.** | 🎂 |

---

## Total Estimated Spend

| Item | When | ₹ |
|------|------|---|
| Wipro Smart Bulb | Week 2 | 1,000 |
| Jetson + SSD + Charger (or VERGEENO bundle) | Week 4 | 37,000–40,000 |
| ReSpeaker Mic Array v3.0 | Week 4 | 7,499 |
| BT Speaker (if needed) | Week 4 | 0–14,000 |
| Cables + misc | Week 4 | 1,000 |
| NeoPixel strip | Week 5 | 500 |
| Enclosure materials | Week 5–6 | 1,500 |
| **TOTAL** | | **₹48,500–65,500** |

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Jetson delivery delayed | Can't build on hardware | Order by April 15 latest. Software works on Mac as backup demo. |
| ReSpeaker unavailable | No far-field mic | TONOR USB conference mic (₹3,000) as backup. Order both if nervous. |
| Wipro bulb incompatible | No light control | Buy early (Week 2). If it doesn't work with tinytuya, pivot to a different Tuya bulb. |
| LLM too slow on Jetson | Awkward pauses | Use Qwen 2.5 1B as fallback. Faster but slightly less smart. |
| Bluetooth audio glitchy | Audio cuts out during demo | Hardwire a 3.5mm speaker as backup. Keep BT speaker fully charged. |
| Enclosure not ready | Ugly demo | The assistant works without enclosure. Prioritize software reliability over looks. |
| You run out of time | Incomplete project | Weeks 1–4 give you a working Mac prototype. That alone is a demoable gift. |

---

## Golden Rule

> If you're ever behind schedule, cut scope — not quality.
> A JARVIS that does 3 things perfectly is better than one that does 6 things poorly.
> The minimum viable demo is: voice command → play a song → change the lights → say something sweet.
> Everything else is bonus.
