"""
SQLite Memory Provider — v1: interaction logging + keyword recall.

This is the simplest useful memory: every interaction gets logged to a local
SQLite database, and you can search it with keyword queries. No embeddings,
no multi-user, no encryption — just a reliable local log.

Why SQLite?
  - Zero dependencies (it's in Python's stdlib)
  - Single file, easy to backup/move
  - Runs on Mac, Jetson, and Pi with zero config
  - Fast enough for thousands of interactions
  - WAL mode handles concurrent reads/writes safely

The database lives at {config.memory.db_path}, defaulting to
assistant/data/memory.db. The data/ directory is gitignored.

Schema (v1 — intentionally simple):
  interactions: one row per user message (may produce multiple intents)
  ┌─────────┬──────────┬────────────┬──────────┬─────────────┬──────────┬──────────┬──────────┐
  │ id (PK) │ timestamp│ user_id    │input_text│ intents_json│responses │ outcome  │ feedback │
  └─────────┴──────────┴────────────┴──────────┴─────────────┴──────────┴──────────┴──────────┘

Future versions add: facts table, users table, embeddings table, FTS5 index.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from core.interfaces import MemoryProvider, Interaction, Memory, Intent
from core.registry import register
from core.config import config
from core.logger import get_logger

log = get_logger("memory.sqlite")


@register("memory", "sqlite")
class SQLiteMemoryProvider(MemoryProvider):
    """
    Local SQLite-backed memory store.

    Stores every interaction as a row in the interactions table.
    Recall uses SQL LIKE for keyword search (v1).
    Future: FTS5 full-text search, then semantic embeddings.
    """

    def __init__(self, **kwargs):
        memory_cfg = config.get("memory", {})
        db_path_str = kwargs.get("db_path") or memory_cfg.get("db_path", "data/memory.db")

        # Resolve relative paths from the assistant directory
        db_path = Path(db_path_str)
        if not db_path.is_absolute():
            db_path = Path(__file__).parent.parent.parent / db_path

        # Ensure the directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path
        self._conn = None  # persistent connection, created lazily
        self._init_db()

        log.info("Memory initialized at %s", self.db_path)

    def _init_db(self):
        """Create tables if they don't exist. Idempotent."""
        conn = self._get_conn()
        conn.executescript("""
            -- WAL mode: allows concurrent reads while writing.
            -- Without this, a long recall query could block interaction logging.
            PRAGMA journal_mode=WAL;

            -- Synchronous NORMAL: ~2x faster writes vs FULL, still crash-safe
            -- with WAL mode. Only risk: OS crash could lose the last transaction
            -- (not app crash — that's always safe). Acceptable for interaction logs.
            PRAGMA synchronous=NORMAL;

            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT 'default',
                input_text TEXT NOT NULL,
                intents_json TEXT NOT NULL,
                responses_json TEXT NOT NULL,
                outcome TEXT DEFAULT '',
                feedback TEXT DEFAULT NULL
            );

            -- Index on timestamp for recent-first queries
            CREATE INDEX IF NOT EXISTS idx_interactions_timestamp
                ON interactions(timestamp DESC);

            -- Index on user_id for multi-user filtering (future-proofing)
            CREATE INDEX IF NOT EXISTS idx_interactions_user
                ON interactions(user_id);

            -- Schema version tracking — so future migrations know what to do
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );

            INSERT OR IGNORE INTO schema_version (version, applied_at)
                VALUES (1, datetime('now'));
        """)

    def _get_conn(self) -> sqlite3.Connection:
        """
        Get the persistent database connection, creating it on first call.

        Reusing a single connection avoids the ~5ms overhead of sqlite3.connect()
        on every query. WAL mode + NORMAL synchronous makes this safe for
        concurrent reads/writes from the same thread. For multi-threaded access
        (future), we'd use a connection pool instead.
        """
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), timeout=5.0)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _connect(self) -> sqlite3.Connection:
        """Get the database connection. Alias for backward compat."""
        return self._get_conn()

    def log_interaction(self, interaction: Interaction) -> int:
        """
        Log a complete interaction to the database.

        The intents list gets JSON-serialized. Each Intent is stored as:
          {"name": "music_play", "params": {"query": "Sajni"}, "confidence": 1.0}

        Returns the auto-generated interaction ID.
        """
        timestamp = interaction.timestamp or datetime.now(timezone.utc).isoformat()

        # Serialize intents — store the structured data, not just the name
        intents_data = []
        for intent in interaction.intents:
            if isinstance(intent, Intent):
                intents_data.append({
                    "name": intent.name,
                    "params": intent.params,
                    "response": intent.response,
                    "confidence": intent.confidence,
                })
            elif isinstance(intent, dict):
                intents_data.append(intent)
            else:
                intents_data.append({"name": str(intent)})

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO interactions
                    (timestamp, user_id, input_text, intents_json, responses_json, outcome, feedback)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    interaction.user_id,
                    interaction.input_text,
                    json.dumps(intents_data, ensure_ascii=False),
                    json.dumps(interaction.responses, ensure_ascii=False),
                    interaction.outcome,
                    interaction.feedback,
                ),
            )
            interaction_id = cursor.lastrowid

        log.debug("Logged interaction #%d: [%s] %s",
                  interaction_id,
                  " + ".join(i.get("name", "?") for i in intents_data),
                  interaction.input_text[:50])

        return interaction_id

    def recall(self, query: str, user_id: str = "default",
               limit: int = 5) -> list[Memory]:
        """
        Search interactions by keyword (v1).

        Searches across input_text, intents_json, and responses_json.
        This is a simple SQL LIKE search — good enough for "what did I play
        yesterday?" but won't handle semantic queries like "that sad song."

        v2 will add FTS5 full-text search.
        v3 will add embedding-based semantic search.
        """
        # Split query into keywords for AND matching
        keywords = [k.strip() for k in query.lower().split() if len(k.strip()) > 1]

        if not keywords:
            return self.get_recent(user_id=user_id, limit=limit)

        # Build WHERE clause: each keyword must match somewhere
        conditions = []
        params = []
        for kw in keywords:
            conditions.append(
                "(LOWER(input_text) LIKE ? OR LOWER(intents_json) LIKE ? OR LOWER(responses_json) LIKE ?)"
            )
            like = f"%{kw}%"
            params.extend([like, like, like])

        where = " AND ".join(conditions)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, timestamp, user_id, input_text, intents_json, responses_json, outcome
                FROM interactions
                WHERE user_id = ? AND {where}
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                [user_id, *params, limit],
            ).fetchall()

        return [self._row_to_memory(row) for row in rows]

    def get_recent(self, user_id: str = "default",
                   limit: int = 10) -> list[Memory]:
        """Get the N most recent interactions, newest first."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, timestamp, user_id, input_text, intents_json, responses_json, outcome
                FROM interactions
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()

        return [self._row_to_memory(row) for row in rows]

    def get_stats(self, user_id: str = "default") -> dict:
        """Summary stats about stored interactions."""
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM interactions WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]

            if total == 0:
                return {"total_interactions": 0, "top_intents": {}}

            first = conn.execute(
                "SELECT MIN(timestamp) FROM interactions WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]

            last = conn.execute(
                "SELECT MAX(timestamp) FROM interactions WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]

            # Count intent types — parse the JSON in Python since SQLite
            # JSON support varies across platforms
            rows = conn.execute(
                "SELECT intents_json FROM interactions WHERE user_id = ?",
                (user_id,),
            ).fetchall()

        intent_counts = {}
        for row in rows:
            try:
                intents = json.loads(row["intents_json"])
                for intent in intents:
                    name = intent.get("name", "unknown")
                    intent_counts[name] = intent_counts.get(name, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass

        # Sort by count descending
        top_intents = dict(sorted(intent_counts.items(), key=lambda x: -x[1]))

        return {
            "total_interactions": total,
            "first_interaction": first,
            "last_interaction": last,
            "top_intents": top_intents,
        }

    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        """Convert a database row to a Memory object."""
        intents = json.loads(row["intents_json"])
        responses = json.loads(row["responses_json"])

        # Build a human-readable summary
        intent_names = [i.get("name", "?") for i in intents]
        intent_str = " + ".join(intent_names)

        # Extract key details for the summary
        parts = [f'You said: "{row["input_text"]}"']
        parts.append(f"Intent: {intent_str}")
        if responses:
            # Truncate long responses for the summary
            resp_preview = responses[0][:100]
            if len(responses[0]) > 100:
                resp_preview += "..."
            parts.append(f"Response: {resp_preview}")

        content = " → ".join(parts)

        return Memory(
            content=content,
            category="interaction",
            timestamp=row["timestamp"],
            relevance=1.0,  # v1: no relevance scoring, all results equal
            raw={
                "id": row["id"],
                "user_id": row["user_id"],
                "input_text": row["input_text"],
                "intents": intents,
                "responses": responses,
                "outcome": row["outcome"],
            },
        )
