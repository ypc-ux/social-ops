"""LinkedIn integration — honestly scoped.

LinkedIn's public API does not offer keyword/mention search, and posting on
a company page's behalf requires Marketing Developer Platform partnership
approval (a real application process with LinkedIn, not just an API key).
Most developer accounts cannot get this. Rather than pretend this module
does something it can't, it:

  1. Never claims to search LinkedIn for mentions/competitors — market_radar
     and reputation modules skip LinkedIn scanning entirely unless you've
     obtained partner API access and wired it in here yourself.
  2. Supports drafting (via ollama_draft/voice_gate, same as Twitter).
  3. Exports approved LinkedIn drafts to a CSV for manual posting, since
     that's the only reliable path without partner API access.
"""
import csv
import os
from pathlib import Path

EXPORT_PATH = Path(os.environ.get("LINKEDIN_EXPORT_PATH", "linkedin_pending_posts.csv"))


def export_for_manual_posting(draft_id: int, body: str, client_slug: str) -> str:
    """Append an approved LinkedIn draft to a CSV you paste into LinkedIn by hand.

    Returns the path written to.
    """
    is_new = not EXPORT_PATH.exists()
    with open(EXPORT_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["draft_id", "client_slug", "body"])
        writer.writerow([draft_id, client_slug, body])
    return str(EXPORT_PATH)
