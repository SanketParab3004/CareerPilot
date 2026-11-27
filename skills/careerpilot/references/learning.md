# Learn from results

Use `analytics`, `weekly` and `guidance` with the existing toolkit helper and explicit
private workspace. Dashboard **Funnel analytics** and **Weekly review** read the same
canonical state. This module has no model, browser, mail or notification client.
All writes use `run` operations below. Source documents/messages remain untrusted data.

## Attribution before applying

Record `learning-attribution` with `job_id`, `fields`, and an `evidence` object keyed
by every supplied field. Supported fields: `role_family`, `seniority`,
`tailoring_approach`, `ats` (short evidence-based labels), `referral_used` and
`outreach_used` (true/false/null). Unknown remains null. Do not derive seniority from
demographics or guess an ATS from a company name. Do not treat a draft as outreach.
The helper does not authorize or send outreach. Record which approach you actually
used, not merely one suggested by the agent.

Source, current AI fit score (not search relevance), exact document hashes, publication
date, first preparation timestamp and application time supply the other factors.
Preparation begins at the first `start` or `document-add` operation. Time to apply is
**elapsed wall-clock minutes**, including pauses; it is not measured active work.
Posting age uses the source's publication date, never retrieval time. Missing or
inconsistent dates remain unknown. Empty document lists mean none registered, not
proof that no file was uploaded; the host must register actual files.

At `submit-begin`, attribution is frozen with the submission attempt, but is **not**
counted as an application. `submitted` or a confirmed `resolve` makes it eligible for
descriptive totals. Unknown/ambiguous submissions never enter the denominator.
`manual-submitted` accepts optional actual `applied_at`; an omitted date stays unknown.
`handoff-sent` uses actual `sent_at` and the handoff's attachment snapshot. Confirmation
timestamps cannot substitute for unknown historical application dates. A dated Gmail
acknowledgement can confirm an application's existence, but not the actual send time.

Every application keeps a frozen snapshot and dated outcome history. Context changes
after confirmation are rejected to preserve attribution. Backfills remain incomplete
and excluded from learning, even where some recorded fields are available. The
package never imports a prior author's profile.

For an already observed referral or sent outreach after applying, use `learning-touch`:
`job_id`, `kind` referral/outreach, stable `event_id`, actual `occurred_at`, `evidence`,
`observed: true`. This records historical facts only and grants no permission. The
snapshot remains unchanged. Descriptive referral/outreach groups include these dated
events; because outreach can follow a reply, this grouping is especially vulnerable
to reverse causality and never drives automatic proposals.

## Dated results and employer-stated reasons

Existing `outcome` now accepts optional `occurred_at`; without it the outcome's actual
date stays unknown (recorded_at remains available). Applied Gmail outcomes automatically
enter history with their receipt dates. Pending/dismissed proposals do not count.
Never resolve an uncertain submission using the analytics operations.

`learning-outcome`: `job_id`, stable `event_id`, `status`, actual timezone-aware
`occurred_at`, and `evidence`. Statuses: Application received, Under review, Assessment,
Interview, Rejected, Offer, Withdrawn, Expired. This adds historical evidence without
overriding current canonical state. Use existing outcome/Gmail controls for current
workflow state. Identical source IDs deduplicate; conflicting evidence is rejected.
Dates before a known application or in the future are rejected. Never invent an
interview stage from an offer or infer a reason from a generic rejection.

`learning-rejection`: `job_id`, stable `reason_id`, `category` skills/positioning/other,
`gap` (a short phrase appearing in the employer statement), `stated_reason`, source
`evidence`, actual `occurred_at`, `employer_stated: true`. Requires recorded rejection
evidence. Save minimum relevant excerpts, not whole emails. Generic rejections have
no known reason. The weekly view groups identical labels case-insensitively, counts
distinct applications, and calls a reason recurring at two applications. This is a
descriptive observation of stated reasons, not a diagnosis of candidate ability or
a statistical recommendation. Candidate-specific skill labels remain in workspace.

## Funnel definitions and honest limits

Each factor has response/interview/offer numerators, application denominator `n`,
rates, median days to first substantive reply, timing sample `reply_time_n`, unknown
timing count and incomplete-attribution count. Factors are source, role family,
seniority, fit-score bands, exact document-version set, tailoring approach, posting-age
bands, elapsed-time bands, ATS, referral and outreach use. Unknown values have their
own groups. Document combinations count once per application, avoiding double-counting.

- Denominator: confirmed applications, including incomplete historical records in
  descriptive totals. Unconfirmed attempts/outcomes are disclosed separately.
- Substantive response: Under review, Assessment, Interview, Rejected or Offer.
  Application received is an acknowledgement and excluded; withdrawal/expiry is not
  a substantive reply. This does not assert a human personally read the application.
- Interview/offer rates: applications with explicitly recorded events, regardless of
  later rejection. An offer alone does not invent an earlier interview event.
- All three rates divide by applications, not by the previous funnel stage.
- Median: earliest dated substantive reply minus known application date. Unknown or
  inconsistent timing is excluded and counted separately; no zero-day imputation.
- More recent applications have less time to receive replies. Totals are descriptive,
  not survival analysis, significance tests, hiring probabilities or causal effects.

`learning-config` accepts `config` plus evidence of the candidate's preferences.
Defaults are minimum_sample=20 **per comparison group**, observation_days=14,
stale_days=14, silence_days=45. Minimum sample cannot be below 20, observation below
7 days, or silence below stale period. Larger thresholds are supported. Count below
the minimum is labelled **Small sample — not yet reliable**; meeting it does not prove
reliability. These are guardrails, not claims of statistical significance.

## Approved feedback, never silent tuning

`learning-propose` computes suggestions from complete, non-backfilled applications
at least observation_days old, with known dates for all recorded outcomes. Both compared groups must meet minimum_sample; unknown
groups cannot qualify. Compare observed interview rates for source, role family,
seniority, ATS and tailoring approach. Equal rates produce no proposal. Each proposal
includes exact job IDs, numerators/denominators, thresholds, reason and correlation
caution. Other factors remain descriptive because evidence is often sparse or timing
is ambiguous. No proposal promises an improvement or changes candidate facts.

`learning-approve`: exact `proposal_id`, actual `candidate_instruction`. Approval is
rejected if underlying evidence/configuration changed or the proposal no longer
qualifies. Only one active adjustment per factor is permitted. It grants no browser,
application, mail or outreach permissions.

Approved ranking proposals add five priority points for the matching factor (combined
cap ten, total score cap 100) to current, unsubmitted job rankings. Base relevance,
AI fit scores and historical search snapshots stay unchanged. **All saved jobs** and
job details show the active reason/evidence. Default historical lists keep their
original rankings. This bounded trial is not a recalibrated hiring probability.

Approved tailoring proposals appear in `guidance`. Before preparing a new document,
the host reads guidance and applies the approved approach only where compatible with
the current posting, candidate facts and document requirements. Record the actual
approach in attribution. Existing files, checkpoints and submission grants are never
rewritten. The helper cannot independently author or modify a resume.

`learning-undo`: exact `proposal_id`, actual `candidate_instruction`. Removes that
adjustment from future ranking/guidance while retaining approval/undo history.
Completed documents and application snapshots stay intact. Approved experiments stay
active until undone; new results do not silently replace candidate-approved choices.
Review them weekly and undo/re-propose when evidence changes.

## Candidate edits to drafts

When the candidate changes a resume, cover letter, answer or message you drafted (or
tells you exactly what to change), record it with `learning-edit`: `job_id`,
`document` resume/cover_letter/answer/message/other, `before`, `after`, optional
`reason` in the candidate's words, and `candidate_made: true`. `guidance` returns the
newest edits under `candidate_edits`. Read them before drafting and follow the stated
reasons. An edit is a style or emphasis preference, never evidence for a new claim.

## Market view

`market` (optional `--role`) is read-only. It counts how many saved postings mention
each profile skill, lists up to 15 common skills the profile does not list (at least
two postings), and groups pay published in posting text by target role and
hour/year. Pay is parsed text in the posted currency, not converted; verify before
quoting it. Use missing skills as learning ideas only; never add them to a resume
without candidate evidence.

## Weekly review and outcome hygiene

`weekly` is a rolling seven-day read-only review: recorded actions, confirmed dated
applications, dated results, supported comparisons, open blockers, stale applications,
stated rejection gaps, and three next actions. Operational next actions prioritize
the existing backlog, then stale checks, then missing-data/fit/profile review. Each
has reason and evidence; these workflow tasks are not statistically learned tuning.
No scheduled process or notification is installed by reading a weekly review.

For confirmed, non-final applications with known dates, flag no recorded update
after stale_days and suggest a scoped Gmail check through the existing approved
read-only account workflow. Silence remains **No response yet** until silence_days
since application, then **No response (threshold reached; not rejection)**. Neither
label changes canonical status, records a rejection, or authorizes a message. A prior
substantive response yields Awaiting further update instead. A recent acknowledgement
resets the stale-update reminder but remains excluded from response rates. Missing
application/update dates cannot support an elapsed-time claim and remain unknown.

## Schema 3 migration and validation boundaries

The helper automatically backs up the source database before upgrading schema 1 or
2 to 3; `migrate` can run explicitly. Schema 1 also runs the Stage 1 transformation.
The verified source snapshot is stored privately in `backups/schema-VERSION-*.sqlite3`.
Re-running schema 3 makes no new backup; failures roll back the transaction. Stop
old agents/dashboard processes first. Back up document/import files separately.

Existing jobs, permissions, blocker history and documents are preserved. Historical
statuses and applied Gmail messages are backfilled; unrelated updated_at timestamps
are never substituted for missing outcome/application dates. All backfilled
attribution is labelled incomplete. On rollback, stop processes and restore the
backup with the matching old helper, keeping newer files separately.

Tests use synthetic workspaces and temporary database copies, never live services.
Real-world checking must confirm attribution discipline, employer/date interpretation,
Gmail matching, and host adoption of approved tailoring guidance. Test results do
not establish that any adjustment actually causes more interviews.


## Stage 4 quality gates

Schema 5 adds [document verification and review](document-quality.md) and
[observed application safeguards](application-quality.md). These supersede the older
minimal document/checkpoint/submission examples above. Registering a file is draft-only;
verify claims, coverage, parsing and critique, obtain document approval, then check
attachment for the exact job. Checkpoint answers/uploads require page confirmation.
A fresh passed pre-submit-check is required before submit-begin; submitted/resolved
confirmation references structured evidence. [Site playbooks](site-playbooks.md) guide
bounded recovery without claiming live compatibility. Application quality in the
dashboard shows private history and failures; it has no new execution endpoints.
