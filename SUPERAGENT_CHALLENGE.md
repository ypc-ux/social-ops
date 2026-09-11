# Social-Ops — Social Media Orchestrator Superagent

## What It Does
Complete social media management pipeline that drafts content, scores it against brand voice, checks daily post budgets, and either auto-posts or holds for human review. Multi-tenant system where one deployment serves your own brand and every client account.

Four modules:
1. **Content Engine** — topic → Ollama draft → voice gate → queue
2. **Market Radar** — searches for competitor mentions, spike detection vs. recent history, drafts a response
3. **Reviews & Reputation** — finds new mentions of the brand, drafts a reply
4. **Orchestrator** — every draft is scored by Claude against the brand voice + checked against the daily post budget; auto-approves or holds for a human, notifies Slack

## Tools Connected (5+)
- **Ollama** — local AI for drafting content (cheap, runs locally)
- **Claude (Anthropic)** — independent voice scoring (separate from whatever drafted it)
- **SQLite** — draft storage, client configuration, approval logs
- **Twitter API** — post tweets, search mentions, reply to brand mentions
- **Mastodon API** — post statuses, search hashtags (free, no account needed to read)
- **LinkedIn API** — export for manual posting (API not fully wired yet)
- **Slack** — notifications when drafts are held for review

## Autonomous Decisions
- **Voice scoring**: Claude scores every draft against the client's brand voice profile
- **Budget checking**: checks if daily post budget has been reached
- **Auto-approval**: if voice score >= threshold AND budget not exceeded, auto-approves
- **Hold logic**: if voice score < threshold OR budget exceeded, holds for human review
- **Fail-closed**: if voice gate can't run (no API key, scoring error), draft is held for manual review, never silently shipped
- **Platform routing**: decides which platform to post to based on module and client config

## Daily Cadence
Runs on scheduled cycles:
- Content Engine: drafts posts based on topics/ideas
- Market Radar: scans for competitor mentions, drafts responses
- Reputation: scans for brand mentions, drafts replies
- Orchestrator: processes all pending drafts through voice+budget gate

The orchestrator runs continuously, processing drafts as they're created. Every draft passes through the gate before posting.

## Context Across Sessions
SQLite stores:
- Client configuration (brand voice profiles, daily post budgets, auto-post settings)
- Draft history (all drafts, scores, decisions, posting status)
- Approval logs (who approved/rejected, when, why)
- Platform post IDs (links back to actual posts on Twitter/Mastodon)

Every decision has full context: what was drafted, why it was scored that way, what the budget was, what happened.

## Quality Gate
The orchestrator never posts anything itself when it's uncertain. It decides who reviews it, not whether it ships silently. This is the key difference between this and a naive "auto-post everything" system.

## Testing & Quality
- Multi-tenant from day one (clients table, per-client voice profiles)
- Voice gate fails closed (never silently ships bad content)
- Approval logging (every decision tracked)
- Platform abstraction (same code works for Twitter, Mastodon, LinkedIn)

## Integration with Portfolio
Publishes signals to ops digest:
- `did` signals when drafts are created, auto-approved, posted
- `needs_you` signals when drafts are held for review

The ops digest monitors social-ops daily and reports which drafts need attention.

## Scoring
- **Qualifying**: 10 points (autonomous agent doing real work)
- **Complex**: 15 points (orchestrates 5+ tools, makes autonomous decisions, holds context, runs on scheduled cycles)
- **Total**: 25 points
