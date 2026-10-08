# Owner setup checklist: protect the repo without breaking the daily post

**Who does this:** you, in GitHub's settings. Agents may not change repo settings (Guardian brief, out of scope), and every step below is an R2 or R5 action, so each is yours to approve.
**Time:** about 60 minutes in total, spread over at least two days (step 4 waits for a real post). **Cost:** nothing, as long as the repo stays public (see "What needs a paid plan").
**Repo facts this is written for** (read from GitHub's API on 2026-10-07, read-only): `gh0stl0nely/business-assets`, public, personal account, default branch `main`, `main` not protected, no rulesets, secret scanning and push protection both **disabled**.
**Where the evidence is:** `knowledge/security/K-sec-0003` to `K-sec-0006`, `K-sec-0008`, `K-sec-0009`, `K-sec-0010`. GitHub menu names change; each click path is marked (docs) when it comes from a GitHub page and (check on screen) when it does not.

> ## Do not protect `main` yet
> **Protect `main` only after you have approved the poster change (step 3), it has run for one real post, and you have checked that post (step 4).** Today the poster saves its history by committing straight to `main`. With the unchanged workflow, a protected `main` rejects that save; the post is already live, and the next backup run (there are three start times a day) posts the same day's content again. Protecting `main` first recreates the exact failure this checklist exists to prevent.
>
> Even after the move to a side branch, a failed save used to allow the same double post. The fix is a **fail-closed** poster: it records its intent before it posts, and refuses to post if it cannot. It is designed, simulated (`test_fail_closed.py`, 80 checks) and written up as a change request: `agent-system/change-requests/03-guardian-poster-fail-closed.md`. It has **not** been tried on real GitHub. That is what steps 3 to 5 do, in that order.

## Steps, in this order

| # | Step | Time | Why it is in this place |
|---|---|---|---|
| 1 | Turn on secret scanning alerts | 5 min | Currently disabled; free on public repos. |
| 2 | Turn on push protection | 5 min | Currently disabled; blocks a push that contains a known key format. |
| 3 | Approve and apply the poster change | 30 min | Must come before step 5. Needs a maintenance session and an R2 Preflight Brief. |
| 4 | Watch one real post | 5 min, next day | Proves the new flow on real GitHub before anything is locked. |
| 5 | Protect `main` | 10 min | Nothing can reach `main` except a pull request you merge. |
| 6 | Run the real-GitHub probe | 5 min | Proves the workflow can still save its history with `main` protected. |
| 7 | Decide the identity question | 5 min | Whether a session can merge its own pull request (see below). |
| 8 | Hooks | later | Guardrail inside Claude sessions. R2 brief. |

### 1. Secret scanning alerts (docs: [enabling secret scanning](https://docs.github.com/en/code-security/secret-scanning/enabling-secret-scanning-features/enabling-secret-scanning-for-your-repository); K-sec-0009)
**This is off today.** GitHub's pages say scanning "runs automatically for free" on public repositories, but partner-pattern secrets "are reported directly to the provider and aren't displayed in your repository alerts", and a read of your repository on 2026-10-07 shows `secret_scanning` as `disabled`. So a leaked key might be reported to its provider and revoked, and you would still never be told. To get alerts in your own repository: Settings, Security and quality, Advanced Security; to the right of **Secret Protection** click **Enable**, read the notice, click **Enable Secret Protection**. Afterwards the status reads enabled.

### 2. Push protection (docs: [enabling push protection](https://docs.github.com/en/code-security/secret-scanning/enabling-secret-scanning-features/enabling-push-protection-for-your-repository); K-sec-0004, K-sec-0009)
Same page: in the **Secret Protection** section, to the right of **Push protection**, click **Enable**. You need the owner or admin role, which you have. GitHub's page on push protection says protection **for users** is on by default for public repositories, but that is a separate setting from the one on the repository, and your repository's own setting reads `disabled` today (read-only API call, 2026-10-07), so this step is still needed. Anyone with write access can still bypass a block by giving a reason; that is why the hooks (step 8) exist too. Confirm both read enabled when you are done.

### 3. The poster change (R2; ask Chief of Staff for a Preflight Brief; a maintenance session makes it, not the Guardian)
Full design, tests and runbook: `agent-system/change-requests/03-guardian-poster-fail-closed.md`. In short, three things change, all in files the Guardian did **not** edit:
- `scripts/post_threads.py` gets a patch of about 20 lines (`poster-state/post_threads.gate.patch`): it claims the day on a side branch before posting, marks the point of no return before the publish request, and records the post after it.
- Three files are added to `scripts/`: `poster_gate.py`, `restore_state.sh`, `save_state.sh`.
- `.github/workflows/daily-post.yml` gets a restore step and a replacement save step that runs even if the post step failed (`poster-state/proposed-workflow-steps.yml`).

Order (each step is checkable; `main` is still unprotected throughout):
1. **First open Threads and check that no post is live today that `main` does not know about.** If one is, stop and use the section "poster-state was deleted, rewound or re-created" below (pause first). Then create the branch `poster-state` from `main` in the GitHub web page (Code, branch menu, type the name, Create branch). No force, nothing is overwritten. This is only safe now because the poster has not yet run under the gate; after that, creating the branch from `main` is never enough on its own.
2. Merge the change by pull request. If the old workflow saved a post to `main` between 1 and 2, the first new run **stops on purpose** ("branch is behind"). Fix: from a checkout of `main`, run `python3 scripts/poster_gate.py save`, which merges `main`'s posts into the branch without losing any.
3. Run the workflow by hand, mode `dry_run`. **This does not exercise any push**: the dry run returns before the claim and before the save, so it only proves that the restore step can read the branch.
4. Do not start step 5 until step 4 has passed.

**Rollback (do these in order, or the original failure comes back):** `main`'s `state.json` goes stale once the new flow runs, so putting the old workflow back alone makes the old poster forget every day posted since. (1) Pause posting (`"paused": true` in `config.json`, by pull request). (2) `python3 scripts/poster_gate.py export /tmp/state.json`; it refuses while any claim is unconfirmed. (3) Commit that file as `bloor-assets/state.json` on `main` by pull request. (4) If `main` is protected, also unprotect it, because the old save step pushes to `main`. (5) Revert the workflow and un-pause. The simulation shows the naive rollback posting a day twice and this sequence not doing so.

### 4. Watch one real post
After the next scheduled post: (a) the Actions run is green; (b) the `poster-state` branch has two new commits, "Claim <date> post" and "Record <date> post"; (c) in `state.json` on that branch, `claims.<date>.status` is `posted`; (d) Threads shows exactly one post for the day. If a run fails with **BLOCKED** (exit 11), that is the safety working: an earlier run claimed the day and never confirmed it. Open Threads. If the post is live: `python3 scripts/poster_gate.py complete <date> manual <permalink>`. If nothing is live: `python3 scripts/poster_gate.py release <date> "checked Threads: nothing live"`. If (d) shows two posts, pause (`"paused": true` through a pull request), delete the duplicate, and tell Chief of Staff before doing anything else.

### poster-state was deleted, rewound or re-created (a day may already have posted)
**Why the order matters.** The gate remembers each day on the `poster-state` branch. If that branch is deleted and created again from `main`, or moved back to an older commit, it has forgotten every post made since its history was last saved. If today's post is already live, the next run (a backup cron, a manual run) sees nothing recorded for today and posts it a second time. The simulation reproduces exactly that (`test_fail_closed.py`, S15 and S17), and the earlier version of this checklist told you to do it. Do these four things, in this order, every time:
1. **Pause the poster with its own switch, first.** By pull request, set `"paused": true` in `bloor-assets/config.json` (the poster then prints "Posting is paused" and does nothing). Merge it. Open the Actions tab and wait until no poster run is in progress. Nothing can post while it is paused, so there is no race with a backup cron.
2. **Put the branch back.** Deleted: create `poster-state` from `main` (web page, as in step 3.1). Rewound: nothing to create; a backup of the branch tip, if you have one, only helps.
3. **Re-create the claim for every day that already posted.** Open Threads and list the days with a live post since the history was last good: today at the very least, and earlier days too if you ever run the poster by hand with `--date`. For each day run `python3 scripts/poster_gate.py complete DATE ID LINK` (ID and LINK are on the live post; write `unknown` for the ID if you cannot find it). That records the day exactly as a normal run would. Then **check**: `python3 scripts/poster_gate.py status DATE` must print `DATE: posted` and exit 0, and `python3 scripts/poster_gate.py status` lists what the branch records so you can compare it with Threads. (Before the poster change is applied, the script is in `agents/03-guardian/poster-state/`.)
4. **Unpause, last.** By pull request, set `"paused": false`. At the next run the log should say "Already posted for DATE (recorded on the state branch)" for each day you re-created, and nothing new should appear on Threads.
- If `main`'s own `state.json` already records the day (the old workflow saved it), the restore step refuses with "behind" instead; that case is the `save` fix in the table at the end, not this section.
- A run that is **cancelled or killed after it claimed the day** leaves its claim behind (no cleanup code runs on SIGKILL or SIGTERM; S19 shows both). The next run is blocked (exit 11): you get a missed post, never a double post. Look at Threads: nothing live, `release`; live, `complete`.

### 5. Protect `main` (docs: [about protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches); K-sec-0005, K-sec-0010; check on screen)
Settings, Branches, **Add classic branch protection rule** for `main` (classic rules and rulesets are both free on public repos; this checklist uses the **classic rule** because its wording is the one GitHub documents). If you prefer a ruleset, the equivalents are listed at the end of this step.
- **Require a pull request before merging: on, with 0 required approvals.** (In a classic rule leave "Require approvals" unticked; in a ruleset set "Required approvals" to 0. The page I read does not state that 0 is allowed, so confirm on screen.) You cannot approve your own pull request ("Pull request authors cannot approve their own pull requests"), so any number above 0 would lock you out.
- **Force pushes and deletions blocked.** In the classic rule these are the options "Allow force pushes" and "Allow deletions": **leave both unticked** (blocked is GitHub's default for a protected branch). A ruleset words them "Block force pushes" and "Restrict deletions".
- **Do not allow bypassing the above settings: ticked.** Admins are exempt by default, and your sessions act as an admin (see step 7), so without this the rule binds nobody.
- No required status checks (none are wired to GitHub yet).
- You still merge pull requests on the web page as normal; that is not a direct push.
- **Rollback:** the same screen, delete the rule. Nothing is lost.
- **If you use a ruleset instead:** it has no "Do not allow bypassing" checkbox. It has a **bypass list** ("Add bypass"). Keep that list **empty** and confirm on screen that your admin account is not bypassing; GitHub's pages do not say whether the list starts empty or whether admins can bypass by default (check on screen). Set "Required approvals" to 0 (same caveat as above).

### 6. Real-GitHub probe (after step 5)
Add `poster-state/test-poster-state.yml.proposed` as `.github/workflows/test-poster-state.yml` (by pull request), run it once from the Actions tab, read the result, then delete the workflow file and the branch `poster-state-test`. It claims, records and re-reads a fake day (2099-01-01) on a throwaway branch with protection ON, and posts nothing. This is the **only** real proof that the workflow's token can write a side branch while `main` is protected; the simulations cannot show it, and GitHub's pages do not say (K-sec-0005, K-sec-0006). It must run after step 5 to mean anything. If it fails: delete the `main` rule (step 5 rollback) and tell Chief of Staff. Nothing posts wrongly in the meantime: with the gate in place, a failed claim means no post, not two.

### 7. Identity: can a session merge its own pull request? (decision for you; QUESTIONS.md Q2; K-sec-0010)
Claude sessions push to GitHub **as you**: pull request #2 was opened by `gh0stl0nely`, and so was the review, and that account has admin permission. The 0-approval rule in step 5 therefore does **not** stop a session from pressing merge on its own pull request, because the same account is allowed to. Two things do stop it:

| Option | What stops a session merging its own PR | Cost to you |
|---|---|---|
| A. Hooks only (step 8) | Blocks `gh pr merge` (in every spelling tried), `gh api -X PUT .../merge`, pushes to `main`, and connector merge tools, inside Claude sessions. A guardrail, not a security boundary: a determined program can get around a text parser. | R2 brief; nothing else. |
| B. A second free GitHub account for sessions, with approvals set to 1 | GitHub itself: the session account can open and review, only you can approve and merge. This is the real two-key gate. | Create the account, add it as a collaborator, and hand a token to the session environment. **Handling that token is an R5 step: only you do it, and I never see it.** |

Until you choose, treat A as the only barrier and keep merging by hand.

### 8. Hooks (later; also an R2 brief)
`agents/03-guardian/hooks/` holds two hook scripts and `settings.example.json`. They are **not active**. Installing means merging the example into `.claude/settings.json`. They are **a guardrail, not a security boundary**: they read the text of a command and refuse the well-known mistakes (force pushes, pushes and merges into `main`, recursive deletes outside `/tmp`, download-and-run, secret-looking content in a commit or push, edits to the workflow, `.claude/settings*`, the hooks and `agent-system/contracts/`). They do not stop you, a script written to a file and then run, or anything outside a Claude session. Run `python3 agents/03-guardian/hooks/test_hooks.py` first (645 checks). See `hooks/README.md`, in particular its **Known limits** section: the real controls are that sessions never hold secrets and the GitHub settings in this checklist, not the hooks.
- **Install them after step 3**, because they block edits to `.github/workflows/`. If a maintenance session must edit the workflow with the hooks on, start that session with `GUARDIAN_UNLOCK=.github/workflows/` set by you; the agent cannot set it.
- They allow exactly three GitHub writes through `gh api` (comment on a pull request, open a pull request, edit a comment), so a review session's comment fallback still works. `gh pr comment` and `gh pr create` are allowed as before.
- The first install should be checked with one harmless blocked command (for example `git push --force` on a scratch branch); I could not run a live Claude Code session with the hooks installed.

### Optional hardening
- Settings, Actions, General, **Fork pull request workflows**: the options are "Require approval for first-time contributors who are new to GitHub", "Require approval for first-time contributors" and "Require approval for all external contributors". By default first-time contributors already need approval, so the optional step is only to choose the strictest option, "all external contributors" (docs: managing GitHub Actions settings; check on screen). The poster workflow only runs on a schedule and by hand, so this is low risk today.
- Settings, Actions, General, "Workflow permissions": the poster file already asks for `contents: write` itself. Leave the default at read-only so any future workflow has to ask. I could not read this repo's current setting (the API path is blocked for sessions), so look at it. Note that anyone with write access can raise a workflow's token permissions by editing the workflow's `permissions:` key, which is why the hooks protect `.github/workflows/`.
- History scan: this review could only see a shallow copy. On a full clone run `git log --all -p | python3 .claude/skills/secrets-hygiene/scripts/scan_secrets.py --diff -`; zero findings is the goal. If it reports one, revoke the credential first, then ask for a brief.

## What needs a paid plan
**Nothing above, while the repo is public and personal.** What would:
- Making the repo **private**: GitHub's page lists secret scanning for private repos only as "organization-owned private and internal repositories" with GitHub Secret Protection on a Team or Enterprise plan. It does not list a private repo in a personal account, so the real prerequisite would probably be moving the repo into an organization. That is not confirmed; read the page again before making it private (K-sec-0003).
- **Path-based push rules** (for example "no one pushes to `.github/workflows/`"): listed only for Team-plan private and internal repos (K-sec-0006), so not available here; the hooks cover that gap only inside Claude sessions.
- **Bypass lists and push restrictions** on classic branch protection are described for organization-owned repos (K-sec-0005). You do not need them if you follow step 3 instead of trying to let the bot through.
The hooks and scripts run on the machine where the session runs and add no GitHub cost; whether they add anything to Claude Pro usage is not something I could measure, but they make no model calls.

## What this does not do
- It does not stop you, or anyone with admin rights who turns the rules off.
- It does not protect your Threads token: that lives in Actions secrets and only you can rotate it (R5). Push protection and the scanners look for keys in code; they cannot know the token's value.
- The poster gate cannot see Threads. If a run is blocked, you look at Threads; that check is yours.
- The hooks are a guardrail for a mistaken or manipulated agent, not a security boundary or a sandbox.
- A leaked key is never fixed by deleting it from the file: revoke or rotate it at the provider first, then clean up.

## If something goes wrong
| Symptom | First action |
|---|---|
| The workflow's restore step fails "branch does not exist" | **Do not just create the branch.** The run stopped on purpose; nothing was posted. First check Threads for a post today, then follow the section "poster-state was deleted, rewound or re-created": pause, put the branch back, `complete` each posted day, `status`, and only then unpause. Only before step 3 has ever run is creating it from `main` enough. |
| Restore fails "branch is behind this checkout" | `main` records a post the branch lacks. Run `python3 scripts/poster_gate.py save` from a checkout of `main`, then re-run. Nothing was posted. |
| The post step fails with **BLOCKED** or "cannot confirm it is safe to post" | Step 4: look at Threads, then `complete` or `release` the day. Nothing was posted by that run. |
| The post step fails "POSTED ... but could not record it" | The post is live. Do not post again. The save step may already have recorded it; if not, run `complete` for that day. |
| A run was cancelled or killed after claiming the day | The next run is blocked (exit 11). Look at Threads. Nothing live: `release` the day. Live: `complete` it. A missed post, never a double post. |
| Two posts on one day | Pause (`"paused": true` through a pull request), delete the duplicate on Threads, then check `poster-state`'s last commits. |
| Push to `main` rejected for you | Expected under protection. Use a pull request; or delete the rule for a moment (step 5 rollback) and say why. |
| A block message from a hook | Read the rule name in the message. It says what to write instead (usually a Preflight Brief). |
