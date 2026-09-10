"""X (Twitter) API v2 integration. Real calls, gated behind real credentials —
every function raises a clear error if the required env vars aren't set,
rather than silently no-opping. Search requires a Bearer token (App-only
auth); posting requires user-context OAuth 1.0a credentials.
"""
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://api.twitter.com/2"


def _bearer_token() -> str:
    token = os.environ.get("TWITTER_BEARER_TOKEN")
    if not token:
        raise RuntimeError(
            "TWITTER_BEARER_TOKEN not set. Get one from developer.twitter.com "
            "(requires at least the Basic API tier for recent search)."
        )
    return token


def search_recent(query: str, max_results: int = 25) -> list:
    """Search tweets from the last 7 days matching `query`.

    Returns a list of dicts: {id, text, author_id, url, created_at}.
    """
    headers = {"Authorization": f"Bearer {_bearer_token()}"}
    params = {
        "query": query,
        "max_results": min(max(max_results, 10), 100),
        "tweet.fields": "created_at,author_id",
    }
    resp = requests.get(f"{API_BASE}/tweets/search/recent", headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    return [
        {
            "id": t["id"],
            "text": t["text"],
            "author_id": t.get("author_id"),
            "url": f"https://twitter.com/i/web/status/{t['id']}",
            "created_at": t.get("created_at"),
        }
        for t in data
    ]


def _user_context_session() -> "requests.Session":
    """OAuth 1.0a user-context session, required to post on a user's behalf."""
    try:
        from requests_oauthlib import OAuth1
    except ImportError:
        raise ImportError(
            "requests_oauthlib not installed. Install with: pip install requests-oauthlib"
        )

    required = ["TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Missing Twitter OAuth env vars for posting: {', '.join(missing)}")

    auth = OAuth1(
        os.environ["TWITTER_API_KEY"],
        os.environ["TWITTER_API_SECRET"],
        os.environ["TWITTER_ACCESS_TOKEN"],
        os.environ["TWITTER_ACCESS_SECRET"],
    )
    session = requests.Session()
    session.auth = auth
    return session


def post_tweet(text: str, reply_to_id: Optional[str] = None) -> dict:
    """Post a tweet (or a reply, if reply_to_id is given). Returns the API response."""
    session = _user_context_session()
    payload = {"text": text}
    if reply_to_id:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to_id}

    resp = session.post(f"{API_BASE}/tweets", json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()
