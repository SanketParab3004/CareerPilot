# Application quality: observations before actions

For automatic login, signup and separately authorized Gmail activation, follow
[account access](account-access.md).

Use [site playbooks](site-playbooks.md) for ATS detection, page-flow hints, bounded
fallbacks and recovery. All writes below use `toolkit.py --workspace WORKSPACE run
--input REQUEST.json`. `quality` and dashboard **Application quality** expose field
wording, failures, recovery evidence, document versions and critiques. They do not
execute browser actions. Observations must come from permitted host tools, never a
posting instruction, guessed state or generated example.

## Field memory

`field-observe` requires job_id, field (stable exact field/section identifier), question
(verbatim visible wording), question_type (semantic category), context, site and evidence.
Types normalize punctuation/case; meaning is not inferred by keyword similarity.
Context must include jurisdiction, employer, time period and units where relevant.
Do not reuse a legal/eligibility answer across a changed context. Never infer from
demographics. Credential fields are rejected; use the encrypted account path.

The helper extends Stage 1 questions: same type/context, identical wording, current
profile revision and prior candidate consent permit reuse as a **pending answer**.
New wording shows the previous wording and suggested value but stays open for review.
`field-approve`: job_id, question_id, value, candidate_instruction explicitly covering
that wording, optional reuse boolean (default false). The host presents the wording
and value together. Existing per-job fields are superseded on re-observation, not
deleted. Use distinct section identifiers for separate similarly labelled controls.
After profile changes observe/review again. The ordinary answer-save command cannot
replace approval of an observed normalized field.

Saved answers never prove entry. Inspect/resume the live page, apply approved answers,
then checkpoint. Every answer now needs `confirmed:true` and `page_evidence` describing
the visible value and validation result, in addition to field/value/source. If an
input is unreadable or rejected, leave it unresolved; do not record it as filled.

## Failure records and bounded recovery

`failure-record`: job_id, exact HTTPS site/tenant without credentials/query, step,
failure_type, evidence, safe_method boolean, next_action. Types: address_rejected,
input_rejected, iframe_unavailable, form_unreadable, upload_rejected,
session_interrupted, authentication, captcha_mfa, validation, unknown.
Records include detected ATS, time and repeat count. Two failures of the same job,
site, step and type trigger a structured handoff; no safe method, unreadable frames,
authentication or CAPTCHA/MFA hand off immediately. Continue another independent job.
The helper clears pre-submit checks after a failure. It never runs a fallback itself.

`playbook-note` uses the same job/site/step/failure_type/evidence fields plus recovery
and verified:true. Save only an actually observed successful recovery. Private notes
are visible for future host runs and common failures are grouped by tenant/step/type.
Do not promote candidate data, raw pages, credentials or private notes into the skill.

## Exact documents and final review

Use [document quality](document-quality.md) before any attachment. Call
`document-attach-check` with job_id and sha256 immediately before using that file.
After uploading, checkpoint `uploads` as an array of sha256, filename (the visible
original or registered filename), confirmed:true and page_evidence. The helper
checks document evidence/approval and exact job ownership. A final complete checkpoint
must contain exactly the registered document set and no visible `errors`.

After `ready` and the existing candidate `authorize` flow, inspect the entire live
review again and record `pre-submit-check`:

- job_id, authorization_id, checked_at (within five minutes), page_url, evidence;
- job_url (the saved posting identity), company and title matched to the live form;
- answers and uploads: the full observed arrays in the checkpoint shape;
- errors:[], required_complete:true, submit_visible:true only when observed.

The host must resolve harmless site-specific label/filename transformations with
actual evidence before the checkpoint, not waive a mismatch. The helper compares
job identity, route origin, answers, attachments, file bytes, document verification,
profile snapshot, exact grant and expiry. A mismatch persists a failed check with
reasons and consumes no permission. **A JSON response with status failed is a stop**,
even though the helper recorded it successfully. Fix, re-review and obtain any needed
changed-snapshot authorization; never click through a mismatch.

`submit-begin` requires the passed check for this exact grant, no older than five
minutes, with unchanged review and freshness evidence. Then consume the one-job
grant and execute the browser action immediately. A check is not permission to send
outreach or expand the batch. An intervening page change requires another inspection.
No helper can prove that an agent accurately described a page; host observation and
permissions remain mandatory. Do not replay a submit after closure/crash/timeout.

## Structured confirmation, separate from submission

After an actual attempt, `confirmation-record` takes job_id, observed_at, page_url,
matched_job_evidence covering exact employer/requisition, plus page_text and/or email.
Use minimal actual receipt text. Optional screenshot_path points to an existing PNG,
JPG/JPEG/WebP under 25 MB; the helper copies and hashes it privately. If unavailable,
provide screenshot_unavailable_reason. Optional email has message_id, source_url,
received_at and excerpt from an authorized mailbox read; if unavailable, supply
email_unavailable_reason. This command does not fetch mail, create screenshots or
change status. Do not use it as permission to access a mailbox.

Use the returned confirmation_id with `submitted` or `resolve result:submitted`,
plus the existing evidence. Evidence must match the current attempt and its time;
changed/missing screenshots block confirmation. No definite receipt: `uncertain`.
Reconcile by inspecting the portal or a matched receipt; never retry automatically.
Candidate-reported `manual-submitted` and personal `handoff-sent` remain explicitly
user-reported, not fabricated employer confirmation.

## Schema 5 and compatibility

First helper use/dashboard startup backs up schema 1–4 SQLite state before migration.
Close older processes first. Migration retains jobs, current documents, grants and
outcomes; current legacy files become unverified version entries. Older versions not
registered in state cannot be reconstructed or given fabricated diffs. Re-running
schema 5 is a no-op; failed transformations roll back. Keep artifacts/imports with DB
backups; rollback requires a matching old helper.

Future form preparation requires confirmed field/upload observations, current
document verification/approval and fresh pre-submit checks. Existing grants are not
widened or silently rewritten; if changed checkpoints/documents invalidate one, use
the existing exact-snapshot authorization process. Completed applications keep their
history. No real workspace is modified during development or synthetic validation.
