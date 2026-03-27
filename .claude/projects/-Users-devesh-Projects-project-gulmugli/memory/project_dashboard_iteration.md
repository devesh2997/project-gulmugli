---
name: Current focus — UI and dashboard iteration
description: Devesh is now focused on iterating on the dashboard UI and frontend components. Previously done by cowork.
type: project
---

As of 2026-03-27, the primary focus is iterating on the UI/dashboard part of the assistant.

**Context:** The core backend (intent pipeline, music, lights, personalities, memory, knowledge, wake word, TTS) is working. The dashboard (React/TypeScript, Vite, Tailwind v4, framer-motion) was built by cowork and needs continued iteration.

**Dashboard architecture:**
- Vite + React 19 + TypeScript + Tailwind v4 + framer-motion
- Connects to assistant via WebSocket on port 8765
- Responsive: large (desktop), medium (7" screen), compact (phone/3.5" embedded)
- Components: Orb (state indicator), StatusBar (personality switcher, volume, clock), Transcript (chat bubbles), NowPlaying (music controls + progress)
- State management via `useAssistant` hook (WebSocket + auto-reconnect with exponential backoff)
- CSS custom properties for theming (can be pushed via WebSocket from backend)
- Dashboard port: 5173 (Vite dev server)

**How to apply:** When making UI changes, both servers need to be running (dashboard on 5173, assistant on 8765). The dashboard proxies /ws to the assistant's WebSocket.
