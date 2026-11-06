# Stage 1: clear the backlog

Audit against 0.8.0: action queue Partial (assistance/next); login sessions Missing;
structured blockers Partial (free text); batched questions Partial (profile answers);
checkpoints Partial (latest snapshot); deadlines/freshness Partial (posting dates and
discovery route evidence); hand-off Partial (drafts/manual-submitted); dashboard queue
Partial (Assistance view). Extend these contracts, do not replace submission events.

Plan: schema 2 with SQLite backup before migration and conservative legacy backfill;
one backlog module called exclusively by Workspace; derived priority queue; exact
tenant login batches; explicitly scoped reusable answers; append-only checkpoints
and live inspection gates; evidence-based freshness and deadlines; candidate-only
handoffs; dashboard controls; synthetic regression/migration/safety tests and package.

Decisions: unknown legacy blocker types remain needs_review; unknown deadlines and
effort remain null. Login completion schedules inspection, never proves authentication.
Question reuse requires identical text and explicit context. Queue estimates are
labelled estimates, never outcome predictions. No browser or model client is added.

Completed all eight Stage 1 contracts. Validation and host execution limitations are recorded in VALIDATION.md and references/backlog.md. Stages 2–6 were not started.
