#!/usr/bin/env python3
"""
preview_yaadein.py — local browser preview of the Yaadein slideshow.

## What it does

Starts a local web server (default port 8766) and opens a browser page
that plays the slideshow as it'll appear on birthday day:

  - Only photos marked `keep: true` or `highlight: true` in captions.yaml
    appear in the slideshow.
  - Each photo displays for ~5 seconds (configurable), Ken Burns zoom +
    crossfade between photos.
  - Caption text overlays the photo with a soft gradient backdrop.
  - Chapter title fades in at the start of each new chapter.
  - Highlighted photos get extra emphasis (longer hold, sparkle border).
  - Progress bar at the bottom shows position in the slideshow.

The preview is intentionally close to the final Yaadein dashboard
component so you can iterate on captions and curation without needing
to run the full Vesper kiosk stack.

## Keyboard shortcuts

  Space         pause/resume
  → / ←         next / previous photo
  J             skip to next chapter
  M             toggle music (if available in events/.../media/songs/)
  F             toggle fullscreen
  C             toggle captions on/off (to see photos uncluttered)
  R             reload from disk (pulls in any captions.yaml edits)

## Run

  python tools/preview_yaadein.py
  python tools/preview_yaadein.py --port 8766
  python tools/preview_yaadein.py --duration 6   # seconds per photo
  python tools/preview_yaadein.py --highlight-only  # show only highlights
  python tools/preview_yaadein.py --chapter 1    # one chapter only
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import webbrowser
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed.", file=sys.stderr)
    sys.exit(1)

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    print("ERROR: fastapi + uvicorn not installed.\n"
          "Run: pip install fastapi uvicorn", file=sys.stderr)
    sys.exit(1)


# ── Embedded frontend ─────────────────────────────────────────────

PREVIEW_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Yaadein · Preview</title>
<style>
  :root {
    --bg: #050507;
    --text: #f5f5f8;
    --caption-bg-top: rgba(0,0,0,0);
    --caption-bg-bot: rgba(0,0,0,0.7);
    --hl-glow: 0 0 32px rgba(251, 191, 36, 0.25);
  }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body {
    margin: 0; padding: 0; height: 100%;
    background: var(--bg); color: var(--text);
    font-family: ui-sans-serif, -apple-system, "SF Pro Display",
                 BlinkMacSystemFont, "Segoe UI", "Inter", sans-serif;
    overflow: hidden;
    user-select: none;
  }

  /* the photo stage */
  .stage {
    position: fixed; inset: 0;
    display: flex; align-items: center; justify-content: center;
    overflow: hidden;
  }

  /* photo layer — two stacked for crossfade */
  .photo {
    position: absolute; inset: 0;
    background-position: center;
    background-size: cover;
    background-repeat: no-repeat;
    opacity: 0;
    transition: opacity 1.2s ease;
    will-change: transform, opacity;
  }
  .photo.active { opacity: 1; }
  .photo.active.kenburns {
    animation: kenburns var(--duration, 5s) ease-in-out forwards;
  }
  @keyframes kenburns {
    from { transform: scale(1.0) translate(0, 0); }
    to   { transform: scale(1.08) translate(-1%, -1%); }
  }

  /* highlight border */
  .stage.highlight::before {
    content: "";
    position: absolute; inset: 0;
    box-shadow: inset 0 0 60px rgba(251, 191, 36, 0.18);
    pointer-events: none;
    z-index: 5;
  }

  /* caption overlay */
  .caption {
    position: absolute; left: 0; right: 0; bottom: 0;
    padding: 80px 8% 64px 8%;
    background: linear-gradient(to bottom, transparent 0%, rgba(0,0,0,0.78) 65%);
    text-align: center;
    pointer-events: none;
    z-index: 10;
    opacity: 0;
    transition: opacity 0.6s ease 0.3s;
  }
  .caption.visible { opacity: 1; }
  .caption-text {
    font-size: 26px;
    font-weight: 500;
    line-height: 1.45;
    letter-spacing: -0.005em;
    max-width: 900px;
    margin: 0 auto;
    text-shadow: 0 2px 12px rgba(0,0,0,0.6);
  }
  @media (max-width: 900px) {
    .caption-text { font-size: 19px; }
  }

  /* chapter intro card */
  .chapter-card {
    position: absolute; inset: 0;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    background: rgba(0,0,0,0.55);
    backdrop-filter: blur(6px);
    text-align: center;
    z-index: 20;
    opacity: 0; pointer-events: none;
    transition: opacity 0.7s ease;
  }
  .chapter-card.visible {
    opacity: 1;
    transition: opacity 0.7s ease;
  }
  .chapter-num {
    font-size: 12px;
    letter-spacing: 4px;
    text-transform: uppercase;
    color: rgba(255,255,255,0.55);
    margin-bottom: 14px;
    font-weight: 600;
  }
  .chapter-title {
    font-size: 38px;
    font-weight: 600;
    line-height: 1.25;
    max-width: 80%;
    letter-spacing: -0.01em;
  }
  .chapter-date {
    font-size: 14px;
    color: rgba(255,255,255,0.55);
    margin-top: 18px;
    letter-spacing: 0.02em;
  }
  .chapter-intro {
    font-size: 17px;
    color: rgba(255,255,255,0.85);
    margin-top: 28px;
    max-width: 65%;
    line-height: 1.5;
    font-style: italic;
  }

  /* progress bar */
  .progress-bar {
    position: fixed; left: 0; right: 0; bottom: 0;
    height: 3px;
    background: rgba(255,255,255,0.08);
    z-index: 30;
  }
  .progress-fill {
    height: 100%;
    background: rgba(255,255,255,0.55);
    width: 0%;
    transition: width 0.15s linear;
  }

  /* control panel — fades on idle */
  .controls {
    position: fixed; top: 20px; right: 20px;
    display: flex; flex-direction: column; gap: 8px;
    z-index: 40;
    opacity: 0.0;
    transition: opacity 0.3s ease;
  }
  .controls.visible { opacity: 1; }
  .controls button {
    background: rgba(0,0,0,0.4);
    color: var(--text);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 12px;
    font-family: ui-monospace, monospace;
    cursor: pointer;
    backdrop-filter: blur(8px);
    transition: background 0.15s ease, border-color 0.15s ease;
  }
  .controls button:hover {
    background: rgba(0,0,0,0.6);
    border-color: rgba(255,255,255,0.25);
  }

  /* index ticker — bottom left */
  .index-ticker {
    position: fixed; left: 20px; bottom: 14px;
    font-size: 11px;
    font-family: ui-monospace, monospace;
    color: rgba(255,255,255,0.4);
    z-index: 30;
    opacity: 0;
    transition: opacity 0.3s ease;
  }
  .index-ticker.visible { opacity: 1; }

  /* status messages */
  .status {
    position: fixed; top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    padding: 30px 40px;
    background: rgba(0,0,0,0.5);
    backdrop-filter: blur(10px);
    border-radius: 12px;
    font-size: 14px;
    z-index: 50;
    text-align: center;
    max-width: 500px;
  }
  .status h2 {
    margin: 0 0 12px 0;
    font-size: 22px;
    font-weight: 600;
  }
  .status p {
    margin: 6px 0;
    color: rgba(255,255,255,0.7);
    font-size: 13px;
    line-height: 1.5;
  }
  .status code {
    font-family: ui-monospace, monospace;
    background: rgba(255,255,255,0.08);
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 12px;
  }

  /* keyboard hints */
  .kbd-hints {
    position: fixed; bottom: 18px; right: 20px;
    display: flex; gap: 16px;
    font-size: 11px; font-family: ui-monospace, monospace;
    color: rgba(255,255,255,0.4);
    z-index: 30;
    opacity: 0;
    transition: opacity 0.3s ease;
  }
  .kbd-hints.visible { opacity: 1; }
  .kbd-hints kbd {
    display: inline-block;
    padding: 1px 5px;
    background: rgba(255,255,255,0.08);
    border-radius: 3px;
    margin: 0 2px;
    color: rgba(255,255,255,0.7);
  }
</style>
</head>
<body>
<div class="stage" id="stage">
  <div class="photo" id="photoA"></div>
  <div class="photo" id="photoB"></div>

  <div class="caption" id="caption">
    <div class="caption-text" id="caption-text"></div>
  </div>

  <div class="chapter-card" id="chapter-card">
    <div class="chapter-num" id="chapter-num">CHAPTER 1</div>
    <div class="chapter-title" id="chapter-title">—</div>
    <div class="chapter-date" id="chapter-date">—</div>
    <div class="chapter-intro" id="chapter-intro"></div>
  </div>
</div>

<div class="progress-bar"><div class="progress-fill" id="progress"></div></div>

<div class="controls" id="controls">
  <button id="btn-play">⏸ Pause</button>
  <button id="btn-captions">Captions: ON</button>
  <button id="btn-reload">Reload</button>
</div>

<div class="index-ticker" id="ticker">0 / 0</div>

<div class="kbd-hints" id="hints">
  <span><kbd>Space</kbd> pause</span>
  <span><kbd>←→</kbd> nav</span>
  <span><kbd>J</kbd> chapter</span>
  <span><kbd>C</kbd> captions</span>
  <span><kbd>R</kbd> reload</span>
  <span><kbd>F</kbd> fullscreen</span>
</div>

<script>
const $ = (id) => document.getElementById(id);

let state = null;
let cursor = 0;
let playing = true;
let captionsOn = true;
let activeLayer = "A";
let timer = null;
let progressTimer = null;
let progressStart = 0;
let chapterShown = -1;

const DURATION = parseInt(new URLSearchParams(location.search).get("d")) || 5000;
const HIGHLIGHT_BONUS = 2000; // ms extra hold for highlights

async function loadState(opts) {
  const r = await fetch("/api/preview" + (opts && opts.query ? opts.query : ""));
  state = await r.json();
  if (!state.photos || state.photos.length === 0) {
    showStatus("Nothing kept yet",
      "Mark some photos as <code>keep</code> or <code>highlight</code> in the curate tool first.<br><br>" +
      "Run: <code>python tools/curate_photos.py</code>"
    );
    return false;
  }
  hideStatus();
  return true;
}

function showStatus(title, html) {
  let el = $("status");
  if (!el) {
    el = document.createElement("div");
    el.id = "status";
    el.className = "status";
    document.body.appendChild(el);
  }
  el.innerHTML = `<h2>${title}</h2><p>${html}</p>`;
}
function hideStatus() {
  const el = $("status");
  if (el) el.remove();
}

function showChapterCard(photo) {
  const ch = photo.chapter;
  if (ch === chapterShown) return;
  chapterShown = ch;

  const chapterData = state.chapters[ch] || {};
  $("chapter-num").innerText = "CHAPTER " + ch + " OF " + Object.keys(state.chapters).length;
  $("chapter-title").innerText = chapterData.title || "";
  $("chapter-date").innerText = chapterData.date_range || "";
  $("chapter-intro").innerText = chapterData.intro_caption || "";
  $("chapter-card").classList.add("visible");
  setTimeout(() => $("chapter-card").classList.remove("visible"), 3500);
}

function render() {
  const photo = state.photos[cursor];
  if (!photo) return;

  // Detect chapter transition
  const prevPhoto = cursor > 0 ? state.photos[cursor - 1] : null;
  if (!prevPhoto || prevPhoto.chapter !== photo.chapter) {
    showChapterCard(photo);
  }

  // Crossfade photos
  const nextLayer = activeLayer === "A" ? "B" : "A";
  const nextEl = $("photo" + nextLayer);
  const prevEl = $("photo" + activeLayer);
  nextEl.style.backgroundImage = `url('/photos/${photo.file}')`;
  nextEl.classList.add("kenburns");
  nextEl.style.setProperty("--duration",
    ((photo.highlight ? DURATION + HIGHLIGHT_BONUS : DURATION) / 1000) + "s");
  nextEl.classList.add("active");
  prevEl.classList.remove("active");
  prevEl.classList.remove("kenburns");
  activeLayer = nextLayer;

  // Caption
  const cap = $("caption-text");
  const capContainer = $("caption");
  if (captionsOn && photo.caption && photo.caption.trim()) {
    cap.innerText = photo.caption;
    capContainer.classList.add("visible");
  } else {
    capContainer.classList.remove("visible");
  }

  // Highlight glow on stage
  $("stage").classList.toggle("highlight", !!photo.highlight);

  // Ticker
  $("ticker").innerText = (cursor + 1) + " / " + state.photos.length;

  // Progress bar
  startProgress(photo.highlight ? DURATION + HIGHLIGHT_BONUS : DURATION);

  // Schedule next
  if (timer) clearTimeout(timer);
  if (playing) {
    timer = setTimeout(() => {
      next();
    }, photo.highlight ? DURATION + HIGHLIGHT_BONUS : DURATION);
  }
}

function startProgress(duration) {
  if (progressTimer) cancelAnimationFrame(progressTimer);
  const prog = $("progress");
  prog.style.transition = "none";
  prog.style.width = "0%";
  // Force reflow
  prog.offsetWidth;
  prog.style.transition = `width ${duration}ms linear`;
  prog.style.width = "100%";
}

function next() {
  cursor = (cursor + 1) % state.photos.length;
  render();
}
function prev() {
  cursor = (cursor - 1 + state.photos.length) % state.photos.length;
  render();
}
function nextChapter() {
  const curCh = state.photos[cursor].chapter;
  for (let i = cursor + 1; i < state.photos.length; i++) {
    if (state.photos[i].chapter !== curCh) {
      cursor = i; render(); return;
    }
  }
  cursor = 0; render();
}

function togglePlay() {
  playing = !playing;
  $("btn-play").innerText = playing ? "⏸ Pause" : "▶ Play";
  if (playing) {
    render();  // restarts timer
  } else {
    if (timer) clearTimeout(timer);
    // freeze the progress where it is
    const prog = $("progress");
    const cs = window.getComputedStyle(prog);
    prog.style.transition = "none";
    prog.style.width = cs.width;
  }
}

function toggleCaptions() {
  captionsOn = !captionsOn;
  $("btn-captions").innerText = "Captions: " + (captionsOn ? "ON" : "OFF");
  $("caption").classList.toggle("visible", captionsOn && state.photos[cursor].caption);
}

async function reload() {
  const ok = await loadState();
  if (ok) {
    cursor = 0; chapterShown = -1;
    render();
  }
}

function toggleFullscreen() {
  if (!document.fullscreenElement) document.documentElement.requestFullscreen();
  else document.exitFullscreen();
}

// Mouse idle → hide controls
let idleTimer;
function showControls() {
  $("controls").classList.add("visible");
  $("hints").classList.add("visible");
  $("ticker").classList.add("visible");
  if (idleTimer) clearTimeout(idleTimer);
  idleTimer = setTimeout(() => {
    $("controls").classList.remove("visible");
    $("hints").classList.remove("visible");
    $("ticker").classList.remove("visible");
  }, 3000);
}
document.addEventListener("mousemove", showControls);
showControls();

// Buttons
$("btn-play").onclick = togglePlay;
$("btn-captions").onclick = toggleCaptions;
$("btn-reload").onclick = reload;

// Keyboard
document.addEventListener("keydown", (ev) => {
  if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
  const k = ev.key.toLowerCase();
  if      (k === " ")                 { ev.preventDefault(); togglePlay(); }
  else if (k === "arrowright")        { ev.preventDefault(); next(); }
  else if (k === "arrowleft")         { ev.preventDefault(); prev(); }
  else if (k === "j")                 { ev.preventDefault(); nextChapter(); }
  else if (k === "c")                 { ev.preventDefault(); toggleCaptions(); }
  else if (k === "r")                 { ev.preventDefault(); reload(); }
  else if (k === "f")                 { ev.preventDefault(); toggleFullscreen(); }
});

// Bootstrap
loadState().then((ok) => { if (ok) render(); });
</script>
</body>
</html>
"""


# ── Server ─────────────────────────────────────────────────────────


def build_app(captions_path: Path, photos_dir: Path, args) -> FastAPI:
    app = FastAPI(title="Vesper Yaadein Preview")

    app.mount("/photos", StaticFiles(directory=str(photos_dir)), name="photos")

    @app.get("/", response_class=HTMLResponse)
    def root():
        return PREVIEW_HTML

    def _effective_caption(entry):
        """Manual caption wins. `<NO_CAPTION>` in manual forces silent."""
        manual = (entry.get("caption_manual") or "").strip()
        if manual == "<NO_CAPTION>":
            return ""
        if manual:
            return manual
        # Back-compat with old schema (single `caption` field)
        if entry.get("caption_ai"):
            return entry["caption_ai"]
        return entry.get("caption", "")

    @app.get("/api/preview")
    def preview():
        """Return the slideshow state — only kept/highlighted photos,
        with their captions and chapter metadata. Manual captions take
        precedence over AI captions."""
        doc = yaml.safe_load(captions_path.read_text())

        # Filter photos: keep + highlight only (unless --all or --highlight-only)
        if args.all:
            photos_raw = doc.get("photos", [])
        elif args.highlight_only:
            photos_raw = [p for p in doc.get("photos", [])
                          if p.get("highlight")]
        else:
            photos_raw = [p for p in doc.get("photos", [])
                          if p.get("keep") or p.get("highlight")]

        if args.chapter:
            photos_raw = [p for p in photos_raw
                          if p.get("chapter") == args.chapter]

        # Sort by chapter then position (preserve chronological)
        photos_raw = sorted(photos_raw,
                            key=lambda p: (p.get("chapter", 0),
                                           p.get("date", "")))

        photos = []
        for p in photos_raw:
            photos.append({
                "file": p["file"],
                "date": p.get("date"),
                "chapter": p.get("chapter"),
                "caption": _effective_caption(p),
                "caption_source": ("manual" if (p.get("caption_manual") or "").strip()
                                   else "ai" if p.get("caption_ai")
                                   else "none"),
                "highlight": bool(p.get("highlight")),
            })

        chapters = {}
        for key, meta in doc.get("chapters", {}).items():
            ch_num = int(key.replace("chapter_", ""))
            chapters[ch_num] = {
                "title": (meta.get("title") or "").replace("[edit] ", ""),
                "date_range": meta.get("date_range"),
                "intro_caption": meta.get("intro_caption", ""),
                "photo_count": meta.get("photo_count"),
            }

        return JSONResponse({
            "photos": photos,
            "chapters": chapters,
            "total_album_photos": len(doc.get("photos", [])),
        })

    return app


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captions",
                        default="events/astha-birthday/media/captions.yaml")
    parser.add_argument("--photos-dir",
                        default="events/astha-birthday/media/photos")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--duration", type=int, default=5,
                        help="Seconds per photo (default 5)")
    parser.add_argument("--all", action="store_true",
                        help="Show all photos (incl. skip/undecided)")
    parser.add_argument("--highlight-only", action="store_true",
                        help="Only highlighted photos")
    parser.add_argument("--chapter", type=int,
                        help="Only this chapter")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent.parent
    captions_path = Path(args.captions)
    if not captions_path.is_absolute():
        captions_path = here / captions_path
    photos_dir = Path(args.photos_dir)
    if not photos_dir.is_absolute():
        photos_dir = here / photos_dir

    if not captions_path.exists():
        print(f"ERROR: captions.yaml not at {captions_path}.", file=sys.stderr)
        return 1
    if not photos_dir.exists():
        print(f"ERROR: photos directory not at {photos_dir}.", file=sys.stderr)
        return 1

    app = build_app(captions_path, photos_dir, args)
    url = f"http://127.0.0.1:{args.port}?d={args.duration * 1000}"

    print(f"\n  Vesper Yaadein Preview")
    print(f"  ────────────────────────")
    print(f"  Server:    {url}")
    print(f"  Captions:  {captions_path}")
    print(f"  Per photo: {args.duration}s (+{2}s extra for highlights)")
    print(f"  Filter:    "
          f"{'all photos' if args.all else 'highlights only' if args.highlight_only else 'kept + highlighted'}")
    if args.chapter:
        print(f"  Chapter:   {args.chapter} only")
    print()
    print(f"  Tip: edit captions.yaml in your editor while this runs,")
    print(f"  then press R in the browser to reload — no restart needed.")
    print()

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
