#!/usr/bin/env python3
"""Run every Guardian eval and test suite, print a summary, and (with --log FILE) save the full output.

  python3 agents/03-guardian/run_evals.py [--log agents/03-guardian/eval-log.txt]

Exit 0 only if every suite passes. Nothing here needs the network or any secret.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
REPO = Path(__file__).resolve().parents[2]
SUITES = [
    ("risk-classify", ".claude/skills/risk-classify/evals/run_evals.py"),
    ("secrets-hygiene", ".claude/skills/secrets-hygiene/evals/run_evals.py"),
    ("preflight-brief", ".claude/skills/preflight-brief/evals/run_evals.py"),
    ("rollback-plan", ".claude/skills/rollback-plan/evals/run_evals.py"),
    ("skill-vetting", ".claude/skills/skill-vetting/evals/run_evals.py"),
    ("hooks", "agents/03-guardian/hooks/test_hooks.py"),
    ("poster-state (simulation)", "agents/03-guardian/poster-state/test_poster_state.py"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log")
    a = ap.parse_args()
    out, rows, ok_all = [], [], True
    for name, rel in SUITES:
        p = subprocess.run([sys.executable, str(REPO / rel)], cwd=REPO, capture_output=True, text=True)
        text = p.stdout + (("\n[stderr]\n" + p.stderr) if p.stderr.strip() else "")
        m = re.search(r"(\d+)/(\d+) checks passed", p.stdout)
        if m:
            passed, total = int(m.group(1)), int(m.group(2))
        else:  # the first two skills print "N passed, M failed"
            m = re.search(r"(\d+) passed, (\d+) failed", p.stdout)
            passed, total = (int(m.group(1)), int(m.group(1)) + int(m.group(2))) if m else (0, 0)
        ok = p.returncode == 0 and m is not None and passed == total
        ok_all &= ok
        rows.append((name, passed, total, ok))
        out.append(f"===== {name}  ({rel}) =====\n{text}")
    summary = ["", "Summary"] + [f"  {'PASS' if ok else 'FAIL'}  {n}: {p}/{t}" for n, p, t, ok in rows]
    summary.append(f"  TOTAL: {sum(r[1] for r in rows)}/{sum(r[2] for r in rows)}")
    print("\n".join(summary))
    if a.log:
        Path(a.log).write_text("\n".join(out) + "\n" + "\n".join(summary) + "\n", encoding="utf-8")
    for n, p, t, ok in rows:
        if not ok:
            print(f"Suite failed: {n}", file=sys.stderr)
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
