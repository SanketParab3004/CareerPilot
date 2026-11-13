# Stage 4 audit and plan

Audit: ATS playbooks Missing; normalized field memory Partial (exact question/context
reuse exists); failure logging Partial (blockers); field fallback guidance Partial;
pre-submit comparison Partial (snapshot/hash/expiry gates); confirmation evidence
Partial (text); claim verification and tailoring checks Partial (instructions only);
parse test Partial (import extraction); exact-job attachment guard Partial (registration
per job); document rules Missing; version diffs Partial (hashes retained on disk);
positioning variants Missing; recruiter review Partial (instructions).

Implement schema 5 with backup-first migration preserving records and grants. Add
document quality/version records and explicit approval, profile/source-backed claims,
requirement mapping, final-file extraction/visual checks, rules and truthful variants.
Add application quality records for normalized answer review, observed fields/uploads,
failures and fresh pre-submit checks against existing grants. Add portable ATS guidance,
read-only quality views, analytics variant attribution, synthetic tests and docs.

Decisions: no page limit by default; never truncate. Extract text with standard-library
DOCX/TXT/MD support and optional pypdf, with explicit errors for unsupported formats.
Semantic claim entailment and visual layout remain evidenced host reviews, never a
claim that a hash proves truth. Changed wording always needs candidate review before
reuse. Site patterns are hints, never selectors or authorization. No live applications.

Completed: all fourteen requested features have helper enforcement and/or portable
host procedures appropriate to the capability. 147 synthetic tests, skill validation,
JavaScript syntax and packaging pass. Synthetic dashboard navigation verified the
new evidence view. See VALIDATION.md for limits of semantic/visual and live-site checks.
