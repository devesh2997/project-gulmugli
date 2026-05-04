# Hardware Assembly — Notes & Decisions Log

> **Purpose:** persist everything discussed about the physical build so we
> don't have to re-derive the trade-offs every time hardware comes back up.
> When you next pick this up, the conversation continues from here, not
> from scratch.

**Last updated:** 2026-05-05 (during birthday-pack development)
**Status:** decision deferred — Devesh wants time to think before
committing to a path. Software development continues unblocked on Mac.

---

## Components on hand (already purchased)

| Component | Identification | Spec | Notes |
|---|---|---|---|
| **Display** | 7" Waveshare HDMI LCD (Rev 4.1) | 1024×600 IPS, capacitive touch over USB | HDMI for video + microUSB for power+touch. Has a backlight ON/OFF switch. PWM/GND pads available for brightness control (not needed). **No soldering required.** |
| **Speaker** | Generic 4–8 Ω, 3 W speaker with bare wires | Red/black wires, no JST connector | Connects to amplifier via screw terminals (which need to be soldered onto the amp first). |
| **Microphone** | I²S MEMS mic — likely INMP441 family | Round PCB, pin labels: `L/R, WS/SM, SCK, SD, VDD, GND`. Header pins ship loose | Single-mic, digital output. Single-mic ⇒ no beamforming, no echo cancellation. **Header pins need soldering.** |
| **Amplifier** | Adafruit MAX98357A I²S Class-D mono amp clone | Vin 2.5–5.5 V, 9 dB gain, mono (L+R)/2 output, screw terminal block + header pins ship loose | Pairs with the I²S mic (shared BCLK + LRCK). **Headers AND screw terminal need soldering.** |
| **LED strip** | WS2812B / NeoPixel addressable, 5 V | Labels visible: `+5V DIN GND` / `+5V DO GND`. Black PCB. Estimated 30–40 LEDs total across two segments | Addressable RGB. Each LED ~60 mA at full white → 30 LEDs ≈ 1.8 A peak. Needs external 5 V/3 A supply (Jetson can't safely deliver this). 470 Ω data resistor + 1000 µF cap mandatory. |
| **Breadboard** | Standard 830-tie-point full-size | Power rails on top + bottom, two 5-tie-point banks (a-e, f-j) | No issues, fits any of the audio paths. |
| **Jumper wires** | Large rainbow bundle | M-M, M-F, F-F variants visible | Plenty for any wiring scenario. |

---

## Comparison: this mic vs ReSpeaker

| Property | INMP441 (current) | ReSpeaker Mic Array v2.0 |
|---|---|---|
| Cost | ~₹250 / $3 | ~₹6,000 / $70 |
| Mics on board | 1 | 4 (linear array) |
| Connection | I²S → GPIO header | USB plug-and-play |
| Far-field pickup | Up to ~1.5 m clean | 4–5 m clean |
| Beamforming | None — picks up everything equally | Yes — focuses on active speaker |
| Echo cancellation | None — mic re-hears playback | Built-in DSP cancels playback |
| Noise suppression | Basic | Aggressive (DSP) |
| Setup effort | Configure I²S in DTS, write ALSA config | `lsusb` — done |
| Voice-assistant fit | OK if user is within 2 ft | Excellent for "kiosk in a room" |

**Recommendation captured:** start with INMP441 to get the full pipeline
working at close range. If pickup at distance is bad, order ReSpeaker
later and swap (provider pattern in the assistant means the swap is a
config change, not code).

---

## Constraints stated by Devesh

1. **No soldering iron.** Doesn't have one, doesn't want to buy one,
   doesn't want to learn. (Followed up with curiosity about what
   soldering would entail — see the soldering primer below — but final
   stance was still "deferred.")
2. **One enclosure.** Everything inside a single tabletop box, including
   speaker. This rules out external USB conference speakers (they're
   ~10–15 cm tall — too big).
3. **Surprise integrity.** Astha doesn't know any of this exists.
   May 14 is the *launch*, not a soft-flip on existing hardware.
4. **9-day deadline** (May 5 → May 14, 2026). Shipping time + assembly
   time both compressed.

---

## Three viable paths (analyzed in detail)

### Path 1 — Buy pre-soldered versions of the same components

Replace the two boards that need soldering with pre-assembled equivalents.
Keep everything else.

**Spend:** ~₹1,500 / $20.

| Item | Description | India price |
|---|---|---|
| Adafruit MAX98357A (assembled) | #3006 ships with header pins + screw terminal pre-attached | ₹500-800 |
| Pre-soldered INMP441 module | Search "INMP441 pre-soldered with header" on Amazon.in / Robu | ₹400-600 |
| Solderless WS2812B 3-pin connector | Snaps onto the strip's bare pads, presents 3 jumper-friendly pins | ₹100-200 (5-pack) |

**Existing components reused:**
- Bare-wire speaker → screws into the amp's terminal (no solder needed
  for the speaker, just for the terminal-to-PCB joint, which is already
  done in the assembled version)
- Breadboard, jumper wires, screen — all unchanged

**Pros:**
- Smallest spend
- Native I²S audio (best latency, ALSA-direct integration)
- All components inside the breadboard footprint inside one enclosure
- Existing skills/learning carries over (we discussed I²S architecture
  in detail)

**Cons:**
- Trusting Indian-clone pre-soldered breakouts to have clean joints
  (Adafruit-genuine is reliable; clones are hit-or-miss)
- 5-7 day shipping window in India, eats into the deadline

### Path 2 — Tiny USB I²S audio module (cleanest)

Use a USB audio adapter with mic-in + headphone-out and a small
embedded-friendly powered speaker.

**Spend:** ~₹1,500-2,500 / $20-30.

| Item | Notes |
|---|---|
| Plugable USB Audio Adapter / Sabrent USB-AUDIO | ~6×2×1 cm, plug-and-play on Linux |
| 3.5 mm electret mic capsule, pre-wired | Plug into the USB adapter's mic-in |
| Adafruit #1314 mini powered speaker (or generic 3W with built-in amp + 3.5 mm jack) | ~5×5×3 cm, fits enclosure |

**Pros:**
- Zero GPIO config, zero ALSA debugging — `lsusb` and you're done
- Plug-and-play, smallest possible internal footprint
- All failures are visible (USB device disappears) instead of
  audio-degrades-mysteriously-over-weeks
- Existing components (INMP441 / amp / bare-wire speaker) become spares

**Cons:**
- Higher latency than I²S (~40-100 ms USB audio vs ~5 ms I²S — usually
  unnoticeable for voice)
- More USB cable management inside the enclosure
- Doesn't reuse the components already bought

### Path 3 — Find someone to solder, just once

Ask a maker space or electronics repair shop to solder the 14 joints.
Total time for a competent solderer: ~10 minutes. Cost: free at
hackerspaces in HYD/BLR/DEL (Workbench Projects, MakersAsylum, Maker's
Loft) or ~₹100-200 at any electronics market repair counter.

**Pros:**
- Cheapest option (₹0-200)
- Preserves the cleanest audio architecture (I²S)
- Devesh isn't the one doing the work — just dropping off two boards

**Cons:**
- Travel + scheduling friction
- Requires physical visit to a shop or hackerspace

---

## Soldering primer (in case Devesh ever reconsiders)

### Equipment cost in India: ₹1,200-2,000

| Item | Purpose | Price |
|---|---|---|
| Temperature-controlled soldering iron (60-80W) | Core tool | ₹500-1500 |
| Lead-free solder wire (0.6 mm or 0.8 mm, rosin core) | The metal | ₹150-300 (100 g spool — lifetime supply) |
| Soldering iron stand with sponge | Where you put the hot iron | ₹150-300 |
| Brass tip cleaner | Cleans tip without thermal shock | ₹100-200 (optional) |
| Flux paste (small tube) | Helps solder flow | ₹100-200 (optional, 5x easier with) |
| Cheap multimeter | Verify continuity | ₹400-800 (optional) |

**Minimum viable kit:** ~₹800 (iron + solder + stand). **Full kit:** ~₹2,000.

### Don't bother with

- Solder sucker / desoldering wick (no mistakes that bad on 14 joints)
- Helping-hands / PCB vise (overkill for header-pin work; tape works)
- Solder fumes extractor (ventilate the room and you're fine)
- Soldering station ≥ ₹3,000 (single iron is enough)

### The skill

Total time-to-competent: **~75 minutes total**.

1. **30 min:** unbox iron, plug in (350°C lead-free target), watch one
   YouTube video — *"How to solder through-hole pins"* by Adafruit or
   Sparkfun. The technique:
   - Touch iron to joint where pin and PCB pad meet (NOT to the solder)
   - Wait 1-2 seconds for the joint to heat
   - Touch solder to the joint (NOT the iron)
   - Solder flows in, count to two, pull solder away
   - Pull iron away
   - That's it. Cool joint = shiny, conical, ~2 mm tall
2. **30 min practice:** sacrificed electronics or cheap perfboard. By
   joint #5, comfortable.
3. **15 min real work:** the 14 project joints.

### Why through-hole headers are the friendliest soldering target

Modern hobby soldering can get into surface-mount territory — tiny
0.5 mm pitch, microscope required, painful. **You have none of that.**
Through-hole header pins on a breakout PCB are the easiest possible
introduction. Holes are 0.6 mm wide, pitch is 2.54 mm, you can see
everything with the naked eye, and the joint geometry is forgiving.

---

## Connection plans (for when assembly happens)

### Screen — easiest, no breadboard, no soldering

Two cables, after the Jetson is powered off:

1. **HDMI cable:** screen's HDMI port → any HDMI port on the Jetson
2. **MicroUSB cable:** screen's "Touch" port → any USB-A port on the
   Jetson (use a *data* USB cable, not charge-only)

Power on the Jetson. Backlight switch ON. Should boot to the Ubuntu
desktop with touch working immediately. Fix resolution if needed:
`xrandr --output HDMI-0 --mode 1024x600`.

**Common gotchas:**
- Black screen → backlight switch is OFF
- Touch inverted → calibrate via `xinput-calibrator` later

### Mic + amp via I²S (for Path 1 or Path 3)

Both speak the same protocol. Jetson is master, mic + amp are slaves.
Mic feeds Jetson via DIN; Jetson feeds amp via DOUT. They share
BCLK and LRCK clocks.

```
   Jetson  ──── BCLK ─────┬─── mic SCK
            ─── LRCK ─────┼─── mic WS
            ─── DIN  ←──── mic SD       (mic feeds Jetson)
            ─── DOUT ────→ amp DIN      (Jetson feeds amp)
                          └─── amp BCLK
                              amp LRC
```

Jetson Orin Nano J6 (40-pin) pin map (with I²S2 enabled via `jetson-io.py`):

| Function | Jetson pin | Wire color |
|---|---|---|
| 3.3 V (mic VDD) | **Pin 1** | Red |
| 5 V (amp Vin) | **Pin 2** | Orange |
| GND (shared) | **Pins 6, 9, 39** | Black |
| BCLK (I2S2 SCLK) | **Pin 12** | Yellow |
| LRCK (I2S2 FS) | **Pin 35** | Green |
| Mic data → Jetson (I2S2 DIN) | **Pin 38** | Blue |
| Jetson → Amp data (I2S2 DOUT) | **Pin 40** | White |

**Critical safety:** never reverse 3.3 V and 5 V — INMP441 will smoke
on 5 V.

### LED strip — WS2812B

| Strip pin | Goes to | Note |
|---|---|---|
| 5 V (Vcc) | External 5 V/3 A power supply (NOT Jetson 5 V pin) | 30 LEDs at full white = ~1.8 A; Jetson can't supply that safely |
| GND | Power supply GND **AND** Jetson GND | Common ground required |
| DIN | Jetson GPIO pin (e.g., pin 32) via a **470 Ω resistor** | Resistor protects first LED from voltage spikes |

Plus a **1000 µF capacitor across the strip's 5 V/GND** at the input
end (smooths inrush current). Bent legs into the breadboard, no solder
needed.

### Speaker → amp

Strip ~5 mm of insulation on the bare red/black wires. Loosen both
screws on the green terminal block (which must be soldered to the amp
PCB first — that's one of the 14 joints in Path 3, or pre-done in
Path 1's Adafruit assembled version). Insert one wire per side (red
to `+`, black to `−`), tighten.

---

## Software status (no hardware blocked)

The assistant is fully developable on Mac. As of last hardware
discussion the software state was:

- ✅ Vesper rebrand + protocol-id decoupling
- ✅ Phase 0 — event manager, theme switching, manual-trigger intent
- ✅ Phase 1.1 — intro runner (launch sequence engine)
- ✅ Phase 1.2 — persisted trigger state
- ✅ Phase 3.4 — party hat avatar overlay
- ✅ Phase 4 — Astha jokes engine + NLU intent
- ✅ Phase 5.1 — confetti dashboard layer
- 🟡 Phase 3.2 — Angry Astha personality + "kya hua → kuch nahi" prefilter
- 🤖 Phase 2.1 — Yaadein photo slideshow (sub-agent in flight)
- 🤖 Phase 5.4 — birthday quiz (sub-agent in flight)

Total tests: 215+ unit cases all green on Mac.

The only hardware-dependent feature is **audio I/O** itself — TTS
playback + mic input. Until one of Path 1 / 2 / 3 lands, the launch
sequence's `play_audio` and `speak` steps run on Mac through `afplay`
+ kokoro TTS, which is the same software path that would run on
Jetson once audio hardware is wired up.

---

## Decisions to make when Devesh next picks this up

1. **Path 1 / 2 / 3 / soldering kit?** — pick one
2. **If Path 1:** order the three components (Adafruit MAX98357A
   assembled + pre-soldered INMP441 + solderless WS2812B connector)
   and wait for shipping
3. **If Path 2:** order USB audio adapter + electret mic + small
   powered speaker
4. **If Path 3:** find a hackerspace / electronics shop in HYD/BLR/DEL
5. **If learning to solder:** order the ₹800-2,000 starter kit and
   block 75 minutes for learning + practice
6. **External 5V/3A power supply for the LED strip** — needed for any
   path. ~₹500-800. Search "5V 3A DC adapter with barrel jack."
7. **Enclosure design** — Devesh has been working on this separately;
   exact internal volume drives final component-fit checks. Reference
   sizes: Jetson + breadboard + screen + speaker fit comfortably in a
   ~25×15×7 cm box.

---

## Open question: ReSpeaker upgrade timing

If far-field voice pickup is bad with the single-mic INMP441 (or with
a USB single-mic adapter in Path 2), the upgrade is **ReSpeaker Mic
Array v2.0** (~₹6,000 / $70). Trigger to upgrade: she has to lean
toward the mic to be heard from across the room.

Defer this decision until after the first end-to-end test with whatever
mic ships in the chosen path.

---

## Cross-references

- [`jarvis/BIRTHDAY_ROADMAP.md`](../BIRTHDAY_ROADMAP.md) — software roadmap
- [`jarvis/05-the-body/JETSON_SETUP.md`](./JETSON_SETUP.md) — original Jetson OS / driver setup
- [`jarvis/assistant/CLAUDE.md`](../assistant/CLAUDE.md) — codebase overview, hardware-portability rules
- Photos of components and conversation transcripts: in this session's
  conversation history (May 5, 2026)
