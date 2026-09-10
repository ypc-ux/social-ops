"""Mastodon — a genuinely free, keyless data source.

Public hashtag timelines on any Mastodon instance are open, unauthenticated
REST endpoints (per the public-apis project's listing of free/keyless
APIs) — no account, no API key, no paid tier. The tradeoff: Mastodon has no
general full-text mention search without auth, only public hashtag
timelines. That means this is a real alternative for tracking a competitor
or brand that has (or that you assign) a hashtag, not a drop-in replacement
for arbitrary keyword search the way the paid X API is. Documented
honestly rather than papering over the gap.
"""
import os
import re
from html import unescape

import requests

DEFAULT_INSTANCE = "mastodon.social"


def _strip_html(content: str) -> str:
    text = re.sub(r"<[^>]+>", " ", content or "")
    return unescape(re.sub(r"\s+", " ", text)).strip()


def hashtag_timeline(hashtag: str, instance: str = DEFAULT_INSTANCE, limit: int = 25) -> list:
    """Fetch recent public posts tagged with `hashtag` (no leading #).

    Returns a list of dicts: {id, text, url, created_at, author}. No
    authentication required — this is a public, unauthenticated endpoint.
    """
    hashtag = hashtag.lstrip("#")
    url = f"https://{instance}/api/v1/timelines/tag/{hashtag}"
    resp = requests.get(url, params={"limit": min(max(limit, 1), 40)}, timeout=15)
    resp.raise_for_status()
    posts = resp.json()
    return [
        {
            "id": p["id"],
            "text": _strip_html(p.get("content", "")),
            "url": p.get("url"),
            "created_at": p.get("created_at"),
            "author": p.get("account", {}).get("acct"),
        }
        for p in posts
    ]


def post_status(text: str, instance: str = None, reply_to_id: str = None) -> dict:
    """Post a status. Reading is keyless; posting on your own account is not
    — Mastodon still requires an access token for write actions (create one
    free, in your own account's Development settings — no paid tier, but
    not literally keyless either).
    """
    instance = instance or os.environ.get("MASTODON_INSTANCE", DEFAULT_INSTANCE)
    token = os.environ.get("MASTODON_ACCESS_TOKEN")
    if not token:
        raise RuntimeError(
            "MASTODON_ACCESS_TOKEN not set. Free to create (Preferences > Development "
            "in your own Mastodon account) but required to post."
        )
    payload = {"status": text}
    if reply_to_id:
        payload["in_reply_to_id"] = reply_to_id
    resp = requests.post(
        f"https://{instance}/api/v1/statuses",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
