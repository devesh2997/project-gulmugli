---
name: UI design vision and principles
description: Devesh's detailed vision for the dashboard UI — soft, custom, animated, personality-driven, intent-aware avatar
type: feedback
---

## Core Design Philosophy
- **NOT generic** — no standard card-based layouts, no cookie-cutter design systems
- **Apple-inspired vibe** — animations, minimal, clean, neat — but NOT copying Apple's design system
- **Soft and calming** — not black-and-white, not "dark mode with white text". Use color, gradients, light — but everything should feel soft and soothing
- **Minimal default view** — the always-on screen should be very clean, but there should be ways to access more data/controls when needed
- **Multi-screen** — likely a touchscreen, so swipe between screens. Even without touch, easy navigation between views
- **Context-aware UI** — elements fly in/out based on what the system is doing. Not static layouts.

## Personality Theming
- Each personality gets its own look and feel
- Not all UI components change — mainly: orb/avatar appearance, color palette, glow effects, animation style
- The avatar/orb is the primary differentiator between personalities

## Avatar / Orb Vision
- **Pixelated line avatar** — shows eyebrows, mouth, nose in a minimal line-art style
- Expressive — reacts to assistant state (idle, listening, thinking, speaking)
- NOT a generic glowing orb — should feel like a character

## Intent Badges (Key Feature)
- When the assistant processes intents, small badges/tabs fly in and out
- Example: "play music and turn on lights" → a music note badge flies in, then a lightbulb badge
- Shows the user what the assistant is actively doing, step by step
- Keeps users engaged even during processing delays
- Badges should animate in, briefly show, then resolve (checkmark or fly out)

## Interaction Model
- Default: minimal, calm, always-on display
- On interaction: elements animate in contextually
- Touch/swipe: navigate between screens (now playing, settings, conversation history, etc.)
- Everything should feel intuitive and "AI-like"
- Elements auto-show/hide based on context (not manual toggles)

**Why:** Devesh wants this to feel like a custom, personal product — not a generic dashboard. It's a birthday gift, so the experience matters as much as the functionality.

**How to apply:** Every UI change should be evaluated against these principles. When in doubt, prefer soft/animated/contextual over static/boxy/utilitarian.
