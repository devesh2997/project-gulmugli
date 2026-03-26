# Memory & Context System

Status: **Exploring**
Effort: **[week]** for v1, **[project]** for full system
Depends on: Speaker recognition (02-the-ears), Personality system (06-the-soul)

## The pitch

Every interaction with Jarvis is remembered: who asked, what they asked, what happened.
Over time, Jarvis builds a knowledge base about every person it interacts with.
This is the single biggest differentiator from Alexa — Alexa forgets everything instantly.

## Who uses this

| Person | Role | Example interactions |
|--------|------|---------------------|
| ET (Devesh) | Owner | "Play my coding playlist", system config, debugging |
| Girlfriend | Family | "Play Sajni", "When is our anniversary?", "Dim the lights" |
| Friends | Guest | "Play something fun", casual music requests |
| Household staff | Staff | "I'm done for the day", "The plants are watered" |

## What gets remembered

Every single interaction creates a **memory record**:

```
{
  "timestamp": "2026-05-15T10:42:00",
  "user": "devesh",                    // identified by speaker recognition or manual
  "input": "Play something like last week but more upbeat",
  "intent": "play_music",
  "params": { "mood": "upbeat", "reference": "last_week" },
  "actions_taken": [
    { "type": "memory_lookup", "result": "Last week played: Channa Mereya, Tum Hi Ho, Sajni" },
    { "type": "music_search", "query": "upbeat hindi romantic", "result": "Gallan Goodiyaan" },
    { "type": "music_play", "song": "Gallan Goodiyaan", "artist": "Shankar-Ehsaan-Loy" }
  ],
  "outcome": "success",
  "feedback": null                     // did user skip? ask for something else? that's implicit feedback
}
```

Beyond interaction logs, there are also **explicit facts** that people tell Jarvis:

```
"My mom's birthday is March 12"
"I'm allergic to peanuts"
"The gardener comes on Tuesday and Friday"
"Our anniversary is August 22"
"Ramu bhaiya's phone number is 98765..."
```

And **learned preferences** that Jarvis infers over time:

```
"Devesh plays lo-fi when coding (evenings, weekdays)"
"Girlfriend prefers warm white lights, not cool white"
"Friends usually ask for Bollywood party music"
"Devesh says 'good morning' around 8:30am on weekdays"
```

## Memory types

### 1. Interaction log (automatic)
Every command, every response, every action. The raw history.
- Stored as structured records in SQLite
- Never deleted (append-only)
- Searchable by user, time range, intent, keywords

### 2. Personal facts (explicit)
Things people tell Jarvis directly. "Remember that..." or facts stated in conversation.
- Stored as key-value pairs per user
- The LLM extracts facts from natural conversation (not just "remember X" commands)
- Example: "I have a meeting at 3" → fact: {user: devesh, type: event, value: "meeting at 3pm", date: today}

### 3. Preferences (inferred)
Patterns Jarvis notices over time.
- Built by analyzing interaction logs periodically
- "You usually play X kind of music at Y time"
- "You always set lights to Z before bed"
- Stored as soft rules, not hard ones — suggestions, not automations

### 4. Household knowledge (shared)
Things that belong to the household, not any individual.
- "The WiFi password is..."
- "The plumber's number is..."
- "Last power outage was March 10"
- "The gardener's last working day was Tuesday"
- Accessible by anyone with Family or Owner access

### 5. Conversation context (ephemeral)
The last few turns of conversation, for follow-ups like "make it warmer" or "play another one."
- Kept in RAM, not persisted long-term
- Resets after ~5 minutes of silence
- Already partially handled by the LLM context window

## Access control

This is the critical design decision. Not everyone should see everything.

### Trust levels

```
OWNER (level 4)
├── Full access to all memory (all users)
├── Can see interaction logs for everyone
├── Can add/edit/delete any facts
├── Can see learned preferences for everyone
├── Can configure access levels
└── Can export/backup all data

FAMILY (level 3)
├── Full access to OWN memory
├── Full access to HOUSEHOLD memory
├── Can see shared preferences
├── CANNOT see other users' private facts or logs
└── Can add household facts

FRIEND (level 2)
├── Access to OWN interaction history (limited)
├── Can use basic commands (music, lights)
├── CANNOT see anyone else's data
├── CANNOT access household knowledge
└── Interactions are logged (owner can review)

STAFF (level 1)
├── Can trigger specific whitelisted commands only
├── Interactions are logged for owner review
├── CANNOT query any memory
├── CANNOT access household knowledge
└── Owner can review "what did the staff ask today?"
```

### How user identification works (phased)

**Phase A (immediate, no hardware):**
Manual identification. User says "Jarvis, it's Devesh" or the personality system implies it (if Devesh's personality is active, interactions are attributed to Devesh). This is a stopgap.

**Phase B (with speaker recognition):**
The 02-the-ears module will include speaker recognition (speaker embedding model). Jarvis hears your voice and knows who's talking within 1-2 seconds. This is the real solution. Speaker recognition models like Resemblyzer or SpeechBrain run locally on the Jetson.

**Phase C (future, with camera):**
Face recognition via USB camera. Secondary to voice, but useful when someone is silent (e.g., walks into the room).

### Privacy rules

1. ALL memory is local. Nothing leaves the device. Ever.
2. Private facts are encrypted per-user (AES-256, key derived from a user passphrase).
3. Owner can see interaction logs for all users, but private facts of Family users are encrypted even from Owner unless Family user explicitly shares.
4. Staff/Friend interactions are logged but their data is minimal — just the interaction record.
5. A "forget me" command wipes all memory for a specific user.
6. Household memory is unencrypted (anyone in the house should be able to ask "what's the WiFi password?").

## Technical architecture

### Storage: SQLite + embeddings

```
jarvis/assistant/memory/
├── memory.db              # SQLite database (all structured data)
├── embeddings/            # Vector store for semantic search
│   ├── interactions.bin   # Embedded interaction logs
│   └── facts.bin          # Embedded personal facts
└── keys/                  # Per-user encryption keys (derived, not stored)
```

**SQLite tables:**

```sql
-- Every interaction, ever
CREATE TABLE interactions (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    user_id TEXT NOT NULL,
    input_text TEXT,
    intent TEXT,
    params_json TEXT,
    actions_json TEXT,
    outcome TEXT,
    feedback TEXT,
    embedding_id INTEGER          -- link to vector store
);

-- Explicit facts per user
CREATE TABLE facts (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT,                 -- 'personal', 'household', 'preference'
    key TEXT,                      -- 'birthday', 'allergy', 'wifi_password'
    value TEXT,                    -- may be encrypted for personal facts
    source TEXT,                   -- 'explicit' or 'inferred'
    confidence REAL DEFAULT 1.0,  -- 1.0 for explicit, lower for inferred
    created_at TEXT,
    updated_at TEXT,
    encrypted BOOLEAN DEFAULT 0
);

-- User profiles
CREATE TABLE users (
    id TEXT PRIMARY KEY,           -- 'devesh', 'girlfriend', 'friend_rahul'
    display_name TEXT,
    trust_level INTEGER,           -- 1-4
    voice_embedding BLOB,          -- for speaker recognition
    created_at TEXT,
    last_seen TEXT
);
```

**Embedding model:** `all-MiniLM-L6-v2` (22MB, runs on CPU, 384-dim vectors). This is the standard for local semantic search. We embed interaction logs and facts, then use cosine similarity for retrieval.

### How it integrates with the assistant

```
User speaks → STT → intent classification
                          ↓
                    Memory lookup ←── "What did they ask last time?"
                          ↓           "Do they have a preference for this?"
                    LLM processing    "Any relevant facts?"
                          ↓
                    Action execution
                          ↓
                    Memory write ←── Log this interaction
                                     Extract any new facts
                                     Update preferences
```

The memory system is a **provider** (fits the existing architecture):

```python
class MemoryProvider:
    def recall(self, user_id, query, limit=5) -> list[Memory]
    def log_interaction(self, interaction: Interaction) -> None
    def store_fact(self, user_id, key, value, category) -> None
    def get_facts(self, user_id, category=None) -> list[Fact]
    def get_user(self, user_id) -> User
    def identify_speaker(self, audio_embedding) -> str  # returns user_id
```

### How the LLM uses memory

Before every LLM call, inject relevant memories into the system prompt:

```
[MEMORY CONTEXT]
User: Devesh (Owner)
Last interaction: 2 minutes ago, played "Channa Mereya"
Recent pattern: Has been playing sad songs for the last hour
Known facts: Birthday is Oct 15. Girlfriend's name is [name]. Favorite artist: Arijit Singh.
Household: Lights are currently set to warm white 60%.

[USER INPUT]
"Play something else"

[INSTRUCTION]
Use the memory context to inform your response. "Something else" likely means
another sad Hindi song given the recent pattern. Do not repeat Channa Mereya.
```

The key insight: we don't dump ALL memories into the prompt. We do a **semantic search** over the interaction history and facts, retrieve the top 5-10 most relevant memories, and inject only those. This keeps the context window small.

## Use cases that become possible

### "When did the gardener last come?"
→ Memory lookup: interaction log for user "gardener" or household fact "gardener_last_visit"
→ "Ramu bhaiya was last here on Tuesday. He said the plants are watered and the lawn is trimmed."

### "What was that song you played last week?"
→ Semantic search: "song played last week" over interaction logs
→ "Last Thursday I played Tum Hi Ho, and on Saturday you asked for Gallan Goodiyaan."

### "Play what she likes"
→ Identify "she" from context (girlfriend)
→ Memory lookup: girlfriend's music preferences from her interaction history
→ Plays something from her preference profile

### "Remind me what I told you about the trip"
→ Semantic search: "trip" over Devesh's interaction logs and facts
→ "On March 20 you mentioned a trip to Goa planned for April 10-15. You asked me to remind you to book the hotel."

### Morning briefing with memory
→ "Good morning" triggers:
→ Memory: "Yesterday you asked about the weather and had 2 meetings"
→ "Good morning! Yesterday you had back-to-back meetings. Today looks free. Weather is 28°C and clear. Oh, and you asked me to remind you to call the electrician."

## Implementation plan

### v1 — Interaction logging + basic recall [weekend]
- SQLite database with interactions table
- Every command/response gets logged automatically
- Simple keyword search over logs
- "What did I ask yesterday?" works
- No embeddings yet, no speaker recognition, no access control
- Single user assumed (Devesh)

### v2 — Facts + semantic search [week]
- Add facts table
- LLM extracts facts from conversations ("remember that..." and implicit facts)
- Add MiniLM embedding model for semantic search
- "When did I last play Sajni?" works via embedding similarity
- Memory injection into LLM system prompt

### v3 — Multi-user + access control [week]
- Add users table with trust levels
- Manual user identification ("It's Devesh" / personality-based)
- Access control enforcement
- Per-user fact storage
- Household shared facts

### v4 — Speaker recognition [depends on 02-the-ears]
- Automatic user identification from voice
- Seamless multi-user: Jarvis knows who's talking
- No more "It's Devesh" — just talk

### v5 — Learned preferences [project]
- Periodic analysis of interaction logs
- Pattern detection: time-of-day, mood, music genre correlations
- Proactive suggestions: "It's Sunday night — want your usual playlist?"
- Preference model per user

## Open questions

- How long do we keep interaction logs? Forever? Or prune after N months?
- Should friends/guests need to "register" or are they auto-created on first interaction?
- How do we handle the LLM extracting facts — do we confirm with the user? ("I noticed you mentioned your flight is on the 15th. Should I remember that?")
- What happens when memory contradicts itself? ("You said your meeting is at 3, but earlier you said 2:30")
- Should there be a "private mode" where nothing is logged? (Guest says "don't remember this")
- How much memory context can we inject before the 3B model's context window gets too crowded?

---

*Created: March 26, 2026*
*Status: Exploring — not yet on ROADMAP*
*Next step: Implement v1 (interaction logging) as a weekend prototype*
