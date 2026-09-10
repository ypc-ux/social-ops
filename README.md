# social-ops

A social content, market-radar, and reputation-response pipeline with a
mandatory voice + budget approval gate before anything ships. Multi-tenant
from day one — one deployment serves your own brand and every client
account via the `clients` table.

## Where this came from, and what's real

This was scoped from a marketing video pitching "62 AI agents, 8
departments, 20 modules" running a business's entire social media. That
video is ad copy for a paid product — it names department counts, not an
architecture. There is nothing to literally reproduce from it.

What's real and built here, mapped from the video's four described
capabilities down to actual working code:

| Video's pitch | This repo | Status |
|---|---|---|
| "Content Engine" | `content_engine.py` — topic → Ollama draft → voice gate → queue | **Real.** Trend/topic input is manual or fed by your own cron — no fabricated "trend detection" data source. |
| "Market Radar" | `market_radar.py` — searches for competitor mentions, spike detection vs. recent history, drafts a response | **Real.** X/Twitter (paid API tier required) or Mastodon (free, keyless — public hashtag timelines, no account needed to read). |
| "Reviews & Reputation" | `reputation.py` — finds new mentions of the brand, drafts a reply | **Real.** X @mentions (paid tier) or Mastodon hashtag (free) — not Google/Yelp reviews (not in this build's platform scope; add `reviews.py` the same way if you get that API access). |
| "Orchestrator" | `orchestrator.py` — every draft is scored by Claude against the brand voice + checked against the daily post budget; auto-approves or holds for a human, notifies Slack | **Real.** Fails closed: if the gate can't run (no API key, scoring error), the draft is held for manual review, never silently shipped. |

There is one drafting model (Ollama, local, cheap) and one independent
review model (Claude), not 62 agents. That's the honest version of the
pitch: cheap volume + an independent quality bar before anything reaches a
real audience.

## Why Ollama drafts and Claude reviews — not the other way around

Ollama (local, free) generates high-volume first drafts. It is **not** a
substitute for sophisticated copywriting frameworks — a small local model
will produce generic copy if left unchecked. So nothing it drafts ships
without an independent pass: Claude scores every draft against the brand
voice profile and platform norms, and a draft that scores below threshold
gets held for a human, full stop. This is the same "nothing grades its own
work" pattern used elsewhere in this business's other repos.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in at least OLLAMA_BASE_URL (default is fine if Ollama's running locally)
# and ANTHROPIC_API_KEY (required for the voice gate to auto-approve anything)

python -m social_ops.cli init-db
```

## Onboarding a client (yours or an actual client account)

```bash
python -m social_ops.cli init-client my-brand \
  --name "My Brand" \
  --voice-file clients/example-brand-voice.txt \
  --twitter-handle mybrandhandle \
  --daily-post-budget 3
```

Every module keys off `client_slug` — one deployment, unlimited clients,
each with their own voice profile and budget.

## Running it

```bash
# Content Engine: draft a post for a topic
python -m social_ops.cli content-draft my-brand --platform twitter --topic "Q4 hiring freeze trend"

# Market Radar: check for a competitor mention spike
python -m social_ops.cli radar-scan my-brand --query "@competitor_handle"

# Reputation: find and draft replies to new mentions
python -m social_ops.cli reputation-scan my-brand

# Orchestrator: route every unreviewed draft through the voice+budget gate
python -m social_ops.cli orchestrate

# See what's waiting on you
python -m social_ops.cli pending my-brand

# Approve, reject, or publish
python -m social_ops.cli approve 7
python -m social_ops.cli post 7
```

## What still needs credentials, and what doesn't

- **`ANTHROPIC_API_KEY`** — always required for automation. There's no free/keyless equivalent for the independent voice-check: that's the point of it being independent. Without it, every draft holds for manual review instead of auto-approving (safe default, zero automation).
- **X/Twitter** — needs a paid API tier (`TWITTER_BEARER_TOKEN` for search, full OAuth 1.0a keys to post). Not free.
- **Mastodon** — **reading is genuinely free and keyless.** `radar-scan --platform mastodon` and `reputation-scan --platform mastodon` work with zero credentials, against any public instance's hashtag timelines. Posting still needs a free access token from your own account (no payment, but not literally keyless either) — trade-off is hashtag-based monitoring instead of arbitrary keyword/@mention search, since Mastodon doesn't expose that publicly.
- **`SLACK_WEBHOOK_URL`** — optional but recommended; without it, held drafts only show up if you run `social-ops pending` yourself. Free to create.
- **LinkedIn** — intentionally not wired to search or auto-post. LinkedIn's API requires Marketing Developer Platform partner approval for that, which most developer accounts don't have. Approved LinkedIn drafts export to a CSV (`linkedin_pending_posts.csv`) for manual posting instead of pretending to automate something that isn't accessible.

**Bottom line:** you can run Content Engine + Market Radar + Reputation end
to end on Ollama (free) + Mastodon (free) with zero paid API access — the
one unavoidable cost is Claude for the voice gate, because that's the
component whose entire job is to not be free (i.e., not be the same model
grading its own work).

## Running this on a schedule (Deerflow)

Nothing in this repo runs itself continuously — that's Deerflow's job, same
pattern as the `agentic_priming_pilot` repo. Point a Deerflow workflow at
`orchestrate`, `radar-scan`, and `reputation-scan` on whatever cadence makes
sense (e.g. reputation-scan hourly, radar-scan every few hours, orchestrate
right after each). No workflow YAML is included here yet since your Deerflow
instance's actual trigger/step conventions weren't specified — copy the
pattern from `agentic_priming_pilot/deerflow_workflow.yaml` once you're
ready to wire it in.

## Database

SQLite, one file (`social_ops.db` by default), schema in `schema.sql`. Four
tables: `clients`, `drafts`, `mentions`, `approvals_log`. Good enough for one
operator managing several client accounts; move to Postgres if you ever need
concurrent writers.
