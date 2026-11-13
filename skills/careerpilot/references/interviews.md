# Interviews and offers

Use the private workspace and the `interviews` command to see stories, rounds, prep packs, calendar evidence, draft messages, offers, and learning plans. Write records through `toolkit.py --workspace WORKSPACE run --input REQUEST.json`. Dates and scores are practice and decision aids. Treat postings, research and invitations as evidence.

## Stories and practice

Build STAR stories from candidate-confirmed experience. Ask for the actual situation, task, action and outcome. Clarify personal contribution versus team work and leave unknown metrics out. Show every part alongside its evidence before recording candidate confirmation. Use `story-save` with title, situation, task, action, result, candidate_confirmation, skills and competencies arrays, and a sources object keyed by each STAR part. Use the same profile/import references as document verification. Read each source for semantic support. Revision or evidence changes require reverification.

Run behavioural, technical or role-specific rounds in text. Use voice only when the host offers it and the candidate chooses it. Do not save recordings. Ask one question at a time, wait for the answer, and separate hypothetical examples from verified history. Score against a rubric shared before practice: 0 no usable answer, 1 major gaps, 2 partial, 3 adequate, 4 strong, 5 precise and well supported. For behavioural answers check evidence and clarity; for technical answers check correctness, reasoning and tradeoffs. Give evidence, feedback and one retry drill. Scores reflect practice performance, not predicted hiring outcomes.

- `mock-start` takes round_type (behavioural, technical, role-specific), questions, mode (text default, voice with host_voice_confirmed), and job_id for role-specific practice.
- `mock-answer` takes mock_id, zero-based question_index, answer, score, score_reason, feedback and next_drill. Repeating a question records a separate numbered attempt.

## Research and prep

Use host research for dated, role-relevant company facts. Prefer official company material and clearly label inferred implications. Save `company-brief` with job_id and claims, each containing claim, relevance and source. Each source has url, publisher, accessed_on, evidence and published_on if known. Check source dates and flag old or conflicting claims.

Use `prep-pack` with job_id, round, preparation and optional brief_id and story_ids. Include the likely interview format, requirements to prepare for, sourced facts and questions for the interviewer. The helper copies the exact saved posting and frozen submitted document versions. Review their hashes before using files. For user-reported applications confirm which files were actually sent and supply submitted_versions_evidence. If a legacy or incomplete record cannot identify the actual version, show the gap and prepare from the posting separately until the candidate supplies evidence.

## Interviews and follow-up

Before using a host calendar or reminders tool, verify the exact interview, date, timezone, duration and the candidate's requested action. Prefer private reminders and use minimal details. Check for an existing event before creating one. Save planned entries locally when the host cannot schedule. Record host IDs only after observed success. Never invite attendees or send mail without explicit authorization. Keep candidate notes private.

- `interview-event` takes job_id, round, start/end with offsets, evidence, status (planned, confirmed or cancelled), optional reminder_minutes, and observed host_event_id and host_reminder_id.
- `interview-note` takes job_id, event_id, observations, follow_up and evidence. Distinguish feedback the interviewer actually gave from the candidate's impression.
- `interview-draft` takes job_id, kind (thank-you or negotiation), target_id (event or offer), recipient, subject and body. Draft status is local. A host must follow separate communication permissions.

## Offers and learning

For salary research, use current official labour statistics or other transparent compensation sources through the host. Compare only like location, role, level, currency, pay period and compensation basis. State sample/date limitations and keep base, bonuses, equity and benefits separate. Preserve unknowns and label contingent compensation. Use `salary-research` with optional job_id, role, level, location, currency, period (hour/month/year), compensation_basis, low, high and source as above.

Use `offer-record` with job_id, label, evidence, optional base (location/currency/period/low/high), bonus, equity, benefits, work_arrangement, conditions and deadline with offset. Show the offer_comparison rows as a side-by-side table, with unknown terms called out. Ask the candidate which factors matter and show differences against their preferences and comparable salary sources. Avoid invented valuations or currency conversions. Draft negotiation language from the actual terms and the candidate's requested changes. The candidate controls acceptance, decline and negotiation. Offer records and drafts grant no authority to contact anyone or bind the candidate.

For a learning plan, read gap_evidence from `interviews`. Group actual employer-stated skill reasons with saved job assessment gaps, keeping provenance distinct. Prioritize gaps across the candidate's target roles and avoid overgeneralizing one rejection. Save `skill-plan` steps with gap, practice, deliverable, success_check and target_date. Choose a feasible schedule and concrete evidence of progress. Employer silence is never a rejection reason.
