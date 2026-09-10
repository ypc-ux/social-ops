-- social-ops schema. One database serves every client (yours and future
-- client accounts) via the clients table — no per-client database needed.

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    voice_profile TEXT NOT NULL,           -- free-text description of brand voice
    twitter_handle TEXT,
    linkedin_handle TEXT,
    daily_post_budget INTEGER NOT NULL DEFAULT 3,
    auto_post INTEGER NOT NULL DEFAULT 0,  -- 0 = always hold for human posting, even if auto-approved
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    module TEXT NOT NULL,                  -- content_engine | market_radar | reputation
    platform TEXT NOT NULL,                -- twitter | linkedin
    topic TEXT,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',  -- draft | pending_approval | approved | rejected | posted | post_failed
    voice_score INTEGER,
    voice_reasoning TEXT,
    draft_source TEXT,                     -- ollama | claude_escalated | unscored
    reply_to_url TEXT,                     -- for reputation replies / market_radar responses
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    decided_at TEXT,
    posted_at TEXT,
    platform_post_id TEXT
);

CREATE TABLE IF NOT EXISTS mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    platform TEXT NOT NULL,
    kind TEXT NOT NULL,                    -- competitor | own_brand
    handle TEXT,
    text TEXT,
    url TEXT,
    detected_at TEXT NOT NULL DEFAULT (datetime('now')),
    spike_flag INTEGER NOT NULL DEFAULT 0,
    draft_id INTEGER REFERENCES drafts(id)
);

CREATE TABLE IF NOT EXISTS approvals_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id INTEGER NOT NULL REFERENCES drafts(id),
    decision TEXT NOT NULL,                -- auto_approved | approved | rejected
    reason TEXT,
    decided_by TEXT NOT NULL DEFAULT 'orchestrator',
    decided_at TEXT NOT NULL DEFAULT (datetime('now'))
);
