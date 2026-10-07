#!/usr/bin/env python3
"""Run every Verifier skill's evals: .claude/skills/<skill>/evals/cases.json.

Each file looks like {"skill": "...", "cases": [case, ...]}. A case is {"id", "kind", "why", "steps": [step, ...]};
a case with the step keys at its top level is a one-step case. A step is:

  cmd            list of strings; placeholders {skill} (the skill folder), {fx} (its fixtures folder), {tmp} (a fresh
                 folder for this case), {repo} (repository root)
  expect_exit    exit code the command must return (default 0)
  stdout_json    list of assertions on the JSON the command printed
  files          {"path with placeholders": [assertions]}: assertions on a JSON or JSON Lines file the command wrote
  validate       [{"schema": "claim-ledger", "file": "..."}]: the file must pass agent-system/contracts/validate.py
  validate_rejects  {"schema": ..., "file": ..., "min_rejected": N}: every object in the file must be rejected by the
                 contract validator (counted per object, so 100% rejection is measured, not assumed)
  text_contains / text_absent   strings that must (not) appear in stdout+stderr
  file_text_absent  [{"files": [...], "strings": [...]}]: none of the strings may appear in any of the files
  json_equal     [{"a": file, "b": file, "drop_keys": [...]}]: two JSON files must be equal once those keys are dropped

An assertion is {"path": "claims[claim_id=C-1].result", "equals" | "not_equals" | "in" | "contains" | "exists" | "len" |
"regex": value}. Paths use dots, [N] for an index and [key=value] to pick a list item by a field.

Usage: run_evals.py [--skill NAME] [--case ID] [--json] [--keep]
Exit code: 0 all pass, 1 at least one fails.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / ".claude" / "skills"
sys.path.insert(0, str(REPO / "agents" / "02-verifier" / "lib"))
import vlib  # noqa: E402

TOKEN = re.compile(r"([^.\[\]]*)((?:\[[^\]]*\])*)")
MISSING = object()


def get_path(obj, path):
    cur = obj
    for part in path.split("."):
        m = TOKEN.fullmatch(part)
        if not m:
            return MISSING
        name, idxs = m.group(1), re.findall(r"\[([^\]]*)\]", m.group(2))
        if name:
            if not isinstance(cur, dict) or name not in cur:
                return MISSING
            cur = cur[name]
        for ix in idxs:
            if re.fullmatch(r"-?\d+", ix):
                i = int(ix)
                if not isinstance(cur, list) or not -len(cur) <= i < len(cur):
                    return MISSING
                cur = cur[i]
            elif "=" in ix:
                k, v = ix.split("=", 1)
                found = [x for x in cur if isinstance(x, dict) and str(x.get(k)) == v] if isinstance(cur, list) else []
                if not found:
                    return MISSING
                cur = found[0]
            else:
                return MISSING
    return cur


def check_assertion(obj, a):
    got = get_path(obj, a["path"])
    if "exists" in a:
        ok = (got is not MISSING) == bool(a["exists"])
        return ok, f"{a['path']} exists={got is not MISSING}, wanted {a['exists']}"
    if got is MISSING:
        return False, f"{a['path']} not found"
    if "equals" in a:
        return got == a["equals"], f"{a['path']} = {got!r}, wanted {a['equals']!r}"
    if "not_equals" in a:
        return got != a["not_equals"], f"{a['path']} = {got!r}, wanted anything but {a['not_equals']!r}"
    if "in" in a:
        return got in a["in"], f"{a['path']} = {got!r}, wanted one of {a['in']!r}"
    if "contains" in a:
        ok = (a["contains"] in got) if isinstance(got, (str, list, dict)) else False
        return ok, f"{a['path']} = {got!r}, wanted it to contain {a['contains']!r}"
    if "len" in a:
        return isinstance(got, (list, str, dict)) and len(got) == a["len"], f"len({a['path']}) = {len(got) if hasattr(got, '__len__') else got!r}, wanted {a['len']}"
    if "regex" in a:
        return isinstance(got, str) and re.search(a["regex"], got) is not None, f"{a['path']} = {got!r}, wanted match {a['regex']!r}"
    return False, f"assertion has no operator: {a}"


def load_any(path):
    text = Path(path).read_text(encoding="utf-8").strip()
    if str(path).endswith(".jsonl"):  # always a list, even for a single row
        return [json.loads(l) for l in text.splitlines() if l.strip()]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(l) for l in text.splitlines() if l.strip()]


def drop(obj, keys):
    if isinstance(obj, dict):
        return {k: drop(v, keys) for k, v in obj.items() if k not in keys}
    if isinstance(obj, list):
        return [drop(v, keys) for v in obj]
    return obj


def run_step(step, env, fails):
    def sub(s):  # replace only the four known placeholders, so JSON braces in arguments are left alone
        if not isinstance(s, str):
            return s
        for k in ("skill", "fx", "tmp", "repo"):
            s = s.replace("{" + k + "}", env[k])
        return s
    cmd = [sub(c) for c in step["cmd"]]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=env["repo"], timeout=300)
    text = p.stdout + p.stderr
    if p.returncode != step.get("expect_exit", 0):
        fails.append(f"exit code {p.returncode}, wanted {step.get('expect_exit', 0)}; output: {text.strip()[:300]}")
    for s in step.get("text_contains", []):
        if sub(s) not in text:
            fails.append(f"output lacks text {s!r}")
    for s in step.get("text_absent", []):
        if sub(s) in text:
            fails.append(f"output contains text that must be absent: {s!r}")
    if step.get("stdout_json"):
        try:
            data = json.loads(p.stdout)
        except json.JSONDecodeError as e:
            fails.append(f"stdout is not JSON ({e})")
            data = None
        for a in step["stdout_json"] if data is not None else []:
            ok, msg = check_assertion(data, a)
            if not ok:
                fails.append(msg)
    for fpath, asserts in (step.get("files") or {}).items():
        fp = Path(sub(fpath))
        if not fp.is_file():
            fails.append(f"expected file was not written: {fp.name}")
            continue
        data = load_any(fp)
        for a in asserts:
            ok, msg = check_assertion(data, a)
            if not ok:
                fails.append(f"{fp.name}: {msg}")
    for v in step.get("validate", []):
        fp = sub(v["file"])
        r = subprocess.run([sys.executable, str(REPO / "agent-system/contracts/validate.py"), v["schema"], fp],
                           capture_output=True, text=True, cwd=env["repo"])
        if r.returncode != 0:
            fails.append(f"{Path(fp).name} does not fit {v['schema']}: {(r.stdout + r.stderr).strip()[:300]}")
    if step.get("validate_rejects"):
        v = step["validate_rejects"]
        fp = sub(v["file"])
        objs = load_any(fp)
        objs = objs if isinstance(objs, list) else [objs]
        tmp = Path(env["tmp"]) / "single.json"
        accepted = []
        for i, o in enumerate(objs):
            tmp.write_text(json.dumps(o), encoding="utf-8")
            r = subprocess.run([sys.executable, str(REPO / "agent-system/contracts/validate.py"), v["schema"], str(tmp)],
                               capture_output=True, text=True, cwd=env["repo"])
            if r.returncode == 0:
                accepted.append(o.get("claim_id", i) if isinstance(o, dict) else i)
        if len(objs) < v.get("min_rejected", 1):
            fails.append(f"only {len(objs)} object(s) in {Path(fp).name}, wanted at least {v.get('min_rejected', 1)}")
        if accepted:
            fails.append(f"the contract validator accepted {len(accepted)} of {len(objs)} objects that must be rejected: {accepted}")
    for fa in step.get("file_text_absent", []):
        for fpath in fa["files"]:
            fp = Path(sub(fpath))
            body = fp.read_text(encoding="utf-8") if fp.is_file() else ""
            for needle in fa["strings"]:
                if needle in body:
                    fails.append(f"{fp.name} contains text that must be absent: {needle!r}")
    for je in step.get("json_equal", []):
        a, b = load_any(sub(je["a"])), load_any(sub(je["b"]))
        keys = set(je.get("drop_keys", []))
        if drop(a, keys) != drop(b, keys):
            fails.append(f"{Path(sub(je['a'])).name} and {Path(sub(je['b'])).name} differ after dropping {sorted(keys)}")
    return p


def run_case(skill, case, keep):
    tmp = Path(tempfile.mkdtemp(prefix="vev-"))
    env = {"skill": str(SKILLS / skill), "fx": str(SKILLS / skill / "fixtures"), "tmp": str(tmp), "repo": str(REPO)}
    steps = case.get("steps") or [case]
    fails = []
    try:
        for i, step in enumerate(steps):
            before = len(fails)
            run_step(step, env, fails)
            for k in range(before, len(fails)):
                fails[k] = (f"step {i + 1}: " if len(steps) > 1 else "") + fails[k]
    except Exception as e:  # a harness error is a failed case, loudly
        fails.append(f"harness error: {type(e).__name__}: {e}")
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
    return fails


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skill")
    ap.add_argument("--case")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--keep", action="store_true", help="keep the temp folders (their paths are printed)")
    a = ap.parse_args()
    results, kinds_by_skill = [], {}
    for f in sorted(SKILLS.glob("*/evals/cases.json")):
        skill = f.parent.parent.name
        if a.skill and a.skill != skill:
            continue
        spec = json.loads(f.read_text(encoding="utf-8"))
        for case in spec["cases"]:
            if a.case and a.case != case["id"]:
                continue
            fails = run_case(skill, case, a.keep)
            results.append({"skill": skill, "id": case["id"], "kind": case.get("kind", ""), "passed": not fails, "failures": fails})
            kinds_by_skill.setdefault(skill, set()).add(case.get("kind", ""))
    if not results:
        sys.exit("no eval cases found")
    required = {"normal", "missing-data", "seeded-error", "adversarial"}
    gaps = {s: sorted(required - k) for s, k in kinds_by_skill.items() if not a.case and required - k}
    if a.json:
        print(json.dumps({"results": results, "kind_gaps": gaps}, indent=2))
    else:
        for r in results:
            print(f"{'PASS' if r['passed'] else 'FAIL'}  {r['skill']:22} {r['id']:34} [{r['kind']}]")
            for m in r["failures"]:
                print(f"        - {m}")
        n = sum(r["passed"] for r in results)
        print(f"\n{n}/{len(results)} eval cases passed.")
        for s, g in gaps.items():
            print(f"GAP: {s} has no case of kind: {', '.join(g)}")
    sys.exit(0 if all(r["passed"] for r in results) and not gaps else 1)


if __name__ == "__main__":
    main()
