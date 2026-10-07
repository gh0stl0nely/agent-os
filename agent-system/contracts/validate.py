#!/usr/bin/env python3
"""Validate agent-system JSON against the contracts.

Usage:
  python3 validate.py                      run the bundled examples (CI-style self test)
  python3 validate.py <schema-stem> FILE   validate FILE against <schema-stem>.schema.json
                                           (claim-ledger | knowledge-record | agent-envelope)
FILE may hold one JSON object or a JSON Lines file (one object per line).

Self test rule: examples/<stem>.valid*.json must pass; examples/<stem>.invalid*.json must fail.
Needs: pip install jsonschema (add rfc3339-validator to also check date-time formats).
Exit code 0 = all as expected, 1 = a mismatch.
"""
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

HERE = Path(__file__).resolve().parent
STEMS = ["claim-ledger", "knowledge-record", "agent-envelope"]


def validator(stem):
    schema = json.loads((HERE / f"{stem}.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def load_objects(path):
    text = Path(path).read_text(encoding="utf-8").strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]


def errors_for(v, obj):
    return sorted(v.iter_errors(obj), key=lambda e: list(e.path))


def self_test():
    bad = 0
    for stem in STEMS:
        v = validator(stem)
        for path in sorted((HERE / "examples").glob(f"{stem}.*.json")):
            expect_valid = ".valid" in path.name and ".invalid" not in path.name
            errs = [e for obj in load_objects(path) for e in errors_for(v, obj)]
            ok = (not errs) if expect_valid else bool(errs)
            print(f"{'PASS' if ok else 'FAIL'}  {path.name}  (expected {'valid' if expect_valid else 'invalid'})")
            if not ok:
                bad += 1
                for e in errs[:3]:
                    print(f"      {list(e.path)}: {e.message}")
    return 1 if bad else 0


def check_file(stem, path):
    if stem not in STEMS:
        sys.exit(f"unknown schema '{stem}', choose one of {STEMS}")
    v = validator(stem)
    bad = 0
    for i, obj in enumerate(load_objects(path), 1):
        errs = errors_for(v, obj)
        if errs:
            bad += 1
            print(f"object {i}: INVALID")
            for e in errs:
                print(f"  {list(e.path)}: {e.message}")
        else:
            print(f"object {i}: ok")
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.exit(self_test())
    if len(sys.argv) == 3:
        sys.exit(check_file(sys.argv[1], sys.argv[2]))
    sys.exit(__doc__)
