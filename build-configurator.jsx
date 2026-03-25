import { useState, useMemo } from "react";

// ============================================================
// JARVIS Build Configurator
// Mix-and-match components, see total cost, compare builds
// All prices in INR, all links India-deliverable
// ============================================================

// Stock status legend: "in-stock", "low-stock", "check", "out-of-stock"
const CATEGORIES = [
  {
    id: "compute",
    label: "Compute Board",
    icon: "CPU",
    required: true,
    options: [
      {
        id: "jetson-orin-nano-8gb",
        name: "NVIDIA Jetson Orin Nano Super 8GB (Dev Kit)",
        price: [28000, 35000],
        link: "amazon.in/dp/B0BZJTQ5YP",
        altLinks: ["tannatechbiz.com/nvidia-jetson-orin-nano-developer-kit.html", "fabtolab.com/seeed-nvidia-jetson-orin-nano-super-developer-kit", "thinkrobotics.com (Made-in-India deployment kit)"],
        note: "Primary target. CUDA GPU, 8GB shared RAM. Runs 3B-7B LLMs locally via Ollama.",
        tags: ["recommended"],
        stock: "in-stock",
      },
      {
        id: "rpi5-8gb",
        name: "Raspberry Pi 5 (8GB)",
        price: [7200, 8000],
        link: "hubtronics.in/raspberry-pi-5-8gb",
        altLinks: ["silverlineelectronics.in (in stock)", "amazon.in/s?k=raspberry+pi+5+8gb (Rs 8-15k, check seller)"],
        note: "Fallback. No GPU, CPU-only inference. Smallest models only. Authorized price Rs 7200-8000.",
        tags: ["budget", "fallback"],
        stock: "in-stock",
      },
      {
        id: "rpi5-ai-hat",
        name: "Raspberry Pi 5 (8GB) + AI HAT+ 2 (40 TOPS)",
        price: [17000, 20000],
        link: "hubtronics.in/raspberry-pi-5-8gb",
        altLinks: ["crazypi.com (AI HAT+ 26 TOPS)", "robocraze.com (AI Kit 13 TOPS)"],
        note: "Mid-range option. 40 TOPS NPU but limited to 1-1.5B models on Hailo. Different inference pipeline than Ollama.",
        tags: [],
        stock: "check",
      },
    ],
  },
  {
    id: "screen",
    label: "Front Screen",
    icon: "SCREEN",
    required: false,
    options: [
      {
        id: "no-screen",
        name: "No Screen (Phase 1 - Voice Only)",
        price: [0, 0],
        link: "",
        note: "Blank front panel with speaker grille. Add a screen later by swapping the front panel.",
        tags: ["phase1"],
        isNone: true,
        stock: "in-stock",
      },
      {
        id: "waveshare-5dp",
        name: "Waveshare 5DP-CAPLCD-H (5 inch IPS, narrow bezel)",
        price: [4500, 5500],
        link: "hubtronics.in/5dp-caplcd-h",
        altLinks: ["waveshare.com/5dp-caplcd.htm (global, ships to India)"],
        note: "Best value. 1024x600, 800 nits, 3-4mm bezel, air-bonded glass. Plug-and-play HDMI + USB touch.",
        tags: ["recommended", "phase2"],
        specs: "1024x600 | IPS | 800 nits | 3-4mm bezel",
        stock: "check",
      },
      {
        id: "waveshare-5-amoled",
        name: "Waveshare 5.5 inch AMOLED",
        price: [10000, 10500],
        link: "robu.in/product/waveshare-5-5inch-1080x1920-hdmi-amoled-capacitive-touch-screen-with-case/",
        altLinks: ["evelta.com/5-5inch-amoled-capacitive-touch-screen-waveshare/", "indiamart.com (search: waveshare 5.5 amoled, Rs 10089)", "amazon.in/dp/B07N8WWDRK"],
        note: "Thinnest bezel (2-3mm), true blacks, 1080x1920 portrait. Premium. Check stock - some sellers show out-of-stock.",
        tags: ["premium", "phase2"],
        specs: "1080x1920 | AMOLED | 2-3mm bezel",
        stock: "check",
      },
      {
        id: "waveshare-5-v4",
        name: "Waveshare 5 inch LCD (H) V4",
        price: [3500, 4500],
        link: "amazon.in/dp/B0BR8HRGSZ",
        altLinks: ["robu.in/product/waveshare-5inch-800x480-hdmi-capacitive-touch-screen-lcd-h-display-slimmed-down-version-v4/", "rees52.com (search: waveshare 5 inch)", "robomart.com (search: waveshare 5 inch)"],
        note: "Budget 5 inch. 800x480, standard brightness, 4-5mm bezel. Most widely available in India.",
        tags: ["budget", "phase2"],
        specs: "800x480 | IPS | Standard brightness",
        stock: "in-stock",
      },
      {
        id: "waveshare-7",
        name: "Waveshare 7 inch HDMI LCD (H) with case",
        price: [5000, 7000],
        link: "amazon.in/dp/B077PLVZCX",
        altLinks: ["hubtronics.in/7inch-hdmi-lcd-c", "robu.in/product/waveshare-7-inch-capacitive-hdmi-lcd-display-h-with-case/", "tannatechbiz.com (search: waveshare 7 inch)", "evelta.com/7inch-capacitive-touch-screen-hdmi-lcd-1024x600-with-case-waveshare/"],
        note: "Biggest screen. 1024x600 IPS. Amazon shows low stock - check alternatives.",
        tags: ["phase2"],
        specs: "1024x600 | IPS | 5-6mm bezel",
        stock: "low-stock",
      },
    ],
  },
  {
    id: "audio",
    label: "Audio Output",
    icon: "SPEAKER",
    required: true,
    options: [
      {
        id: "usb-codec-10w",
        name: "Waveshare USB Audio Codec + 50mm 10W Speaker",
        price: [2300, 3000],
        link: "waveshare.com/usb-to-audio.htm",
        altLinks: ["amazon.in/s?k=waveshare+usb+audio+codec (check availability)", "amazon.in/dp/B0BN44QCFQ (Electronic Spices 50mm speaker)"],
        note: "USB plug-and-play codec (no I2S wiring) + 50mm pre-wired speaker. Best sound. Codec may need Waveshare direct or AliExpress.",
        tags: ["recommended"],
        stock: "check",
      },
      {
        id: "usb-codec-3w",
        name: "Waveshare USB Audio Codec + 40mm 3W Speaker",
        price: [2100, 2700],
        link: "waveshare.com/usb-to-audio.htm",
        altLinks: ["amazon.in/s?k=40mm+3W+speaker"],
        note: "Same codec, smaller speaker. Adequate for voice, weak for music.",
        tags: ["budget"],
        stock: "check",
      },
      {
        id: "usb-speaker",
        name: "USB Mini Speaker (all-in-one)",
        price: [500, 1000],
        link: "amazon.in/s?k=usb+mini+speaker+portable",
        note: "Cheapest option. Single USB cable, no separate codec needed. Sound quality is basic.",
        tags: ["budget"],
        stock: "in-stock",
      },
    ],
  },
  {
    id: "mic",
    label: "Microphone Array",
    icon: "MIC",
    required: true,
    options: [
      {
        id: "respeaker-4mic",
        name: "ReSpeaker 4-Mic Array (HAT)",
        price: [2000, 3000],
        link: "fabtolab.com/repeaker-4-mic-array-rpi",
        altLinks: ["thingbits.in/products/respeaker-4-mic-array-for-raspberry-pi", "mgsuperlabs.com (check stock)", "robozar.com/product/respeaker-4-mic-array-for-raspberry-pi/"],
        note: "4 mics with beamforming. Plugs onto GPIO header (has pass-through header on top for LED + OLED wiring). Eliminates need for GPIO breakout board. Stock is spotty - check before ordering.",
        tags: ["recommended"],
        stock: "check",
      },
      {
        id: "respeaker-2mic",
        name: "ReSpeaker 2-Mic Pi HAT",
        price: [800, 1200],
        link: "fabtolab.com/respeaker-hat",
        altLinks: ["amazon.in/s?k=respeaker+2+mic+hat"],
        note: "2 mics, simpler. Good enough for small rooms.",
        tags: ["budget"],
        stock: "check",
      },
      {
        id: "usb-mic",
        name: "USB Conference Microphone",
        price: [1500, 3000],
        link: "amazon.in/s?k=usb+conference+microphone+omnidirectional",
        note: "Plug-and-play USB. No GPIO wiring. Good pickup. Always in stock on Amazon.",
        tags: [],
        stock: "in-stock",
      },
    ],
  },
  {
    id: "status",
    label: "Status Display (Top)",
    icon: "OLED",
    required: true,
    options: [
      {
        id: "oled-1-3",
        name: "1.3 inch I2C OLED (SH1106)",
        price: [350, 700],
        link: "amazon.in/dp/B0BSVBKD8R",
        altLinks: ["dnatechindia.com/sh1106-I2C-128-64-oled-display-module-blue-india.html", "quartzcomponents.com/products/oled-display-1-3-inch-i2c-interface-4-pin-white-sh1106"],
        note: "Shows status, now playing, personality. 4 Dupont wires to I2C pins. In stock on Amazon.in.",
        tags: ["recommended"],
        stock: "in-stock",
      },
      {
        id: "oled-0-96",
        name: "0.96 inch I2C OLED (SSD1306)",
        price: [150, 350],
        link: "amazon.in/s?k=0.96+inch+OLED+I2C+display",
        note: "Smaller but cheaper. Same wiring, less visible.",
        tags: ["budget"],
        stock: "in-stock",
      },
    ],
  },
  {
    id: "leds",
    label: "LED Ring",
    icon: "LED",
    required: false,
    options: [
      {
        id: "no-leds",
        name: "No LED Ring",
        price: [0, 0],
        link: "",
        note: "Skip the ring. You can always add it later.",
        tags: [],
        isNone: true,
        stock: "in-stock",
      },
      {
        id: "ws2812b-24",
        name: "WS2812B 24-LED Ring (65-72mm)",
        price: [200, 500],
        link: "amazon.in/dp/B0D5CQ4PHS",
        altLinks: ["amazon.in/dp/B0B2D7742J (DIYmall 5-pack)"],
        note: "Fits the top plate channel. 3 Dupont wires to GPIO. Per-personality colors. In stock on Amazon.in.",
        tags: ["recommended"],
        stock: "in-stock",
      },
      {
        id: "ws2812b-16",
        name: "WS2812B 16-LED Ring (45mm)",
        price: [150, 300],
        link: "amazon.in/s?k=WS2812B+16+LED+ring",
        note: "Smaller, subtler glow. Same wiring.",
        tags: ["budget"],
        stock: "in-stock",
      },
    ],
  },
  {
    id: "wiring",
    label: "Wiring and Mounting",
    icon: "CABLE",
    required: true,
    options: [
      {
        id: "wiring-full",
        name: "Full Kit (jumpers + standoffs + cables + ties)",
        price: [950, 1850],
        link: "amazon.in/s?k=40+pin+GPIO+screw+terminal+breakout",
        altLinks: ["amazon.in/s?k=dupont+jumper+wire+120", "amazon.in/s?k=M2.5+nylon+standoff", "amazon.in/s?k=magnetic+usb+c+cable"],
        note: "Dupont Wires 120pc (Rs 150-250), M2.5 Standoffs (Rs 200-400), Magnetic USB-C (Rs 400-800), Velcro Ties (Rs 150-250), short HDMI 30cm (Rs 200-400). GPIO breakout NOT needed if using ReSpeaker (it has pass-through header).",
        tags: ["recommended"],
        stock: "in-stock",
      },
      {
        id: "wiring-minimal",
        name: "Minimal (jumper wires + USB-C cable only)",
        price: [350, 550],
        link: "amazon.in/s?k=dupont+jumper+wire+120",
        note: "Just the essentials. Dupont jumpers + a USB-C cable. No standoffs or cable management.",
        tags: ["budget"],
        stock: "in-stock",
      },
    ],
  },
  {
    id: "printing",
    label: "3D Printing",
    icon: "PRINT",
    required: true,
    options: [
      {
        id: "print-service",
        name: "3Ding.in FDM Print Service (all 6 parts)",
        price: [3500, 5500],
        link: "3ding.in",
        note: "Upload STL files. FDM/PLA, Standard, 20% infill, White or Black. Ships in 3-5 days.",
        tags: ["recommended"],
        stock: "in-stock",
      },
      {
        id: "print-self",
        name: "Self-print (own printer, PLA filament only)",
        price: [200, 500],
        link: "amazon.in/s?k=PLA+filament+1.75mm+1kg",
        note: "Just filament cost. Needs access to an FDM printer.",
        tags: ["budget"],
        stock: "in-stock",
      },
    ],
  },
];

// Preset builds
const PRESETS = [
  {
    id: "minimal-voice",
    name: "Minimal Voice",
    desc: "Cheapest way to get JARVIS running (Pi 5, no GPU)",
    selections: {
      compute: "rpi5-8gb",
      screen: "no-screen",
      audio: "usb-speaker",
      mic: "respeaker-2mic",
      status: "oled-0-96",
      leds: "no-leds",
      wiring: "wiring-minimal",
      printing: "print-self",
    },
  },
  {
    id: "mid-range",
    name: "Mid-Range (Pi 5 + AI HAT)",
    desc: "NPU accelerated, 40 TOPS, limited to small models",
    selections: {
      compute: "rpi5-ai-hat",
      screen: "no-screen",
      audio: "usb-codec-10w",
      mic: "respeaker-4mic",
      status: "oled-1-3",
      leds: "ws2812b-24",
      wiring: "wiring-full",
      printing: "print-service",
    },
  },
  {
    id: "recommended-voice",
    name: "Recommended (Voice Only)",
    desc: "Best balance of quality and cost. Add screen later.",
    selections: {
      compute: "jetson-orin-nano-8gb",
      screen: "no-screen",
      audio: "usb-codec-10w",
      mic: "respeaker-4mic",
      status: "oled-1-3",
      leds: "ws2812b-24",
      wiring: "wiring-full",
      printing: "print-service",
    },
  },
  {
    id: "smart-display",
    name: "Smart Display (Best Value Screen)",
    desc: "Full build with 5 inch narrow-bezel IPS screen",
    selections: {
      compute: "jetson-orin-nano-8gb",
      screen: "waveshare-5dp",
      audio: "usb-codec-10w",
      mic: "respeaker-4mic",
      status: "oled-1-3",
      leds: "ws2812b-24",
      wiring: "wiring-full",
      printing: "print-service",
    },
  },
  {
    id: "premium",
    name: "Premium Build",
    desc: "Best everything. AMOLED screen, top-tier audio.",
    selections: {
      compute: "jetson-orin-nano-8gb",
      screen: "waveshare-5-amoled",
      audio: "usb-codec-10w",
      mic: "respeaker-4mic",
      status: "oled-1-3",
      leds: "ws2812b-24",
      wiring: "wiring-full",
      printing: "print-service",
    },
  },
];

function TagBadge({ tag }) {
  var colors = {
    recommended: "bg-green-100 text-green-700",
    budget: "bg-amber-100 text-amber-700",
    premium: "bg-purple-100 text-purple-700",
    phase1: "bg-gray-100 text-gray-600",
    phase2: "bg-blue-100 text-blue-700",
    fallback: "bg-orange-100 text-orange-700",
  };
  return (
    <span className={"text-xs px-2 py-0.5 rounded-full font-medium " + (colors[tag] || "bg-gray-100 text-gray-600")}>
      {tag}
    </span>
  );
}

function StockBadge({ status }) {
  if (!status) return null;
  var styles = {
    "in-stock": "bg-green-900 text-green-300",
    "low-stock": "bg-yellow-900 text-yellow-300",
    "check": "bg-blue-900 text-blue-300",
    "out-of-stock": "bg-red-900 text-red-300",
  };
  var labels = {
    "in-stock": "In Stock",
    "low-stock": "Low Stock",
    "check": "Check Availability",
    "out-of-stock": "Out of Stock",
  };
  return (
    <span className={"text-xs px-2 py-0.5 rounded font-medium " + (styles[status] || "bg-gray-800 text-gray-400")}>
      {labels[status] || status}
    </span>
  );
}

function formatPrice(range) {
  if (range[0] === 0 && range[1] === 0) return "Free";
  if (range[0] === range[1]) return "Rs " + range[0].toLocaleString("en-IN");
  return "Rs " + range[0].toLocaleString("en-IN") + " - " + range[1].toLocaleString("en-IN");
}

function midPrice(range) {
  return Math.round((range[0] + range[1]) / 2);
}

export default function BuildConfigurator() {
  // Initialize with recommended preset
  var initSelections = {};
  CATEGORIES.forEach(function(cat) {
    var rec = cat.options.find(function(o) { return o.tags && o.tags.indexOf("recommended") !== -1; });
    initSelections[cat.id] = rec ? rec.id : cat.options[0].id;
  });

  var ref = useState(initSelections);
  var selections = ref[0];
  var setSelections = ref[1];

  var ref2 = useState(false);
  var showLinks = ref2[0];
  var setShowLinks = ref2[1];

  function select(catId, optId) {
    setSelections(function(prev) {
      var next = {};
      Object.keys(prev).forEach(function(k) { next[k] = prev[k]; });
      next[catId] = optId;
      return next;
    });
  }

  function applyPreset(preset) {
    setSelections(function() {
      var next = {};
      Object.keys(preset.selections).forEach(function(k) { next[k] = preset.selections[k]; });
      return next;
    });
  }

  // Compute totals
  var totals = useMemo(function() {
    var low = 0;
    var high = 0;
    var mid = 0;
    var items = [];
    CATEGORIES.forEach(function(cat) {
      var selectedId = selections[cat.id];
      var opt = cat.options.find(function(o) { return o.id === selectedId; });
      if (opt) {
        low += opt.price[0];
        high += opt.price[1];
        mid += midPrice(opt.price);
        if (!opt.isNone) {
          items.push({ name: opt.name, price: opt.price, category: cat.label });
        }
      }
    });
    return { low: low, high: high, mid: mid, items: items };
  }, [selections]);

  var iconMap = {
    CPU: "[ ]",
    SCREEN: "[=]",
    SPEAKER: ">>",
    MIC: "o",
    OLED: "[-]",
    LED: "*",
    CABLE: "~",
    PRINT: "III",
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-6 text-gray-100">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-white">JARVIS Build Configurator</h1>
          <p className="text-gray-400 mt-1">Pick your components, see the total. All prices in INR, all items ship to India.</p>
        </div>

        {/* Preset Builds */}
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">Quick Presets</h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {PRESETS.map(function(p) {
              // Check if current selections match this preset
              var isActive = true;
              Object.keys(p.selections).forEach(function(k) {
                if (selections[k] !== p.selections[k]) isActive = false;
              });
              return (
                <button key={p.id} onClick={function() { applyPreset(p); }}
                  className={"p-3 rounded-xl border text-left transition-all " +
                    (isActive
                      ? "border-blue-500 bg-blue-500 bg-opacity-20"
                      : "border-gray-600 bg-gray-800 hover:border-gray-400")}>
                  <div className="font-bold text-sm text-white">{p.name}</div>
                  <div className="text-xs text-gray-400 mt-1">{p.desc}</div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Main: categories + summary side by side */}
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Categories */}
          <div className="flex-1 space-y-4">
            {CATEGORIES.map(function(cat) {
              return (
                <div key={cat.id} className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
                  <div className="px-4 py-3 border-b border-gray-700 flex items-center gap-2">
                    <span className="text-gray-500 font-mono text-xs">{iconMap[cat.icon] || "?"}</span>
                    <h3 className="font-bold text-white text-sm">{cat.label}</h3>
                    {cat.required && <span className="text-xs text-red-400 ml-auto">required</span>}
                    {!cat.required && <span className="text-xs text-gray-500 ml-auto">optional</span>}
                  </div>
                  <div className="p-2 space-y-1">
                    {cat.options.map(function(opt) {
                      var isSelected = selections[cat.id] === opt.id;
                      return (
                        <button key={opt.id}
                          onClick={function() { select(cat.id, opt.id); }}
                          className={"w-full text-left p-3 rounded-lg transition-all " +
                            (isSelected
                              ? "bg-blue-600 bg-opacity-20 border border-blue-500"
                              : "bg-gray-750 border border-transparent hover:border-gray-600 hover:bg-gray-700")}>
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className={"w-3 h-3 rounded-full border-2 flex-shrink-0 " +
                                  (isSelected ? "border-blue-400 bg-blue-400" : "border-gray-500")} />
                                <span className={"text-sm font-medium " + (isSelected ? "text-white" : "text-gray-300")}>{opt.name}</span>
                              </div>
                              <p className="text-xs text-gray-400 mt-1 ml-5">{opt.note}</p>
                              {opt.specs && <p className="text-xs text-gray-500 mt-0.5 ml-5 font-mono">{opt.specs}</p>}
                              <div className="flex gap-1.5 mt-1.5 ml-5 flex-wrap">
                                {opt.stock && <StockBadge status={opt.stock} />}
                                {opt.tags && opt.tags.map(function(t) { return <TagBadge key={t} tag={t} />; })}
                              </div>
                              {showLinks && opt.link && (
                                <div className="mt-1.5 ml-5 space-y-1">
                                  <div>
                                    <span className="text-xs text-gray-500 mr-1">Primary:</span>
                                    <span className="font-mono text-xs text-blue-400 select-all cursor-text bg-gray-900 px-2 py-0.5 rounded break-all">
                                      {opt.link}
                                    </span>
                                  </div>
                                  {opt.altLinks && opt.altLinks.map(function(al, idx) {
                                    return (
                                      <div key={idx}>
                                        <span className="text-xs text-gray-500 mr-1">Alt:</span>
                                        <span className="font-mono text-xs text-gray-400 select-all cursor-text bg-gray-900 px-2 py-0.5 rounded break-all">
                                          {al}
                                        </span>
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                            <div className="text-right flex-shrink-0">
                              <div className={"font-mono text-sm font-bold " +
                                (opt.isNone ? "text-gray-500" : isSelected ? "text-green-400" : "text-gray-300")}>
                                {formatPrice(opt.price)}
                              </div>
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Sticky Summary */}
          <div className="lg:w-80 flex-shrink-0">
            <div className="lg:sticky lg:top-6 space-y-4">
              {/* Total */}
              <div className="bg-gradient-to-br from-blue-900 to-gray-800 rounded-xl border border-blue-700 p-5">
                <div className="text-xs text-blue-300 uppercase tracking-wide font-semibold mb-1">Estimated Total</div>
                <div className="text-3xl font-bold text-white">
                  Rs {totals.mid.toLocaleString("en-IN")}
                </div>
                <div className="text-sm text-blue-300 mt-1">
                  Range: Rs {totals.low.toLocaleString("en-IN")} - Rs {totals.high.toLocaleString("en-IN")}
                </div>
                <div className="text-xs text-gray-400 mt-2">
                  Mid-point estimate. Actual prices vary by seller and availability.
                </div>
              </div>

              {/* Itemized */}
              <div className="bg-gray-800 rounded-xl border border-gray-700 p-4">
                <div className="text-xs text-gray-400 uppercase tracking-wide font-semibold mb-3">Your Build</div>
                <div className="space-y-2">
                  {totals.items.map(function(item, i) {
                    return (
                      <div key={i} className="flex justify-between items-start gap-2">
                        <div className="text-xs text-gray-300 flex-1 min-w-0">{item.name}</div>
                        <div className="text-xs font-mono text-green-400 flex-shrink-0 text-right">
                          Rs {midPrice(item.price).toLocaleString("en-IN")}
                        </div>
                      </div>
                    );
                  })}
                </div>
                <div className="border-t border-gray-600 mt-3 pt-3 flex justify-between">
                  <span className="text-sm font-bold text-white">Total (mid)</span>
                  <span className="text-sm font-bold text-green-400 font-mono">Rs {totals.mid.toLocaleString("en-IN")}</span>
                </div>
              </div>

              {/* Toggle links */}
              <button onClick={function() { setShowLinks(!showLinks); }}
                className="w-full text-center text-xs text-blue-400 hover:text-blue-300 py-2">
                {showLinks ? "Hide purchase links" : "Show purchase links"}
              </button>

              {/* Comparison note */}
              <div className="bg-gray-800 rounded-xl border border-gray-700 p-4">
                <div className="text-xs text-gray-400 uppercase tracking-wide font-semibold mb-2">For Reference</div>
                <div className="space-y-1.5 text-xs text-gray-400">
                  <div className="flex justify-between">
                    <span>Amazon Echo (4th gen)</span>
                    <span className="font-mono text-gray-300">Rs 10,000</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Echo Show 5</span>
                    <span className="font-mono text-gray-300">Rs 9,000</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Echo Show 8</span>
                    <span className="font-mono text-gray-300">Rs 15,000</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Google Nest Hub (2nd gen)</span>
                    <span className="font-mono text-gray-300">Rs 8,000</span>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-2">
                  JARVIS runs fully locally, no cloud dependency, open source, and does song disambiguation better than any of these.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-8 pt-6 border-t border-gray-700 text-center text-sm text-gray-500">
          JARVIS Build Configurator - All prices in INR - Birthday Deadline: May 14, 2026
        </div>
      </div>
    </div>
  );
}
