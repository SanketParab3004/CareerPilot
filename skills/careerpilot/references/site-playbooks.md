# Site playbooks

Read the matching row after observing the live employer and tenant. Domain detection
in `application_quality.detect` is a hint, not proof of a trusted site or a fixed UI.
Custom domains and embedded forms require visible branding/route evidence. Record
unknown systems as generic. Never infer a safe selector, required question, completed
step or submission from this guide. Tenant configuration can change every flow.

| System / detection hint | Inspect the flow and field patterns | Failure to watch for / recovery |
|---|---|---|
| Workday / myworkdayjobs.com, myworkdaysite.com | Employer-specific candidate account; resume import or manual information; experience/education, questions, disclosures and review as present. Inspect repeated work-history rows, date widgets and country-dependent address controls. | Imported dates/roles may need correction; dependent region choices may reset. Choose the actual country, wait for options, then the actual region. Recheck every parsed row and attachment. Expired login: same-tenant login sitting, then live resume inspection. |
| Greenhouse / greenhouse.io | Job post and application, resume/contact fields and employer custom questions; optional autofill. Check which resume is attached, not just which profile is selected. | Autofill or embedded form may omit custom answers or retain an old resume. Inspect visible values and filename after parsing. Use the permitted frame context or visible direct application link; otherwise hand off. |
| Lever / lever.co | Job and apply form; resume parsing, contact information and custom questions. Inspect labels, select/multi-select values and required disclosures. | Parsed fields can differ from source; file rejection or blank extracted fields. Compare actual values, use supported original-format export and recheck. Never infer skills or auto-consent. |
| Ashby / ashbyhq.com | Employer-configured form; field connectors/custom questions mean layout and required fields vary. Inspect sections, conditional questions and uploads. | A selection can reveal new required questions; re-inspect after each conditional change. Unknown questions go to the batched list. Inaccessible embedded content uses the frame fallback below. |
| iCIMS / icims.com | Employer portal, candidate profile/login, resume parsing, job-specific questions and review as configured. Distinguish general profile updates from this job's application. | Session transitions, stale profile attachments or upload failures. Verify exact requisition and attachment after login, and resume from live state. A saved profile is not an application receipt. |
| SmartRecruiters / smartrecruiters.com | Employer job, candidate/contact information, resume and screening questions as configured. Inspect privacy/consent and the final application control separately. | Parsed information or a previously stored attachment can be stale. Compare every submitted value to the reviewed snapshot; re-upload only a checked job document. Ambiguous completion is uncertain. |
| Taleo / taleo.net | Configured career-section application flow, account/profile, attachments, questionnaires and review. Follow the visible progress indicator, not a prescribed page count. | Session expiry, required fields on a later page, stale attachments or navigation losing state. Save each observed checkpoint; inspect after re-login. Never use browser Back to guess whether a submit happened. |
| Oracle Recruiting / oraclecloud.com | Verify employer/requisition, then follow visible candidate and application steps. Do not assume it is Taleo. | One-time codes or identity transitions require the candidate. Never persist codes; after assistance inspect current job and all retained fields. |
| SAP SuccessFactors / successfactors.com or .eu | Verify employer tenant, candidate profile and job-specific application sections. | Profile-save versus application-submit can be distinct. Read the visible control and receipt; uncertain completion is never retried. |
| Other / custom employer domains | Record observed platform evidence or generic. Enumerate visible steps and required labels before acting. | No safe readable method: `failure-record` then candidate handoff. Do not probe hidden APIs or invent a selector map. |

These are inspection/recovery hypotheses, not claims that these failures occurred on
the candidate's site. Use `failure-record` for observed site, step and type; use
`playbook-note` only after an observed recovery. Private workspace notes improve the
next run for that tenant; they never modify or export the portable playbook. Common
failure counts and evidence IDs are available in `quality` and the dashboard.

## Bounded fallbacks

- Address rejected: inspect the exact validation message, country/region dependency
  and allowed options. Try a supported formatting-only change without changing the
  actual address, then re-read the value. Do not substitute a nearby city or fake ZIP.
  At most two failed attempts for the same site/step/type, then hand off.
- Embedded iframe: use the host's documented frame controls, or a visible direct
  employer application link if permitted. Re-verify destination and job. Never change
  frame security, inject scripts to bypass restrictions, or call private endpoints.
- Unreadable form: use an available permitted accessibility or screenshot/visual
  tool, re-observe after interaction, and capture evidence. If labels/values cannot be
  verified, stop; a guessed click or screenshot alone does not prove a field is filled.
- Upload rejection: inspect permitted type/size; export a supported file and repeat
  document verification. Do not rename a PDF to DOCX or silently remove true content.
- CAPTCHA/MFA/bot detection: candidate assistance, no bypass. Shared browser failure:
  stop the runner, checkpoint unaffected work, do not repeatedly hit every portal.

## Source basis and limits (checked November 6, 2026)

Vendor/employer documentation supports the broad flows; the bounded recovery policy
above is CareerPilot's design, not a vendor guarantee. No live employer form was tested.

- [Workday employer candidate instructions](https://www.wlu.edu/employment-opportunities/staff-positions/application-instructions-for-new-external-applicants): account and application workflow.
- [Greenhouse candidate FAQ](https://support.greenhouse.io/hc/en-us/articles/43418495049499-MyGreenhouse-FAQ-for-Candidates): resume/autofill behavior.
- [Lever resume parsing](https://help.lever.co/s/article/Understanding-Resume-Parsing): extracted candidate fields require checking.
- [Ashby application forms](https://docs.ashbyhq.com/application-forms): employer-customized forms.
- [iCIMS employer candidate guide](https://www.honorhealth.com/sites/default/files/careers/honorhealth-careers-iCIMS-application.pdf): profile, resume and candidate dashboard.
- [SmartRecruiters candidate experience](https://learning.sap.com/courses/smartrecruiters-for-sap-successfactors-academy/exploring-the-candidate-experience_fdf1f35a-7ebc-458c-9194-0a1823a8ea98): candidate application process.
- [Oracle Taleo application flow](https://docs.oracle.com/en/cloud/saas/taleo-enterprise/22a/otcug/c-applicationflow.html): configurable sequence of application pages.
