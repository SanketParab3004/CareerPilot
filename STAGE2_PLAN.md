# Stage 2: learn from results

Audit: Attribution Partial (source/fit/documents already saved); funnel Missing;
honest statistics Missing; approved feedback/undo Missing; weekly review Partial
(events/backlog); outcome hygiene Partial (Gmail history); rejection reasons Partial
(free-text evidence); dashboard analytics Missing. Extend existing helper, mail
review and dashboard, preserving submission and outreach boundaries.

Plan: schema 3 migration with verified SQLite backup; immutable application snapshots
and dated outcome history; descriptive cohort analytics with denominators and missing
data disclosure; approved/undoable future-only adjustments; weekly review and silence
flags; stated-reason records; dashboard; synthetic regression/safety/migration tests;
package and one local commit. Never touch real job-search-workspace.

Design: 20 applications per comparison group minimum (configurable upward), at least
14 days observation by default; backfilled/incomplete records excluded from learning.
Acknowledgements are not substantive replies. Rates use confirmed applications as
denominator and never imply causation. Silence is an analytical label, never Rejected.
Ranking boosts are bounded and separate from original fit/relevance; tailoring changes
are host-consumed guidance for new documents, not automatic rewrites.

Stage 2 implemented and validated. Host browser/mail/tailoring behavior needs real-world checking; no live services were used. Stage 3 follows in a separate commit.
