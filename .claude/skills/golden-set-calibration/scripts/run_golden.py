#!/usr/bin/env python3
"""Run the golden set and report how many seeded errors the Verifier catches, per error type and per layer.

Each case is audited twice with a fixed clock: code only (no model judgments) and with judgments (the recorded
builder replay, or fresh ones from --judgments). A seeded error counts as caught only if the claim did not pass AND
one of the case's expected reason codes is on it. A claim that is merely blocked for lack of a judgment is not a catch.

Usage:
  run_golden.py [--cases DIR] [--judgments FILE] [--save LABEL] [--compare latest|LABEL] [--json]
                [--simulate-broken recompute|structure]
Exit code: 0 ok; 1 if a structural type is below 100% caught by code alone, any code-layer case is missed by code alone,
a control failed, or a case errored.
"""
import argparse
import copy
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
SK = HERE.parents[2]
sys.path.insert(0, str(REPO / "agents" / "02-verifier" / "lib"))
for d in ("claim-evidence-audit", "recompute-in-code", "source-check", "adversarial-review"):
    sys.path.insert(0, str(SK / d / "scripts"))
import audit as audit_mod  # noqa: E402
import recompute  # noqa: E402
import structure_check  # noqa: E402
import vlib  # noqa: E402

GOLDEN = REPO / "agents" / "02-verifier" / "golden"
RUBRICS = REPO / "agents" / "02-verifier" / "rubrics"
FIXED_NOW = "2026-10-07T12:00:00-04:00"
STRUCTURAL = ["missing_evidence", "verified_without_evidence", "assumed_status", "malformed_row"]
CONTROL_TYPES = ("control", "injection_ignored")
PREFIX = "@sha256:"


def resolve_specs(specs, root):
    out = {}
    for s in specs or []:
        s = copy.deepcopy(s)
        for inp in s.get("inputs", []):
            v = inp.get("sha256")
            if isinstance(v, str) and v.startswith(PREFIX):
                inp["sha256"] = vlib.sha256_file(Path(root) / v[len(PREFIX):])
        out[s["claim_id"]] = s
    return out


def run_once(case, root, rubric, judgments):
    res = audit_mod.audit(copy.deepcopy(case["envelope"]), copy.deepcopy(case["ledger"]), str(root), rubric,
                          copy.deepcopy(judgments), resolve_specs(case.get("specs"), root), vlib.now_from(FIXED_NOW))
    cid = case["expect"]["claim_id"]
    claim = next((c for c in res["report"]["claims"] if c["claim_id"] == cid), None)
    if claim is None:  # the claim is not in the report at all: the audit did not look at it
        return {"audit_status": res["status"], "result": "absent", "reason_codes": [], "flags": []}
    return {"audit_status": res["status"], "result": claim["result"], "reason_codes": list(claim["reason_codes"]),
            "flags": [f.get("type") for f in claim.get("flags", [])]}


def judge_outcome(case, out):
    """caught / missed / wrong_reason / passed_clean / false_positive for one run."""
    exp = case["expect"]
    if case["error_type"] in CONTROL_TYPES:
        ok = out["result"] == "pass" and (not exp.get("flag_present") or exp["flag_present"] in out["flags"])
        return "passed_clean" if ok else ("pending" if out["result"] == "pending" else "false_positive")
    if out["result"] == "pass":
        return "missed"
    if out["result"] == "pending":
        return "pending"
    return "caught" if set(out["reason_codes"]) & set(exp["reason_codes_any"]) else "wrong_reason"


def run_case(case, judgments_override):
    rubric = vlib.load_rubric(RUBRICS / f"{case['rubric']}.md")
    root = GOLDEN / "root"
    rec = {"id": case["id"], "error_type": case["error_type"], "layer": case["layer"]}
    try:
        code = run_once(case, root, rubric, None)
        # fresh judgments replace the replay entirely; a case missing from the file gets none (so it reports pending)
        jd = judgments_override.get(case["id"]) if judgments_override is not None else case.get("judgments")
        withj = run_once(case, root, rubric, jd)
    except Exception as e:  # a crash is a result, not a reason to stop measuring
        rec.update({"code_only": {"outcome": "error", "error": f"{type(e).__name__}: {e}"},
                    "with_judgments": {"outcome": "error", "error": f"{type(e).__name__}: {e}"}})
        return rec
    rec["code_only"] = {**code, "outcome": judge_outcome(case, code)}
    rec["with_judgments"] = {**withj, "outcome": judge_outcome(case, withj)}
    return rec


def summarise(records):
    types = {}
    for r in records:
        t = types.setdefault(r["error_type"], {"cases": 0, "layers": {}, "ids": []})
        t["cases"] += 1
        t["ids"].append(r["id"])
        L = t["layers"].setdefault(r["layer"], {"cases": 0, "caught_code_only": 0, "caught_with_judgments": 0})
        L["cases"] += 1
        good = ("caught", "passed_clean")
        L["caught_code_only"] += r["code_only"]["outcome"] in good
        L["caught_with_judgments"] += r["with_judgments"]["outcome"] in good
    for t in types.values():
        t["caught_code_only"] = sum(L["caught_code_only"] for L in t["layers"].values())
        t["caught_with_judgments"] = sum(L["caught_with_judgments"] for L in t["layers"].values())
        t["needs_model_layer"] = any(l in ("model-judged-replay",) for l in t["layers"])
    return types


def fmt_rate(n, d):
    return f"{n}/{d} ({100 * n // d if d else 0}%)"


def report(records, types, label_judge):
    lines = []
    lines.append(f"Golden set run. Clock fixed at {FIXED_NOW}. Judgments: {label_judge}.")
    lines.append("")
    lines.append(f"{'error type':27}{'cases':>6}  {'code alone':>14}  {'with judgments':>16}  note")
    for name in sorted(types, key=lambda k: (k in CONTROL_TYPES, k)):
        t = types[name]
        ctl = name in CONTROL_TYPES
        n = t["cases"]
        if t["needs_model_layer"]:
            model_n = sum(L["cases"] for l, L in t["layers"].items() if l == "model-judged-replay")
            code_n = n - model_n
            code_c = sum(L["caught_code_only"] for l, L in t["layers"].items() if l != "model-judged-replay")
            code_txt = f"{fmt_rate(code_c, code_n)}" if code_n else "n/a"
            note = f"{model_n} case(s) not measurable by code alone ({'fresh judgments' if label_judge.startswith('fresh') else 'builder replay, non-independent'})"
        elif ctl:
            code_txt = "n/a"
            note = "clean cases: counted as passed when they pass; they need the adversarial judgment, so code alone cannot finish them"
        else:
            code_txt = fmt_rate(t["caught_code_only"], n)
            note = ""
        lines.append(f"{name:27}{n:>6}  {code_txt:>14}  {fmt_rate(t['caught_with_judgments'], n):>16}  {note}")
    lines.append("")
    problems = []
    for name in STRUCTURAL:
        if name in types and types[name]["caught_code_only"] < types[name]["cases"]:
            missed = [r["id"] for r in records if r["error_type"] == name and r["code_only"]["outcome"] != "caught"]
            problems.append(f"structural type {name} below 100% by code alone; not caught: {', '.join(missed)}")
    for name in STRUCTURAL:
        if name not in types:
            problems.append(f"structural type {name} has no cases")
    for r in records:
        if r["layer"] == "code" and r["error_type"] not in CONTROL_TYPES and r["code_only"]["outcome"] != "caught" \
                and r["error_type"] not in STRUCTURAL:
            problems.append(f"{r['id']} ({r['error_type']}) is a code-layer case but code alone did not catch it: "
                            f"{r['code_only'].get('outcome')} {r['code_only'].get('reason_codes')}")
        if r["error_type"] in CONTROL_TYPES and r["with_judgments"]["outcome"] != "passed_clean":
            problems.append(f"control {r['id']} did not pass clean: {r['with_judgments']}")
        for k in ("code_only", "with_judgments"):
            if r[k]["outcome"] == "error":
                problems.append(f"{r['id']} crashed ({k}): {r[k].get('error')}")
    not_caught = [(r["id"], r["error_type"], r["with_judgments"]["outcome"], r["with_judgments"].get("reason_codes"))
                  for r in records if r["error_type"] not in CONTROL_TYPES and r["with_judgments"]["outcome"] != "caught"]
    for cid, typ, outc, rc in not_caught:
        lines.append(f"not caught with judgments: {cid} ({typ}): {outc} {rc}")
    seeded = [r for r in records if r["error_type"] not in CONTROL_TYPES]
    ctl = [r for r in records if r["error_type"] in CONTROL_TYPES]
    code_layer = [r for r in seeded if r["layer"] in ("code",)]
    lines.append("")
    lines.append(f"Seeded errors: {len(seeded)}. Caught by code alone in the 'code' layer: "
                 f"{fmt_rate(sum(r['code_only']['outcome'] == 'caught' for r in code_layer), len(code_layer))}. "
                 f"Caught with judgments (all layers): {fmt_rate(sum(r['with_judgments']['outcome'] == 'caught' for r in seeded), len(seeded))}.")
    lines.append(f"Controls: {len(ctl)}. Passed clean: {sum(r['with_judgments']['outcome'] == 'passed_clean' for r in ctl)}. "
                 f"False positives: {sum(r['with_judgments']['outcome'] == 'false_positive' for r in ctl)}.")
    return lines, problems


def compare(prev, records, types):
    out = []
    pt = prev.get("types", {})
    for name, t in sorted(types.items()):
        p = pt.get(name)
        if not p:
            out.append(f"{name}: new type, no earlier measurement")
            continue
        for key in ("caught_code_only", "caught_with_judgments"):
            a, b = p.get(key), t[key]
            if a is not None and a != b:
                out.append(f"{name} {key}: {a} -> {b} of {t['cases']}" + ("  (FELL)" if b < a else "  (rose)"))
    prev_cases = {c["id"]: c for c in prev.get("cases", [])}
    for r in records:
        pc = prev_cases.get(r["id"])
        if not pc:
            out.append(f"{r['id']}: new case")
            continue
        for k in ("code_only", "with_judgments"):
            if pc[k]["outcome"] != r[k]["outcome"]:
                out.append(f"{r['id']} {k}: {pc[k]['outcome']} -> {r[k]['outcome']}")
    return out or ["no change from the earlier run"]


def load_history(spec):
    hist = GOLDEN / "history"
    if not hist.is_dir():
        return None, None
    files = sorted(hist.glob("*.json"), key=lambda p: json.loads(p.read_text())["saved_at"])
    if spec == "latest":
        return (json.loads(files[-1].read_text()), files[-1].name) if files else (None, None)
    p = hist / f"{spec}.json"
    return (json.loads(p.read_text()), p.name) if p.is_file() else (None, None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", default=str(GOLDEN / "cases"))
    ap.add_argument("--judgments", help="JSON file: case id -> {source_support: [...], adversarial: [...]} from a fresh session")
    ap.add_argument("--save", metavar="LABEL")
    ap.add_argument("--compare", metavar="latest|LABEL")
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    ap.add_argument("--simulate-broken", choices=["recompute", "structure"],
                    help="deliberately disable one checker to prove this runner reports it (never saved)")
    a = ap.parse_args()
    if a.simulate_broken and a.save:
        sys.exit("--simulate-broken results are never saved")

    prev, prev_name = (load_history(a.compare) if a.compare else (None, None))
    if a.compare and prev is None:
        print(f"no earlier measurement found for '{a.compare}'; nothing to compare with", file=sys.stderr)

    if a.simulate_broken == "recompute":
        recompute.compare = lambda claimed, recomputed, tol: {"claimed": str(claimed), "recomputed": str(recomputed),
                                                              "difference": "0", "classification": "exact", "result": "pass"}
    elif a.simulate_broken == "structure":
        structure_check.check_structure = lambda envelope, rows, now: []

    override = vlib.read_json(a.judgments) if a.judgments else None
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(a.cases).glob("*.json"))]
    if not cases:
        sys.exit(f"no cases found in {a.cases}")
    records = [run_case(c, override) for c in cases]
    types = summarise(records)
    label = "fresh judgments from " + a.judgments if override is not None else "recorded builder replay (non-independent)"
    lines, problems = report(records, types, label)
    if a.simulate_broken:
        lines.insert(0, f"*** SIMULATED BREAKAGE: {a.simulate_broken} checker disabled on purpose; this is a test of the runner ***")
    if a.json:
        print(json.dumps({"cases": records, "types": types, "problems": problems}, indent=2, ensure_ascii=False))
    else:
        print("\n".join(lines))
        if prev is not None:
            print(f"\nCompared with {prev_name}:")
            for l in compare(prev, records, types):
                print("  " + l)
        if problems:
            print("\nPROBLEMS:")
            for p in problems:
                print("  - " + p)
    if a.save:
        hist = GOLDEN / "history"
        hist.mkdir(exist_ok=True)
        saved = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (hist / f"{a.save}.json").write_text(json.dumps(
            {"label": a.save, "saved_at": saved, "clock": FIXED_NOW, "judgments": label, "cases": records, "types": types,
             "problems": problems}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nsaved golden/history/{a.save}.json")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
