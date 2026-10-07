#!/usr/bin/env python3
"""Check that a rubric file has the fixed shape (see agents/02-verifier/rubrics/_SHAPE.md).

Usage: rubric_lint.py RUBRIC.md [RUBRIC2.md ...]
Exit code: 0 all fit, 1 at least one does not.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "agents" / "02-verifier" / "lib"))
import vlib  # noqa: E402


def main(paths):
    bad = 0
    for p in paths:
        r = vlib.load_rubric(p)
        if r["problems"]:
            bad += 1
            print(f"FAIL  {p}")
            for pr in r["problems"]:
                print(f"      - {pr}")
        else:
            print(f"ok    {p}  ({len(r['checks'])} checks, domain {r['config']['domain']})")
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
