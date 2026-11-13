# Daily top five workflow

One-step manual request to a tool-enabled host:

> Run CareerPilot's daily top five using my saved search profile PROFILE_ID.

The host completes the workflow below in the current session. **Run daily workflow**
in the dashboard saves the run and provides a copyable host prompt; the dashboard
does not launch an AI agent. If browser/search/document tools are unavailable, record
blocked/partial progress honestly. No model API client or scheduler is bundled.

## Saved profiles and capacity

`daily-profile-save`: `name`, `role`, `location`, optional `posted_within` any/1/7/30,
`include_unknown_dates`, capacity 1–5, `rules`; optional existing `profile_id` updates
the profile. Rules may include locations (list), eligibility (explicit candidate
requirements), minimum_salary plus currency and period. Do not derive eligibility
from name, nationality, demographics or where the person lives. Unknown stays unknown.
Runs snapshot the profile; later edits never silently expand a running search.

`daily-config` sets global `capacity` 1–5; default five preparations per **UTC day**
across all daily runs, with each saved profile's smaller limit respected. A preparation
claim consumes capacity even if later blocked; never retry to evade the quality cap.
Candidate-directed work outside daily runs remains a separate workflow.

## Host execution contract (manual or authorized scheduler)

1. `daily-start` with profile_id. Resume an unfinished same-profile run for today
   instead of duplicating it. Use returned run id/search_id and frozen profile.
2. Execute the existing primary-portal workflow: LinkedIn AND Indeed, permitted host
   tools only, external routes only. Never scrape connections. Preserve source dates,
   source URL, verified employer route and optional evidenced identity below. Record
   coverage for both portals, even blocked/failed, then portal-search-finish.
3. Record applicable identity and quality facts; inspect candidate rules and warm-path
   evidence. `daily-build` freezes the top five or remaining capacity using current
   explained relevance, approved Stage 2 adjustments and optional warm-path boost.
   Previously applied/uncertain, skipped, snoozed and over-capacity jobs stay in the
   pipeline and an explicit digest audit; none is silently deleted. Quality concerns
   are visible flags, never hidden filters. A partial source run remains partial.
4. For each selected item, recheck live posting/route with freshness-record. Call
   `daily-prepare-begin` with run_id/job_id and review_evidence when quality flags exist.
   This atomically claims capacity. Read approved tailoring guidance, evaluate actual
   fit, select the job, prepare/register real materials using confirmed facts only.
   Follow the existing browser workflow if asked to fill; never submit implicitly.
5. `daily-prepared`: run_id, job_id, status prepared/blocked and actual evidence.
   Prepared requires registered documents and an evidenced fit evaluation; it does
   not assert that an employer form is reviewed or submitted. For a blocked job,
   the helper also creates an action-queue blocker; supply blocker_type and next_action
   when known, then continue the other capacity-claimed jobs.
6. `daily-publish` after every item is prepared, explicitly blocked, skipped or snoozed.
   The dashboard digest shows source coverage, materials state, scores/boosts, flags
   and audit reasons. Fewer than five is valid; never invent jobs or material completion.
7. Optional `daily-notify` with run_id and the candidate's actual delivery instruction
   sends a Telegram digest notice through existing encrypted Telegram settings. Only
   generated run ID, count and coverage label leave the machine. Full job details and
   decisions remain in the dashboard, reachable via the user's own remote access.
   No delivery is attempted without opt-in. Ambiguous failure is marked uncertain
   and never auto-retried. Dashboard publication alone needs no Telegram service.

A scheduler must invoke this entire host workflow with exact workspace/profile and
an explicitly approved cadence, tool access and delivery preference. Read host-specific
setup in hosts.md. Never install or claim a schedule from a feature request. Without
a scheduler, the one-step manual host request works; it is not a standalone CLI web
crawler. `daily-start` alone records pending work and does not claim searches ran.

## Digest decisions and submission boundaries

`daily-decision`: exact run_id/job_id, decision approve/skip/snooze and actual
candidate_instruction. Approve additionally requires a future timezone-aware
expires_at and invokes existing **authorize** for exactly that job. Only a current
ready, reviewed application passes; a prepared resume is insufficient. If the form
is not reviewed yet, finish it through the host and obtain approval for the actual
snapshot. Do not invent an expiry or infer permission from opening a digest.

Approval records intent only. Before any actual authorized click, submit-begin must
consume the correct grant; record observed confirmation or Submission uncertain.
No digest endpoint clicks Submit. Outreach still requires separate message approval.
Skip records a persistent exclusion from future daily picks; snooze requires a future
timezone-aware until. Both keep the job visible. A later explicit digest decision
can replace a prior decision; never infer an unskip from renewed discovery.

## Deduplication and repeat-application warnings

Existing URL normalization remains. `job-add` may additionally carry `identity` with
employer (actual end-employer), requisition_id, employer_domain and evidence.
`job-identity` attaches that object to an existing job. Use a verified employer domain,
not a shared generic ATS or staffing agency domain. Exact employer/domain/requisition
matches across URLs merge into the existing canonical job, retaining source/title/URL
observations as aliases and preserving application state. Existing portal citation
tracking keeps both LinkedIn and Indeed references.

Similar normalized employer/title pairs, renamed roles, old postings and similar
agency jobs produce **possible** duplicate/repost warnings, not destructive merges.
Known end-employer identity helps detect agency duplicates; unknown clients remain
unknown. A confirmed application to the same employer and similar role produces a
repeat-application warning. Review requisition and scope rather than applying twice.

## Quality flags without hidden jobs

`job-quality`: job_id, `facts` and `signals`. Facts: agency, eligibility object, salary
object (maximum/currency/period), plus source evidence. Signals are objects with kind,
confidence possible/confirmed, reason and evidence. Kinds: scam, ghost, evergreen,
repost, staffing_duplicate, eligibility, salary, location. Record actual source
excerpts, never external instructions or speculative certainty.

The helper also flags explicit payment-request phrases as possible scam concerns,
standing talent-pool wording, postings older than 60 days for availability recheck,
similar roles and repeat applications. Age alone does not prove a ghost posting.
Rules compare explicitly supplied salary/currency/period, location and eligibility;
unknown or incompatible units stay unknown rather than being converted or guessed.
All flags show reasons/evidence in the digest and job detail. They never delete a
listing. Eligibility conflicts require candidate/source review, not demographic inference.

## Schema 4

Helper reads/mutations/dashboard startup back up the source database before upgrading
schema 1/2/3 to 4. Older-stage transformations run in sequence when needed. A verified
private SQLite backup precedes changes; transactions roll back failure, and rerunning
schema 4 is a no-op. Stop older processes first. Stage 2 attribution/approvals and all
submission grants remain intact. Existing contact checked_at becomes last_verified_at;
no connections, messages or candidate profile are imported by migration. Back up
artifacts/imports separately; restore with a matching old helper if rolling back.


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
