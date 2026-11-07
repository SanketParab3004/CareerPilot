# Discovery and fit ranking

Use the user's target role, location/work arrangement, experience level and deal-breakers. Preserve the source URL, source name, retrieved date, complete available description, and external job identifier when present.

## Required primary sources and application type

**Search LinkedIn and Indeed for every primary discovery run.** Follow [primary portal searches](portal-search.md) to create a dated list, record source outcomes, and import verified external-application postings. The user's filter excludes LinkedIn Easy Apply and Indeed Apply / Easily apply / Apply with Indeed. A listing offering on-platform application is excluded even if an external link also exists. Unknown application routes remain excluded until inspected.

Use allowed host browser/retrieval tools, authorized source connectors, or user-provided posting evidence. If a portal needs login, CAPTCHA or unavailable access, mark that source blocked/partial. Do not replace it silently with employer sites or public feeds, and do not claim complete coverage. Do not invent an official API or use cookie extraction, CAPTCHA bypasses or unapproved scraping services. Current tool/platform access rules still apply.

The dashboard defaults to a **LinkedIn + Indeed** request with role, location and posting-date filters. It saves the request and supplies a host-agent prompt; it does not scrape those portals directly. The existing Remotive/Jobicy/Arbeitnow fetcher is an explicitly selected supplementary search, with separate unverified results. It does not fulfill required primary coverage. Never describe a public-feed-only list as a LinkedIn/Indeed search.

Rank every qualifying external posting, including low matches, and retain source posting dates. Source verification and application-route filtering are independent of fit score. A search's automatic word/location score remains separate from the AI fit assessment below. Do not overwrite historical list snapshots when adding AI evaluations.

Deduplicate before ranking. The helper removes common tracking parameters and fragments for URL identity, but different URLs may represent the same role. Compare employer, title, location and requisition number before adding another posting. Preserve the original URL for navigation. Expired/dead postings should be marked `Expired`; never silently replace their text with an unrelated opening.

For each role, assess required skills, experience, location/work arrangement, career relevance and user deal-breakers. Separate mandatory requirements from preferences. Distinguish unknown eligibility from a confirmed mismatch. Record strengths, gaps, unknowns, recommendation and evidence excerpts with `evaluate`. An optional 0–100 score must include its rationale; it is a comparison aid, not a hiring probability. Do not present simple keyword overlap as AI fit.

Return a compact shortlist with source links. Selecting a job for preparation is recorded with `select`; searching/ranking alone does not put jobs into the application queue. Selection can follow the user's explicit batch instructions without asking again.

## Stage 1 backlog integration

Follow [backlog and recovery](backlog.md) for the schema-2 action queue, exact-tenant login sessions, batched candidate answers, recovery gates, deadline/freshness records and candidate-sent application drafts. Save a live `freshness-record` before tailoring or form work. `resume` now schedules live inspection; it does not establish that the form is safe. The dashboard Action queue groups by type or site, accepts candidate answers and login completion, shows handoff drafts, and records candidate-reported sending. It never executes application submissions or sends email.

## Stage 2 results integration

Read [results and learning](learning.md) for schema-3 attribution, dated outcome history, sample-aware funnel rates, weekly review, stale-update settings, rejection reasons and approved adjustments. Use `analytics`, `weekly` and `guidance`; only the helper changes persistent state. Applied Gmail outcomes feed history, while pending/dismissed mail does not. Before new document preparation, consult approved tailoring guidance and record the actual approach with evidence. Statistical proposals require candidate approval and support undo; they do not authorize application submission or outreach.
