# Stage 3: referrals and daily jobs

Audit: connection import/matching Missing; warm boost Missing; referral sequence
Partial (drafts only); contact cards Partial (sources/checked_at); cadence/DNC Missing;
network analytics Partial (observed outreach/referral touches); daily top 5 Missing;
digest approval Partial (exact existing authorizations); saved search/capacity Missing;
dedup Partial (URL); quality flags Missing; partial portal coverage Exists; UI Missing.

Plan: backup-first schema 4; file-only connection imports and evidence-based matching;
bounded optional boost, sourced contact verification, separately authorized referral
messages with cadence and DNC; daily host workflow with persisted searches, capacity,
dedup/quality evidence and digest decisions through existing authorize; analytics/UI;
synthetic tests, docs, package, one local commit. No live service tests or real workspace.

Decisions: default 5 preparations per UTC day across runs; primary sources remain
LinkedIn and Indeed. Confirmed requisition identities deduplicate; fuzzy/agency/title
similarity produces visible warnings, never destructive merges. Default cadence 7
days, at most 2 messages per contact in 30 days; reply/referral/decline stops sequence.
Telegram digest sends only generated IDs/counts via explicit opt-in; dashboard holds
full details. Never install a schedule or send referral outreach implicitly.

Completed: all Stage 3 features implemented in the canonical skill helper and dashboard.
126 synthetic tests pass, including migrations and authorization safety boundaries.
Read VALIDATION.md for browser checks and remaining live-host verification limits.
