"""The gate every draft passes through before it ships.

Checks, in order:
  1. Voice fit + safety (voice_gate.score_post, via Claude — independent of
     whatever drafted it).
  2. Daily post budget for the client.

If both pass: auto-approved. If the client has auto_post enabled, it's
immediately posted; otherwise it's approved but still waits for a human to
run `social-ops post <id>`.

If either fails: held as pending_approval and (if configured) a Slack
notification is sent so a human can review it. The orchestrator never posts
anything itself when it's uncertain — it decides who reviews it, not
whether it ships silently.
"""
import logging
import os

import requests

from . import db
from .voice_gate import gate_configured, score_post

logger = logging.getLogger(__name__)


def notify_slack(message: str) -> None:
    webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook:
        logger.info("SLACK_WEBHOOK_URL not set; skipping notification. Message was:\n%s", message)
        return
    try:
        requests.post(webhook, json={"text": message}, timeout=10)
    except Exception as e:
        logger.warning("Slack notification failed: %s", e)


def process_draft(conn, draft_row) -> dict:
    """Run one draft through the voice + budget gate. Returns the decision dict."""
    client = conn.execute("SELECT * FROM clients WHERE id = ?", (draft_row["client_id"],)).fetchone()

    if not gate_configured():
        _hold(conn, draft_row, reason="Voice gate not configured (no ANTHROPIC_API_KEY) — manual review required.")
        return {"decision": "pending_approval", "reason": "gate_not_configured"}

    scored = score_post(draft_row["body"], client["voice_profile"], draft_row["platform"])
    conn.execute(
        "UPDATE drafts SET voice_score = ?, voice_reasoning = ? WHERE id = ?",
        (scored["score"], scored["reasoning"], draft_row["id"]),
    )
    conn.commit()

    threshold = int(os.environ.get("VOICE_GATE_THRESHOLD", "75"))
    if scored["score"] < threshold:
        _hold(conn, draft_row, reason=f"Voice score {scored['score']} below threshold {threshold}: {scored['reasoning']}")
        return {"decision": "pending_approval", "reason": "voice_score_low", "score": scored["score"]}

    today_count = db.posts_today_count(conn, client["id"])
    if today_count >= client["daily_post_budget"]:
        _hold(conn, draft_row, reason=f"Daily post budget ({client['daily_post_budget']}) already reached today.")
        return {"decision": "pending_approval", "reason": "budget_exceeded"}

    conn.execute(
        "UPDATE drafts SET status = 'approved', decided_at = datetime('now') WHERE id = ?",
        (draft_row["id"],),
    )
    conn.execute(
        "INSERT INTO approvals_log (draft_id, decision, reason, decided_by) VALUES (?, 'auto_approved', ?, 'orchestrator')",
        (draft_row["id"], scored["reasoning"]),
    )
    conn.commit()
    logger.info("Draft %s auto-approved (score=%d)", draft_row["id"], scored["score"])
    return {"decision": "approved", "score": scored["score"]}


def _hold(conn, draft_row, reason: str) -> None:
    conn.execute(
        "UPDATE drafts SET status = 'pending_approval' WHERE id = ?",
        (draft_row["id"],),
    )
    conn.commit()
    notify_slack(
        f":bell: *social-ops* draft #{draft_row['id']} needs your review\n"
        f"Platform: {draft_row['platform']} | Module: {draft_row['module']}\n"
        f"Reason: {reason}\n"
        f"---\n{draft_row['body']}\n---\n"
        f"Approve: `social-ops approve {draft_row['id']}`  |  Reject: `social-ops reject {draft_row['id']}`"
    )
