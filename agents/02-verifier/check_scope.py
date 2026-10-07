#!/usr/bin/env python3
"""Check that this branch only touches paths the Verifier role owns.

Compares the working tree and HEAD with a base (default origin/main, else main). Fails if any file was deleted or
modified, or any file outside the owned paths was added. The one allowed outside path is this role's own change
request under agent-system/change-requests/02-verifier-*.

Why: BUILD-PROTOCOL review step 1 ("the diff touches only the role's owned paths"). A tracked file of the live
Threads poster was once deleted by accident while cleaning up Python caches; this guard would have caught it.

Usage: check_scope.py [--base REF] [--repo DIR] | --selftest
Exit code: 0 ok (or no base to compare with: says so), 1 violation, 2 usage error.
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

OWNED = [r"^agents/02-verifier/", r"^knowledge/verification/", r"^agent-system/change-requests/02-verifier-",
         r"^\.claude/skills/(claim-evidence-audit|recompute-in-code|source-check|adversarial-review|golden-set-calibration)/"]


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def violations(repo, base):
    # the index and working tree against the base, so an unstaged deletion is seen as well as a committed one
    out = git(repo, "diff", "--name-status", "--no-renames", base).stdout
    bad = []
    for line in out.splitlines():
        status, _, path = line.partition("\t")
        owned = any(re.search(p, path) for p in OWNED)
        if status != "A":
            bad.append(f"{'deleted' if status == 'D' else 'modified'}: {path}")
        elif not owned:
            bad.append(f"added outside the owned paths: {path}")
    return bad


def find_base(repo, wanted):
    for ref in ([wanted] if wanted else ["origin/main", "main"]):
        if git(repo, "rev-parse", "--verify", "-q", ref).returncode == 0:
            return ref
    return None


def selftest():
    with tempfile.TemporaryDirectory() as d:
        run = lambda *a: subprocess.run(["git", "-C", d, *a], capture_output=True, text=True, check=True)
        run("init", "-q", "-b", "main")
        run("config", "user.email", "t@example.invalid")
        run("config", "user.name", "t")
        (Path(d) / "scripts").mkdir()
        (Path(d) / "scripts" / "poster.pyc").write_text("x")
        (Path(d) / "README.md").write_text("x")
        run("add", "-A")
        run("commit", "-q", "-m", "base")
        # clean: an owned file added
        (Path(d) / "agents" / "02-verifier").mkdir(parents=True)
        (Path(d) / "agents" / "02-verifier" / "a.py").write_text("x")
        run("add", "-A")
        ok = violations(d, "main")
        # violations: a deletion, a modification, an outside add
        (Path(d) / "scripts" / "poster.pyc").unlink()
        (Path(d) / "README.md").write_text("changed")
        (Path(d) / "elsewhere.txt").write_text("x")
        run("add", "-A")
        bad = violations(d, "main")
    expect = {"deleted: scripts/poster.pyc", "modified: README.md", "added outside the owned paths: elsewhere.txt"}
    if ok:
        print(f"selftest FAILED: a clean change was flagged: {ok}")
        return 1
    if set(bad) != expect:
        print(f"selftest FAILED: wanted {sorted(expect)}, got {sorted(bad)}")
        return 1
    print("selftest ok: a deletion, a modification and an outside add are flagged; an owned add is not")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base")
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[2]))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())
    base = find_base(a.repo, a.base)
    if base is None:
        print("no base branch (origin/main or main) to compare with; scope not checked")
        sys.exit(0)
    bad = violations(a.repo, base)
    if bad:
        print(f"{len(bad)} change(s) outside the Verifier's lane compared with {base}:")
        for b in bad:
            print("  - " + b)
        sys.exit(1)
    print(f"ok: every change compared with {base} is an addition inside the Verifier's owned paths")


if __name__ == "__main__":
    main()
