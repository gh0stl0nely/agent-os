# Owner setup checklist: protect the repo without breaking the daily post

**Who does this:** you, in GitHub's settings. Agents may not change repo settings (Guardian brief, out of scope), and every step below is an R2 or R5 action, so each is yours to approve.
**Time:** about 40 minutes once. **Cost:** nothing, as long as the repo stays public (see "What needs a paid plan").
**Repo facts this is written for:** `gh0stl0nely/business-assets`, public, personal account, default branch `main`, daily poster running from `.github/workflows/daily-post.yml`.
**Status of the facts:** GitHub menu names change. Where a click path comes from GitHub's own pages it is marked (docs); where it is from memory it is marked (check on screen). Evidence is in `knowledge/security/K-sec-0003` to `K-sec-0006` and `K-sec-0008`.

## Read this first: the one thing that can go wrong

Today the poster saves its history by committing `bloor-assets/state.json` **straight to `main`** (the last step of the workflow). If you protect `main` with a "pull request required" rule and change nothing else, that push is rejected. The post will already be live on Threads, but the history will not be saved. The workflow has three backup start times inside the posting window, and the only thing that stops a second post is that history file. So a protected `main` with the unchanged workflow can post the same day's content more than once.

Whether GitHub lets the workflow's own bot skip the rule on a personal repo is **not confirmed** by anything I could read (K-sec-0005, K-sec-0006). So the safe order is: move the history off `main` first, test it, then protect `main`.

The fix is written and tested in a simulation (`agents/03-guardian/poster-state/`): the history is saved to a separate branch, `poster-state`, which stays unprotected. Run the check yourself any time: `python3 agents/03-guardian/poster-state/test_poster_state.py` (20 checks). It simulates GitHub; step 4 below is the real test.

## Steps, in this order

| # | Step | Time | Why it is in this place |
|---|---|---|---|
| 1 | Confirm secret scanning is on | 3 min | Free on public repos; catches leaked keys. |
| 2 | Turn on push protection | 5 min | Blocks a push that contains a known key format, before it lands. |
| 3 | Move the poster history to `poster-state` | 15 min | Must come before step 5. |
| 4 | (Recommended) Real test of a side-branch push | 5 min | Proves step 3 works on real GitHub, without posting. |
| 5 | Protect `main` | 10 min | Nothing can reach `main` except a pull request you merge. |
| 6 | Check the next real post | 2 min | Proves the whole chain. |

### 1. Secret scanning (docs)
Settings, then Security (called "Code security" or "Advanced Security" on some screens), then Secret scanning. On a public repo it runs on its own and is free. Confirm it says enabled. Nothing to pay for.

### 2. Push protection (docs, K-sec-0004)
Settings, Security and quality, Advanced Security, Secret Protection, Push protection: switch it on. GitHub's pages disagree on whether it is already on by default for public repos, so **look at the screen and confirm it reads enabled**. Anyone with write access can still bypass a block by giving a reason; that is why the hooks (step 7) exist too.

### 3. Move the poster history (needs an R2 Preflight Brief; ask Chief of Staff for one)
This changes the live poster, so it is a separate approved change, made by a maintenance session, not by me. What changes:
1. Create the branch once, from `main` as it is today (it holds today's post record): on GitHub, Code, branch menu, type `poster-state`, Create branch from `main`. **Do this before the workflow change goes live**; without it the new workflow stops on purpose (it fails closed rather than posting from stale history).
2. Copy `agents/03-guardian/poster-state/restore_state.sh` and `save_state.sh` into `scripts/`.
3. In `.github/workflows/daily-post.yml`: add a step "Restore post history" (`bash scripts/restore_state.sh`) right after checkout, and replace the old "Save post history" step with `bash scripts/save_state.sh`. Exact text: `proposed-workflow-steps.yml`. Nothing else in the workflow changes; the secret `THREADS_ACCESS_TOKEN` is untouched.
4. Run the workflow once by hand with mode `check` or `dry_run` (Actions tab, Run workflow). Neither posts. Confirm the "Restore post history" step is green.
5. **Rollback:** put the old save step back and delete the two scripts. `poster-state` can stay; it is harmless. Test of the rollback: dry run, then confirm a normal run reads `state.json` from `main` again.

After this, `bloor-assets/state.json` on `main` is no longer the live record; `poster-state` is. Pull-request edits to `queue.json`, `config.json` and `manifest.json` on `main` still take effect, as before (tested).

### 4. Real test of a side-branch push (recommended, optional)
Add `agents/03-guardian/poster-state/test-poster-state.yml.proposed` as `.github/workflows/test-poster-state.yml`, run it once from the Actions tab, confirm it is green and creates the branch `poster-state-test`, then delete the workflow file and that branch. It posts nothing and never touches `poster-state`. If you run it **after** step 5 it also proves the workflow can write a side branch while `main` is protected.

### 5. Protect `main` (docs, K-sec-0005; check on screen)
Settings, Branches, add a rule for `main` (or a Ruleset; the free tier allows both on public repos):
- Require a pull request before merging: **on**. Required approvals: **0** (you are the only reviewer, and you cannot approve your own pull request, so a higher number locks you out).
- Do not allow force pushes: **on**. Do not allow deletions: **on**.
- "Do not allow bypassing the above settings" (or "Include administrators"): **on** if Claude sessions push with your own admin identity, so the rule binds them too. **I could not confirm which identity sessions push as** (QUESTIONS.md Q2). With it on, you still merge pull requests on the web page as normal; that is not a direct push.
- Leave required status checks off; there are no tests wired to GitHub yet.
- **Rollback:** the same screen, delete the rule (10 seconds). Nothing is lost.

### 6. Check the next real post
After the next post: (a) Actions run is green, including "Save post history"; (b) the `poster-state` branch has a new commit "Record today's post"; (c) Threads shows exactly one post for the day. If (c) shows two, turn the protection off, set `"paused": true` in `config.json` through a pull request, and tell Chief of Staff.

### 7. Hooks (later; also an R2 brief)
`agents/03-guardian/hooks/` holds two hook scripts and `settings.example.json`. They are **not active**. Installing means merging the example into `.claude/settings.json`. They block, in Claude sessions only: force pushes, pushes to or merges into `main`, recursive deletes outside `/tmp`, download-and-run, secret-looking content in a commit, push or file write, and edits to the workflow, `.claude/settings*`, the hooks themselves and `agent-system/contracts/`. They do not stop you, and they do not touch the workflow run on GitHub. Run `python3 agents/03-guardian/hooks/test_hooks.py` first (219 checks). See `hooks/README.md` for limits.

### 8. Optional hardening
- Settings, Actions, General: set "Fork pull request workflows from outside collaborators" to require approval (check on screen). The poster workflow only runs on a schedule and by hand, so this is low risk today.
- Settings, Actions, General, "Workflow permissions": the poster file already asks for `contents: write` itself. Leave the default at read-only so any future workflow has to ask.
- History scan: this review could only see the 9 commits in the shallow copy it had, and found no secret-like value. On a full clone run `git log --all -p | python3 .claude/skills/secrets-hygiene/scripts/scan_secrets.py --diff -`; zero findings is the goal. If it reports one, revoke the credential first, then ask for a brief.

## What needs a paid plan
**Nothing above, while the repo is public and personal.** What would:
- Making the repo **private**: secret scanning and push protection then need GitHub Secret Protection on a Team or Enterprise plan (K-sec-0003).
- **Path-based push rules** (for example "no one pushes to `.github/workflows/`"): listed only for Team-plan private and internal repos (K-sec-0006), so not available here; the hooks cover that gap only inside Claude sessions.
- **Bypass lists and push restrictions** on classic branch protection are described for organization-owned repos (K-sec-0005). You do not need them if you follow step 3 instead of trying to let the bot through.
The hooks and scripts run on the machine where the session runs and add no GitHub cost; whether they add anything to Claude Pro usage is not something I could measure, but they make no model calls.

## What this does not do
- It does not stop you, or anyone with admin rights who turns the rules off.
- It does not protect your Threads token: that lives in Actions secrets and only you can rotate it (R5). Push protection and the scanners look for keys in code; they cannot know the token's value.
- The hooks are a speed bump for a mistaken or manipulated agent, not a sandbox.
- A leaked key is never fixed by deleting it from the file: revoke or rotate it at the provider first, then clean up.

## If something goes wrong
| Symptom | First action |
|---|---|
| The workflow's restore step fails "branch does not exist" | Do step 3.1 (create `poster-state` from `main`). The run stopped on purpose; nothing was posted. |
| Two posts on one day | Pause (`"paused": true` through a pull request), delete the duplicate on Threads, then check `poster-state`'s last commit. |
| Push to `main` rejected for you | Expected under protection. Use a pull request; or delete the rule for a moment (step 5 rollback) and say why. |
| A block message from a hook | Read the rule name in the message. It says what to write instead (usually a Preflight Brief). |
