# Change request: make the Threads poster fail closed (claim before posting)

- **From:** 03 Guardian builder session (round 2, answering the review of PR #2)
- **Touches (not edited by this PR):** `scripts/post_threads.py`, `.github/workflows/daily-post.yml`. Both are live. Changing them is an **R2** action: it needs a Preflight Brief and the owner's yes, and a maintenance session makes the change, not the Guardian.
- **Priority:** high. **Do not protect `main` until the owner has approved this change and the real-GitHub test (step 6 below) has passed.**
- **Where the working code is:** `agents/03-guardian/poster-state/` (`poster_gate.py`, `post_threads.gate.patch`, the two wrappers, `proposed-workflow-steps.yml`). Tests: `test_fail_closed.py` (55 checks) and `test_poster_state.py` (20 checks). Both run offline.

## 1. The problem, in the reviewer's terms

`post_threads.py` avoids posting twice in one day by one thing only: it reads `state["posted"]` from the checked-out `bloor-assets/state.json` and skips if today is there. The workflow has three start times (14:35, 15:35, 16:35 UTC) so a late or failed run is covered by a later one. That works only if the record of a post reaches the next run. Three ways it does not:

| # | Failure path (from the review) | What happens with the live design | Reproduced in |
|---|---|---|---|
| F1 | The post goes live, then saving the record fails (branch protection, a network blip, a push conflict) | The next cron checks out a history without today and **posts again** | `test_fail_closed.py` S0 (old flow, 2 posts live) |
| F2 | Migration with a stale branch: `poster-state` is cut from `main`, then the old workflow saves one more post to `main` before the cutover | The new workflow restores the older branch copy and forgets that post | S10 |
| F3 | Rollback: the new design has run for days (records only on `poster-state`), the owner reverts the workflow, and the old workflow reads `main`'s old `state.json` | The old script posts a day that is already live | S11 (naive rollback, 3 posts live) |

The earlier proposal (restore from a branch, save to a branch) fixes protection but not F1: a failed save after a live post is still invisible to the next run. The root cause is that the poster records the post **after** it happens, and the record is a best-effort extra step. The fix is to record the **intent** first.

## 2. The design

State lives in `bloor-assets/state.json` on an unprotected branch, `poster-state`. The file keeps its old shape (`posted`, which the script already reads and writes) and gains one new key the script ignores: `claims`, a map from date to `{status, run, at}` where status is `claimed`, `posted` or `released`.

The poster's sequence on a real post becomes:

1. **Claim.** Before anything is created on Threads, read the branch tip, refuse if today is posted or already claimed, then push a commit that adds `claims[today] = claimed`. The push is **non-force**, so git itself makes it a compare-and-swap: if two runs try at once, one push is rejected, that run re-reads, sees the other's claim and stops. If the claim cannot be written (branch unreachable, push refused three times) the poster exits 12 and **does not post**.
2. **Point of no return.** One line immediately before the publish request marks that from here on a failure can no longer prove nothing was published.
3. **Publish**, then read the permalink, then the script writes its own `state.json` exactly as today.
4. **Complete.** Push `posted[today]` (the same entry the script wrote) and `claims[today] = posted`. If this fails three times the poster exits 1 with `::error::POSTED <date> but could not record it`, and the claim stays.
5. **Finish (in a `finally`).** If the run failed **before** the point of no return, the claim is released (so a later cron can post). If it failed at or after it, the claim is **kept**.

A kept, unconfirmed claim is what makes F1 safe: the next cron restores the branch, tries to claim, finds `claimed` and exits 11 (`BLOCKED`). Nothing is posted and GitHub emails the owner that the run failed. The owner looks at Threads and either records the post (`poster_gate.py complete DATE ID LINK`) or, if nothing is live, releases the claim (`poster_gate.py release DATE "checked Threads: nothing live"`). This is deliberately conservative: it prefers a missed day the owner can fix in a minute over a duplicate post on a public account.

The save step stays, and runs with `if: always()`: when the post is live but step 4 failed, the script's own `state.json` still holds the record, and save merges it into the branch (and upgrades the claim to `posted`) if the branch is reachable again by then.

### What each failure does (all simulated)

| Case | Result | Check |
|---|---|---|
| Normal day, then a backup cron | One post; the backup says "Already posted" | S1 |
| F1: record cannot be written at all | Post live once; backup crons exit 11; owner records it; next run skips | S2 |
| Record fails but the save step works | Branch upgraded to posted; backup does nothing | S3 |
| Claim cannot be written | No post, exit 12; posts once the branch is writable | S4 |
| No state branch | Restore stops the run; claim also refuses | S4b |
| Failure before publish (container error) | Claim released; backup cron posts once | S5 |
| ...and the release cannot be written | Claim blocks (safe), nothing posted | S5b |
| Publish times out but the post is live | Claim kept; backup blocked; one post live | S6 |
| Publish rejected (HTTP 400, not live) | Claim kept; backup blocked; owner releases; next run posts | S7 |
| Post live, permalink read fails | Claim kept; backup blocked; one post live | S8 |
| Two runs at the same instant | Exactly one claim wins, the other exits 11 | S9 |
| F2: branch is behind `main` | Restore **and** claim both refuse; `save` from a `main` checkout fixes it | S10 |
| F3: rollback | Naive rollback double-posts; export-then-PR rollback does not | S11 |

Known limit, stated plainly: after a publish **HTTP 400** the claim is kept even though nothing is live, because the client cannot tell a rejected publish from a lost response in general. The cost is one blocked day that the owner clears by hand. I chose that over guessing.

## 3. The change to the live files (not made here)

- `scripts/post_threads.py`: `post_threads.gate.patch`, about 20 lines: one import, one claim call after the token check, one `point_of_no_return()` before the publish call, one `complete(...)` after the state write, and a `try/finally` around `main()` in `__main__`. `--dry-run` and `--check` never reach the gate (S12). The test applies the patch to the current script and fails if it stops applying.
- `scripts/`: add `poster_gate.py`, `restore_state.sh`, `save_state.sh` (all standard library plus git).
- `.github/workflows/daily-post.yml`: restore step after checkout (with `id: restore`); the save step replaced by `save_state.sh` with `if: always() && steps.restore.outcome == 'success'`. Text in `proposed-workflow-steps.yml`. `permissions: contents: write` is already present and is enough for a side-branch push, to be confirmed by step 6.

## 4. Migration, in this order (each step is checkable)

1. Owner approves the Preflight Brief for this change. **`main` is still unprotected.**
2. Create `poster-state` from the current `main` in the GitHub web UI (no force; nothing is overwritten).
3. Merge the change (patch, scripts, workflow) by pull request. If the old workflow saved a post to `main` between steps 2 and 3, the first new run **refuses** (F2) instead of guessing. Fix: from a checkout of `main` run `python3 scripts/poster_gate.py save`, which merges `main`'s posts into the branch without losing any.
4. Run the workflow by hand in mode `dry_run`. Note: **this does not exercise any push** (it returns before the claim and before the save). It proves only that restore reads the branch.
5. Wait for one real scheduled post. Confirm: Threads shows one post; `poster-state` has a "Claim" and a "Record" commit; `claims[today]` is `posted`.
6. **Only now** protect `main` (checklist step 6), then run `test-poster-state.yml.proposed` once. It claims, records and re-reads a fake day on a throwaway branch with protection on, which is the only real-GitHub proof that the workflow token can write a side branch under the rule. If it fails, unprotect `main` and stop.

## 5. Rollback (F3) — do these in order, or the original failure comes back

The old workflow reads `main`'s `state.json`, which the new design never updates. Reverting the workflow alone makes the old poster forget every day posted since the cutover.

1. Pause posting if a post is due soon (`"paused": true` in `config.json`, by pull request).
2. `python3 scripts/poster_gate.py export /tmp/state.json`. It writes the branch's history in the old format and **refuses while any claim is unconfirmed**, so a post nobody recorded cannot be hidden.
3. Commit that file as `bloor-assets/state.json` on `main` by pull request.
4. If `main` is protected, the old save step (push to `main`) will fail, so rolling back the workflow also means turning protection off (or rolling back only the save step, which changes nothing about the double-post risk).
5. Revert the workflow, un-pause. `poster-state` can stay.

S11 shows the naive rollback posting day 2 a second time and this sequence not doing so.

## 6. What this does not claim

- It was tested against a local bare repository and a fake Threads. GitHub's own behaviour (does the Actions token push a side branch while `main` is protected?) is unconfirmed until step 6 of the migration passes.
- It does not stop a human from pressing "post" in `workflow_dispatch` mode `post`: that mode passes `--force`, which skips the time window but not the claim, so it is also protected from duplicates.
- Threads itself is the final source of truth for "is it live". The gate cannot see Threads; it relies on the owner's check in the blocked case.
- `poster-state` is public like the repo. It holds only dates, post ids and permalinks of already public posts.
