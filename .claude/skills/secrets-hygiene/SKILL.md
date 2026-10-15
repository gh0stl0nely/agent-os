---
name: secrets-hygiene
description: Scan any diff, file, folder or plan for secrets (API keys, tokens, passwords, private keys, key files) and give the owner step-by-step instructions for storing them safely. Use before every commit or pull request, whenever a plan mentions an API key, token, password, credential, login or .env file, when a secret may have leaked into a file or chat, and when anyone asks where or how to keep a key. Never reads, prints, stores or sends a secret value; recommends a password manager and the GitHub Actions secret store. Agents never handle secrets, so this skill writes instructions for the owner instead.
---

# secrets-hygiene

**Model tier:** Haiku or Sonnet. A script does the pattern scanning; the model only explains findings and writes the owner steps. High volume, low judgment, so the cheapest tier is fine.

## Purpose
Find secret-like values and risky files before they reach a commit, a pull request, a log or a chat, and turn each finding into steps only the owner can do. Class R0: it reads and reports, and it writes nothing.

## Inputs
- A diff, a file, a folder, staged changes, or a plan in text. If nothing is given, ask for one of those; do not scan the whole machine.
- Never ask the owner to paste a secret to "check" it.

## Procedure
1. **Script:** `python3 .claude/skills/secrets-hygiene/scripts/scan_secrets.py` with one mode: `--staged` (before a commit), `--diff FILE` (a unified diff; only added lines count), `--paths P...` (files or folders), or `--text` (a plan on stdin; also flags plans that tell someone to paste, store or commit a secret).
2. **Script:** the report lists rule, file, line and length for each finding, plus `suppressed` items and `skipped` files (binary, too large, unreadable). It never contains a value.
3. **Judgment:** for each finding say what it probably is and what is at risk. Do not open the file to look at the value; the line number is enough for the owner.
4. **Judgment:** if `skipped` is not empty, say which files were not scanned and why. A skipped file is not a clean file.
5. Give the owner the `owner_instructions` from the report, unchanged in meaning. The first step is always to revoke or rotate at the provider.
6. Findings or not, state the class: any action that would create, store, rotate or use a credential is **R5, human only**. This skill may write instructions; it never performs the step.

## Evidence rules
Each finding is a claim with computation evidence (the script and the line). Status `pending` until the Verifier checks it. "No findings" is a claim too: report the number of files scanned and the skipped list with it, so it can be checked. Do not say "clean" for something that was skipped.

## Outputs
JSON report from the script plus a short plain-language summary for the owner. For another agent, an envelope fitting `agent-envelope.schema.json`: `status: ok` when clean, `blocked` with an escalation naming the file and line when not.

## Side effects
None. Class R0 for scanning and for writing instructions. Removing a secret from git history is class R3 and needs its own Preflight Brief; rotating a credential is R5 and is the owner's.

## Escalation
Stop and tell the owner at once if a high-severity finding is in a file already pushed to the public repo: treat the value as exposed and give the rotate-first steps. Do not wait for a review.

## Knowledge use
Check `knowledge/security/` first: K-sec-0003 and K-sec-0004 (GitHub secret scanning and push protection), K-sec-0008 (how to store a secret for a GitHub Action). The patterns are heuristics (see `reference.md`); GitHub secret scanning and push protection are the primary layer, this is the second.
