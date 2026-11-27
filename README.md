# CareerPilot

**An AI job-search assistant that runs inside the AI agent you already use (Claude Code or Codex).**

You tell it what jobs you want. It finds them, ranks how well you fit, writes a resume tailored to each one, fills in the application forms, and tracks every reply. It stops before **Submit** so you stay in control.

Everything stays on your computer. There's no account, no subscription and no API key.

---

## What it does

| Step | What CareerPilot does for you |
|---|---|
| 1. **Build your profile** | Reads your resume (PDF, Word, text) or LinkedIn export and shows you the profile before saving it. |
| 2. **Find jobs** | Searches LinkedIn and Indeed for jobs that apply on the employer's own site, skips Easy Apply, and removes duplicates and reposts. |
| 3. **Rank your fit** | Scores each job against your profile and explains the strengths and gaps. |
| 4. **Tailor your resume** | Writes a resume and cover letter for each job using only facts from your profile, never invented ones, then checks the final file. |
| 5. **Fill applications** | Fills the employer's form in your browser and pauses at Review. You press Submit. |
| 6. **Track replies** | Reads job emails in Gmail (read-only) and updates each application: interview, rejection, offer. |
| 7. **Learn what works** | Shows which roles, sources and resume versions get responses, plus the skills and pay in your target jobs. |
| 8. **Prepare for interviews** | Builds a story bank from your real experience and runs practice rounds. |

It also has a **local dashboard** in your browser, **referral matching** from your LinkedIn connections, a **daily top 5** of new jobs, and optional **Telegram alerts** when it needs you (for example a CAPTCHA or login).

### What it won't do

- **Submit without your OK.** Submitting needs your approval for each job, or a batch you approve explicitly.
- **Make things up.** Every resume claim must trace back to your profile.
- **Solve CAPTCHAs, create logins on its own, or send messages for you** without your approval.
- **Work without an AI agent.** CareerPilot is a set of instructions plus a small Python helper. The AI agent does the thinking and the browsing.

---

## What you need

- **An AI agent that supports skills:** [Claude Code](https://code.claude.com/docs/en/skills) or [Codex](https://learn.chatgpt.com/docs/build-skills).
- **Python 3.10 or newer** ([download](https://www.python.org/downloads/)). Check with `python --version`.
- **For filling applications:** a browser tool connected to your agent, such as Claude in Chrome.
- **Optional:** Gmail connected to your agent (to track replies) and a Telegram bot (for phone alerts).

---

## Install (about 2 minutes)

**1. Download the project**

```bash
git clone https://github.com/SanketParab3004/CareerPilot.git
cd CareerPilot
```

Or click **Code → Download ZIP** on GitHub and unzip it.

**2. Install the skill into your agent**

For Claude Code:
```bash
python tools/install_skill.py --host claude --user
```

For Codex:
```bash
python tools/install_skill.py --host codex --user
```

`--user` makes it available in all your projects. Use `--project "PATH"` to install it in one folder only. Add `--dry-run` to see where it would go without installing.

**3. Start it**

Open your agent and type:

- Claude Code: **`/careerpilot`**
- Codex: **`$careerpilot`**

On first run it creates a private `job-search-workspace` folder in your current folder (or anywhere you tell it), confirms the location with you, then walks you through setup.

---

## Using it

Just ask in plain English. For example:

> Set up my profile from my resume at C:\Users\me\resume.pdf

> Find Data Analyst jobs in Toronto posted in the last week

> Tailor my resume for the top 3 jobs and show me before saving

> Fill in the applications and stop at Review for me to submit

> Check Gmail for replies to my applications

> What skills do my target jobs ask for that I don't list?

> Show my progress this week

### Try it with fake data first

Want to look around before using your own details? Run a demo workspace:

```bash
python skills/careerpilot/scripts/toolkit.py --workspace demo-workspace demo
python skills/careerpilot/scripts/toolkit.py --workspace demo-workspace dashboard --open
```

### Open your dashboard

The dashboard shows your jobs, documents, applications and results in your browser. Ask your agent to "open my CareerPilot dashboard". On Windows you can also double-click **`Open Dashboard.cmd`**.

It runs only on your computer, and it never submits applications or sends email.

---

## Your data and privacy

- Your profile, jobs and documents are stored in a **private folder you choose**, separate from the skill. Never commit that folder to Git.
- Saved passwords are encrypted: Windows uses DPAPI, macOS uses Keychain and Linux uses Secret Service.
- Gmail access is **read-only** and limited to job emails.
- Back up anytime with `backup --archive FILE`. Delete everything with `secure-delete`. See [setup](skills/careerpilot/references/setup.md).

---

## Updating

Download the latest version, move your old installed `careerpilot` skill folder somewhere else (the installer won't overwrite it), and run the install command again. Your private job-search folder upgrades automatically and is backed up first. See [UPGRADE.md](UPGRADE.md).

---

## FAQ

**Is it free?** Yes. You only need your own AI agent subscription.

**Does it work with ChatGPT or Gemini on the web?** No. It needs an agent that can run files, Python and a browser, such as Claude Code or Codex.

**Will employers know an AI helped?** CareerPilot fills forms the same way you would, and you press Submit yourself. The resumes contain your real experience.

**Which countries?** Any. Search location, currency and work-permit questions are configurable. It was built and tested for Canada.

**Something isn't working.** Run `python skills/careerpilot/scripts/toolkit.py --workspace YOUR-FOLDER doctor` for plain-English fixes, or [open an issue](https://github.com/SanketParab3004/CareerPilot/issues).

---

## Learn more

- [How the skill works (SKILL.md)](skills/careerpilot/SKILL.md)
- [Resume tailoring](skills/careerpilot/references/resume-tailoring.md) · [Applications](skills/careerpilot/references/application-quality.md) · [Gmail tracking](skills/careerpilot/references/email-review.md) · [Learning from results](skills/careerpilot/references/learning.md)
- [Compatibility](COMPATIBILITY.md) · [Changelog](CHANGELOG.md)

## For developers

```bash
python -m unittest discover -s tests -v   # run tests (synthetic data only)
python tools/package_skill.py             # build dist/careerpilot.zip
```

```text
skills/careerpilot/   The installable skill (instructions + Python helper)
tools/                Installer and packager
tests/                Automated tests
legacy/dashboard/     Old standalone prototype, not used by the skill
```

The Python helper uses only the standard library. PDF import optionally uses `pypdf`.

## License

[MIT](LICENSE). Free to use, change and share.
