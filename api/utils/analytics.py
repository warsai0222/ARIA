"""
Query analytics — logs each chat request to Neon PostgreSQL.

Completely optional: if DATABASE_URL is not set, all calls are no-ops.
The analytics table is created / migrated automatically on first use.

Schema:
    CREATE TABLE IF NOT EXISTS aria_query_log (
        id               SERIAL PRIMARY KEY,
        query            TEXT NOT NULL,
        session_id       TEXT,
        cache_hit        BOOLEAN DEFAULT FALSE,
        couldnt_answer   BOOLEAN DEFAULT FALSE,
        response_snippet TEXT,
        response_time_ms INTEGER,
        created_at       TIMESTAMPTZ DEFAULT NOW()
    );
"""

from __future__ import annotations

import os

_pool = None
_table_ready = False
_enabled = bool(os.environ.get("DATABASE_URL"))

# Phrases that indicate the bot deflected / couldn't answer
_DEFLECTION_PHRASES = [
    "i don't have that detail",
    "reach out to varshith directly",
    "i can only help with questions about varshith",
    "don't have specific information",
    "not sure about that",
    "i don't have information",
]


def is_deflection(response: str) -> bool:
    """Return True if the response signals the bot couldn't answer."""
    lower = response.lower()
    return any(phrase in lower for phrase in _DEFLECTION_PHRASES)


async def _get_pool():
    global _pool
    if _pool is None and _enabled:
        try:
            import asyncpg
            _pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=3)
        except Exception:
            pass
    return _pool


async def _ensure_table() -> None:
    """Create table and run any schema migrations idempotently."""
    global _table_ready
    if _table_ready or not _enabled:
        return
    pool = await _get_pool()
    if pool is None:
        return
    async with pool.acquire() as conn:
        # Base table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS aria_query_log (
                id               SERIAL PRIMARY KEY,
                query            TEXT NOT NULL,
                session_id       TEXT,
                cache_hit        BOOLEAN DEFAULT FALSE,
                response_time_ms INTEGER,
                created_at       TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        # Migrations — safe to run repeatedly (IF NOT EXISTS / DO NOTHING pattern)
        for column, definition in [
            ("couldnt_answer",   "BOOLEAN DEFAULT FALSE"),
            ("response_snippet", "TEXT"),
        ]:
            await conn.execute(f"""
                DO $$ BEGIN
                    ALTER TABLE aria_query_log ADD COLUMN {column} {definition};
                EXCEPTION WHEN duplicate_column THEN NULL;
                END $$;
            """)
    _table_ready = True


async def log_query(
    query: str,
    session_id: str = "",
    cache_hit: bool = False,
    couldnt_answer: bool = False,
    response_snippet: str = "",
    response_time_ms: int = 0,
) -> None:
    """Log a query. Silently no-ops if analytics is disabled or DB is unreachable."""
    if not _enabled:
        return
    try:
        pool = await _get_pool()
        if pool is None:
            return
        await _ensure_table()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO aria_query_log
                       (query, session_id, cache_hit, couldnt_answer, response_snippet, response_time_ms)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                query[:1000],
                session_id,
                cache_hit,
                couldnt_answer,
                response_snippet[:500] if response_snippet else "",
                response_time_ms,
            )
    except Exception:
        pass  # never let analytics failures break the main flow
