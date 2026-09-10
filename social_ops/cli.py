#!/usr/bin/env python3
"""social-ops CLI. Run `python -m social_ops.cli <command> --help` for details."""
import argparse
import logging
import sys

from dotenv import load_dotenv

from . import content_engine, db, market_radar, orchestrator, reputation
from .platforms import linkedin, twitter

load_dotenv()
log = logging.getLogger("social-ops")


def cmd_init_db(args):
    db.init_db()
    print(f"Initialized database at {db.DB_PATH}")


def cmd_init_client(args):
    conn = db.get_connection()
    voice_profile = args.voice
    if args.voice_file:
        with open(args.voice_file) as f:
            voice_profile = f.read()
    conn.execute(
        """INSERT INTO clients (slug, name, voice_profile, twitter_handle, linkedin_handle, daily_post_budget, auto_post)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (args.slug, args.name, voice_profile, args.twitter_handle, args.linkedin_handle,
         args.daily_post_budget, 1 if args.auto_post else 0),
    )
    conn.commit()
    conn.close()
    print(f"Client '{args.slug}' created.")


def cmd_content_draft(args):
    draft_id = content_engine.create_draft(args.client, args.platform, args.topic, context=args.context or "")
    print(f"Draft #{draft_id} created. Run `social-ops orchestrate {draft_id}` to route it.")


def cmd_radar_scan(args):
    result = market_radar.scan_competitor(args.client, args.query, platform=args.platform)
    print(result)


def cmd_reputation_scan(args):
    ids = reputation.scan_mentions(args.client, platform=args.platform)
    print(f"Drafted {len(ids)} replies: {ids}")


def cmd_orchestrate(args):
    conn = db.get_connection()
    if args.draft_id:
        rows = conn.execute("SELECT * FROM drafts WHERE id = ?", (args.draft_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM drafts WHERE status = 'draft'").fetchall()

    for row in rows:
        result = orchestrator.process_draft(conn, row)
        print(f"Draft #{row['id']}: {result}")
    conn.close()


def cmd_pending(args):
    conn = db.get_connection()
    query = "SELECT * FROM drafts WHERE status = 'pending_approval'"
    params = ()
    if args.client:
        client = db.get_client(conn, args.client)
        query += " AND client_id = ?"
        params = (client["id"],)
    rows = conn.execute(query, params).fetchall()
    for row in rows:
        print(f"#{row['id']} [{row['platform']}/{row['module']}] score={row['voice_score']}: {row['body'][:80]}")
    conn.close()


def cmd_approve(args):
    conn = db.get_connection()
    conn.execute("UPDATE drafts SET status = 'approved', decided_at = datetime('now') WHERE id = ?", (args.draft_id,))
    conn.execute(
        "INSERT INTO approvals_log (draft_id, decision, reason, decided_by) VALUES (?, 'approved', ?, 'human')",
        (args.draft_id, args.reason or ""),
    )
    conn.commit()
    conn.close()
    print(f"Draft #{args.draft_id} approved.")


def cmd_reject(args):
    conn = db.get_connection()
    conn.execute("UPDATE drafts SET status = 'rejected', decided_at = datetime('now') WHERE id = ?", (args.draft_id,))
    conn.execute(
        "INSERT INTO approvals_log (draft_id, decision, reason, decided_by) VALUES (?, 'rejected', ?, 'human')",
        (args.draft_id, args.reason or ""),
    )
    conn.commit()
    conn.close()
    print(f"Draft #{args.draft_id} rejected.")


def cmd_post(args):
    conn = db.get_connection()
    row = conn.execute("SELECT * FROM drafts WHERE id = ?", (args.draft_id,)).fetchone()
    if row is None:
        sys.exit(f"No draft #{args.draft_id}")
    if row["status"] != "approved":
        sys.exit(f"Draft #{args.draft_id} is '{row['status']}', not 'approved'. Approve it first.")

    client = conn.execute("SELECT * FROM clients WHERE id = ?", (row["client_id"],)).fetchone()

    try:
        if row["platform"] == "twitter":
            reply_id = None
            if row["reply_to_url"]:
                reply_id = row["reply_to_url"].rsplit("/", 1)[-1]
            result = twitter.post_tweet(row["body"], reply_to_id=reply_id)
            conn.execute(
                "UPDATE drafts SET status = 'posted', posted_at = datetime('now'), platform_post_id = ? WHERE id = ?",
                (result.get("data", {}).get("id"), args.draft_id),
            )
        elif row["platform"] == "linkedin":
            path = linkedin.export_for_manual_posting(args.draft_id, row["body"], client["slug"])
            conn.execute("UPDATE drafts SET status = 'posted', posted_at = datetime('now') WHERE id = ?", (args.draft_id,))
            print(f"Exported to {path} for manual posting (LinkedIn API not wired — see platforms/linkedin.py).")
        else:
            sys.exit(f"Unknown platform '{row['platform']}'")

        conn.commit()
        print(f"Draft #{args.draft_id} posted.")
    except Exception as e:
        conn.execute("UPDATE drafts SET status = 'post_failed' WHERE id = ?", (args.draft_id,))
        conn.commit()
        sys.exit(f"Posting failed: {e}")
    finally:
        conn.close()


def build_parser():
    parser = argparse.ArgumentParser(prog="social-ops")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init-db", help="Create the database and tables.")
    p.set_defaults(func=cmd_init_db)

    p = sub.add_parser("init-client", help="Register a new client (your own brand or a client account).")
    p.add_argument("slug")
    p.add_argument("--name", required=True)
    p.add_argument("--voice", default="", help="Inline voice profile text.")
    p.add_argument("--voice-file", help="Path to a file with the voice profile (overrides --voice).")
    p.add_argument("--twitter-handle")
    p.add_argument("--linkedin-handle")
    p.add_argument("--daily-post-budget", type=int, default=3)
    p.add_argument("--auto-post", action="store_true", help="Post immediately on auto-approval, no manual `social-ops post` step.")
    p.set_defaults(func=cmd_init_client)

    p = sub.add_parser("content-draft", help="Draft a post for a topic (Content Engine).")
    p.add_argument("client")
    p.add_argument("--platform", required=True, choices=["twitter", "linkedin"])
    p.add_argument("--topic", required=True)
    p.add_argument("--context")
    p.set_defaults(func=cmd_content_draft)

    p = sub.add_parser("radar-scan", help="Scan for a competitor mention spike (Market Radar).")
    p.add_argument("client")
    p.add_argument("--query", required=True, help="Competitor name or @handle to search for.")
    p.add_argument("--platform", default="twitter", choices=["twitter"])
    p.set_defaults(func=cmd_radar_scan)

    p = sub.add_parser("reputation-scan", help="Scan for new mentions of the client's own handle.")
    p.add_argument("client")
    p.add_argument("--platform", default="twitter", choices=["twitter"])
    p.set_defaults(func=cmd_reputation_scan)

    p = sub.add_parser("orchestrate", help="Run pending drafts through the voice+budget gate.")
    p.add_argument("draft_id", type=int, nargs="?", help="Specific draft id; omit to process all status='draft' rows.")
    p.set_defaults(func=cmd_orchestrate)

    p = sub.add_parser("pending", help="List drafts waiting on human review.")
    p.add_argument("client", nargs="?")
    p.set_defaults(func=cmd_pending)

    p = sub.add_parser("approve", help="Approve a held draft.")
    p.add_argument("draft_id", type=int)
    p.add_argument("--reason")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("reject", help="Reject a held draft.")
    p.add_argument("draft_id", type=int)
    p.add_argument("--reason")
    p.set_defaults(func=cmd_reject)

    p = sub.add_parser("post", help="Actually publish an approved draft.")
    p.add_argument("draft_id", type=int)
    p.set_defaults(func=cmd_post)

    return parser


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
