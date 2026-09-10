"""Content Engine: topic -> draft -> queued for the orchestrator.

Trend/topic input is intentionally pluggable and manual for now — this repo
does not fabricate a "trend detection" data source with no real signal
behind it. Feed it topics from wherever you actually get them (a Google
Trends export, a keyword you're targeting this week, a Deerflow schedule
that calls this on a cron). What's real here is the draft -> voice-gate
pipeline, not a magic trend radar.
"""
import logging

from . import db
from .ollama_draft import draft_post, init_ollama_client

logger = logging.getLogger(__name__)


def create_draft(client_slug: str, platform: str, topic: str, context: str = "") -> int:
    """Draft a post for a topic and store it as a pending draft row. Returns the draft id."""
    conn = db.get_connection()
    client = db.get_client(conn, client_slug)

    ollama_client = init_ollama_client()
    body = draft_post(client["voice_profile"], platform, topic, context=context, client=ollama_client)

    cur = conn.execute(
        """INSERT INTO drafts (client_id, module, platform, topic, body, status, draft_source)
           VALUES (?, 'content_engine', ?, ?, ?, 'draft', 'ollama')""",
        (client["id"], platform, topic, body),
    )
    conn.commit()
    draft_id = cur.lastrowid
    logger.info("Created content_engine draft %s for %s on %s", draft_id, client_slug, platform)
    conn.close()
    return draft_id
