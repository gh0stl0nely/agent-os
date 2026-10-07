#!/usr/bin/env python3
"""Simulation of the fail-closed poster design (change request 03-guardian-poster-fail-closed). No network, no GitHub,
no real Threads. Exit 0 only if every check passes.

  python3 agents/03-guardian/poster-state/test_fail_closed.py

What is real: the live scripts/post_threads.py (copied, then patched with post_threads.gate.patch), the gate
(poster_gate.py), the two shell wrappers, git itself. What is simulated: Threads (sim_runner.py replaces urlopen) and
GitHub (a local bare repository whose pre-receive hook protects main and can be told to refuse pushes to the state
branch, to model an outage). Nothing here proves GitHub's own behaviour; test-poster-state.yml.proposed does that.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PATCH = HERE / "post_threads.gate.patch"
results = []
D = ["2026-10-0%d" % i for i in range(7, 10)] + ["2026-10-10", "2026-10-11", "2026-10-12", "2026-10-13", "2026-10-14", "2026-10-15"]


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


HOOK = r'''#!/bin/sh
# stands in for GitHub: main is protected; pushes to the state branch can be made to fail (count window) or to be slow
while read old new ref; do
  case "$ref" in
    refs/heads/main)
      [ "$PUSHER" = owner-pr ] || { echo "remote: protected branch: changes must be made through a pull request" >&2; exit 1; } ;;
    refs/heads/poster-state)
      n=$(cat count 2>/dev/null || echo 0); n=$((n+1)); echo $n > count
      [ -f slow ] && sleep 1
      if [ -f fail-from ]; then
        f=$(cat fail-from); u=$(cat fail-until 2>/dev/null || echo 999999)
        if [ "$n" -ge "$f" ] && [ "$n" -le "$u" ]; then echo "remote: simulated outage" >&2; exit 1; fi
      fi ;;
  esac
done
'''


class Env:
    """One simulated GitHub repository plus a fake Threads, isolated per scenario."""

    def __init__(self, root, tag, branch=True):
        self.root, self.tag = root, tag
        self.origin = root / f"{tag}-origin.git"
        self.world = root / f"{tag}-threads.json"
        sh(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)], root)
        sh(["git", "config", "receive.denyNonFastForwards", "true"], self.origin)
        (self.origin / "hooks" / "pre-receive").write_text(HOOK, encoding="utf-8")
        (self.origin / "hooks" / "pre-receive").chmod(0o755)
        self.seed = root / f"{tag}-seed"
        sh(["git", "clone", "-q", str(self.origin), str(self.seed)], root)
        sh(["git", "config", "user.name", "owner"], self.seed); sh(["git", "config", "user.email", "o@example.invalid"], self.seed)
        s = self.seed
        (s / "scripts").mkdir(); (s / "bloor-assets").mkdir()
        shutil.copy(APP / "post_threads.py", s / "scripts" / "post_threads.py")
        shutil.copy(APP / "post_threads_unpatched.py", s / "scripts" / "post_threads_unpatched.py")
        for f in ("poster_gate.py", "restore_state.sh", "save_state.sh", "sim_runner.py"):
            shutil.copy(HERE / f, s / "scripts" / f)
        (s / "bloor-assets" / "config.json").write_text(json.dumps({"timezone": "America/Toronto", "post_hour_local": 11, "raw_base_url": "https://example.invalid/raw/", "footer": "", "default_media": [], "paused": False}), encoding="utf-8")
        (s / "bloor-assets" / "queue.json").write_text(json.dumps({"posts": [{"on": d, "text": f"synthetic post {d}", "topic_tag": "test"} for d in D]}), encoding="utf-8")
        (s / "bloor-assets" / "manifest.json").write_text(json.dumps({"assets": []}), encoding="utf-8")
        (s / "bloor-assets" / "state.json").write_text(json.dumps({"posted": {"2026-10-06": {"id": "0", "permalink": "https://example.invalid/t/0", "at": "2026-10-06T11:00:00-04:00"}}}, indent=2) + "\n", encoding="utf-8")
        sh("git add -A && git commit -q -m seed", s)
        sh("git push -q origin HEAD:main", s, env={"PUSHER": "owner-pr"})
        if branch:
            self.bootstrap()
        self.n = 0

    def bootstrap(self):
        sh("git push -q origin main:refs/heads/poster-state", self.seed, env={"PUSHER": "owner-pr"})
        (self.origin / "count").write_text("0")

    def runner(self, label=None):
        self.n += 1
        d = self.root / f"{self.tag}-run{self.n}-{label or ''}"
        sh(["git", "clone", "-q", "--depth=1", f"file://{self.origin}", str(d)], self.root)
        return d

    # outage control, relative to the number of state-branch pushes seen so far
    def pushes(self):
        return int((self.origin / "count").read_text() or 0)

    def outage(self, start=1, length=None):
        base = self.pushes()
        (self.origin / "fail-from").write_text(str(base + start))
        if length is None:
            (self.origin / "fail-until").unlink(missing_ok=True)
        else:
            (self.origin / "fail-until").write_text(str(base + start + length - 1))

    def heal(self):
        for f in ("fail-from", "fail-until"):
            (self.origin / f).unlink(missing_ok=True)

    def live(self):
        try:
            return json.loads(self.world.read_text())["live"]
        except FileNotFoundError:
            return []

    def tip(self):
        p = sh(f"git --git-dir={self.origin} show poster-state:bloor-assets/state.json", self.root, check_=False)
        return json.loads(p.stdout) if p.returncode == 0 else None

    # the steps of the proposed workflow
    def restore(self, r):
        return sh(["bash", "scripts/restore_state.sh"], r, check_=False)

    def post(self, r, day, fault="", script="post_threads.py"):
        env = {"SIM_WORLD": str(self.world), "SIM_FAULT": fault, "GITHUB_RUN_ID": f"run-{self.n}"}
        return sh([sys.executable, "-B", "scripts/sim_runner.py", f"scripts/{script}", "--force", "--date", day], r, env=env, check_=False)

    def save(self, r):
        return sh(["bash", "scripts/save_state.sh"], r, check_=False)

    def workflow(self, day, fault="", label=None, script="post_threads.py"):
        """restore -> post -> save (save runs even if post failed, but only if restore succeeded), like the proposed workflow."""
        r = self.runner(label)
        out = {"r": r, "restore": self.restore(r)}
        out["post"] = self.post(r, day, fault, script) if out["restore"].returncode == 0 else None
        out["save"] = self.save(r) if out["restore"].returncode == 0 else None
        return out

    def gate(self, r, *args):
        return sh([sys.executable, "-B", "scripts/poster_gate.py", *args], r, check_=False)


with tempfile.TemporaryDirectory(dir=os.path.expanduser("~")) as td:
    root = Path(td)

    # ------------------------------------------------------------ the patch applies to the REAL script
    APP = root / "app"
    (APP).mkdir()
    shutil.copy(REPO / "scripts" / "post_threads.py", APP / "post_threads_unpatched.py")
    shutil.copy(REPO / "scripts" / "post_threads.py", APP / "post_threads.py")
    stage = root / "patch-stage"; (stage / "scripts").mkdir(parents=True)
    shutil.copy(REPO / "scripts" / "post_threads.py", stage / "scripts" / "post_threads.py")
    p = sh(["patch", "-p1", "--dry-run", "-i", str(PATCH)], stage, check_=False)
    check("patch: post_threads.gate.patch applies cleanly to the CURRENT scripts/post_threads.py", p.returncode == 0, p.stdout + p.stderr)
    sh(["patch", "-p1", "-s", "-i", str(PATCH)], stage)
    shutil.copy(stage / "scripts" / "post_threads.py", APP / "post_threads.py")
    p = sh([sys.executable, "-B", "-c", "import ast,sys;ast.parse(open(sys.argv[1]).read())", str(APP / "post_threads.py")], root, check_=False)
    check("patch: the patched script is valid Python", p.returncode == 0, p.stderr)
    g = sh("git status --porcelain -- scripts .github/workflows bloor-assets", REPO).stdout
    check("scope: this work did not modify scripts/, .github/workflows/ or bloor-assets/ in the repository", g.strip() == "", g)

    # ------------------------------------------------------------ S0: the reviewer's finding, reproduced on the OLD flow
    e2 = Env(root, "s0b")
    e2.outage()
    a = e2.workflow(D[0], script="post_threads_unpatched.py", label="first")
    check("S0 (the finding): old flow, first run posts, then its save fails", len(e2.live()) == 1 and a["save"].returncode == 1)
    b = e2.workflow(D[0], script="post_threads_unpatched.py", label="backup")
    check("S0 (the finding): the backup cron restores a history without today's post and POSTS A SECOND TIME", len(e2.live()) == 2, str(e2.live()))

    # ------------------------------------------------------------ S1: happy path
    e = Env(root, "s1")
    a = e.workflow(D[0], label="first")
    t = e.tip()
    check("S1: normal day: restore, claim, post, complete, save all succeed and exactly one post is live",
          a["restore"].returncode == 0 and a["post"].returncode == 0 and a["save"].returncode == 0 and len(e.live()) == 1, str(a["post"].stderr[-300:]))
    check("S1: the state branch records the post AND the claim as posted", D[0] in t["posted"] and t["claims"][D[0]]["status"] == "posted")
    check("S1: the poster's own entry and the branch's entry are identical (no second competing record)", t["posted"][D[0]] == json.loads((a["r"] / "bloor-assets" / "state.json").read_text())["posted"][D[0]])
    check("S1: the save step had nothing left to do", "unchanged" in a["save"].stdout, a["save"].stdout + a["save"].stderr)
    b = e.workflow(D[0], label="backup")
    check("S1: a backup cron the same day posts nothing", b["post"].returncode == 0 and len(e.live()) == 1 and "Already posted" in b["post"].stdout)
    check("S1: the next day posts again (the claim is per date)", e.workflow(D[1], label="next")["post"].returncode == 0 and len(e.live()) == 2)

    # ------------------------------------------------------------ S2: reviewer failure path 1: the record cannot be written at all
    e = Env(root, "s2")
    e.outage(start=2)  # the claim (push 1) works; every later write to the state branch fails
    a = e.workflow(D[0], label="first")
    check("S2: after the claim, the record of the post cannot be written: the post is live but nothing durable says so",
          len(e.live()) == 1 and a["post"].returncode == 1 and a["save"].returncode == 1 and "POSTED" in a["post"].stderr, a["post"].stderr[-300:])
    check("S2: the loud message tells the owner not to post again", "Do not post again" in a["post"].stderr)
    b = e.workflow(D[0], label="backup1")
    c = e.workflow(D[0], label="backup2")
    check("S2 (the fix): the backup crons are BLOCKED (exit 11) by the unconfirmed claim and post nothing", b["post"].returncode == 11 and c["post"].returncode == 11 and len(e.live()) == 1, f"{b['post'].returncode} {c['post'].returncode} {e.live()}")
    check("S2: the block message says what to check and where the runbook is", "Check Threads" in b["post"].stderr and "runbook" in b["post"].stderr)
    e.heal()
    owner = e.runner("owner")
    p = e.gate(owner, "complete", D[0], "p1", "https://example.invalid/t/p1")
    check("S2: after the outage the owner records the post by hand (complete)", p.returncode == 0, p.stderr)
    d = e.workflow(D[0], label="after-fix")
    check("S2: the next run sees it as posted and does nothing", d["post"].returncode == 0 and len(e.live()) == 1 and "Already posted" in d["post"].stdout)

    # ------------------------------------------------------------ S3: the record fails once but the save step succeeds
    e = Env(root, "s3")
    e.outage(start=2, length=3)  # exactly the three attempts of 'complete' fail; the save step's push works
    a = e.workflow(D[0], label="first")
    t = e.tip()
    check("S3: complete fails (exit 1) but the always-run save step records the post", a["post"].returncode == 1 and a["save"].returncode == 0 and D[0] in t["posted"], f"{a['save'].stderr[-200:]}")
    check("S3: the save step upgrades the claim to posted (a claim can never contradict a recorded post)", t["claims"][D[0]]["status"] == "posted")
    b = e.workflow(D[0], label="backup")
    check("S3: the backup cron then posts nothing", b["post"].returncode == 0 and len(e.live()) == 1)

    # ------------------------------------------------------------ S4: cannot claim -> cannot post
    e = Env(root, "s4")
    e.outage(start=1, length=3)  # all three claim attempts fail
    a = e.workflow(D[0], label="first")
    check("S4: if the claim cannot be recorded the poster does NOT post (exit 12) and the run fails loudly", a["post"].returncode == 12 and len(e.live()) == 0 and "not posting" in a["post"].stderr, a["post"].stderr[-300:])
    e.heal()
    b = e.workflow(D[0], label="backup")
    check("S4: the backup cron posts once the branch is writable again (nothing was lost)", b["post"].returncode == 0 and len(e.live()) == 1)

    # ------------------------------------------------------------ S4b: the branch cannot be read at all
    e = Env(root, "s4b", branch=False)
    a = e.workflow(D[0], label="first")
    check("S4b: no state branch: restore fails, the poster never runs, nothing is posted", a["restore"].returncode == 1 and a["post"] is None and len(e.live()) == 0)
    r = e.runner("direct")
    p = e.post(r, D[0])
    check("S4b: even if restore were skipped, the claim step refuses (exit 12) without the branch", p.returncode == 12 and len(e.live()) == 0, p.stderr[-200:])

    # ------------------------------------------------------------ S5: failure BEFORE publishing releases the claim
    e = Env(root, "s5")
    a = e.workflow(D[0], fault="container-error", label="first")
    t = e.tip()
    check("S5: a failure before publish (container error): nothing live, run fails", a["post"].returncode == 1 and len(e.live()) == 0)
    check("S5: the claim was released, so it does not block", t["claims"][D[0]]["status"] == "released", str(t["claims"]))
    b = e.workflow(D[0], label="backup")
    check("S5: the backup cron posts normally", b["post"].returncode == 0 and len(e.live()) == 1)
    e = Env(root, "s5b")
    e.outage(start=2)  # claim ok, then the release cannot be written either
    a = e.workflow(D[0], fault="container-error", label="first")
    b = e.workflow(D[0], label="backup")
    check("S5b: if the release itself cannot be written the claim stays and BLOCKS (safe direction: nothing posted, owner emailed)", b["post"].returncode == 11 and len(e.live()) == 0)

    # ------------------------------------------------------------ S6/S7/S8: failure AT or AFTER publishing keeps the claim
    for name, fault, live_n in (("S6 publish times out but the post IS live", "publish-timeout", 1),
                                ("S7 publish rejected with HTTP 400 (not live)", "publish-400", 0),
                                ("S8 post live, reading its permalink fails", "permalink-500", 1)):
        e = Env(root, name[:2].lower())
        a = e.workflow(D[0], fault=fault, label="first")
        b = e.workflow(D[0], label="backup")
        t = e.tip()
        check(f"{name}: the claim is kept, the backup cron is blocked (exit 11) and live posts stay at {live_n}",
              a["post"].returncode != 0 and b["post"].returncode == 11 and len(e.live()) == live_n and t["claims"][D[0]]["status"] == "claimed", f"{a['post'].returncode} {b['post'].returncode} {e.live()} {t['claims']}")
    # S7 recovery: the owner has checked Threads, nothing is live, releases the claim
    r = e.runner("owner")  # e is S8 now; rebuild S7 for the recovery check
    e = Env(root, "s7r")
    e.workflow(D[0], fault="publish-400", label="first")
    p = e.gate(e.runner("owner"), "release", D[0], "owner checked Threads: nothing is live")
    c = e.workflow(D[0], label="after-release")
    check("S7: after the owner checks Threads and releases the claim, the next run posts once", "released" in p.stdout and c["post"].returncode == 0 and len(e.live()) == 1, p.stdout + p.stderr)

    # ------------------------------------------------------------ S9: two runs at the same instant
    e = Env(root, "s9")
    (e.origin / "slow").write_text("1")
    ra, rb = e.runner("a"), e.runner("b")
    pa = subprocess.Popen([sys.executable, "-B", "scripts/poster_gate.py", "claim", D[0], "A"], cwd=ra, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"})
    pb = subprocess.Popen([sys.executable, "-B", "scripts/poster_gate.py", "claim", D[0], "B"], cwd=rb, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"})
    oa, ob = pa.communicate(), pb.communicate()
    codes = sorted([pa.returncode, pb.returncode])
    check("S9: two simultaneous claims: exactly one wins (exit 0 'claimed'), the other is blocked (exit 11)", codes == [0, 11] and ("claimed" in oa[0] or "claimed" in ob[0]), f"{codes} {oa} {ob}")
    check("S9: the branch holds one claim, by one of the two runs", e.tip()["claims"][D[0]]["run"] in ("A", "B"))

    # ------------------------------------------------------------ S10: reviewer failure path 2: stale branch (migration)
    e = Env(root, "s10")  # branch cut from main now
    sh("git checkout -q main", e.seed)
    posted = json.loads((e.seed / "bloor-assets" / "state.json").read_text())
    posted["posted"][D[0]] = {"id": "old", "permalink": "https://example.invalid/t/old", "at": D[0] + "T11:00:00-04:00"}
    (e.seed / "bloor-assets" / "state.json").write_text(json.dumps(posted, indent=2) + "\n", encoding="utf-8")
    sh("git commit -qam 'old workflow saved a post to main after the branch was cut'", e.seed)
    sh("git push -q origin HEAD:main", e.seed, env={"PUSHER": "owner-pr"})
    a = e.workflow(D[0], label="cutover")
    check("S10: main records a post that the state branch lacks: restore REFUSES (exit 1) and the poster never runs",
          a["restore"].returncode == 1 and "behind" in a["restore"].stderr and a["post"] is None and len(e.live()) == 0, a["restore"].stderr[-300:])
    r = e.runner("skip-restore")
    p = e.post(r, D[1])  # a different day: the script's own check cannot help, only the gate's behind-check can
    check("S10: if restore were skipped, the claim step refuses too (exit 12) rather than trusting a stale history", p.returncode == 12 and "behind" in p.stderr and len(e.live()) == 0, f"{p.returncode} {p.stdout[-200:]} {p.stderr[-200:]}")
    r = e.runner("adopt")
    p = e.save(r)
    check("S10: the documented fix (run save from a main checkout) merges main's posts into the branch", p.returncode == 0 and D[0] in e.tip()["posted"], p.stderr[-200:])
    b = e.workflow(D[0], label="after-fix")
    check("S10: after the fix, the day main knew about is recognised as posted (not posted again) and the next day posts normally",
          b["post"].returncode == 0 and len(e.live()) == 0 and e.workflow(D[1], label="next")["post"].returncode == 0 and len(e.live()) == 1)

    # ------------------------------------------------------------ S11: reviewer failure path 3: rollback recreates the failure
    e = Env(root, "s11")
    e.workflow(D[0], label="day1"); e.workflow(D[1], label="day2")
    check("S11: setup: two days posted under the new design; main's state.json still lacks them", len(e.live()) == 2 and D[1] not in json.loads((e.seed / "bloor-assets" / "state.json").read_text())["posted"])
    naive = e.runner("naive-rollback")  # the old workflow: checkout of main, no restore
    p = e.post(naive, D[1], script="post_threads_unpatched.py")
    check("S11 (the finding): a NAIVE rollback (old workflow, main's stale state) posts day 2 a second time", len(e.live()) == 3, str(e.live()))
    e = Env(root, "s11b")
    e.workflow(D[0], label="day1"); e.workflow(D[1], label="day2")
    r = e.runner("export")
    out = root / "exported-state.json"
    p = e.gate(r, "export", str(out))
    check("S11 (the fix): export writes the branch's history in the old format, with no claims", p.returncode == 0 and set(json.loads(out.read_text())) == {"posted"} and D[1] in json.loads(out.read_text())["posted"], p.stderr)
    sh("git checkout -q main", e.seed)
    (e.seed / "bloor-assets" / "state.json").write_text(out.read_text(), encoding="utf-8")
    sh("git commit -qam 'state: sync from poster-state before rollback'", e.seed)
    sh("git push -q origin HEAD:main", e.seed, env={"PUSHER": "owner-pr"})
    rolled = e.runner("rollback")
    p = e.post(rolled, D[1], script="post_threads_unpatched.py")
    check("S11 (the fix): after syncing main by pull request, the rolled-back OLD workflow does not post day 2 again", len(e.live()) == 2 and "Already posted" in p.stdout, p.stdout + p.stderr[-200:])
    e = Env(root, "s11c")
    e.outage(start=2)
    e.workflow(D[0], label="day1")
    e.heal()
    p = e.gate(e.runner("export"), "export", str(root / "x.json"))
    check("S11: export REFUSES while a claim is unconfirmed, so a rollback cannot hide a post nobody recorded", p.returncode == 1 and "unconfirmed claim" in p.stderr, p.stderr)

    # ------------------------------------------------------------ S12: dry run and token check do not touch the gate; wrappers keep their messages
    e = Env(root, "s12", branch=False)
    r = e.runner("dry")
    p = sh([sys.executable, "-B", "scripts/sim_runner.py", "scripts/post_threads.py", "--dry-run", "--date", D[0]], r, env={"SIM_WORLD": str(e.world)}, check_=False)
    check("S12: --dry-run works with no state branch and calls no gate (nothing claimed, nothing live)", p.returncode == 0 and "Dry run" in p.stdout and e.live() == [])
    p = sh([sys.executable, "-B", "scripts/sim_runner.py", "scripts/post_threads.py", "--check"], r, env={"SIM_WORLD": str(e.world)}, check_=False)
    check("S12: --check (token test) works with no state branch", p.returncode == 0 and "Token works" in p.stdout, p.stderr[-200:])

    # ------------------------------------------------------------ S12b: the proposed workflow text carries the safeguards
    wf = (HERE / "proposed-workflow-steps.yml").read_text(encoding="utf-8")
    probe = (HERE / "test-poster-state.yml.proposed").read_text(encoding="utf-8")
    check("S12b: the proposed save step runs even when the post step failed, but not when restore failed", "if: always() && steps.restore.outcome == 'success'" in wf)
    check("S12b: the real-GitHub probe runs the gate on a throwaway branch and never force-pushes", "poster_gate.py claim" in probe and "push -f" not in probe and "--force" not in probe and "STATE_BRANCH: poster-state-test" in probe)
    check("S12b: the probe says it must run after protection and that a dry run does not exercise the push", "ONLY AFTER main is protected" in probe and "does NOT exercise" in probe)

    # ------------------------------------------------------------ S13: state model rules (unit)
    sys.path.insert(0, str(HERE))
    import poster_gate as g
    P = lambda d: {"id": "1", "permalink": "x", "at": d}
    m = g.merge({"posted": {"a": P("1")}, "claims": {"a": {"status": "posted", "at": "1"}}}, {"posted": {"b": P("2")}, "claims": {"b": {"status": "claimed", "at": "2"}}})
    check("S13: merge keeps every post and every claim from both sides", set(m["posted"]) == {"a", "b"} and set(m["claims"]) == {"a", "b"})
    m = g.merge({"posted": {}, "claims": {"a": {"status": "released", "at": "9"}}}, {"posted": {}, "claims": {"a": {"status": "claimed", "at": "1"}}})
    check("S13: merge never lets an older 'claimed' be erased by a 'released' it did not see (higher status wins)", m["claims"]["a"]["status"] == "claimed")
    m = g.merge({"posted": {"a": P("1")}, "claims": {"a": {"status": "claimed", "at": "1"}}}, {"posted": {}, "claims": {}})
    check("S13: a claim cannot contradict a recorded post (upgraded to posted)", m["claims"]["a"]["status"] == "posted")
    m = g.merge({"posted": {"a": P("tip")}}, {"posted": {"a": P("local")}})
    check("S13: for the same day the authoritative (first) record wins", m["posted"]["a"]["at"] == "tip")
    check("S13: an old-format file (no claims key) is accepted", g.normalise({"posted": {}})["claims"] == {})
    check("S13: the file written has no claims key while there are none (identical to the old format)", '"claims"' not in g.dump({"posted": {}, "claims": {}}))
    bad = []
    for v in ({"posted": []}, {"posted": {}, "claims": []}, [], "x"):
        try:
            g.normalise(v); bad.append(v)
        except g.GateError:
            pass
    check("S13: malformed state is rejected, never repaired silently", not bad, str(bad))

print(f"\n{sum(results)}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
