"""Market Radar: watches for competitor mention spikes on X, drafts a
responsive angle when one is detected.

Spike detection is a simple real heuristic, not a black box: this scan's
mention count vs. the average of the client's last 5 scans for the same
query. No historical average yet (first run) -> never flagged a spike,
correctly, since there's nothing to compare against.
"""
import logging

from . import db
from .ollama_draft import draft_reply, init_ollama_client
from .platforms import mastodon, twitter

logger = logging.getLogger(__name__)

SPIKE_MULTIPLIER = 2.0  # this scan must be >= 2x the recent average to flag


def scan_competitor(client_slug: str, query: str, platform: str = "twitter") -> dict:
    """Search recent mentions of `query`, record them, and draft a response
    if this scan is a spike vs. recent history.

    platform='twitter': `query` is a free-text search term/handle. Requires
        a paid X API tier — see platforms/twitter.py.
    platform='mastodon': `query` is a hashtag (no leading #), searched via a
        public, keyless timeline endpoint. Free, but only catches posts
        actually tagged with that hashtag — not arbitrary keyword mentions.

    Returns a summary dict: {count, average, is_spike, draft_id (or None)}.
    """
    conn = db.get_connection()
    client = db.get_client(conn, client_slug)

    if platform == "twitter":
        mentions = twitter.search_recent(query, max_results=50)
    elif platform == "mastodon":
        mentions = mastodon.hashtag_timeline(query, limit=40)
    else:
        raise NotImplementedError(f"market_radar does not support platform='{platform}' — see platforms/linkedin.py for why LinkedIn isn't here.")

    count = len(mentions)

    for m in mentions:
        conn.execute(
            """INSERT INTO mentions (client_id, platform, kind, handle, text, url, detected_at)
               VALUES (?, 'twitter', 'competitor', ?, ?, ?, ?)""",
            (client["id"], query, m["text"], m["url"], m["created_at"] or "now"),
        )
    conn.commit()

    # Average of this query's last 5 prior scans (grouped by detected_at day),
    # excluding the rows just inserted.
    history = conn.execute(
        """SELECT COUNT(*) as c FROM mentions
           WHERE client_id = ? AND kind = 'competitor' AND handle = ?
           AND id NOT IN (SELECT id FROM mentions WHERE client_id = ? AND handle = ? ORDER BY id DESC LIMIT ?)
           GROUP BY date(detected_at) ORDER BY date(detected_at) DESC LIMIT 5""",
        (client["id"], query, client["id"], query, count),
    ).fetchall()
    average = sum(r["c"] for r in history) / len(history) if history else None

    is_spike = average is not None and average > 0 and count >= average * SPIKE_MULTIPLIER
    draft_id = None

    if is_spike:
        top_mention = max(mentions, key=lambda m: len(m["text"])) if mentions else None
        if top_mention:
            ollama_client = init_ollama_client()
            body = draft_reply(
                client["voice_profile"], platform, top_mention["text"], reply_kind="market_radar", client=ollama_client
            )
            cur = conn.execute(
                """INSERT INTO drafts (client_id, module, platform, topic, body, status, draft_source)
                   VALUES (?, 'market_radar', ?, ?, ?, 'draft', 'ollama')""",
                (client["id"], platform, f"competitor spike: {query}", body),
            )
            conn.commit()
            draft_id = cur.lastrowid
            logger.info("Spike detected for %s (%d vs avg %.1f) — drafted response %s", query, count, average, draft_id)

    conn.close()
    return {"count": count, "average": average, "is_spike": is_spike, "draft_id": draft_id}
