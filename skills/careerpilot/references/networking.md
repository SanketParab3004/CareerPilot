# Warm paths and referral sequences

Use `referrals` for the canonical connections, match evidence, boosts, sequence states
and cadence. The dashboard **Referrals** reads this view. Nothing scrapes connection
lists or sends referral messages automatically. Connections and evidence stay private.

## File-only connection import

`network-import`: explicit local `path`, `user_supplied: true`, and for a ZIP the exact
selected `member` ending in Connections.csv. Accept only a user-supplied LinkedIn
export or CSV. Never locate/import someone else's profile, retrieve connection lists,
extract cookies, or treat a public profile scrape as a connection import.

UTF-8 CSV supports Name or First Name/Last Name, URL/Profile URL, Company,
Position/Title, Schools and Former Employers (semicolon-separated). Standard LinkedIn
CSV notices preceding the header are supported. Optional history fields often are
absent from LinkedIn connection exports; keep them unknown, do not scrape to fill them.
Ask the user for an explicitly augmented CSV if needed. Names alone do not establish
that two people are identical. Profile URL is used for identity where supplied;
otherwise file/row identity avoids silently merging people. Re-importing an identical
file/member is idempotent. Files are limited to 25 MB, selected CSV to 10 MB/5000 rows;
unsafe ZIP paths and credential columns are rejected. Original selected evidence is
copied under private workspace imports/connections with hashes and row references.

## Evidence and confidence

Direct connections match the exported employer to the job's verified end-employer
or saved company. Stale/unverified employment gives a **possible** match. Explicit
recent verification (within 90 days) raises that employer match to confirmed. Shared
schools and former employers compare only supplied profile/export facts; they do not
prove friendship or overlapping employment. `former_colleague` needs the candidate's
actual confirmation; never infer it from shared nationality, name or location.

`network-relation`: `connection_id`, type former_colleague/direct_connection,
`candidate_confirmation`. `network-contact-verify`: `connection_id`, actual
`verified_at`, public `source_url`, `evidence`; optionally corrected `company`, `title`
or `profile_url`. Read the source using permitted host tools. No source reading is
performed by the helper. Verification history and original import evidence are kept.

Each path includes reason, source evidence and confidence. A candidate's own former
employer can flag a job without an identified contact; identify an actual connection
before creating a sequence. Similar company names are not silently treated as equal.
Do-not-contact connections are excluded from warm-path suggestions.

An optional +5 priority boost applies to unsubmitted warm-path jobs, separately from
base relevance/fit. It does not promise a referral or interview. Toggle **Warm-path
boost** in Referrals, or `network-config` with `config: {"warm_boost": false}`.
All saved jobs and the daily digest show the boost/evidence. Historical search lists
keep their original scores. Applied applications are not re-ranked for outreach.

## Timing, honest drafts and separate authorization

`network-sequence`: `job_id`, imported `connection_id`. It returns a sequence `id`,
timing, reason and evidence. Already applied → after applying. Deadline within 48
hours → apply first rather than delay for a referral. Otherwise ask about the referral
process before applying while time permits. Inspect the employer's referral policy
and actual deadline; do not invent a guaranteed process or let a draft delay a closing
application. An after-apply sequence cannot be sent until application confirmation.

`network-draft`: `sequence_id`, optional reviewed `body`. The default initial message
asks how referrals work and makes no claims of friendship, experience or entitlement.
A follow-up references only the recorded earlier sent message. Tailor using confirmed
candidate facts; do not invent shared history or imply a referral is already agreed.
Draft content is immutable: create a new draft if the recipient/content changes.

Before any host send, verify the exact professional recipient and current employer.
`network-authorize`: `message_id`, future timezone-aware `expires_at`, actual separate
`candidate_instruction` authorizing that exact recipient and text. Application grants
never cover outreach. `network-send-begin`: `message_id`, returned `authorization_id`.
It rechecks cadence/DNC/recipient and consumes this one-message grant. Only then may
the host perform the authorized send through permitted tools, subject to host approvals.

`network-sent`: `message_id`, actual `sent_at`, observed delivery `evidence`.
`network-uncertain`: `message_id`, evidence of ambiguity. Never retry an ambiguous send
or infer success from a timeout. `network-resolve` reconciles an in-flight/uncertain
message with result sent/not_sent and observed evidence (plus actual sent_at for sent).
Confirmed non-send cancels the old draft; a new draft and permission are required.
The helper does not contain a message transport.

## Cadence, replies and do-not-contact

`network-state`: `sequence_id`, status replied/referred/declined, actual `occurred_at`,
source `evidence`. Record only actual replies or confirmed referrals. Replies must not
predate the sent message. Referral and outreach activity feed Stage 2's dated touches;
analytics also show counts for sent, replied, referred, declined and uncertain sends.
These counts are not causal evidence or permission to contact anyone.

Default cadence: at least seven days between sends, at most two messages to the same
contact in 30 days across all job sequences. The view shows next_followup_at, its
timestamp evidence and any stop reason. A new draft still needs explicit permission.
`network-config` may set followup_days (minimum 3) and max_messages_30d (1–3).
Replies/referrals/declines stop follow-ups for that sequence. Closed applications or
applications already at interview/offer also stop referral outreach. An uncertain
send blocks other messages to that contact until reconciled.

`network-dnc`: `connection_id`, boolean `enabled`, actual `reason`. Declining adds
do-not-contact automatically. The dashboard can add/remove a restriction explicitly;
removal does not restart a stopped sequence or grant permission. Contact identities
share DNC/cadence where the imported profile URL establishes identity. Without a URL,
matching name+company is conservatively restricted; inspect identity before contact.

## Hiring-contact cards

Existing `contact-add` now records a stable ID, verification evidence and
last_verified_at, alongside source/profile/published-email URLs. `verified_at` and
`verification_evidence` may be supplied; otherwise current observation/relevance is
retained. Existing historical checked_at is preserved through migration.
`contact-verify`: `job_id`, `contact_id`, actual `verified_at`, `source_url`, `evidence`
appends verification history without inventing a different person. Cards display
the last verified date and evidence. Public hiring-contact research is separate from
connection-list import; it never authorizes scraping private connection lists.
