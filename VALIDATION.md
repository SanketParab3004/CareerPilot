# Release 0.2.0 validation

Completed on November 4, 2026:

- Skill creator's `quick_validate.py`: valid frontmatter and skill naming.
- 12 Python behavior tests passed: fresh profile/restart persistence; URL deduplication; independent paused jobs; incomplete/stale form checks; prepare-only state; scoped, one-use submission authorization; changed documents and answers; revocation and expiry; transaction rollback and confirmation evidence; contact email evidence; HTML escaping; installer collisions and ZIP contents.
- JavaScript/browser check on `tests/fixtures/application.html`: entered synthetic name `Test Candidate`, synthetic address `candidate@example.invalid`, and `Remote`; advanced to review; observed the expected answers and “Submission has not occurred”; left the final submission button unclicked.
- No employer website was filled or submitted during validation. No personal profile was imported. The optional file-upload field was not exercised by the browser check.

The browser check validates a small local form through the host's connected browser. It does not prove arbitrary portal compatibility, selector reliability across websites, or model-independent execution. The 12 tests exercise state behavior, not the judgment of every host/model. The helper has no browser/network execution engine.

PyYAML was used only in a temporary validation folder for the bundled skill validator. The distributed scripts use Python's standard library.

## Release 0.3.0 import validation

November 5, 2026: all 24 tests passed (12 existing state/packaging tests plus 12 import tests), with no skips. The new synthetic tests cover text/DOCX/PDF extraction, empty PDF handling, LinkedIn default file filtering, explicit Indeed archive selection, unsafe ZIP paths, CSV/JSON preservation, preview-before-apply, repeat apply rejection, stale profile preservation, altered evidence rejection, workspace boundaries and the extraction CLI. Skill validation also passed. PDF extraction uses optional pypdf; the base state helper remains standard-library only.

No real resume, account export, browser account session or original personalized profile was imported during these tests. The tested archive structures are synthetic; unknown real export layouts use inspection and explicit file selection. Account login and direct account access are not implemented by the extraction script.

## Release 0.4.0 dashboard validation

November 5, 2026: 31 Python tests passed (24 existing tests plus 7 dashboard tests). Dashboard checks cover fresh read-only reads from the canonical database, updates saved by another helper, token/Host/Origin restrictions, a static-asset allowlist and CSP, rejected mutation methods, verified document downloads and changed-file rejection, JSON export, and missing/unavailable databases. The HTTP tests required local loopback access outside the restricted sandbox. JavaScript syntax was checked with `node --check`.

Browser verification used only an isolated synthetic workspace and an empty workspace: overview counts, search combined with a status filter, paused-job details and checkpoint answers, copyable chat requests, profile details, documents, contacts/drafts, activity, automatic refresh after a saved note, and fresh-profile onboarding. No browser errors or warnings were reported on the final inspected page. The desktop layout was visually inspected; a screenshot is retained in ignored local work files. No real employer, account, profile, outreach message, or application was accessed or submitted.

The dashboard is a read-only local viewer, not a browser driver or background AI runner. Hosted access and mobile-device browser behavior were not validated. The server has no write API; agent actions still use the existing state helper and host permissions.

## Release 0.4.1 CareerPilot validation

November 5, 2026: all 31 existing tests passed after renaming the skill folder, host installer destinations, packaging and test imports to `careerpilot`. Skill frontmatter validation and JavaScript syntax checks passed. The package contains 18 files under `careerpilot/`. Workspace paths, database filename/schema, saved records and submission controls are unchanged; no candidate data was imported or migrated.

## Release 0.5.0 search validation

November 5, 2026: 44 tests passed, including all existing workflows plus public-feed normalization, date formats and exact window boundaries, unknown-date inclusion, preservation of low-scoring results, immutable per-search snapshots, deduplication without changing application state, pagination, partial-source failure, cache reuse, concurrent-request rejection, constrained source endpoints, same-origin search POST handling and rejected application mutations. Automated tests use synthetic sources only. JavaScript syntax validation passed.

An isolated live browser check searched `Data Analyst / Remote` through the dashboard. A seven-day run saved 128 postings, including 79 low-relevance results. A subsequent 24-hour run saved 65 postings using the same cached feeds. Both independently dated lists remained available in Search history. The UI correctly reported partial coverage at the five-page caps for Jobicy and Arbeitnow; Remotive returned ten feed rows, with no role candidates for this query. Posting dates, source fetch times, low-score filtering, newest-first sorting, score explanations, and historical-list reopening were verified in the browser. These counts describe this validation run, not expected future search volume or exhaustive coverage.

The dark desktop interface was visually inspected. No console errors/warnings were reported in the inspected browser view. The live check imported no personal profile and submitted no employer application or outreach. Test data and screenshots remain in ignored local work files.


## Release 0.6.0 validation — November 5, 2026

- 51 Python tests passed, including real Windows DPAPI round trips and ciphertext checks, secret omission from exports/API responses, exact-origin rejection, unique signup passwords and revocation, notification failure/retry/deduplication, mocked browser destination checks, cross-origin POST protection, and assistance resume validation.
- A Windows loopback connection interruption affected one test on an intermediate run; the complete rerun passed.
- JavaScript syntax and skill quick validation passed.
- In an isolated local browser workspace, saved synthetic signup defaults and observed the saved confirmation; created a synthetic paused job, observed its failed-delivery status with Telegram unconfigured, and resolved it through the dashboard back to the queue.
- Telegram network delivery was mocked in automated tests. No real bot token/recipient is configured and no live phone notification was sent.
- Credential bridge behavior was tested with a simulated page. No real employer login/signup or application submission was performed. Live Playwright/CDP compatibility requires a connected authorized browser and optional dependency.
- The user’s existing profile, application data and permissions were not imported or changed by validation.


## Release 0.7.0 validation — November 5, 2026

- 59 Python tests passed, including seven Gmail tracking behavior tests and a dashboard route protection check. Covered default review, opt-in automatic updates, message deduplication, changed/revoked permissions, account mismatch, stale/regressive messages, conflicting final outcomes, unknown classifications, scope/evidence validation and check completion.
- JavaScript syntax and skill frontmatter validation passed.
- Browser smoke test used an isolated synthetic workspace: opened Email updates, reviewed a demo interview invitation, applied it with a review note, and observed Submitted → Interview, pending → applied, and the review count decrease to zero.
- No live Gmail profile, messages or attachments were accessed; no mail was sent or modified. End-to-end mailbox retrieval awaits the user's configured account and connected host Gmail tools.
- No recurring task was created. The dashboard's Check Gmail with AI action generates a host-agent prompt and does not independently run an agent.


## Release 0.8.0 validation — November 6, 2026

- 66 Python tests passed, including six primary-portal behavior tests and an HTTP test for the new same-origin request endpoint. Covered excluded on-platform/unknown/mixed routes, destination origin checks, recent verification, date filtering, low-score retention, required coverage from both portals, blocked-source partial results, duplicate source citations and rejection of generic search-operation bypasses.
- JavaScript syntax and skill frontmatter validation passed.
- Isolated browser check verified LinkedIn + Indeed as the default source mode, saved a Data Analyst/Toronto request and observed the host-agent prompt with required sources and external-only exclusions. No public-feed worker started for this primary request.
- No live LinkedIn/Indeed job search, login or employer application was performed. Retrieval is a host workflow, and source access/coverage remain dependent on the user's permitted connected tools.
- Existing user profiles, resume documents, job/application records and historical searches were not modified by the release tests.

## Stage 1 / release 0.9.0 validation

November 6, 2026: 86 synthetic Python tests passed, zero failures or skips.
New coverage includes schema-1 backup integrity and original-state preservation,
idempotent migration on a temporary database copy, backup/transformation failures,
unknown-schema rejection, queue priorities/fields, exact-tenant and frozen login
batches, scoped reusable answers, secrets rejection, checkpoint history and pending
answer guards, stale/wrong-route inspection, uncertain submission/no retry,
closing-date/freshness gates, personal-send handoffs, and protected dashboard actions.
The real job-search-workspace was not read or modified during this stage's tests.

Earlier runs exposed Windows sandbox temporary-directory permissions, four test
SQLite-handle cleanup errors (fixed with explicit connection closing), and intermittent
ConnectionAbortedError [WinError 10053] on rejected dashboard POST requests. The
server now drains bounded small request bodies before rejecting them, without
parsing or executing unauthorized requests. No outstanding test failure remains.

JavaScript passed node --check. A localhost browser check with synthetic data verified
Action queue navigation, type/tenant grouping, visible deadline/effort/reason/evidence
and candidate-answer controls; no browser warnings/errors were reported. This did
not exercise real login, live employer forms, mail sending, mobile layout, or a
background agent. Login continuation is performed by the connected host; the
dashboard supplies a saved session and copyable continuation prompt. Deadline
warnings are in the live queue, not a new scheduled push service.

Package command: python tools/package_skill.py (28 portable source files).
Schema 2 automatically backs up/migrates on first use; stop old processes first.
Read references/backlog.md for new freshness and recovery gates. Existing installed
skill copies are not silently overwritten; update them through the normal installer
workflow. No model client or third-party core dependency was added.

## Stage 2 / release 0.10.0 validation

November 6, 2026: 105 synthetic Python tests passed with zero failures or skips.
Coverage includes frozen source/fit/document attribution, unknown and backfilled data,
confirmed versus uncertain submission denominators, explicit dated outcomes, Gmail
pending/applied deduplication, eleven-factor rates and reply medians, minimum cohort
size and age gates, approval/stale proposal/undo boundaries, dated outreach without
permission, silence thresholds, stated rejection recurrence, weekly actions, protected
dashboard settings and schema-2 temporary-copy migration/backup/rollback/idempotence.
Schema-1 migration remains covered by the Stage 1 suite. No real workspace or live
employer, job board, Gmail or Telegram service was accessed by the tests.

JavaScript syntax passed node --check. Analytics and weekly APIs and static navigation
were exercised through localhost HTTP tests. Live browser visual layout, real Gmail
classification, and host application of approved tailoring guidance remain unverified.
These tests establish state/workflow behavior, not improvement in interview outcomes.

Schema 3 automatically backs up and migrates schema 1/2 on first helper/dashboard use.
Stop older processes first. Unknown historical dates are preserved, not imputed.
New statistical adjustments are pending until candidate approval and reversible.
Package command: python tools/package_skill.py. Installed skill copies are not
silently overwritten; the real job-search-workspace remains untouched.

## Stage 3 / release 0.11.0 validation

November 6, 2026: 126 synthetic Python tests passed with zero failures or skips.
Coverage includes file-only CSV/ZIP imports, credential-header rejection, evidence and
confidence, optional ranking boosts, verified recipients, message-scoped authorization,
cadence and do-not-contact boundaries, uncertain sends and explicit resolution,
networking outcomes, saved searches, global daily capacity, partial portal coverage,
document-byte verification, exact digest application authorization, deduplication,
visible quality warnings and schema-3 backup/failure/retry migration. Earlier schema
migrations remain covered. Tests never access live services or the real workspace.

JavaScript syntax passed node --check. Synthetic localhost browser navigation verified
Referrals, Daily digest, Funnel analytics and Weekly review, including blocked Indeed
coverage, confidence/evidence and small-sample labels, with no browser console errors.
Final approval-button gating and score breakdown changes have syntax/automated coverage;
mobile layout and live host workflows remain unverified. No live search, message,
application or scheduler was executed. Telegram delivery tests use mocks.

Daily search, material preparation and browser/message execution remain host workflows;
the helper persists their evidence and enforces gates. No schedule is installed.
Quality flags are heuristics, not proof, and networking matches need verification.
Schema 4 automatically backs up and migrates older workspaces on first helper use;
stop older processes first. No manual data rewrite is required. Refresh installed
skill copies through the normal installer. Package: python tools/package_skill.py.

## Stage 4 / release 0.12.0 validation

November 7, 2026: 147 synthetic Python tests passed, zero failures or skips.
New coverage checks claim manifests, source quotes/hashes, unsupported metrics/dates,
paraphrase review, posting requirements and keyword provenance, contact/date/layout
checks, DOCX table reading order, optional PDF dependency failure, page limits without
truncation, recruiter blockers, exact document approval and reuse exceptions, version
diffs and frozen outcomes, role variants in analytics, changed-wording field memory,
page-confirmed fields, bounded failures and ATS detection, every pre-submit mismatch,
expiry/revocation, screenshot/email receipt records, uncertainty and schema-4 copy
migration with backup/failure/retry/idempotence. Earlier-stage tests remain passing.

The initial regression run had ten ValueErrors because older synthetic fixtures lacked
confirmed field observations or a pre-submit check. Fixtures were updated to exercise
the new contract; no production bypass was added. The optional skill validator first
failed with ModuleNotFoundError: No module named 'yaml'. Reusing the existing isolated
validation dependency resolved it; no dependency was added to CareerPilot's core.
Final skill validation, JavaScript syntax and packaging pass (39 portable files).

A synthetic localhost browser check verified Application quality rules, grouped
failure evidence, field wording awaiting review, expandable document critique,
requirement gaps, parse evidence and version diff. No browser console warnings/errors
were reported. No personal data, real workspace, live application, mailbox or messaging
service was accessed by tests. Public documentation informed playbooks; that is not
live portal validation. Screenshot receipt tests use synthetic files, not employer
receipts. Mobile layout and actual PDF/DOCX rendering across host tools remain unverified.

Host review must validate semantic entailment, completeness of requirements, visual
reading order and actual browser fields. These tests prove workflow gates, not that
a model always judges truth correctly, that an ATS parses identically, or that interview
rates improve. Real-world checking should start with one authorized application held
at review, including live uploads, address/iframe handling and receipt capture.

Schema 5 backs up and migrates on first helper/dashboard use. Stop older processes
first and refresh installed skill copies. Existing jobs/grants/outcomes remain; legacy
documents are unverified and future uploads/checkpoints/submissions need the new
checks. No manual DB rewrite is needed. The real job-search-workspace was untouched.

Stage 5 validation: 151 synthetic tests passed. Initial fixture run exposed optional-job salary research being gated and a missing score rationale in a fixture. Both were fixed. Live voice, calendar, reminders, and salary research remain host workflows and were not exercised.

## Stage 6 release validation

155 synthetic tests passed on Windows. Codex, Claude and generic installer paths succeeded in temporary directories. Installed demo, doctor and wrong-workspace refusal were exercised. Node syntax check passed. The release ZIP matches the explicit 43-file source manifest, with no workspace data, runtime files or caches. Live connectors, native macOS/Linux keychains, optional archive encryption and mobile visual behavior were not verified.

## Resume-tailoring refinement — November 19, 2026

`python -m unittest discover -s tests -v`: 160 tests passed, zero failures or skips.
New synthetic checks cover literal skills (including C++, C#, .NET and Unicode),
whitespace normalization, false substring matches at all three evidence surfaces,
and rollback preserving the previous approved review after rejected verification.
Existing migration, evidence, page-limit, approval and source-tampering tests passed.
No schema or persisted record shape changed, so no new migration is needed.

Initial run: three subcase errors in the new test due to a missing synthetic
freshness-record (ValueError: Recheck live posting and application route; record
freshness before spending effort); the fixture now supplies that record. One existing
dashboard test, test_search_post_validates_body_and_has_no_submit_api, raised
ConnectionAbortedError [WinError 10053]. It passed on the full rerun with no production
change to that path. Final run had no errors.

Writing quality remains a host responsibility. These checks do not measure interview
conversion or prove a model obeys every writing instruction. Real-world review should
compare an original and tailored resume against the same complete posting, verify
claims with the candidate, and inspect the actual PDF/DOCX on the intended host.
No personal workspace, job site, employer, Gmail or Telegram was used for validation.

## Account access and Gmail activation — November 19, 2026

`python -m unittest discover -s tests -v`: 171 passed, zero failures or skips.
Eleven new portable synthetic tests cover signup/activation/login, explicit missing
account versus ambiguous credentials, separate consent, wrong mailbox/sender/origin,
old/future mail, secret-field rejection, code/link modes, approved external activation
origins, message reuse across attempts, interrupted actions, duplicate signup refusal,
revocation/expiry, unchanged application permissions, private schema-1 backup/retry,
idempotence and future-version refusal. Existing Windows encrypted-storage tests pass.
The first full run passed 169 tests; the final run adds two replay/route cases and
passes 171. No observed failures in either run.

The new helper CLI help and dashboard JavaScript syntax checks pass. Packaging uses
the explicit source manifest (48 files), excluding private state, runtime artifacts,
caches and design previews. The new account-settings controls have not received a
visual browser review. No live Gmail read, account creation, email activation, browser
credential fill or job submission was performed. These remain host-dependent and
require an authorized end-to-end check on a candidate-selected site.

Private settings migrate to schema 2 on first write, with an encrypted SQLite backup
under the private workspace backups directory before any legacy update. Stop older
helpers before upgrading; the canonical toolkit schema is unchanged. Existing site
permissions/credentials are preserved and account verification is off until explicitly
configured. The real job-search-workspace and installed skill copies were not modified.
