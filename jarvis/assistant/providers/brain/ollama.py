"""
Ollama brain provider.

Talks to an Ollama server to classify intents and generate responses.
This is currently the primary brain provider for local inference.

To swap to a different LLM backend:
  - Create a new file (e.g., llamacpp.py, openai.py)
  - Implement BrainProvider
  - Register with @register("brain", "your_name")
  - Set brain.provider in config.yaml
"""

import requests
import json
import time

from core.interfaces import BrainProvider, LLMResponse, Intent
from core.registry import register
from core.config import config
from core.logger import get_logger
from core.personality import personality_manager

log = get_logger("brain.ollama")


# ═══════════════════════════════════════════════════════════════
# Prompt builders — these read from personality_manager.active
# so they always reflect the current personality.
# ═══════════════════════════════════════════════════════════════

def _build_music_preference_block(override_prefs: dict = None) -> str:
    """
    Build the music preferences section for prompts.

    Uses per-personality music_preferences if set, otherwise falls back
    to the global config.music.user_preferences.
    """
    # Per-personality override takes priority
    music_prefs = override_prefs or config.get("music", {}).get("user_preferences", {})
    if not music_prefs:
        return ""

    lines = ["\n## User's Music Taste (use this to disambiguate songs)"]

    languages = music_prefs.get("languages", [])
    region = music_prefs.get("region")
    if languages or region:
        langs = ", ".join(languages) if languages else "any"
        lines.append(f"- Languages: {langs}. Region: {region or 'any'}")

    artists = music_prefs.get("favorite_artists", [])
    if artists:
        lines.append(f"- Favorite artists: {', '.join(artists)}")

    genres = music_prefs.get("favorite_genres", [])
    if genres:
        lines.append(f"- Favorite genres: {', '.join(genres)}")

    bias = music_prefs.get("disambiguation_bias", "")
    if bias == "recent_bollywood":
        lines.append("- For Hindi songs: when ambiguous, prefer the recent Bollywood version by a favorite artist.")
        lines.append("- For English songs: prefer the globally popular version. Do NOT add Hindi artists to English songs.")

    return "\n".join(lines)


def _get_personality_names_for_prompt() -> str:
    """Build a list of available personality names for the classification prompt."""
    return ", ".join(
        f'"{p.id}" ({p.display_name})'
        for p in personality_manager.list()
    )


# Module-level recent context — set once at startup by set_conversation_context()
_recent_context: str = ""


def set_conversation_context(memory_provider) -> None:
    """
    Load recent interactions from memory and cache as a compact context string.
    Called once at startup from build_assistant() in main.py.
    """
    global _recent_context
    if not memory_provider:
        return
    try:
        recent = memory_provider.get_recent(limit=5)
        if not recent:
            return
        lines = []
        for mem in reversed(recent):  # oldest first
            # mem.content is a formatted string like "User asked to play Sajni"
            summary = mem.content[:100] if mem.content else ""
            if summary:
                lines.append(f"- {summary}")
        if lines:
            _recent_context = "Recent conversation:\n" + "\n".join(lines)
            log.debug("Loaded %d recent interactions for context", len(lines))
    except Exception as e:
        log.debug("Could not load conversation context: %s", e)


def _build_system_prompt() -> str:
    """
    Build the classification system prompt.

    Called fresh each time because the active personality can change.
    The personality's tone is injected so the LLM's response text
    matches the character, but the intent extraction logic stays stable.
    """
    p = personality_manager.active

    context_section = f"\n\n## Recent Context\n{_recent_context}" if _recent_context else ""

    return f"""You are {p.display_name}, a smart voice assistant used in India. {p.tone}{context_section}

Your ONLY job is to classify the user's spoken request into structured intents.
Extract parameters EXACTLY as the user said them. Do NOT modify, translate, or enrich song names.
The user speaks in English, Hindi, or Hinglish. You must understand all three.

Respond with valid JSON only. No explanation. No markdown.

## Intents

1. "music_play" — Play a song/artist/playlist/genre
   Params: {{"query": "the song/artist/mood keywords EXACTLY as the user said them", "with_video": true|false}}
   IMPORTANT: Do NOT add artist names, movie names, or any enrichment. Just extract what the user said.
   "with_video" defaults to false. Set to true ONLY when the user explicitly asks for video playback.
   Video triggers: "with video", "video mein", "video chalao", "ka video lagao", "video mode"
   Strip the video phrase from the query — do NOT include "with video" in the query string.
   "play Sajni" → query: "Sajni", with_video: false
   "play Sajni with video" → query: "Sajni", with_video: true
   "Sajni ka video lagao" → query: "Sajni", with_video: true
   "kuch romantic sa bajao" → query: "romantic Hindi songs", with_video: false
   "Coldplay bajao" → query: "Coldplay", with_video: false
   For mood/vague requests, translate Hindi to English search terms: "kuch sad sa" → "sad Hindi songs"

2. "music_control" — Control current playback
   Params: {{"action": "pause|resume|skip|stop"}}
   "skip" includes: skip, next, next song, move to next, agle gaane, change the song, dusra gaana
   IMPORTANT: "next song" or "next track" is ALWAYS music_control with action "skip" — it is NOT music_play.
   This is for controlling CURRENT playback — not for requesting new music.

3. "volume" — Change system volume (applies to ALL audio)
   Params: {{"level": "0-100", "output": "default"}}
   Clamp to 100 max. "volume up"→80, "volume down"→30.

4. "light_control" — Change room lights
   Params: {{"action": "on|off|brightness|color|scene", "value": "..."}}
   Scenes include: romantic, movie, party, sleep, reading, sunset, focus, and any "[word] mode" that refers to a lighting mood.
   IMPORTANT: "X mode laga do" where X is a mood/scene (like party, sleep, reading, focus) is ALWAYS light_control, NOT switch_personality.
   Only use switch_personality when the user explicitly names a personality (Jarvis, Devesh, Chandler, etc.).

5. "switch_personality" — Switch assistant personality/character
   Params: {{"personality": "name of the personality to switch to"}}
   Available personalities: {_get_personality_names_for_prompt()}
   "switch to Devesh mode" → personality: "devesh"
   "talk like Chandler" → personality: "chandler"
   "Devesh ban ja" → personality: "devesh"
   "normal mode" / "default mode" / "Jarvis mode" → personality: "jarvis"

6. "chat" — General question, conversation, stories, jokes, etc.
   Params: {{"message": "the user's question or request EXACTLY as said"}}
   IMPORTANT: For chat intents, the "message" param should just be the user's original words.
   Do NOT generate a story, answer, or any content in the message param — just echo what they said.
   The actual response will be generated separately by a different system.

7. "system" — System info (time, date, alarms)
   Params: {{"action": "time|date|alarm|reminder"}}

14. "weather" — Weather queries (current conditions, forecast, rain check)
   Params: {{"query": "current|forecast|rain|temperature", "location": "optional city name"}}
   "what's the weather" → weather {{"query": "current"}}
   "will it rain today" → weather {{"query": "rain"}}
   "weather forecast" → weather {{"query": "forecast"}}
   "temperature kya hai" → weather {{"query": "temperature"}}
   "mausam kaisa hai" → weather {{"query": "current"}}
   "Delhi ka mausam" → weather {{"query": "current", "location": "Delhi"}}

8. "memory_recall" — User asks about past interactions or what they/you did before
   Params: {{"query": "what the user wants to recall"}}
   Extract the KEY TOPIC words — strip filler like "what/did/you/have/for/me".
   IMPORTANT: Keep time words (today, yesterday) EXACTLY as the user said them. Do NOT change "today" to "yesterday" or vice versa.
   "what songs have you played for me today" → query: "songs played today"
   "what did I play yesterday" → query: "played yesterday"
   "last time I asked about lights" → query: "lights"
   "what was the song I played" → query: "song played"
   "kya bajaya tha maine" → query: "music play"
   "pichli baar kya pucha tha" → query: "recent interactions"

9. "memory_stats" — User asks how much the assistant remembers / interaction stats
   Params: {{}}
   "how much do you remember" → memory_stats
   "kitna yaad hai tujhe" → memory_stats

10. "sleep" — User wants the assistant to go to sleep or wake up
   Params: {{"action": "sleep|wake"}}
   Sleep: "good night", "sleep mode", "sone ja", "so ja", "go to sleep"
   Wake: "good morning", "wake up", "jag ja", "uth ja", "jaga do"
   Your response should be a personality-appropriate good night or good morning message.

11. "knowledge_search" — User asks about current events, real-time info, or facts that change over time
   Params: {{"query": "concise search query in English"}}
   Use this ONLY when the user asks about:
     - Current events, news, sports scores, election results
     - Things that change over time: "who is the PM now", "latest score", "today's weather"
     - Keywords that signal recency: "latest", "today", "yesterday", "current", "recent", "abhi"
   Do NOT use for:
     - General knowledge that doesn't change: "what is machine learning", "explain gravity", "what is Python"
     - Jokes, stories, opinions, creative requests, general conversation
     - Anything you can answer well from your training knowledge
   When in doubt between chat and knowledge_search, prefer chat. Only use knowledge_search when the answer REQUIRES up-to-date information.
   Translate Hindi/Hinglish to English for the search query.
   "aaj news kya hai" → query: "India news today"
   "IPL mein kya hua" → query: "IPL cricket latest score"

12. "quiz" — Start or interact with a trivia quiz game
   Params: {{"action": "start|answer|hint|score|quit", "category": "general|bollywood|movies|music|geography|tech|food|cricket", "difficulty": "easy|medium|hard", "answer": "user's answer text"}}
   Start: "play quiz", "quiz khelna hai", "trivia start", "let's play a game", "quiz chalao", "bollywood quiz", "start a hard quiz"
   Answer: any answer during an active quiz — "B", "Shah Rukh Khan", "Paris", "option C"
   Hint: "hint", "clue", "give me a hint", "hint de do"
   Score: "my score", "kitne aaye", "score bata"
   Quit: "quit quiz", "stop quiz", "quiz band karo"
   When starting, extract category and difficulty if mentioned: "play a hard bollywood quiz" → action: "start", category: "bollywood", difficulty: "hard"
   Default category is "general", default difficulty is "medium"

13. "youtube_search" — Search for something on YouTube
   Params: {{"query": "search terms"}}
   "search old Hindi songs on YouTube" → youtube_search {{"query": "old Hindi songs"}}
   "YouTube pe Sajni dhundho" → youtube_search {{"query": "Sajni"}}
   "find cooking videos on YouTube" → youtube_search {{"query": "cooking videos"}}
   "YouTube search Coldplay concerts" → youtube_search {{"query": "Coldplay concerts"}}

14. "reminder" — Set, list, cancel, or snooze reminders
   Params: {{"action": "add|cancel|list|snooze", "text": "description", "time": "HH:MM or relative", "date": "today|tomorrow|YYYY-MM-DD", "repeat": "none|daily|weekly|monthly"}}
   Add: "remind me to call mom at 5pm" → action: "add", text: "call mom", time: "5pm", date: "today"
   "remind me to take medicine at 10pm every day" → action: "add", text: "take medicine", time: "10pm", repeat: "daily"
   "set a reminder for tomorrow at 9am to buy groceries" → action: "add", text: "buy groceries", time: "9am", date: "tomorrow"
   "remind me in 2 hours to check the oven" → action: "add", text: "check the oven", time: "in 2 hours"
   "yaad dilana ki 5 baje call karna hai" → action: "add", text: "call karna hai", time: "5:00"
   "reminder set karo 10 baje medicine leni hai" → action: "add", text: "medicine leni hai", time: "10:00"
   List: "what reminders do I have" → action: "list"
   "list reminders" → action: "list"
   Cancel: "cancel my reminder to call mom" → action: "cancel", text: "call mom"
   "cancel reminder" → action: "cancel"
   Snooze: "snooze reminder" → action: "snooze"
   "snooze for 30 minutes" → action: "snooze", time: "30"
   Default date is "today", default repeat is "none"

15. "timer" — Set, cancel, or manage timers and alarms
   Params: {{"action": "set_timer|set_alarm|cancel|snooze|list", "duration": seconds, "time": "HH:MM", "label": "string", "repeat": "none|daily|weekdays"}}
   Set timer: "set a timer for 5 minutes" → action: "set_timer", duration: 300
   "timer lagao 10 minute" → action: "set_timer", duration: 600
   "set a 30 second timer" → action: "set_timer", duration: 30
   "timer for 2 hours" → action: "set_timer", duration: 7200
   "set a timer for 5 minutes for pasta" → action: "set_timer", duration: 300, label: "pasta"
   Set alarm: "set alarm for 7am" → action: "set_alarm", time: "07:00"
   "alarm at 7:30pm" → action: "set_alarm", time: "19:30"
   "wake me up at 6" → action: "set_alarm", time: "06:00"
   "alarm set karo 7 baje" → action: "set_alarm", time: "07:00"
   "set a daily alarm for 7am" → action: "set_alarm", time: "07:00", repeat: "daily"
   "weekday alarm at 6:30" → action: "set_alarm", time: "06:30", repeat: "weekdays"
   Cancel: "cancel timer" → action: "cancel"
   Snooze: "snooze" → action: "snooze"
   "snooze for 10 minutes" → action: "snooze", duration: 600
   List: "what timers are active" → action: "list"
   IMPORTANT: Timers use "duration" (in seconds). Alarms use "time" (HH:MM format).
   Convert minutes/hours to seconds for duration. Convert 12h to 24h for time.

## Format
Always return an "intents" array, even for a single command.
{{"intents": [{{"intent": "...", "params": {{...}}}}], "response": "Brief spoken acknowledgment IN CHARACTER."}}

IMPORTANT: Only use MULTIPLE intents for genuinely separate actions (e.g., "play music AND turn lights blue").
A single conversational request is ALWAYS one "chat" intent, never two. Examples of ONE intent:
- "tell me a story" → ONE chat intent
- "tell me a joke and then a riddle" → ONE chat intent (it's one conversational request)
- "what's the meaning of life" → ONE chat intent
Only split into multiple intents when combining DIFFERENT intent types (music + lights, music + volume, etc.).

## Response tone
Your "response" field MUST match your current personality:
{p.tone}

IMPORTANT: Always respond in ENGLISH only. Even if the user speaks Hindi or Hinglish, your response text must be in English. Never use Hindi words like "haan", "bolo", "kya", etc. in the response. Keep responses short — one sentence max for acknowledgments.

## Examples

User: "Sajni"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Sajni"}}}}], "response": "Playing Sajni."}}

User: "play Channa Mereya"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Channa Mereya"}}}}], "response": "Playing Channa Mereya."}}

User: "Starboy"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Starboy"}}}}], "response": "Playing Starboy."}}

User: "kuch romantic sa bajao"
{{"intents": [{{"intent": "music_play", "params": {{"query": "romantic Hindi songs"}}}}], "response": "Playing romantic songs."}}

User: "woh gaana jisme ladka train pe naachta hai"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Chaiyya Chaiyya"}}}}], "response": "Playing Chaiyya Chaiyya."}}

User: "play Sajni with video"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Sajni", "with_video": true}}}}], "response": "Playing Sajni with video."}}

User: "Sajni ka video lagao"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Sajni", "with_video": true}}}}], "response": "Playing Sajni video."}}

User: "Starboy video chalao"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Starboy", "with_video": true}}}}], "response": "Playing Starboy video."}}

User: "pause"
{{"intents": [{{"intent": "music_control", "params": {{"action": "pause"}}}}], "response": "Paused."}}

User: "gaana band karo"
{{"intents": [{{"intent": "music_control", "params": {{"action": "stop"}}}}], "response": "Stopped."}}

User: "agle gaane pe jao"
{{"intents": [{{"intent": "music_control", "params": {{"action": "skip"}}}}], "response": "Skipping."}}

User: "change the song"
{{"intents": [{{"intent": "music_control", "params": {{"action": "skip"}}}}], "response": "Skipping."}}

User: "skip this one"
{{"intents": [{{"intent": "music_control", "params": {{"action": "skip"}}}}], "response": "Skipping."}}

User: "move to the next track"
{{"intents": [{{"intent": "music_control", "params": {{"action": "skip"}}}}], "response": "Next track."}}

User: "awaaz badha do"
{{"intents": [{{"intent": "volume", "params": {{"level": "80", "output": "default"}}}}], "response": "Volume up."}}

User: "volume 50"
{{"intents": [{{"intent": "volume", "params": {{"level": "50", "output": "default"}}}}], "response": "Volume set to 50."}}

User: "turn the lights blue"
{{"intents": [{{"intent": "light_control", "params": {{"action": "color", "value": "blue"}}}}], "response": "Lights set to blue."}}

User: "neeli light kar do"
{{"intents": [{{"intent": "light_control", "params": {{"action": "color", "value": "blue"}}}}], "response": "Lights set to blue."}}

User: "movie mode"
{{"intents": [{{"intent": "light_control", "params": {{"action": "scene", "value": "movie"}}}}], "response": "Movie mode on."}}

User: "party mode laga do"
{{"intents": [{{"intent": "light_control", "params": {{"action": "scene", "value": "party"}}}}], "response": "Party mode!"}}

User: "reading mode"
{{"intents": [{{"intent": "light_control", "params": {{"action": "scene", "value": "reading"}}}}], "response": "Reading mode on."}}

User: "what time is it"
{{"intents": [{{"intent": "system", "params": {{"action": "time"}}}}], "response": ""}}

User: "what's the weather"
{{"intents": [{{"intent": "weather", "params": {{"query": "current"}}}}], "response": ""}}

User: "will it rain today"
{{"intents": [{{"intent": "weather", "params": {{"query": "rain"}}}}], "response": ""}}

User: "mausam kaisa hai"
{{"intents": [{{"intent": "weather", "params": {{"query": "current"}}}}], "response": ""}}

User: "weather forecast"
{{"intents": [{{"intent": "weather", "params": {{"query": "forecast"}}}}], "response": ""}}

User: "switch to Chandler mode"
{{"intents": [{{"intent": "switch_personality", "params": {{"personality": "chandler"}}}}], "response": "Oh, so NOW you want the funny one."}}

User: "Devesh ban ja"
{{"intents": [{{"intent": "switch_personality", "params": {{"personality": "devesh"}}}}], "response": "Haan bolo, Devesh here."}}

User: "normal mode"
{{"intents": [{{"intent": "switch_personality", "params": {{"personality": "jarvis"}}}}], "response": "Back to normal."}}

User: "what is the speed of light"
{{"intents": [{{"intent": "chat", "params": {{"message": "what is the speed of light"}}}}], "response": ""}}

User: "explain quantum computing"
{{"intents": [{{"intent": "chat", "params": {{"message": "explain quantum computing"}}}}], "response": ""}}

User: "what did I play yesterday"
{{"intents": [{{"intent": "memory_recall", "params": {{"query": "play yesterday"}}}}], "response": "Let me check..."}}

User: "kya bajaya tha maine"
{{"intents": [{{"intent": "memory_recall", "params": {{"query": "music play"}}}}], "response": "Dekhta hoon..."}}

User: "how much do you remember"
{{"intents": [{{"intent": "memory_stats", "params": {{}}}}], "response": ""}}

User: "aaj kya news hai"
{{"intents": [{{"intent": "knowledge_search", "params": {{"query": "India news today"}}}}], "response": "Let me look that up..."}}

User: "who won the IPL match yesterday"
{{"intents": [{{"intent": "knowledge_search", "params": {{"query": "IPL match result yesterday"}}}}], "response": "Let me check..."}}

User: "what's happening with the Mars rover"
{{"intents": [{{"intent": "knowledge_search", "params": {{"query": "Mars rover latest news"}}}}], "response": "Looking it up..."}}

User: "good night"
{{"intents": [{{"intent": "sleep", "params": {{"action": "sleep"}}}}], "response": "Good night, sleep well."}}

User: "sleep mode"
{{"intents": [{{"intent": "sleep", "params": {{"action": "sleep"}}}}], "response": "Going to sleep now. Good night."}}

User: "sone ja"
{{"intents": [{{"intent": "sleep", "params": {{"action": "sleep"}}}}], "response": "Good night, sweet dreams."}}

User: "good morning"
{{"intents": [{{"intent": "sleep", "params": {{"action": "wake"}}}}], "response": "Good morning! Ready when you are."}}

User: "wake up"
{{"intents": [{{"intent": "sleep", "params": {{"action": "wake"}}}}], "response": "I'm up! What can I do for you?"}}

User: "jag ja"
{{"intents": [{{"intent": "sleep", "params": {{"action": "wake"}}}}], "response": "Good morning! What do you need?"}}

User: "let's play a quiz"
{{"intents": [{{"intent": "quiz", "params": {{"action": "start", "category": "general", "difficulty": "medium"}}}}], "response": "Let's play!"}}

User: "bollywood quiz khelna hai"
{{"intents": [{{"intent": "quiz", "params": {{"action": "start", "category": "bollywood", "difficulty": "medium"}}}}], "response": "Bollywood quiz coming up!"}}

User: "start a hard cricket quiz"
{{"intents": [{{"intent": "quiz", "params": {{"action": "start", "category": "cricket", "difficulty": "hard"}}}}], "response": "A tough cricket quiz it is!"}}

User: "quit quiz"
{{"intents": [{{"intent": "quiz", "params": {{"action": "quit"}}}}], "response": "Quiz ended."}}

User: "remind me to call mom at 5pm"
{{"intents": [{{"intent": "reminder", "params": {{"action": "add", "text": "call mom", "time": "5pm", "date": "today", "repeat": "none"}}}}], "response": "I'll remind you to call mom at 5 PM."}}

User: "remind me to take medicine at 10pm every day"
{{"intents": [{{"intent": "reminder", "params": {{"action": "add", "text": "take medicine", "time": "10pm", "date": "today", "repeat": "daily"}}}}], "response": "Daily reminder set for 10 PM."}}

User: "remind me in 2 hours to check the oven"
{{"intents": [{{"intent": "reminder", "params": {{"action": "add", "text": "check the oven", "time": "in 2 hours"}}}}], "response": "Got it, I'll remind you in 2 hours."}}

User: "what reminders do I have"
{{"intents": [{{"intent": "reminder", "params": {{"action": "list"}}}}], "response": "Let me check your reminders."}}

User: "cancel my reminder to call mom"
{{"intents": [{{"intent": "reminder", "params": {{"action": "cancel", "text": "call mom"}}}}], "response": "Reminder cancelled."}}

User: "set a timer for 5 minutes"
{{"intents": [{{"intent": "timer", "params": {{"action": "set_timer", "duration": 300}}}}], "response": "Timer set for 5 minutes."}}

User: "timer lagao 10 minute"
{{"intents": [{{"intent": "timer", "params": {{"action": "set_timer", "duration": 600}}}}], "response": "Timer set for 10 minutes."}}

User: "set alarm for 7am"
{{"intents": [{{"intent": "timer", "params": {{"action": "set_alarm", "time": "07:00", "repeat": "none"}}}}], "response": "Alarm set for 7 AM."}}

User: "set a daily alarm for 6:30am"
{{"intents": [{{"intent": "timer", "params": {{"action": "set_alarm", "time": "06:30", "repeat": "daily"}}}}], "response": "Daily alarm set for 6:30 AM."}}

User: "cancel timer"
{{"intents": [{{"intent": "timer", "params": {{"action": "cancel"}}}}], "response": "Timer cancelled."}}

User: "snooze"
{{"intents": [{{"intent": "timer", "params": {{"action": "snooze"}}}}], "response": "Snoozed."}}

### Chained commands
User: "play Sajni and set the lights to red"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Sajni"}}}}, {{"intent": "light_control", "params": {{"action": "color", "value": "red"}}}}], "response": "Playing Sajni with red lights."}}

User: "play Sajni volume 30"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Sajni"}}}}, {{"intent": "volume", "params": {{"level": "30", "output": "default"}}}}], "response": "Playing Sajni at volume 30."}}

User: "what songs did you play today and resume the last one"
{{"intents": [{{"intent": "memory_recall", "params": {{"query": "songs played today"}}}}, {{"intent": "music_control", "params": {{"action": "resume"}}}}], "response": "Let me check and resume."}}

User: "Coldplay bajao aur light neeli kar do"
{{"intents": [{{"intent": "music_play", "params": {{"query": "Coldplay"}}}}, {{"intent": "light_control", "params": {{"action": "color", "value": "blue"}}}}], "response": "Playing Coldplay with blue lights."}}

User: "romantic mode laga do with some music"
{{"intents": [{{"intent": "light_control", "params": {{"action": "scene", "value": "romantic"}}}}, {{"intent": "music_play", "params": {{"query": "romantic Hindi songs"}}}}], "response": "Setting romantic mood with music."}}

User: "stop the music and turn off the lights"
{{"intents": [{{"intent": "music_control", "params": {{"action": "stop"}}}}, {{"intent": "light_control", "params": {{"action": "off"}}}}], "response": "Music stopped, lights off."}}

User: "gaana band karo aur light bhi off kar do"
{{"intents": [{{"intent": "music_control", "params": {{"action": "stop"}}}}, {{"intent": "light_control", "params": {{"action": "off"}}}}], "response": "Done, sab band."}}
"""


def _build_enrichment_prompt(personality_music_prefs: dict = None) -> str:
    """
    Separate prompt for Step 2: query enrichment.

    Uses per-personality music prefs if available, otherwise global.
    """
    music_prefs = _build_music_preference_block(personality_music_prefs or None)

    return f"""You are a music search query enhancer.
Given a song name or music query, add the singer/artist name if you KNOW it.
If you don't know the artist, return the query unchanged.
Do NOT guess. Do NOT add movie names unless certain.

{music_prefs}

Respond with JSON: {{"enriched": "the enhanced query"}}

Examples:
"Sajni" → {{"enriched": "Sajni Arijit Singh"}}
"Channa Mereya" → {{"enriched": "Channa Mereya Arijit Singh"}}
"Starboy" → {{"enriched": "Starboy The Weeknd"}}
"Bohemian Rhapsody" → {{"enriched": "Bohemian Rhapsody Queen"}}
"romantic Hindi songs" → {{"enriched": "romantic Hindi songs"}}
"Coldplay" → {{"enriched": "Coldplay"}}
"some random song I don't know" → {{"enriched": "some random song I don't know"}}
"""


@register("brain", "ollama")
class OllamaBrainProvider(BrainProvider):
    """Ollama-backed brain. Talks to a local Ollama server."""

    def __init__(self, model: str = None, endpoint: str = None, **kwargs):
        brain_config = config.get("brain", {})
        self.model = model or brain_config.get("model", "llama3.2:3b")
        self.endpoint = endpoint or brain_config.get("endpoint", "http://localhost:11434")
        self.temperature = brain_config.get("temperature", 0.3)

        # keep_alive controls how long Ollama keeps the model loaded in GPU/RAM
        # after the last request. Default is "5m" which means after 5 minutes of
        # inactivity, Ollama unloads the model. Reloading a 3B model takes 5-15
        # seconds on edge hardware — catastrophic for perceived latency.
        #
        # We set it to -1 (forever) so the model stays hot. On a Jetson with 8GB
        # shared memory, this is the right trade-off: we'd rather use the RAM
        # than make the user wait 10 seconds after a bathroom break.
        self._keep_alive = brain_config.get("keep_alive", -1)

        # Reusable HTTP session — avoids TCP handshake + connection setup per request.
        # On localhost this saves ~2-5ms per call, which adds up across
        # classify + enrich + chat (3 calls per interaction).
        self._session = requests.Session()

        # Prompts are NOT cached — they rebuild each call to reflect the active personality.
        # _build_system_prompt() and _build_enrichment_prompt() read from personality_manager.active.

        # Warm up: send a tiny request to force Ollama to load the model into
        # GPU/RAM NOW, at startup, rather than on the first user request.
        # Without this, the first "Hey Jarvis" after boot takes 10+ seconds
        # while the model loads. The warm-up request is fast (~100ms for 1 token).
        self._warm_up()

    def _warm_up(self):
        """
        Force Ollama to load the model into memory at startup.

        Sends a minimal generate request with num_predict=1 so the model
        gets loaded but barely any computation happens. This turns a 10-second
        first-request delay into a 0.5-second startup cost.
        """
        try:
            log.info("Warming up Ollama model %s...", self.model)
            start = time.time()
            self._session.post(
                f"{self.endpoint}/api/generate",
                json={
                    "model": self.model,
                    "prompt": "hi",
                    "stream": False,
                    "keep_alive": self._keep_alive,
                    "options": {"num_predict": 1},
                },
                timeout=60,  # model loading can take a while on first boot
            )
            elapsed = time.time() - start
            log.info("Ollama model warm (%.1fs).", elapsed)
        except Exception as e:
            log.warning("Ollama warm-up failed: %s. First request will be slow.", e)

    def generate(self, prompt: str, system: str = "", json_mode: bool = False,
                 temperature: float = None) -> LLMResponse:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self._keep_alive,
            "options": {"temperature": temperature or self.temperature},
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        start = time.time()
        resp = self._session.post(f"{self.endpoint}/api/generate", json=payload)
        latency = time.time() - start

        data = resp.json()
        text = data.get("response", "").strip()
        eval_count = data.get("eval_count", 0)
        eval_duration = data.get("eval_duration", 1)
        tok_per_sec = eval_count / (eval_duration / 1e9) if eval_duration > 0 else 0

        return LLMResponse(
            text=text,
            model=self.model,
            latency=latency,
            tokens_generated=eval_count,
            tokens_per_second=tok_per_sec,
            raw=data,
        )

    def classify_intent(self, user_input: str) -> list[Intent]:
        resp = self.generate(
            prompt=user_input,
            system=_build_system_prompt(),
            json_mode=True,
            temperature=self.temperature,
        )

        meta = {
            "model": resp.model,
            "latency": resp.latency,
            "tok_per_sec": resp.tokens_per_second,
        }

        try:
            parsed = json.loads(resp.text)
        except json.JSONDecodeError:
            log.warning("LLM returned invalid JSON, falling back to chat. Raw: %s", resp.text)
            return [Intent(
                name="chat",
                params={"message": user_input},
                response="",
                confidence=0.0,
                meta={**meta, "error": "json_parse_failed", "raw": resp.text},
            )]

        response = parsed.get("response", "")

        # New format: {"intents": [...], "response": "..."}
        if "intents" in parsed and isinstance(parsed["intents"], list):
            intents = [
                Intent(
                    name=i.get("intent", "chat"),
                    params=i.get("params", {}),
                    response=response,
                    confidence=1.0,
                    meta=meta,
                )
                for i in parsed["intents"]
            ] or [Intent(name="chat", params={"message": user_input}, response="", meta=meta)]

            # Defensive: if the LLM returned multiple chat intents, merge them.
            # A single conversational request should never be split into two
            # chat intents — that causes duplicate responses (e.g., two stories).
            chat_intents = [i for i in intents if i.name == "chat"]
            non_chat_intents = [i for i in intents if i.name != "chat"]
            if len(chat_intents) > 1:
                log.warning(
                    "LLM returned %d chat intents — merging into one. "
                    "This usually means the classifier over-split a single request.",
                    len(chat_intents),
                )
                merged_chat = Intent(
                    name="chat",
                    params={"message": user_input},  # use original input, not LLM output
                    response=response,
                    confidence=1.0,
                    meta=meta,
                )
                intents = non_chat_intents + [merged_chat]

            return intents

        # Backward compat: old format {"intent": "...", "params": {...}, "response": "..."}
        return [Intent(
            name=parsed.get("intent", "chat"),
            params=parsed.get("params", {}),
            response=response,
            confidence=1.0,
            meta=meta,
        )]

    def enrich_query(self, raw_query: str) -> str:
        """
        Step 2: Enrich a music query with artist/context.

        Separate from classification so that:
          - Classification extracts clean params ("Sajni", not "Sajni Arijit Singh")
          - Enrichment adds artist when confident ("Sajni" → "Sajni Arijit Singh")
          - The raw query is always available for fallback search
        """
        # Use per-personality music prefs if available
        p = personality_manager.active
        enrichment_prompt = _build_enrichment_prompt(p.music_preferences)

        resp = self.generate(
            prompt=raw_query,
            system=enrichment_prompt,
            json_mode=True,
            temperature=0.2,  # lower temp = more conservative
        )

        try:
            parsed = json.loads(resp.text)
            enriched = parsed.get("enriched", raw_query)
            if enriched != raw_query:
                log.debug('Enriched "%s" → "%s"', raw_query, enriched)
            return enriched
        except json.JSONDecodeError:
            log.warning("Enrichment returned invalid JSON, using raw query. Raw: %s", resp.text)
            return raw_query  # enrichment failed, return original

    def list_models(self) -> list[str]:
        resp = self._session.get(f"{self.endpoint}/api/tags")
        return [m["name"] for m in resp.json().get("models", [])]
