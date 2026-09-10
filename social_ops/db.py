"""SQLite access layer. One file database, one schema, many clients."""
import os
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get("SOCIAL_OPS_DB", "social_ops.db")
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection = None) -> None:
    own_conn = conn is None
    conn = conn or get_connection()
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    if own_conn:
        conn.close()


def get_client(conn: sqlite3.Connection, slug: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM clients WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        raise ValueError(f"No client with slug '{slug}'. Run `social-ops init-client` first.")
    return row


def posts_today_count(conn: sqlite3.Connection, client_id: int) -> int:
    row = conn.execute(
        """SELECT COUNT(*) as c FROM drafts
           WHERE client_id = ? AND status IN ('approved', 'posted')
           AND date(created_at) = date('now')""",
        (client_id,),
    ).fetchone()
    return row["c"]
