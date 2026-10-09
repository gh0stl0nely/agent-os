#!/usr/bin/env python3
"""Simulated test (no network, no GitHub): does the proposed poster-state flow keep the daily state save working
when main is protected? Exit 0 only if every check passes.

  python3 agents/03-guardian/poster-state/test_poster_state.py

A local bare repository stands in for GitHub. Its pre-receive hook rejects any push to main unless the pusher sets
PUSHER=owner-pr (standing in for the owner merging a pull request in the web page). This is a SIMULATION of branch
protection; it proves the scripts' logic, not GitHub's behaviour. The real check is test-poster-state.yml.proposed.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RESTORE, SAVE = HERE / "restore_state.sh", HERE / "save_state.sh"
WORKFLOW = (REPO / ".github" / "workflows" / "daily-post.yml").read_text(encoding="utf-8")
results = []


def check(name, ok, detail=""):
    ok = bool(ok)
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


def sh(cmd, cwd, env=None, check_=True):
    e = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null", **(env or {})}
    p = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), capture_output=True, text=True, env=e)
    if check_ and p.returncode != 0:
        raise RuntimeError(f"{cmd} failed: {p.stderr[-300:]}")
    return p


def state(day, previous=None):
    """The post history as the poster script writes it: the earlier days are kept and today's entry is added."""
    posted = dict(json.loads(previous)["posted"]) if previous else {}
    posted[day] = {"id": "1", "permalink": "https://example.invalid/p/1", "at": day + "T11:00:00-04:00"}
    return json.dumps({"posted": posted}, indent=2) + "\n"


def read(r):
    return (r / "bloor-assets" / "state.json").read_text(encoding="utf-8")


def old_save_step():
    """The exact shell of the current 'Save post history' step, read from the live workflow file."""
    m = re.search(r"- name: Save post history\n\s+run: \|\n((?:\s{10}.*\n?)+)", WORKFLOW)
    return "\n".join(l[10:] for l in m.group(1).splitlines()) if m else None


with tempfile.TemporaryDirectory(dir=os.path.expanduser("~")) as td:
    tmp = Path(td)
    origin = tmp / "origin.git"
    sh(["git", "init", "-q", "--bare", "-b", "main", str(origin)], tmp)
    hook = origin / "hooks" / "pre-receive"
    hook.write_text('#!/bin/sh\nwhile read old new ref; do\n  if [ "$ref" = "refs/heads/main" ] && [ "$PUSHER" != "owner-pr" ]; then\n    echo "remote: protected branch: changes must be made through a pull request" >&2; exit 1\n  fi\ndone\n', encoding="utf-8")
    hook.chmod(0o755)
    seed = tmp / "seed"
    sh(["git", "clone", "-q", str(origin), str(seed)], tmp)
    sh(["git", "config", "user.name", "owner"], seed); sh(["git", "config", "user.email", "o@example.invalid"], seed)
    (seed / "bloor-assets").mkdir()
    (seed / "bloor-assets" / "state.json").write_text(state("2026-10-06"), encoding="utf-8")
    (seed / "bloor-assets" / "queue.json").write_text('{"2026-10-08": "text A"}\n', encoding="utf-8")
    sh("git add -A && git commit -q -m seed", seed)
    sh("git push -q origin HEAD:main", seed, env={"PUSHER": "owner-pr"})

    def runner(label):
        """A fresh shallow checkout, like actions/checkout, with the bot identity."""
        d = tmp / label
        sh(["git", "clone", "-q", "--depth=1", f"file://{origin}", str(d)], tmp)
        return d

    # ---- the simulated protection works, and the CURRENT workflow step fails under it
    step = old_save_step()
    check("setup: the current 'Save post history' step was found in .github/workflows/daily-post.yml", step and "git push" in step)
    r = runner("old-run")
    (r / "bloor-assets" / "state.json").write_text(state("2026-10-07", read(r)), encoding="utf-8")
    p = sh(["bash", "-eo", "pipefail", "-c", step], r, check_=False)
    check("risk: with main protected, the CURRENT workflow's state push to main is rejected (exit non-zero)", p.returncode != 0 and "protected" in p.stderr, p.stderr[-150:])
    check("risk: so enabling protection without changing the workflow loses the state: main on the remote has no record of today's post",
          "2026-10-07" not in sh(f"git --git-dir={origin} show main:bloor-assets/state.json", tmp).stdout)

    # ---- bootstrap: the owner creates the side branch once from main
    sh("git push -q origin main:refs/heads/poster-state", seed, env={"PUSHER": "owner-pr"})

    # ---- restore fails closed when the branch is missing or broken
    r = runner("no-branch")
    p = sh(["bash", str(RESTORE)], r, env={"STATE_BRANCH": "does-not-exist"}, check_=False)
    check("restore: a missing state branch stops the run (fail closed) with a clear message", p.returncode == 1 and "does not exist" in p.stderr)
    bad = tmp / "bad-seed"
    sh(["git", "clone", "-q", str(origin), str(bad)], tmp)
    sh(["git", "config", "user.name", "o"], bad); sh(["git", "config", "user.email", "o@example.invalid"], bad)
    sh("git checkout -q -b poster-state-bad", bad)
    (bad / "bloor-assets" / "state.json").write_text("{not json", encoding="utf-8")
    sh("git commit -qam bad", bad)
    sh("git push -q origin poster-state-bad", bad)
    r = runner("bad-json")
    p = sh(["bash", str(RESTORE)], r, env={"STATE_BRANCH": "poster-state-bad"}, check_=False)
    check("restore: a state file that is not valid JSON stops the run", p.returncode == 1 and "not a valid post history" in p.stderr)
    check("restore: and leaves the checked-out file untouched", json.loads((r / "bloor-assets" / "state.json").read_text())["posted"].keys() == {"2026-10-06"})

    # ---- day 1 flow with main protected
    r = runner("day1")
    p = sh(["bash", str(RESTORE)], r)
    check("restore: the state comes back from the side branch", p.returncode == 0 and "restored" in p.stdout)
    p = sh(["bash", str(SAVE)], r)
    check("save: with no change, nothing is pushed", "unchanged" in p.stdout)
    (r / "bloor-assets" / "state.json").write_text(state("2026-10-07", read(r)), encoding="utf-8")  # the post step ran
    p = sh(["bash", str(SAVE)], r, check_=False)
    check("save: after a post, the state is pushed to the side branch even though main is protected", p.returncode == 0 and "saved" in p.stdout, p.stderr[-200:])
    check("save: the save does not change main", sh("git rev-parse origin/main", r).stdout == sh(f"git --git-dir={origin} rev-parse main", tmp).stdout)
    check("save: the working tree of the run is not disturbed (still shows today's state)", "2026-10-07" in (r / "bloor-assets" / "state.json").read_text())

    # ---- the next scheduled run (a backup cron) must see today's post
    r2 = runner("day1-backup")
    check("risk: a fresh checkout of main alone does NOT contain today's post (this is why restore is needed)", "2026-10-07" not in (r2 / "bloor-assets" / "state.json").read_text())
    sh(["bash", str(RESTORE)], r2)
    posted = json.loads((r2 / "bloor-assets" / "state.json").read_text())["posted"]
    check("restore: the backup run restores today's post, so the script will not post twice", "2026-10-07" in posted and "2026-10-06" in posted)
    check("restore: other files still come from main (queue edits made by pull request are used)", "2026-10-08" in (r2 / "bloor-assets" / "queue.json").read_text())

    # ---- a queue edit merged to main by the owner (pull request) still works and is picked up
    sh("git checkout -q main", seed)
    (seed / "bloor-assets" / "queue.json").write_text('{"2026-10-08": "text A", "2026-10-09": "text B"}\n', encoding="utf-8")
    sh("git commit -qam 'queue: add 10-09'", seed)
    p = sh("git push -q origin HEAD:main", seed, env={"PUSHER": "owner-pr"}, check_=False)
    check("normal: the owner's merge to main still works under the simulated protection", p.returncode == 0)
    (seed / "bloor-assets" / "queue.json").write_text('{"2026-10-08": "text A", "2026-10-09": "text B", "2026-10-10": "text C"}\n', encoding="utf-8")
    sh("git commit -qam 'queue: add 10-10'", seed)
    p = sh("git push -q origin HEAD:main", seed, check_=False)
    check("normal: a direct push to main without the owner's merge is rejected (the protection is real in this simulation)", p.returncode != 0 and "protected" in p.stderr)
    sh("git reset -q --hard HEAD~1", seed)
    r3 = runner("day2")
    sh(["bash", str(RESTORE)], r3)
    check("normal: day 2 sees both the new queue entry (from main) and yesterday's post (from the side branch)",
          "2026-10-09" in (r3 / "bloor-assets" / "queue.json").read_text() and "2026-10-07" in (r3 / "bloor-assets" / "state.json").read_text())

    # ---- two runs racing: the side branch moved between fetch and push
    ra, rb = runner("race-a"), runner("race-b")
    sh(["bash", str(RESTORE)], ra); sh(["bash", str(RESTORE)], rb)
    (ra / "bloor-assets" / "state.json").write_text(state("2026-10-08", read(ra)), encoding="utf-8")
    sh(["bash", str(SAVE)], ra)
    (rb / "bloor-assets" / "state.json").write_text(state("2026-10-09", read(rb)), encoding="utf-8")
    p = sh(["bash", str(SAVE)], rb, check_=False)
    check("save: when the branch moved since the checkout, the second save still succeeds (fetches the tip, commits on top)", p.returncode == 0, p.stderr[-200:])
    tip = json.loads(sh(f"git --git-dir={origin} show poster-state:bloor-assets/state.json", tmp).stdout)["posted"]
    check("save: history on the side branch is a straight line and keeps every earlier day", len(sh(f"git --git-dir={origin} log --oneline poster-state", tmp).stdout.splitlines()) >= 3 and {"2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09"} <= tip.keys())

    # ---- failure path
    r4 = runner("outage")
    (origin / "hooks" / "pre-receive").write_text('#!/bin/sh\necho "remote: simulated outage" >&2\nexit 1\n', encoding="utf-8")
    sh(["bash", str(RESTORE)], r4)
    (r4 / "bloor-assets" / "state.json").write_text(state("2026-10-10", read(r4)), encoding="utf-8")
    p = sh(["bash", str(SAVE)], r4, check_=False)
    check("save: if the push fails twice it exits 1 and tells the owner not to re-run the post step blindly", p.returncode == 1 and "Do not re-run the post step" in p.stderr)

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
