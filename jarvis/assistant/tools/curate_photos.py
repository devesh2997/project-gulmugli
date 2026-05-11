#!/usr/bin/env python3
"""
curate_photos.py — fast keep/skip/highlight tool for the 560 album photos.

## What it does

Starts a local web server (default port 8765) and opens a browser page
that lets you walk through every photo with keyboard shortcuts. Each
decision is saved to `captions.yaml` immediately (no save button —
your work persists on every keypress).

## Keyboard shortcuts (in the browser)

  → / Space   next photo
  ←           previous photo

  K           KEEP this photo (mark for slideshow)
  S           SKIP this photo (won't appear in slideshow)
  H           HIGHLIGHT (special photo — visual emphasis in slideshow)
  U           UNDECIDED (clears any prior marking)
  D           toggle the metadata sidebar

  J           jump to next chapter
  Shift+J     jump to previous chapter

  Number keys (1-9) followed by Enter — jump to chapter N

## Smart features

  - **Burst detection**: when this photo is part of a burst (multiple
    near-identical shots within 10s), you see a "Burst 3 of 5"
    indicator. Most bursts: keep ONE, skip the rest.
  - **Chapter context**: the chapter title and date range show at the
    top so you remember what you're looking at.
  - **Auto-advance after action**: pressing K/S/H/U auto-advances to
    the next photo. So you can rip through 560 in 15-20 min.
  - **Progress bar**: total decisions made / total photos.
  - **Resume**: re-running the tool starts at the first un-decided
    photo, not at photo 1.

## Run

  python tools/curate_photos.py
  python tools/curate_photos.py --port 8766
  python tools/curate_photos.py --start-photo 200    # jump straight to photo 200
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import webbrowser
from collections import OrderedDict
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed.", file=sys.stderr)
    sys.exit(1)

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("ERROR: fastapi + uvicorn not installed.\n"
          "Run: pip install fastapi uvicorn", file=sys.stderr)
    sys.exit(1)


# Preserve YAML ordering
class OrderedDumper(yaml.SafeDumper):
    pass


class OrderedLoader(yaml.SafeLoader):
    pass


def _odict_repr(d, v):
    return d.represent_mapping("tag:yaml.org,2002:map", v.items())


def _odict_cons(l, n):
    return OrderedDict(l.construct_pairs(n))


OrderedDumper.add_representer(OrderedDict, _odict_repr)
OrderedDumper.add_representer(dict, _odict_repr)
OrderedLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _odict_cons
)


# ── Embedded frontend ─────────────────────────────────────────────

CURATE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Curate · Vesper Yaadein</title>
<style>
  :root {
    --bg: #0a0a0c;
    --panel: #15151a;
    --border: #2a2a32;
    --text: #e6e6ea;
    --text-dim: #8a8a96;
    --accent-keep: #4ade80;
    --accent-skip: #f87171;
    --accent-highlight: #fbbf24;
    --accent-undecided: #64748b;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; height: 100%; }
  body {
    background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Inter", sans-serif;
    overflow: hidden;
  }
  .app { display: flex; height: 100vh; }

  /* photo area */
  .photo-area {
    flex: 1; display: flex; flex-direction: column;
    background: #000; position: relative;
  }
  .photo-frame {
    flex: 1; display: flex; align-items: center; justify-content: center;
    overflow: hidden; padding: 12px;
  }
  .photo-frame img {
    max-width: 100%; max-height: 100%; object-fit: contain;
    border-radius: 6px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
    transition: opacity 0.15s ease;
  }
  .photo-frame img.loading { opacity: 0.3; }

  /* status bar at bottom — now MORE PROMINENT */
  .status-bar {
    display: flex; align-items: center; gap: 20px;
    padding: 14px 22px; background: var(--panel);
    border-top: 1px solid var(--border); font-size: 14px;
  }
  .status-progress {
    flex: 1; height: 10px; background: #1f1f26; border-radius: 5px;
    overflow: hidden; position: relative;
    box-shadow: inset 0 1px 2px rgba(0,0,0,0.4);
  }
  .status-progress > div {
    height: 100%;
    background: linear-gradient(90deg,
      var(--accent-keep) 0%,
      var(--accent-highlight) 100%);
    transition: width 0.4s ease;
    box-shadow: 0 0 12px rgba(74, 222, 128, 0.4);
  }
  .status-counts {
    display: flex; gap: 16px; font-variant-numeric: tabular-nums;
    color: var(--text-dim);
    font-weight: 500;
  }
  .status-counts strong {
    color: var(--text);
    font-weight: 600;
  }
  .status-counts .keep { color: var(--accent-keep); }
  .status-counts .skip { color: var(--accent-skip); }
  .status-counts .hl { color: var(--accent-highlight); }
  .status-counts .un { color: var(--accent-undecided); }
  .progress-pct {
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    min-width: 50px; text-align: right;
  }
  /* filter chip */
  .filter-chip {
    background: rgba(74, 222, 128, 0.12);
    border: 1px solid rgba(74, 222, 128, 0.3);
    color: var(--accent-keep);
    font-size: 11px; padding: 4px 10px;
    border-radius: 12px;
    margin-right: 8px;
    font-weight: 500;
  }

  /* caption editor block (in sidebar) */
  .caption-block {
    margin-top: 22px;
    padding-top: 18px;
    border-top: 1px solid var(--border);
  }
  .caption-block h3 {
    margin: 0 0 10px 0;
    font-size: 10px; letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--text-dim);
  }
  .caption-source {
    margin-bottom: 8px; padding: 8px 12px;
    background: rgba(255,255,255,0.03);
    border-left: 2px solid var(--text-dim);
    border-radius: 0 4px 4px 0;
    font-size: 12px; line-height: 1.5;
    color: var(--text);
    max-height: 120px; overflow-y: auto;
    word-wrap: break-word;
  }
  .caption-source.ai { border-left-color: #8b5cf6; }
  .caption-source.manual { border-left-color: #fbbf24; }
  .caption-source.empty {
    color: var(--text-dim); font-style: italic;
  }
  .caption-source-label {
    font-size: 9px; letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 4px; opacity: 0.6;
  }
  .caption-source.ai .caption-source-label { color: #8b5cf6; }
  .caption-source.manual .caption-source-label { color: #fbbf24; }
  textarea.caption-input {
    width: 100%; min-height: 70px;
    background: rgba(251, 191, 36, 0.06);
    color: var(--text);
    border: 1px solid rgba(251, 191, 36, 0.25);
    border-radius: 6px;
    padding: 10px 12px;
    font-family: -apple-system, sans-serif;
    font-size: 13px; line-height: 1.45;
    resize: vertical;
    margin-top: 4px;
  }
  textarea.caption-input:focus {
    outline: none;
    border-color: rgba(251, 191, 36, 0.6);
    background: rgba(251, 191, 36, 0.1);
  }
  .caption-actions {
    display: flex; gap: 6px; margin-top: 6px;
    font-size: 11px;
  }
  .caption-actions button {
    background: rgba(255,255,255,0.05);
    color: var(--text-dim);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 4px 10px;
    cursor: pointer;
    font-family: inherit;
    font-size: 11px;
  }
  .caption-actions button:hover {
    background: rgba(255,255,255,0.1);
    color: var(--text);
  }
  .caption-actions button.save {
    background: rgba(251, 191, 36, 0.15);
    color: var(--accent-highlight);
    border-color: rgba(251, 191, 36, 0.3);
  }
  .caption-actions button.save:hover {
    background: rgba(251, 191, 36, 0.25);
  }

  /* current decision indicator (big overlay on photo) */
  .decision-badge {
    position: absolute; top: 18px; left: 18px;
    padding: 6px 14px; border-radius: 6px;
    font-weight: 600; font-size: 13px;
    letter-spacing: 1px; text-transform: uppercase;
    backdrop-filter: blur(8px);
    background: rgba(0,0,0,0.4);
  }
  .decision-badge.keep { color: var(--accent-keep); }
  .decision-badge.skip { color: var(--accent-skip); }
  .decision-badge.highlight { color: var(--accent-highlight); }
  .decision-badge.undecided { color: var(--accent-undecided); }

  /* sidebar */
  .sidebar {
    width: 360px; background: var(--panel);
    border-left: 1px solid var(--border);
    overflow-y: auto; padding: 24px 22px;
    font-size: 13px;
  }
  .sidebar.hidden { display: none; }
  .sidebar h2 {
    margin: 0 0 4px 0; font-size: 18px; font-weight: 700;
  }
  .sidebar .filename {
    color: var(--text-dim); font-family: ui-monospace, monospace;
    font-size: 11px; margin-bottom: 18px;
  }
  .sidebar h3 {
    margin: 18px 0 6px 0; font-size: 10px;
    letter-spacing: 2px; text-transform: uppercase;
    color: var(--text-dim);
  }
  .sidebar .row {
    display: flex; justify-content: space-between;
    padding: 4px 0; gap: 12px;
  }
  .sidebar .row .k { color: var(--text-dim); }
  .sidebar .row .v {
    font-family: ui-monospace, monospace; font-size: 12px;
    text-align: right;
  }
  .burst-warning {
    margin: 12px 0; padding: 10px 12px;
    background: rgba(251, 191, 36, 0.08);
    border: 1px solid rgba(251, 191, 36, 0.25);
    border-radius: 6px; color: #fbbf24;
    font-size: 12px; line-height: 1.4;
  }
  .chapter-banner {
    margin: 0 0 18px 0; padding: 12px 14px;
    background: rgba(74, 222, 128, 0.06);
    border: 1px solid rgba(74, 222, 128, 0.18);
    border-radius: 8px;
  }
  .chapter-banner .num {
    font-size: 10px; color: var(--text-dim);
    letter-spacing: 2px; text-transform: uppercase;
    margin-bottom: 4px;
  }
  .chapter-banner .title { font-size: 14px; font-weight: 600; }
  .chapter-banner .date {
    color: var(--text-dim); font-size: 12px; margin-top: 4px;
  }

  /* shortcut hints */
  .shortcut-hints {
    position: absolute; bottom: 64px; left: 18px;
    padding: 8px 12px; background: rgba(0,0,0,0.5);
    backdrop-filter: blur(8px); border-radius: 6px;
    font-size: 11px; color: var(--text-dim);
    display: flex; gap: 14px; font-variant-numeric: tabular-nums;
  }
  .shortcut-hints kbd {
    display: inline-block; padding: 1px 6px; margin: 0 2px;
    background: #2a2a32; border-radius: 3px;
    color: var(--text); font-family: ui-monospace, monospace;
    font-size: 10px;
  }
</style>
</head>
<body>
<div class="app">
  <div class="photo-area">
    <div class="photo-frame">
      <img id="photo" alt="">
    </div>
    <div id="decision-badge" class="decision-badge undecided">UNDECIDED</div>

    <div class="shortcut-hints">
      <span><kbd>K</kbd>eep</span>
      <span><kbd>S</kbd>kip</span>
      <span><kbd>H</kbd>ighlight</span>
      <span><kbd>U</kbd>ndecided</span>
      <span><kbd>←→</kbd> nav</span>
      <span><kbd>J</kbd> next chapter</span>
      <span><kbd>D</kbd> sidebar</span>
      <span><kbd>C</kbd> edit caption</span>
    </div>

    <div class="status-bar">
      <span class="filter-chip" id="filter-chip" style="display:none"></span>
      <div class="status-counts">
        <span>Photo <strong id="position">0</strong> / <strong id="total">0</strong></span>
        <span class="keep">✓ <strong id="count-keep">0</strong></span>
        <span class="skip">✗ <strong id="count-skip">0</strong></span>
        <span class="hl">★ <strong id="count-highlight">0</strong></span>
        <span class="un">· <strong id="count-undecided">0</strong></span>
      </div>
      <div class="status-progress"><div id="progress-bar" style="width: 0%"></div></div>
      <span class="progress-pct" id="progress-pct">0%</span>
    </div>
  </div>

  <div class="sidebar" id="sidebar">
    <div class="chapter-banner">
      <div class="num"><span id="chapter-num">Chapter ?</span></div>
      <div class="title" id="chapter-title">—</div>
      <div class="date" id="chapter-date">—</div>
    </div>

    <h2 id="photo-date">—</h2>
    <div class="filename" id="photo-filename">—</div>

    <div id="burst-block"></div>

    <h3>When</h3>
    <div id="meta-when"></div>

    <h3>Where</h3>
    <div id="meta-where"></div>

    <h3>Story</h3>
    <div id="meta-story"></div>

    <h3>Frame</h3>
    <div id="meta-frame"></div>

    <div class="caption-block">
      <h3>Caption</h3>

      <div id="caption-ai-block" class="caption-source ai" style="display:none">
        <div class="caption-source-label">AI</div>
        <div id="caption-ai-text"></div>
      </div>
      <div id="caption-manual-block" class="caption-source manual" style="display:none">
        <div class="caption-source-label">Manual (overrides AI)</div>
        <div id="caption-manual-text"></div>
      </div>

      <textarea id="caption-input" class="caption-input"
        placeholder="Type your own caption (overrides AI). Empty to use AI. Type &lt;NO_CAPTION&gt; to force silent."></textarea>

      <div class="caption-actions">
        <button class="save" id="caption-save">Save (⌘↵)</button>
        <button id="caption-clear">Clear manual</button>
        <button id="caption-silent">Force silent</button>
      </div>
    </div>
  </div>
</div>

<script>
let state = null;
let cursor = 0;       // current photo index (0-based)
let preloadCache = {};

const $ = (id) => document.getElementById(id);
const row = (k, v) => `<div class="row"><span class="k">${k}</span><span class="v">${v}</span></div>`;

async function loadState() {
  const r = await fetch('/api/state');
  state = await r.json();
  cursor = state.start_at || 0;
  // Cursor must be within the (possibly filtered) photo list
  if (cursor >= state.photos.length) cursor = 0;
  $('total').innerText = state.photos.length;

  // Filter chip
  const chip = $('filter-chip');
  const f = state.filter || {};
  if (f.chapter !== null && f.chapter !== undefined) {
    chip.innerText = `Chapter ${f.chapter} only`;
    chip.style.display = '';
  } else if (f.undecided_only) {
    chip.innerText = 'Undecided only';
    chip.style.display = '';
  } else {
    chip.style.display = 'none';
  }

  await render();
}

function preload(idx) {
  for (let i = 1; i <= 3; i++) {
    const next = idx + i;
    if (next >= state.photos.length) break;
    const fname = state.photos[next].file;
    if (!preloadCache[fname]) {
      const img = new Image();
      img.src = '/photos/' + fname;
      preloadCache[fname] = img;
    }
  }
}

async function render() {
  const p = state.photos[cursor];
  if (!p) return;

  // photo
  const img = $('photo');
  img.classList.add('loading');
  img.src = '/photos/' + p.file;
  img.onload = () => img.classList.remove('loading');

  // decision badge
  const badge = $('decision-badge');
  let decision = 'UNDECIDED', cls = 'undecided';
  if (p.skip) { decision = 'SKIP'; cls = 'skip'; }
  else if (p.highlight) { decision = 'HIGHLIGHT'; cls = 'highlight'; }
  else if (p.keep) { decision = 'KEEP'; cls = 'keep'; }
  badge.innerText = decision;
  badge.className = 'decision-badge ' + cls;

  // sidebar
  $('position').innerText = cursor + 1;

  const chapter = state.chapters[p.chapter] || {};
  $('chapter-num').innerText = 'Chapter ' + p.chapter + ' of ' + Object.keys(state.chapters).length;
  $('chapter-title').innerText = chapter.title || '(no title yet)';
  $('chapter-date').innerText = chapter.date_range || '';

  $('photo-date').innerText = p.date;
  $('photo-filename').innerText = p.file;

  const e = p.enriched || {};

  // Burst warning
  const burstBlock = $('burst-block');
  if (e.burst_size && e.burst_size > 1) {
    burstBlock.innerHTML = `<div class="burst-warning">
      📸 Burst of ${e.burst_size} near-identical shots.
      Recommended: keep ONE, skip the rest.
    </div>`;
  } else {
    burstBlock.innerHTML = '';
  }

  // When
  let when = '';
  if (e.time_of_day || e.day_of_week) {
    when += row('Time', `${e.day_of_week || ''} ${e.time_of_day || ''}`);
  }
  if (e.hour_24 !== undefined) when += row('Hour', e.hour_24 + ':00');
  if (e.season_india) when += row('Season', e.season_india);
  $('meta-when').innerHTML = when || '<span style="color:var(--text-dim);font-size:12px">no time data</span>';

  // Where
  let where = '';
  if (e.city) where += row('City', e.city);
  if (e.locality && e.locality !== e.city) where += row('Locality', e.locality);
  if (e.state) where += row('State', e.state);
  if (e.country && e.country !== 'India') where += row('Country', e.country);
  $('meta-where').innerHTML = where || '<span style="color:var(--text-dim);font-size:12px">no GPS</span>';

  // Story
  let story = '';
  if (e.days_since_album_start !== undefined) {
    const d = e.days_since_album_start;
    let yrs = (d / 365);
    story += row('Day in story', d + (yrs >= 1 ? ` (~${yrs.toFixed(1)} yrs)` : ''));
  }
  if (e.days_since_prev_photo !== undefined) {
    const g = e.days_since_prev_photo;
    let desc;
    if (g < 0.1) desc = 'burst (same minute)';
    else if (g < 1) desc = 'same day';
    else if (g < 7) desc = `${Math.round(g)}d after prev`;
    else if (g < 60) desc = `${Math.round(g)}d after prev`;
    else desc = `${Math.round(g)}d gap`;
    story += row('Gap', desc);
  }
  if (e.burst_id) story += row('Burst ID', e.burst_id);
  $('meta-story').innerHTML = story || '<span style="color:var(--text-dim);font-size:12px">—</span>';

  // Frame
  let frame = '';
  if (e.orientation) frame += row('Orient', e.orientation);
  if (e.aspect_ratio) frame += row('Aspect', e.aspect_ratio);
  if (e.camera) frame += row('Device', e.camera.replace(/^OnePlus ONEPLUS /, 'OnePlus '));
  if (e.iso) frame += row('ISO', e.iso);
  if (e.flash_fired) frame += row('Flash', 'yes');
  $('meta-frame').innerHTML = frame || '<span style="color:var(--text-dim);font-size:12px">—</span>';

  // Caption blocks
  const aiBlock = $('caption-ai-block');
  const aiText = $('caption-ai-text');
  const manualBlock = $('caption-manual-block');
  const manualText = $('caption-manual-text');
  const input = $('caption-input');

  if (p.caption_ai && p.caption_ai.trim()) {
    aiText.innerText = p.caption_ai;
    aiBlock.style.display = '';
    aiBlock.classList.remove('empty');
  } else {
    aiBlock.style.display = 'none';
  }

  if (p.caption_manual && p.caption_manual.trim()) {
    manualText.innerText = p.caption_manual;
    manualBlock.style.display = '';
  } else {
    manualBlock.style.display = 'none';
  }

  // Pre-fill editor with current manual caption (or AI as starting point if no manual)
  input.value = p.caption_manual || '';
  input.dataset.original = p.caption_manual || '';

  // Update counts
  updateCounts();

  // Preload next few photos
  preload(cursor);
}

function updateCounts() {
  let k=0, s=0, h=0, u=0;
  for (const p of state.photos) {
    if (p.skip) s++;
    else if (p.highlight) h++;
    else if (p.keep) k++;
    else u++;
  }
  $('count-keep').innerText = k;
  $('count-skip').innerText = s;
  $('count-highlight').innerText = h;
  $('count-undecided').innerText = u;
  const decided = k + s + h;
  const pct = state.photos.length > 0
    ? (100 * decided / state.photos.length)
    : 0;
  $('progress-bar').style.width = pct.toFixed(1) + '%';
  $('progress-pct').innerText = pct.toFixed(0) + '%';
}

async function mark(action) {
  const p = state.photos[cursor];
  if (action === 'keep')      { p.keep = true;  p.skip = false; p.highlight = false; }
  if (action === 'skip')      { p.keep = false; p.skip = true;  p.highlight = false; }
  if (action === 'highlight') { p.keep = false; p.skip = false; p.highlight = true; }
  if (action === 'undecided') { p.keep = false; p.skip = false; p.highlight = false; }

  // POST to server
  await fetch('/api/mark', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({file: p.file, action: action}),
  });

  // Re-render badge + counts then auto-advance
  await render();
  if (action !== 'undecided') {
    cursor = Math.min(cursor + 1, state.photos.length - 1);
    await render();
  }
}

function navigate(delta) {
  cursor = Math.max(0, Math.min(state.photos.length - 1, cursor + delta));
  render();
}

function jumpChapter(direction) {
  const curCh = state.photos[cursor].chapter;
  const target = curCh + direction;
  for (let i = (direction > 0 ? cursor : 0); (direction > 0 ? i < state.photos.length : i <= cursor); i += (direction > 0 ? 1 : 1)) {
    if (direction > 0 && state.photos[i].chapter === target) { cursor = i; render(); return; }
  }
  if (direction < 0) {
    // walk backwards to find start of previous chapter
    for (let i = cursor - 1; i >= 0; i--) {
      if (state.photos[i].chapter === target) {
        // walk back to start of that chapter
        while (i > 0 && state.photos[i - 1].chapter === target) i--;
        cursor = i; render(); return;
      }
    }
  }
}

async function saveCaption(textOverride) {
  const p = state.photos[cursor];
  const input = $('caption-input');
  const text = textOverride !== undefined ? textOverride : input.value;
  const r = await fetch('/api/caption', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({file: p.file, text: text}),
  });
  if (r.ok) {
    const result = await r.json();
    p.caption_manual = text;
    p.caption_effective = result.effective;
    // Re-render to reflect updated manual caption display
    await render();
    // Brief visual feedback
    input.style.background = 'rgba(74, 222, 128, 0.18)';
    setTimeout(() => { input.style.background = ''; }, 250);
  }
}

// Caption editor buttons
$('caption-save').onclick = () => saveCaption();
$('caption-clear').onclick = () => { $('caption-input').value = ''; saveCaption(''); };
$('caption-silent').onclick = () => { $('caption-input').value = '<NO_CAPTION>'; saveCaption('<NO_CAPTION>'); };

// Cmd/Ctrl+Enter while focused on textarea = save
$('caption-input').addEventListener('keydown', (ev) => {
  if ((ev.metaKey || ev.ctrlKey) && ev.key === 'Enter') {
    ev.preventDefault();
    saveCaption();
  }
});

document.addEventListener('keydown', async (ev) => {
  // If user is typing in the caption textarea, don't intercept keystrokes
  if (document.activeElement && document.activeElement.tagName === 'TEXTAREA') {
    if (ev.key === 'Escape') {
      ev.preventDefault();
      $('caption-input').blur();
    }
    return;
  }

  if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
  const k = ev.key.toLowerCase();
  if      (k === 'arrowright' || k === ' ') { ev.preventDefault(); navigate(1); }
  else if (k === 'arrowleft')             { ev.preventDefault(); navigate(-1); }
  else if (k === 'k')                     { ev.preventDefault(); await mark('keep'); }
  else if (k === 's')                     { ev.preventDefault(); await mark('skip'); }
  else if (k === 'h')                     { ev.preventDefault(); await mark('highlight'); }
  else if (k === 'u')                     { ev.preventDefault(); await mark('undecided'); }
  else if (k === 'd')                     { ev.preventDefault(); $('sidebar').classList.toggle('hidden'); }
  else if (k === 'j' && !ev.shiftKey)     { ev.preventDefault(); jumpChapter(1); }
  else if (k === 'j' && ev.shiftKey)      { ev.preventDefault(); jumpChapter(-1); }
  else if (k === 'c')                     {
    ev.preventDefault();
    $('caption-input').focus();
    $('caption-input').select();
  }
});

loadState();
</script>
</body>
</html>
"""


# ── Server ─────────────────────────────────────────────────────────


class MarkRequest(BaseModel):
    file: str
    action: str   # "keep" | "skip" | "highlight" | "undecided"


class CaptionRequest(BaseModel):
    file: str
    text: str     # the manual caption — empty string = clear manual override


def _effective_caption(entry: dict) -> str:
    """The caption that should display in the slideshow.

    Manual wins. Explicit `<NO_CAPTION>` in manual forces silent over AI.
    """
    manual = (entry.get("caption_manual") or "").strip()
    if manual == "<NO_CAPTION>":
        return ""
    if manual:
        return manual
    return entry.get("caption_ai") or ""


def _migrate_entry(entry: dict) -> dict:
    """In-place migrate an old `caption` field to the new `caption_ai`
    + `caption_manual` schema. Idempotent."""
    if "caption" in entry and "caption_ai" not in entry:
        entry["caption_ai"] = entry.pop("caption")
    entry.setdefault("caption_ai", "")
    entry.setdefault("caption_manual", "")
    return entry


def build_app(captions_path: Path, photos_dir: Path, enriched_path: Path,
              start_at: int, chapter_filter: int | None = None,
              undecided_only: bool = False) -> FastAPI:
    app = FastAPI(title="Vesper Curate")

    # captions.yaml is the source of truth; we hold it in memory between writes
    lock = threading.Lock()

    def load_captions() -> dict:
        return yaml.load(captions_path.read_text(), Loader=OrderedLoader)

    def save_captions(doc: dict) -> None:
        tmp = captions_path.with_suffix(".yaml.tmp")
        tmp.write_text(
            yaml.dump(doc, Dumper=OrderedDumper, sort_keys=False,
                      allow_unicode=True, width=200)
        )
        tmp.replace(captions_path)

    # Load enriched metadata once
    enriched_doc = {}
    if enriched_path.exists():
        enriched_doc = json.loads(enriched_path.read_text()).get("photos", {})

    # Static photo serving
    app.mount("/photos", StaticFiles(directory=str(photos_dir)), name="photos")

    @app.get("/", response_class=HTMLResponse)
    def root():
        return CURATE_HTML

    @app.get("/api/state")
    def get_state():
        doc = load_captions()
        photos = []
        total_in_album = 0
        for entry in doc.get("photos", []):
            _migrate_entry(entry)
            total_in_album += 1
            fname = entry["file"]
            ch = entry.get("chapter")
            is_undecided = (not entry.get("keep")
                            and not entry.get("skip")
                            and not entry.get("highlight"))

            # Apply filters
            if chapter_filter is not None and ch != chapter_filter:
                continue
            if undecided_only and not is_undecided:
                continue

            photos.append({
                "file": fname,
                "date": entry.get("date"),
                "chapter": ch,
                "caption_ai": entry.get("caption_ai", ""),
                "caption_manual": entry.get("caption_manual", ""),
                "caption_effective": _effective_caption(entry),
                "keep": bool(entry.get("keep", False)),
                "skip": bool(entry.get("skip", False)),
                "highlight": bool(entry.get("highlight", False)),
                "enriched": enriched_doc.get(fname, {}),
            })
        chapters = {}
        for key, meta in doc.get("chapters", {}).items():
            ch_num = int(key.replace("chapter_", ""))
            chapters[ch_num] = {
                "title": (meta.get("title") or "").replace("[edit] ", ""),
                "date_range": meta.get("date_range"),
                "photo_count": meta.get("photo_count"),
            }
        # First undecided photo for resume
        first_undecided = next(
            (i for i, p in enumerate(photos)
             if not p["keep"] and not p["skip"] and not p["highlight"]),
            0,
        )
        return {
            "photos": photos,
            "chapters": chapters,
            "start_at": start_at if start_at is not None else first_undecided,
            "total_in_album": total_in_album,
            "filter": {
                "chapter": chapter_filter,
                "undecided_only": undecided_only,
            },
        }

    @app.post("/api/mark")
    def mark(req: MarkRequest):
        with lock:
            doc = load_captions()
            entry = next((e for e in doc.get("photos", [])
                          if e["file"] == req.file), None)
            if not entry:
                raise HTTPException(404, f"Photo {req.file} not found")
            _migrate_entry(entry)
            if req.action == "keep":
                entry["keep"] = True
                entry["skip"] = False
                entry["highlight"] = False
            elif req.action == "skip":
                entry["keep"] = False
                entry["skip"] = True
                entry["highlight"] = False
            elif req.action == "highlight":
                entry["keep"] = False
                entry["skip"] = False
                entry["highlight"] = True
            elif req.action == "undecided":
                entry["keep"] = False
                entry["skip"] = False
                entry["highlight"] = False
            else:
                raise HTTPException(400, f"Unknown action: {req.action}")
            save_captions(doc)
        return {"ok": True}

    @app.post("/api/caption")
    def set_caption(req: CaptionRequest):
        """Write a user-entered manual caption to caption_manual.

        Manual captions take precedence over the AI-generated caption.
        Empty string clears the manual override (so AI version applies).
        The literal `<NO_CAPTION>` forces silent even when AI wrote a
        caption.
        """
        with lock:
            doc = load_captions()
            entry = next((e for e in doc.get("photos", [])
                          if e["file"] == req.file), None)
            if not entry:
                raise HTTPException(404, f"Photo {req.file} not found")
            _migrate_entry(entry)
            entry["caption_manual"] = req.text
            save_captions(doc)
        return {"ok": True, "effective": _effective_caption(entry)}

    return app


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captions",
                        default="events/astha-birthday/media/captions.yaml")
    parser.add_argument("--photos-dir",
                        default="events/astha-birthday/media/photos")
    parser.add_argument("--enriched",
                        default="events/astha-birthday/media/photos/enriched_metadata.json")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--start-photo", type=int,
                        help="Start at photo N (1-indexed). Default: first un-decided.")
    parser.add_argument("--chapter", type=int,
                        help="Filter view to only photos in chapter N. "
                        "Useful for revisiting a single trip after the first pass.")
    parser.add_argument("--undecided-only", action="store_true",
                        help="Filter view to only photos that haven't been "
                        "keep/skip/highlight'd yet.")
    parser.add_argument("--no-browser", action="store_true",
                        help="Don't auto-open the browser")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent.parent
    captions_path = Path(args.captions)
    if not captions_path.is_absolute():
        captions_path = here / captions_path
    photos_dir = Path(args.photos_dir)
    if not photos_dir.is_absolute():
        photos_dir = here / photos_dir
    enriched_path = Path(args.enriched)
    if not enriched_path.is_absolute():
        enriched_path = here / enriched_path

    if not captions_path.exists():
        print(f"ERROR: captions.yaml not at {captions_path}.", file=sys.stderr)
        return 1
    if not photos_dir.exists():
        print(f"ERROR: photos directory not at {photos_dir}.", file=sys.stderr)
        return 1

    # Inject keep/skip/highlight fields into captions.yaml if missing (idempotent)
    doc = yaml.load(captions_path.read_text(), Loader=OrderedLoader)
    changed = False
    for entry in doc.get("photos", []):
        for key in ("keep", "skip", "highlight"):
            if key not in entry:
                entry[key] = False
                changed = True
    if changed:
        captions_path.write_text(
            yaml.dump(doc, Dumper=OrderedDumper, sort_keys=False,
                      allow_unicode=True, width=200)
        )
        print(f"  added keep/skip/highlight fields to captions.yaml")

    start_at = (args.start_photo - 1) if args.start_photo else None

    app = build_app(captions_path, photos_dir, enriched_path, start_at,
                    chapter_filter=args.chapter,
                    undecided_only=args.undecided_only)

    url = f"http://127.0.0.1:{args.port}"
    print(f"\n  Vesper Curate")
    print(f"  ──────────────")
    print(f"  Server:   {url}")
    print(f"  Captions: {captions_path}")
    print(f"  Photos:   {len(doc['photos'])} total")
    if args.chapter:
        in_chapter = sum(1 for p in doc['photos']
                          if p.get('chapter') == args.chapter)
        print(f"  Filter:   chapter {args.chapter} only ({in_chapter} photos)")
    if args.undecided_only:
        undecided = sum(1 for p in doc['photos']
                        if not p.get('keep') and not p.get('skip')
                        and not p.get('highlight'))
        print(f"  Filter:   undecided only ({undecided} photos)")
    print(f"\n  Keyboard:  K=Keep  S=Skip  H=Highlight  U=Undecided"
          f"  ←→=Nav  J=NextChapter  D=ToggleSidebar  C=EditCaption")
    print()

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
