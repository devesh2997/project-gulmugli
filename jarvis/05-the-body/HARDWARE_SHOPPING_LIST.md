# JARVIS Hardware Shopping List — Core Components

**Last updated:** April 9, 2026
**Focus:** Core hardware (enclosure aesthetics deferred)
**Target platform:** NVIDIA Jetson Orin Nano Super
**Status:** ✅ Jetson received. Now sourcing peripherals.

## Audio architecture decision (locked in)

JARVIS will support **BOTH internal speaker AND external Bluetooth** simultaneously, like Alexa:
- **Internal speaker** (MAX98357A + 50mm driver) — voice responses, alerts, ambient sounds at low volume, "always-on" audio
- **External Bluetooth** (any A2DP speaker) — music playback, story mode, anything that benefits from better fidelity
- Software (`AudioOutputProvider`) routes audio to the right output based on intent type and what's connected

> **How to read this document:** Each component has multiple purchase links ranked by trustworthiness. Prices were verified via web search on April 8, 2026. Always check the link before ordering — stock and pricing change frequently.

> **Trustworthiness scale:** ★★★★★ = Official/authorized distributor, ★★★★ = Well-known Indian retailer, ★★★ = Reputable niche store, ★★ = Marketplace seller (verify before buying), ★ = Unknown/risky

---

## 1. Compute Board — NVIDIA Jetson Orin Nano Super Developer Kit (8GB)

The heart of JARVIS. 67 TOPS AI performance, 1024-core Ampere GPU, 6-core ARM CPU, 8GB LPDDR5.

| # | Seller | Est. Price (₹) | Link | Trust | Notes |
|---|--------|----------------|------|-------|-------|
| 1 | **RPtech India** (NVIDIA authorized) | ~33,000 | [rptechindia.com](https://rptechindia.com/jetson-orin-nano-8gb-developer-kit.html) | ★★★★★ | Official NVIDIA distributor for India. Contact for quote — may require GST invoice. Best price guarantee. |
| 2 | **Robu.in** | ~34,679 | [robu.in](https://robu.in/product/nvidia-jetson-orin-nano-super-developer-kit/) | ★★★★ | Major Indian robotics/electronics store. Reliable shipping. Listed as of Feb 2026. |
| 3 | **IndiaMART (Avinya)** | ~33,000 | [indiamart.com](https://www.indiamart.com/proddetail/nvidia-jetson-orin-nano-super-developer-kit-2855511390333.html) | ★★★ | B2B marketplace — may require bulk inquiry. Pune-based seller. Verify GST and warranty. |
| 4 | **ThinkRobotics** | ~35,000–38,000 | [thinkrobotics.com](https://thinkrobotics.com/products/nvidia-jetson-orin-nano-developer-kit) | ★★★★ | Also sells a "Deployment Kit" (Made in India, Waveshare bundle with NVMe pre-flashed). Slightly pricier but includes extras. |
| 5 | **Tanna TechBiz** | ~33,000–35,000 | [tannatechbiz.com](https://tannatechbiz.com/nvidia-jetson-orin-nano-developer-kit.html) | ★★★ | Indian online retailer. Verify stock before ordering. |
| 6 | **Amazon.in** | ~35,000–40,000 | [amazon.in](https://www.amazon.in/NVIDIA-Jetson-Orin-Nano-Developer/dp/B0BZJTQ5YP) | ★★★★ | Reliable delivery/returns. Price is often inflated by third-party sellers. Check seller rating. |
| 7 | **CrazyPi** | ~38,670 | [crazypi.com](https://www.crazypi.com/jetson-orin-nano-super-developer-kit) | ★★★ | Indian electronics store. Higher price. |
| 8 | **RS India (RS Components)** | ~43,025 (incl. GST) | [in.rsdelivers.com](https://in.rsdelivers.com/product/nvidia/945-13766-0005-000/nvidia-jetson-orin-nano-8gb-developer-kit-945-0005/2647384) | ★★★★★ | Global authorized distributor. Premium price but guaranteed authentic with proper invoice/warranty. |

**Recommendation:** Try RPtech India first (official distributor, best price). If they have long lead times, go Robu.in or ThinkRobotics.

---

## 2. Microphone — ReSpeaker Mic Array v3.0

4-mic far-field array, XMOS XVF-3000 DSP, USB plug-and-play, built-in 12 RGB LEDs, beamforming + noise suppression. Up to 5m voice detection.

| # | Seller | Est. Price (₹) | Link | Trust | Notes |
|---|--------|----------------|------|-------|-------|
| 1 | **Robocraze** | ~7,499 | [robocraze.com](https://robocraze.com/products/respeaker-mic-array-v3-0-with-4-mic-array-and-xvf3000-voice-processor-seeed-studio) | ★★★★ | Main Indian Seeed Studio retailer. Discounted from ₹7,999. Check stock — can go out of stock. |
| 2 | **ThinkRobotics** | ~7,500–8,000 | [thinkrobotics.com](https://thinkrobotics.com/products/respeaker-mic-array-v3-0) | ★★★★ | Another authorized Seeed reseller in India. Reliable shipping. |
| 3 | **Fab.to.Lab** | ~6,811 (bulk 2+) | [fabtolab.com](https://www.fabtolab.com/respeaker-mic-array-v2-0) | ★★★★ | Good Indian electronics store. Note: URL says "v2-0" but page shows v3.0. Check stock — was listed as out-of-stock previously. |
| 4 | **Amazon.in** (third-party) | ~12,000–18,000 | [amazon.in](https://www.amazon.in/seeed-Studio-Respeaker-Array-Microphones/dp/B07D29L3Q1) | ★★ | **AVOID** — massively inflated price from third-party sellers. Often lists the older v2.0 at v3.0 prices. |
| 5 | **Seeed Studio** (direct, international) | ~$59.90 (~₹5,000) | [seeedstudio.com](https://www.seeedstudio.com/ReSpeaker-Mic-Array-v3-0.html) | ★★★★★ | Official manufacturer. Cheapest per-unit but adds international shipping + customs (~₹1,500–2,500 extra). Total ~₹6,500–7,500. |

**Recommendation:** Robocraze is the safest bet — fair price, Indian warranty, fast shipping. If out of stock, try ThinkRobotics or order direct from Seeed Studio.

**Budget alternative:** TONOR TM20 USB conference mic (~₹3,000 on Amazon.in). No beamforming/LEDs but works for a quiet room. You'd add a separate NeoPixel ring for visual feedback.

---

## 3. Storage — NVMe SSD (M.2 2230)

The Jetson Orin Nano has an M.2 2230 slot. 256GB is plenty for OS + all AI models.

| # | Seller | Est. Price (₹) | Link | Trust | Notes |
|---|--------|----------------|------|-------|-------|
| 1 | **Amazon.in — EVM 256GB 2230** | ~2,499–5,499 | [amazon.in](https://www.amazon.in/EVM-256GB-M-2-NVMe-Internal/dp/B0D47LD32L) | ★★★★ | Indian brand. PCIe Gen 3x4, 3000MB/s read. 5-year warranty. Price fluctuates — check price history (lowest seen: ₹2,499). |
| 2 | **PrimeABGB — EVM 256GB 2230** | ~2,500–3,500 | [primeabgb.com](https://www.primeabgb.com/online-price-reviews-india/evm-256gb-2230-nvme-ssd-evmnv30-256gb/) | ★★★★ | Reputable Indian PC hardware retailer (Mumbai-based). Good prices. |
| 3 | **OnlySSD — EVM 256GB 2230** | ~2,500–3,500 | [onlyssd.com](https://onlyssd.com/buy/evm-256gb-2230-nvme-ssd-evmnv30-256gb/) | ★★★★ | Specialist SSD retailer in India. |
| 4 | **Variety Infotech — EVM 256GB** | ~2,149 | [varietyinfotech.com](https://varietyinfotech.com/product/evm-m-2-nvme-pcie-2230-256gb-ssd/) | ★★★ | Cheapest found. Less well-known — verify return policy. |
| 5 | **Amazon.in — Samsung PM991 256GB 2230** | ~3,500–5,000 | [amazon.in](https://www.amazon.in/S%D0%B0msu%D0%BFg-256GB-PCIe-NVMe-PM991/dp/B0BNPMHTV5) | ★★★ | Samsung OEM part (not retail). Reliable but pricier. Third-party seller — check ratings. |
| 6 | **HUBTRONICS — EVM 256GB 2230** | ~3,000–4,000 | [hubtronics.in](https://hubtronics.in/evm-m2-nvme-pcie-2230-256gb) | ★★★★ | Indian electronics retailer. Bundles well with Jetson purchase. |

**Recommendation:** EVM 256GB from Amazon.in or PrimeABGB — wait for a price drop to ~₹2,500 range. The EVM is a solid Indian brand with 5-year warranty.

**Important:** Must be **M.2 2230** form factor (not 2242 or 2280). The Jetson Orin Nano Dev Kit only accepts 2230.

---

## 4. Power Supply — 19V DC Barrel Adapter

The Jetson Orin Nano Dev Kit uses a **DC barrel jack (5.5mm OD × 2.5mm ID)** at **19V**. It does NOT charge via USB-C directly. You need a 19V laptop-style adapter rated at 45W minimum.

| # | Seller | Est. Price (₹) | Link | Trust | Notes |
|---|--------|----------------|------|-------|-------|
| 1 | **Techie Store — 19V 2.37A 45W (5.5×2.5mm)** | ~600–900 | [techiestore.in](https://techiestore.in/product/techie-45w-19v-2-37a-pin-size-5-5mm-x-2-5mm-compatible-toshiba-laptop-charger/) | ★★★ | Toshiba-compatible charger with correct 5.5×2.5mm barrel. Verify pin size carefully before buying. |
| 2 | **Flipkart — TecSone 45W 19V 2.37A** | ~800–1,200 | [flipkart.com](https://www.flipkart.com/tecsone-compatible-acer-45w-laptop-charger-19v-2-37a-5-5mm-x-1-7mm-45-w-adapter/p/itm2c2b31f327072) | ★★★★ | ⚠️ This listing is 5.5×**1.7**mm (Acer pin). You need 5.5×**2.5**mm. Search Flipkart for "19V 2.37A 5.5 2.5mm" instead. |
| 3 | **Amazon.in — Generic 19V 2.37A 5.5×2.5mm** | ~500–1,500 | Search: [amazon.in "19V 2.37A 5.5 2.5mm adapter"](https://www.amazon.in/s?k=19V+2.37A+5.5+2.5mm+adapter) | ★★★ | Multiple sellers. Check pin size (5.5×2.5mm), voltage (19V), and minimum 45W. Read reviews. |
| 4 | **Solutions365 — ASUS 19V 2.37A 45W (5.5×2.5mm)** | ~1,200–1,800 | [solutions365.in](https://solutions365.in/product/asus-19v-2-37a-45w-5-52-5mm-original-power-adapter-asus-45w-adapter-5-52-5mm/) | ★★★★ | Original ASUS adapter — reliable quality. Correct pin size. |
| 5 | **Yahboom — 19V/2.37A DC (Jetson-specific)** | ~$12 + shipping (~₹1,500–2,000 total) | [yahboom.net](https://category.yahboom.net/products/jetson-power-supply) | ★★★★ | Purpose-built for Jetson Orin Nano. International shipping adds cost. |

**⚠️ Critical:** The barrel connector must be **5.5mm outer diameter × 2.5mm inner diameter**. Many laptop adapters look the same but use 5.5×1.7mm (Acer) or other sizes. Double-check before buying. A wrong-size barrel can damage the Jetson.

**Recommendation:** Buy a Toshiba/ASUS-compatible 19V 2.37A adapter with 5.5×2.5mm barrel from Amazon.in or Flipkart (₹600–1,200). Or use any existing 19V laptop charger you have, with a barrel adapter tip.

---

## 5. LED Ring — WS2812B 24-LED NeoPixel Ring

For status lighting around the enclosure (idle=blue, listening=bright blue, thinking=orange, speaking=green, etc.).

| # | Seller | Est. Price (₹) | Link | Trust | Notes |
|---|--------|----------------|------|-------|-------|
| 1 | **Robokits India** | ~434 | [robokits.co.in](https://robokits.co.in/sensors/light-sensor/24-bit-ws2812-5050-rgb-led-built-in-full-color-driving-lights-ring-development-board?cPath=11_422) | ★★★★ | 24-bit WS2812 ring, 108mm outer diameter. In stock. Reliable Indian electronics store. |
| 2 | **Robu.in** | ~300–500 | [robu.in (WS2812B tag)](https://robu.in/product-tag/ws2812b/) | ★★★★ | Carries various WS2812B modules. Check for the 24-LED ring specifically. |
| 3 | **MG Super Labs** | ~400–600 | [mgsuperlabs.co.in](https://www.mgsuperlabs.co.in/estore/NeoPixel-Ring-24-WS2812-5050-RGB-LED) | ★★★ | Indian Adafruit reseller. May go out of stock — pre-order available. 66mm outer diameter (different from Robokits 108mm). |
| 4 | **Amazon.in** | ~400–800 | Search: [amazon.in "WS2812B 24 LED ring"](https://www.amazon.in/s?k=WS2812B+24+LED+ring) | ★★★ | Multiple sellers. Verify it's a ring (not strip) and 24 LEDs. Check reviews. |

**Note:** The enclosure CAD uses a 72mm ring. The Robokits ring is 108mm and the MG Super Labs one is 66mm — you may need to adjust the CAD model or find the exact 72mm size. Alternatively, a 16-LED ring (smaller) from Robokits is ₹277.

**Recommendation:** Robokits India at ₹434 — well-stocked, reliable, cheap.

---

## 6. Amplifier Board — MAX98357A I2S 3W Class D

Converts I2S digital audio from Jetson to amplified analog for the enclosure speaker. Needed if you're building a speaker into the enclosure (not using external Bluetooth speaker).

| # | Seller | Est. Price (₹) | Link | Trust | Notes |
|---|--------|----------------|------|-------|-------|
| 1 | **Robokits India** | ~89 | [robokits.co.in](https://robokits.co.in/sensors/sound/max98357-i2s-3w-class-d-amplifier-interface-audio-decoder-module-filterless-board-for-raspberry-pi-esp32) | ★★★★ | Cheapest option. Generic Chinese module — perfectly functional. |
| 2 | **HUBTRONICS** | ~114 (incl. GST) | [hubtronics.in](https://hubtronics.in/max98357a-stereo-amplifier-module) | ★★★★ | 264 units in stock. Reliable Indian retailer. |
| 3 | **Robocraze (SmartElex)** | ~168–425 | [robocraze.com](https://robocraze.com/products/smartelex-max98357a-i2s-audio-breakout-amplifier-for-raspberry-pi-and-microcontrollers) | ★★★★ | SmartElex branded version. Higher quality PCB. |
| 4 | **Amazon.in** | ~200–500 | [amazon.in](https://www.amazon.in/MAX98357-Amplifier-Interface-Filterless-Raspberry/dp/B08XJSV2BH) | ★★★ | Third-party sellers. Check reviews. |

**Recommendation:** Robokits at ₹89 — dirt cheap and works perfectly for this use case.

**Note:** Only needed if building a speaker into the enclosure. If using an external Bluetooth speaker (JBL etc.), skip this.

---

## 7. Speaker Driver — 40–50mm Full Range

Small speaker to build into the enclosure. Paired with the MAX98357A amplifier above.

| # | Seller | Est. Price (₹) | Link | Trust | Notes |
|---|--------|----------------|------|-------|-------|
| 1 | **MakerBazar** | ~110 | [makerbazar.in](https://makerbazar.in/collections/buzzers-and-speakers) | ★★★★ | 50mm Bluetooth Audio Speaker Driver, 4Ω 3W. Good for voice + basic music. |
| 2 | **Amazon.in** | ~100–300 | Search: [amazon.in "40mm speaker 4 ohm 3W"](https://www.amazon.in/s?k=40mm+speaker+4+ohm+3W) | ★★★ | Multiple options. Look for 40–50mm, 4Ω or 8Ω, 3W minimum. |
| 3 | **Robu.in** | ~100–200 | Search on [robu.in](https://robu.in/?s=speaker+driver) | ★★★★ | Check their speaker/buzzer category. |

**Recommendation:** MakerBazar at ₹110. But honestly, for music quality you're much better off with an external Bluetooth speaker. This built-in speaker is mainly for voice responses and alerts.

**Note:** Only needed if building a speaker into the enclosure. If using an external Bluetooth speaker, skip this.

---

## 8. Touchscreen Display — Waveshare 5.5" AMOLED HDMI

The bedside dashboard. 1080×1920 portrait orientation, capacitive touch (5-point), HDMI input, AMOLED for true blacks (perfect for the dark theme), 6H toughened glass cover.

| # | Seller | Est. Price (₹) | Link | Trust | Notes |
|---|--------|----------------|------|-------|-------|
| 1 | **Robocraze** | ~9,500–10,500 | [robocraze.com](https://robocraze.com/products/waveshare-5-5inch-hdmi-capacitive-touch-amoled-display-1080x1920-with-case) | ★★★★ | Includes plastic case. Indian warranty. Most reliable seller for this. |
| 2 | **Robu.in** | ~9,500–11,000 | [robu.in](https://robu.in/product/waveshare-5-5inch-1080x1920-hdmi-amoled-capacitive-touch-screen-with-case/) | ★★★★ | Same Waveshare unit. Check stock. |
| 3 | **ElectronicsComp** | ~9,500–10,500 | [electronicscomp.com](https://www.electronicscomp.com/waveshare-5.5inch-1080x1920-hdmi-amoled-capacitive-touch-screen-with-case) | ★★★★ | Reliable Indian retailer. |
| 4 | **Zbotic** | ~10,000–11,500 | [zbotic.in](https://zbotic.in/product/waveshare-5-5inch-1080x1920-hdmi-amoled-capacitive-touch-screen-with-case/) | ★★★ | Indian electronics store. |
| 5 | **IndiaMART (Luster Electronics, Gandhinagar)** | ~10,089 | [indiamart.com](https://www.indiamart.com/proddetail/waveshare-5-5-inch-hdmi-amoled-capacitive-touch-screen-25015638591.html) | ★★★ | Direct from authorized reseller. May need GST inquiry. |
| 6 | **Amazon.in** | ~10,500–14,000 | [amazon.in](https://www.amazon.in/5-5inch-HDMI-AMOLED-Resolution-Capacitive/dp/B07ZPCLTVW) | ★★★ | Multiple sellers. Higher price but Amazon return policy. |
| 7 | **Evelta** | varies | [evelta.com](https://www.evelta.com/5-5inch-amoled-capacitive-touch-screen-waveshare/) | ★★★ | Carries Waveshare line. Check stock. |
| 8 | **Waveshare direct** | ~$129 (~₹10,800) + intl shipping | [waveshare.com](https://www.waveshare.com/5.5inch-hdmi-amoled-with-case.htm) | ★★★★★ | Official manufacturer. Adds shipping + customs (~₹2,000). Slower delivery. |

**Connectivity to Jetson:**
- 1× Mini HDMI cable (display side) → Standard HDMI (Jetson side)
- 1× USB-A to USB-C cable for touch input + power (single cable carries both on this display)

**Recommendation:** Robocraze at ~₹10,000 — lowest price from a reliable Indian seller with the protective case included.

**Important:** Get the version **WITH CASE** — the bare display is fragile. The case has M2.5 mounting points perfect for integrating into the enclosure.

---

## 9. Active Cooling — PWM Fan + Heatsink

The Jetson Orin Nano dev kit ships with a passive heatsink that's adequate at 7W but throttles under sustained AI workloads (Ollama + Whisper running simultaneously can hit 15W+). An active fan is essential for the MAXN performance mode we'll be running.

| # | Seller | Est. Price (₹) | Link | Trust | Notes |
|---|--------|----------------|------|-------|-------|
| 1 | **Amazon.in (Generic PWM Fan for Orin Nano)** | ~600–1,200 | [amazon.in](https://www.amazon.in/Cooling-Adjustable-Embedded-Bracket-Modules/dp/B0C9F55LF3) | ★★★ | DC 5V PWM speed-adjustable, comes with screws. Direct mount on dev kit heatsink. |
| 2 | **Robocraze / Robu.in** | ~800–1,500 | Search "Jetson Orin Nano fan" on [robocraze.com](https://robocraze.com) or [robu.in](https://robu.in) | ★★★★ | Multiple options, verify it fits the dev kit (40×40mm or specific Orin mount) |
| 3 | **Waveshare Orin-FAN-PWM (Official)** | ~$10 + shipping (~₹1,800–2,500) | [waveshare.com](https://www.waveshare.com/orin-fan-pwm.htm) | ★★★★★ | Official cooling fan for Orin Nano with elastic bracket. Best fit, slow international shipping. |
| 4 | **Seeed Studio (Heatsink + Fan combo)** | ~$24 (~₹2,000) + shipping | [seeedstudio.com](https://www.seeedstudio.com/Aluminum-Heatsink-with-Fan-for-Jetson-Orin-NX-Orin-Nano-Xavier-NX-Module-p-5633.html) | ★★★★★ | Full aluminum heatsink + fan. Only needed if NOT using the dev kit (dev kit has its own heatsink). |

**Note:** The dev kit ALREADY has a passive heatsink — you only need to add a small PWM fan on top. The Seeed combo is for bare modules without the dev kit carrier.

**PWM control:** The dev kit has a 4-pin fan header that supports PWM speed control. JetPack will auto-throttle the fan based on temperature. Set up: `sudo nvpmodel -m 0 && sudo jetson_clocks --fan` to enable auto-adjusted fan curve.

**Recommendation:** Generic PWM fan from Amazon.in at ~₹800. Dev kit's existing heatsink is fine — just add active airflow.

---

## 10. Bluetooth Speaker (External, for music)

You already have Bluetooth speakers in the household — anything A2DP-compatible works. If buying new specifically for JARVIS:

| Speaker | Est. Price (₹) | Why |
|---------|----------------|-----|
| **JBL Go 4** | ~3,500–4,500 | Compact bedside size, great for voice + casual music, IP67. |
| **JBL Flip 6/7** | ~10,000–14,000 | Rich bass for music, 12-hour battery, IP67. Best music quality in this range. |
| **Marshall Emberton II** | ~12,000–15,000 | Premium aesthetic, classic look, fits bedside design language. |
| **Sony SRS-XB100** | ~3,500–4,500 | Cheaper alternative to JBL Go, slightly better mids. |
| **boAt Stone 350** | ~1,500–2,500 | Budget option. Lower fidelity but very affordable. |

**Recommendation:** Use whatever Bluetooth speaker you already own first. The pairing is software (already supported via `bluetoothctl` on Jetson + our `AudioOutputProvider`). Only buy new if you want better music quality and the existing one isn't cutting it.

**Important for software:** the Jetson Orin Nano has built-in Bluetooth 5.0. We pair via the API/dashboard's Bluetooth scanner (already built in `controls_panel.dart`).

---

## 11. Cables & Miscellaneous

| Item | Est. Price (₹) | Where to Buy | Notes |
|------|----------------|-------------|-------|
| **Micro HDMI → HDMI cable** (for initial setup) | ~200–400 | [Amazon.in — PiBOX India](https://www.amazon.in/India-Adapter-Ethernet-Compatible-Raspberry/dp/B08PW6W54V) or [AmazonBasics](https://www.amazon.in/AmazonBasics-High-Speed-Micro-HDMI-Micro-USB-Cable/dp/B014I8TVLI) | Needed for first boot / debugging. 1.5m is enough. |
| **USB-A to USB-C cable** (for ReSpeaker) | ~150–300 | Amazon.in | Connect ReSpeaker mic to Jetson USB port. |
| **Ethernet cable** (optional, for setup) | ~100–200 | Amazon.in | More reliable than WiFi for initial setup. |
| **Jumper wires (M-F, F-F)** | ~50–100 | [Robu.in](https://robu.in/product-tag/jumper-wires/) or [Robokits](https://robokits.co.in/) | For GPIO connections (LED ring, etc.). |
| **M2.5 brass heat-set inserts** (25 pack) | ~85 (₹3.40 each) | [Robokits](https://robokits.co.in/robot-parts/nut-bolts-standoffs/standoffs/m2.5-x-5-mm-brass-heat-threaded-round-insert-nut-moq-25-pcs.) | For 3D-printed enclosure screw posts. |
| **M2.5 screws** (assorted) | ~50–100 | Robu.in or Robokits | For mounting Jetson to enclosure posts. |
| **Thermal pads** (1–2mm) | ~200–400 | Amazon.in | For Jetson thermal management in enclosure. |

---

## Budget Summary — Core Hardware

| Component | Est. Price (₹) | Status / Priority |
|-----------|----------------|---------------|
| Jetson Orin Nano Super Dev Kit | 33,000–35,000 | ✅ **Owned** |
| **NVMe SSD 256GB (M.2 2230)** | 2,500–3,500 | 🛒 **Buy now** — needed to flash JetPack |
| **Power Supply (19V DC barrel 5.5×2.5mm)** | 600–1,500 | 🛒 **Buy now** — needed to power up |
| **Micro HDMI cable** | 200–400 | 🛒 **Buy now** — initial setup |
| **Active PWM Cooling Fan** | 600–1,200 | 🛒 **Buy now** — sustained AI workloads will throttle without it |
| **ReSpeaker Mic Array v3.0** | 7,000–7,500 | 🛒 **Buy now** — voice testing on Jetson |
| **Waveshare 5.5" AMOLED Touchscreen + Case** | 9,500–11,000 | 🛒 **Buy now** — bedside dashboard display |
| MAX98357A Amplifier (internal speaker) | 89–170 | Phase 2 — internal speaker for voice/alerts |
| Speaker Driver 50mm (internal speaker) | 110–200 | Phase 2 — paired with MAX98357A |
| WS2812B 24-LED Ring | 400–500 | Phase 3 — needs enclosure design |
| Bluetooth speaker (external) | 0 (already owned) or 3,500–14,000 if new | Optional — use existing if you have one |
| Cables & misc (USB, jumpers, screws) | 500–1,000 | 🛒 **Buy now** — small bits |
| **TOTAL (immediate Phase 1 + 1.5 buy)** | **~₹21,000–26,000** | |
| **TOTAL (with internal speaker + LED)** | **~₹21,800–28,000** | |

**Not included (you already own):**

- Jetson Orin Nano (✅ received)
- USB keyboard + mouse (for initial setup)
- HDMI monitor (for initial setup — use any TV; touchscreen will replace later)
- WiFi network
- Likely a Bluetooth speaker (any A2DP works)

---

## Purchase Order (What to Buy When)

| Phase | Items | Total ₹ | Why |
|-------|-------|---------|-----|
| **Phase 1A — TODAY** | NVMe 2230 SSD + 19V/5.5×2.5mm power supply + Micro HDMI cable | ~3,500–5,500 | Boot the Jetson with JetPack. Without these the dev kit is a brick. |
| **Phase 1B — TODAY** | PWM cooling fan + thermal pads | ~800–1,500 | Install during JetPack flash. Sustained Ollama runs will thermal-throttle without active cooling. |
| **Phase 2 — This week** | ReSpeaker Mic Array v3.0 + USB-A→USB-C cable | ~7,500 | Test voice pipeline on Jetson hardware. Order from Robocraze. |
| **Phase 3 — This week/next** | Waveshare 5.5" AMOLED touchscreen + case + Mini HDMI cable | ~10,500 | Get the actual dashboard experience running on the target screen. Can use HDMI monitor in the meantime. |
| **Phase 4 — After basic enclosure** | MAX98357A amp + 50mm speaker driver + jumper wires + brass inserts | ~500–800 | Internal speaker for voice/alerts. Bluetooth speaker handles music. |
| **Phase 5 — Final polish** | WS2812B 24-LED ring | ~500 | Status lighting around enclosure. Wait until enclosure CAD is final. |

**Total to spend in next ~2 weeks:** ~₹22,000 (Phases 1A + 1B + 2 + 3)

---

## Important Warnings

1. **Pin size matters for power supply.** The Jetson barrel jack is 5.5mm × 2.5mm. Many laptop chargers look identical but have different inner diameters (1.7mm for Acer, 2.1mm for some). Using the wrong size can damage the board.

2. **NVMe form factor must be 2230.** The Jetson dev kit physically cannot fit 2242 or 2280 SSDs. Triple-check before buying.

3. **Avoid Amazon.in for the ReSpeaker.** Third-party sellers charge 2–3x the fair price and sometimes sell the older v2.0. Buy from Robocraze or ThinkRobotics.

4. **RPtech India is NVIDIA's official Indian distributor.** For the Jetson, they offer the best price and proper warranty. Contact them first even if their website looks basic.

5. **International ordering** (Seeed Studio, Yahboom, etc.) adds ₹1,500–3,000 in customs/shipping and takes 2–4 weeks. Only use as fallback if Indian retailers are out of stock.

6. **Touchscreen needs Mini HDMI cable** (not Micro HDMI). The Jetson outputs HDMI via DisplayPort/HDMI port (full-size HDMI). The Waveshare AMOLED display has a Mini HDMI input. So you need a **Standard HDMI → Mini HDMI** cable, NOT Micro HDMI. Different connector — easy to confuse.

7. **Active cooling is non-negotiable for AI workloads.** The dev kit's stock passive heatsink is fine for idle/light loads but will thermal-throttle under sustained Ollama + Whisper inference, which is exactly what JARVIS does. Buy the fan with everything else, install before first power-on.

---

*Prices verified via web search on April 8–9, 2026. Stock availability changes frequently — check links before ordering.*
