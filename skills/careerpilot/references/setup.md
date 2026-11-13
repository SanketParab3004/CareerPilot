# Setup and release

Run the commands below with Python 3.10 or later. In the examples, CP means the full path to scripts/toolkit.py in the installed skill. Use a separate private directory per candidate.

## Quickstart

1. Install from the repository with python tools/install_skill.py --host codex --user, --host claude --user, or --host generic --destination PATH. Use --project PATH instead of --user for project scope. For a skill ZIP, extract the careerpilot directory into the host's skill directory.
2. Try python CP --workspace NEW-DEMO-PATH demo. Open it with python CP --workspace NEW-DEMO-PATH dashboard --open. Demo records are synthetic and use example.invalid. Use them for local practice only.
3. Run python CP --workspace PRIVATE-PATH init, then open its dashboard and choose Guided setup. Verify the displayed path and candidate. Complete or skip profile, job targets, browser, Gmail and Telegram. Browser and Gmail are host permissions. Telegram settings are local and delivery is optional.

Run python CP --workspace PRIVATE-PATH doctor for plain fixes. Report browser and Gmail as available only after observing the current host tools and account access. Pass --browser available or --gmail available to doctor after those checks; otherwise leave them unknown. The helper cannot discover a chat host's connectors. A configured Telegram token is not a delivery test.

Before writes or external actions, compare the resolved workspace and candidate to the user's intended candidate. Stop on mismatch. Pass the independently confirmed path as --expect-workspace PATH before the subcommand. Dashboard sessions show the active path and have separate local session URLs. Do not mix files, permissions, or credentials across candidates.

## Regional preferences

Use run with an international-config operation. Optional keys are country (two-letter code), currency (three-letter code), language (language tag), date_format (locale, iso, dmy, mdy), portals (LinkedIn and/or Indeed), and authorization_questions (a list of locally relevant questions). Use these preferences for search locations, host conversation, pay labels and candidate questions. Saved searches freeze their required portals at creation. Both portals remain the default. Never infer citizenship or permission to work. Ask the exact local questions and preserve unknown answers. The dashboard UI remains English and the regional date setting applies to posting dates.

## Private files

Windows credentials use DPAPI. On macOS or Linux, optionally install keyring and cryptography. The workspace settings key is held by macOS Keychain or a running, unlocked Linux Secret Service. Unsupported or unavailable stores can use browser autofill and manual checks. Credential records copied to a different user or path may need reconnection.

Stop the dashboard, helpers and any active writes before backup, export, restore or deletion. Run backup --archive FILE for a workspace snapshot, or full-export --archive FILE for the same portable bundle of canonical state, attachments, imports, reports, backups and encrypted credential records. OS keys remain in their original stores. Add --encrypt to protect the archive with a prompted passphrase. For active workspace encryption, place the entire workspace on a trusted OS-encrypted volume. Restore decrypts to the destination filesystem, so choose an encrypted volume if required. Use restore --archive FILE with a new workspace path. Check the restored workspace before relying on it.

Run secure-delete --confirm-path EXACT-RESOLVED-PATH only after the candidate explicitly chooses deletion. It removes a dedicated workspace with recognized files and removes its non-Windows keychain key when present. It cannot sanitize SSDs, snapshots, cloud sync history or separately stored archives. For device-level secure erasure use the OS or storage vendor process. For cryptographic erasure, destroy the key of a dedicated encrypted volume and account for all copies.

Use metrics-export --archive FILE --consent only with candidate opt-in. It writes fixed aggregate status counts with cells below five suppressed. It includes no names, employers, URLs, dates or candidate identifiers. Review repeated releases for differencing risk before sharing.
