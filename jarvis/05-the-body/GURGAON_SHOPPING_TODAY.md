# JARVIS — Walk-in Shopping Guide (Gurgaon)

**For:** ananddevesh22@gmail.com
**Date:** Today
**Goal:** Boot the Jetson Orin Nano without waiting for delivery

---

## What you need (4 items + bag of cables)

| # | Item | Specs to verify | Budget (₹) |
|---|------|-----------------|------------|
| 1 | **NVMe SSD M.2 2280** | 256GB or 500GB · PCIe NVMe (NOT SATA) · 80mm long · WD/Crucial/Samsung/Kingston/Adata brand | 2,500–5,500 |
| 2 | **19V Laptop-style power adapter** | 19V (NOT 19.5V or 20V) · 45W minimum · **5.5×2.5mm barrel pin** · Toshiba/ASUS-compatible | 600–1,200 |
| 3 | **DisplayPort → HDMI adapter** | DP male → HDMI female · 1080p minimum (4K nice to have) · passive | 300–500 |
| 4 | **40mm 5V PWM fan** | 40×40mm · 5V (NOT 12V) · 4-pin connector preferred (3-pin OK) | 200–500 |

**Total: ~₹3,600–7,700**

---

## Where to buy in Gurgaon (in priority order)

### 🎯 Sector 14 Gurgaon Market (best — 15 min from anywhere in Gurgaon)

| Shop | Address | Phone (verify) |
|------|---------|----------------|
| **Techeroes Computer Shop** | Shop 3 & 4, AKD Tower, Sector 14 | Search Magicpin |
| **Globe Computer Peripherals** | Shop 49, Sector 14 (opp. Om Sweets, near Burger Point) | — |
| **Satya Computer Solution** | Sector 14 (Lenovo authorized) | — |

**Hours:** Mon-Sat 9:30am–8:30pm, Sun 10am–8:30pm
**Strategy:** Walk in, ask for the 4 items above. Bargain — these shops typically run 10-15% above Amazon prices.

### 🥈 Croma / Reliance Digital (backup)

- Croma Cyber Hub (DLF Cyber Hub, Tower D)
- Croma Ambience Mall (NH-8)
- Reliance Digital Ambience Mall
- Reliance Digital MGF Metropolitan (MG Road)

Premium pricing (15-25% above Amazon) but reliable warranty.

### 🚗 Last resort: Nehru Place, Delhi (~30-45 min)

Best selection but half-day trip.
- **Kosmix** — NVMe SSDs, all brands
- **Link Technology** — components
- **Cruserr Technology** — SSDs, RAM
- **Pratham Peripherals** — cables, accessories
- **IT Assets World** — bulk + retail with warranty + GST

---

## ⚠️ Critical things to verify in person before paying

### 1. NVMe SSD
- Label must say **"M.2 2280"** explicitly
- Physical length should be **~80mm** (about 3 inches)
- Must say **"NVMe"** or **"PCIe Gen3/Gen4"**, NOT "SATA"
- **REJECT** if shorter (those are 2230 or 2242)
- **REJECT** if labeled "Raspberry Pi SSD" or comes with a HAT
- **REJECT** the bundle the IoT shop tried to send (it was a Pi 5 SSD Kit, not a Jetson part)

### 2. Power adapter
- Voltage: **19V** ideally; 19.5V (HP/Dell) will work but technically wrong; **20V is too high — DON'T BUY**
- Wattage: **45W minimum** (a 65W or 90W is fine, more headroom)
- Pin size: **5.5mm × 2.5mm** outer × inner. Toshiba/ASUS-compatible
- **REJECT** Acer (5.5×1.7), Dell (7.4×5.0), HP (4.5×3.0) — wrong physical fit
- **REJECT** USB-C chargers — Jetson uses barrel jack, not USB-C
- **REJECT** Lenovo 20V — voltage too high, may damage Jetson

### 3. DisplayPort → HDMI adapter
- DisplayPort male connector on one end (NOT Mini DisplayPort)
- HDMI female on the other (or HDMI cable as alternative)
- Passive adapter is fine (cheaper than active)
- Should support 1080p at minimum

### 4. Fan
- Size: **40mm × 40mm** square
- Voltage: **5V** (NOT 12V — won't work with Jetson's fan header)
- Connector: 4-pin preferred (PWM speed control), 3-pin acceptable
- The Jetson dev kit has a JST-style fan header on the carrier board

---

## What NOT to do

- ❌ Don't buy "Raspberry Pi" branded SSD — it's a Pi-specific bundle that won't work with Jetson
- ❌ Don't buy a HAT (Hardware Attached on Top) — these are Pi accessories
- ❌ Don't buy USB-C charger — Jetson uses barrel jack
- ❌ Don't buy Micro HDMI cable — Jetson outputs DisplayPort, not Micro HDMI
- ❌ Don't accept any item where the seller can't tell you the exact size/voltage/connector

---

## Items to NOT buy in person (order online instead)

- **ReSpeaker Mic Array v3.0** — order from [Robocraze](https://robocraze.com/products/respeaker-mic-array-v3-0-with-4-mic-array-and-xvf3000-voice-processor-seeed-studio) (~₹7,499). Local shops sell the older v2.0 at v3.0 prices.
- **Waveshare 5.5" AMOLED touchscreen** — order from [Robocraze](https://robocraze.com/products/waveshare-5-5inch-hdmi-capacitive-touch-amoled-display-1080x1920-with-case) (~₹10,000). Niche specialty item.

These two arrive in 2-3 days. The 4 items you're buying today are enough to boot the Jetson and start software setup.

---

## After you bring the parts home

1. **Plug in the SSD** to the M.2 Key M slot on the underside of the Jetson dev kit
2. **Mount the fan** on the existing heatsink (use thermal pad if there's a gap)
3. **Connect** monitor (via DP→HDMI adapter), USB keyboard, USB mouse
4. **Plug in power** (verify pin fit before pushing in)
5. **First boot** — JetPack first-time setup wizard appears

Ping me back here when you have the parts and I'll walk you through the JetPack flash + first boot.
