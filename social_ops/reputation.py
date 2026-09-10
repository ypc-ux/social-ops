"""Reputation: watches for mentions/replies to the client's own handle on X
and drafts a reply for each one.

Scoped to X mentions, not reviews — Google/Yelp review monitoring wasn't in
the platform scope this repo was built for. Add a reviews.py alongside this
following the same pattern if/when you wire up Google Business Profile or
Yelp API access.
"""
import logging

from . import db
from .ollama_draft import draft_reply, init_ollama_client
from .platforms import twitter

logger = logging.getLogger(__name__)


def scan_mentions(client_slug: str, platform: str = "twitter") -> list:
    """Find recent mentions of the client's own handle, draft a reply to each
    one that doesn't already have a draft. Returns the list of new draft ids.
    """
    if platform != "twitter":
        raise NotImplementedError("reputation scanning currently only supports platform='twitter'.")

    conn = db.get_connection()
    client = db.get_client(conn, client_slug)
    if not client["twitter_handle"]:
        raise ValueError(f"Client '{client_slug}' has no twitter_handle configured.")

    mentions = twitter.search_recent(f"@{client['twitter_handle']}", max_results=25)
    new_draft_ids = []
    ollama_client = None

    for m in mentions:
        existing = conn.execute(
            "SELECT id FROM mentions WHERE client_id = ? AND url = ?", (client["id"], m["url"])
        ).fetchone()
        if existing:
            continue

        if ollama_client is None:
            ollama_client = init_ollama_client()

        body = draft_reply(client["voice_profile"], platform, m["text"], reply_kind="reputation", client=ollama_client)
        cur = conn.execute(
            """INSERT INTO drafts (client_id, module, platform, topic, body, status, draft_source, reply_to_url)
               VALUES (?, 'reputation', ?, ?, ?, 'draft', 'ollama', ?)""",
            (client["id"], platform, "mention reply", body, m["url"]),
        )
        conn.commit()
        draft_id = cur.lastrowid

        conn.execute(
            """INSERT INTO mentions (client_id, platform, kind, handle, text, url, detected_at, draft_id)
               VALUES (?, 'twitter', 'own_brand', ?, ?, ?, ?, ?)""",
            (client["id"], client["twitter_handle"], m["text"], m["url"], m["created_at"] or "now", draft_id),
        )
        conn.commit()
        new_draft_ids.append(draft_id)
        logger.info("Drafted reply %s to mention %s", draft_id, m["url"])

    conn.close()
    return new_draft_ids
