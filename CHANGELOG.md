# Changelog

## Unreleased

- Account-access workflow with persistent login/signup intent, separate Gmail activation
  permissions, exact-message checks, bounded attempts and recovery without automatic replay.
- Accounts & alerts exposes mailbox/sender/destination consent. Host tools perform the
  actual activation; CAPTCHA/MFA and unclear results still need assistance.
- Private settings schema 2 creates an encrypted backup before upgrading on first write.
  Canonical workspace schema is unchanged. Stop older helpers before updating; existing
  login/signup permissions stay intact and verification is off until explicitly enabled.

- Stronger resume-tailoring workflow with evidence-first achievement selection,
  employer priorities, focused questions and an explained final review.
- Literal keyword checks reject misleading substring matches in the posting,
  source evidence and final document; case and whitespace differences are accepted.
- No schema migration. Existing approvals are preserved; stricter keyword checks
  apply on new verification. Refresh the installed skill or re-upload the ZIP to
  use the updated instructions. Historical documents are not rewritten.

## 1.0.0

Stage 6 adds guided setup, diagnostics, demo generation, native keychain support, workspace archives, regional preferences, workspace checks, aggregate metrics export and a source-only release manifest. Stages 1–5 remain available.
