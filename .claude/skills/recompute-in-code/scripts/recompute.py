#!/usr/bin/env python3
"""Re-run the script a number claim cites and compare its output with the claimed value.

The script is always re-run, never trusted. The tolerance comes from the rubric (via the caller),
never from the producer, so a producer cannot pass a wrong number by declaring a loose tolerance.

Usage:
  recompute.py --claim claim.json --spec spec.json --root DIR [--tolerance-json '{"rounding_decimals":2}']
Exit code: 0 pass, 1 fail, 2 unverifiable.

Spec file (one per claim):
  {"claim_id": "C-...", "script": "scripts/sum_lines.py", "args": ["data/invoice.csv"],
   "inputs": [{"path": "data/invoice.csv", "sha256": "<hex>"}], "timeout_s": 20}
The script is run as `python3 -I <script> <args>` inside DIR and must print JSON to stdout:
  {"value": "300.00", "unit": "CAD"}      (value as a string or number; unit optional)
Limits: this is not a sandbox. It refuses scripts and arguments outside DIR, scrubs the
environment, and applies a timeout. Vetting the script itself belongs to the Guardian.
"""
import argparse
import json
import os
import subprocess
import sys
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "agents" / "02-verifier" / "lib"))
import vlib  # noqa: E402


def compare(claimed, recomputed, tol):
    """Compare two Decimals. difference = claimed - recomputed.

    exact          identical
    rounding       claimed equals the recomputed value rounded to tol['rounding_decimals'] places
                   (either half-up or half-even, they differ only on exact ties)
    within_abs     |difference| <= tol['abs']
    within_rel     |difference| <= tol['rel'] * |recomputed|
    material       none of the above: fail
    """
    diff = claimed - recomputed
    out = {"claimed": str(claimed), "recomputed": str(recomputed), "difference": str(diff)}
    if diff == 0:
        return {**out, "classification": "exact", "result": "pass"}
    tol = tol or {}
    d = tol.get("rounding_decimals")
    if isinstance(d, int) and d >= 0:
        q = Decimal(1).scaleb(-d)
        if claimed in (recomputed.quantize(q, rounding=ROUND_HALF_UP), recomputed.quantize(q, rounding=ROUND_HALF_EVEN)):
            return {**out, "classification": "rounding", "result": "pass"}
    a = vlib.to_decimal(tol.get("abs"))
    if a is not None and abs(diff) <= a:
        return {**out, "classification": "within_abs", "result": "pass"}
    r = vlib.to_decimal(tol.get("rel"))
    if r is not None and recomputed != 0 and abs(diff) <= r * abs(recomputed):
        return {**out, "classification": "within_rel", "result": "pass"}
    pct = None
    if recomputed != 0:
        pct = str((abs(diff) / abs(recomputed) * 100).quantize(Decimal("0.01"))) + "%"
    return {**out, "classification": "material", "result": "fail", "relative_difference": pct}


def _unverifiable(reasoning, code, missing):
    return vlib.mk_result(reasoning, [], "unverifiable", code, missing)


def recompute_claim(root, claim, spec, tolerance, evidence_script=None):
    """Return a standard check result (see vlib.mk_result)."""
    reasoning, checks = [], []
    cid = claim.get("claim_id")
    if not isinstance(spec, dict):
        return _unverifiable([f"No recompute spec was supplied for {cid}."], "no_spec",
                             [f"{cid}: supply a recompute spec (script, args, inputs with sha256)"])
    if spec.get("claim_id") != cid:
        return _unverifiable([f"The spec is for {spec.get('claim_id')}, not {cid}."], "spec_mismatch",
                             [f"{cid}: supply the spec for this claim"])
    script = spec.get("script")
    if evidence_script and script != evidence_script:
        r = vlib.mk_result([f"The claim's evidence cites script {evidence_script!r} but the spec runs {script!r}."],
                           [{"name": "spec_matches_evidence", "outcome": "fail"}], "fail", "spec_script_mismatch",
                           [f"{cid}: make the spec run the same script the evidence cites"])
        return r
    sp = vlib.resolve_inside(root, script)
    if sp is None or not sp.is_file() or sp.suffix != ".py":
        return _unverifiable([f"Script {script!r} is missing, not a .py file, or outside the allowed root."],
                             "script_not_allowed", [f"{cid}: point the evidence at a .py file inside the allowed root"])
    checks.append({"name": "script_inside_root", "outcome": "pass", "detail": str(sp.relative_to(Path(root).resolve()))})

    inputs = spec.get("inputs") or []
    if not inputs:
        return _unverifiable(["The spec lists no inputs, so the run is not reproducible from logged inputs."],
                             "inputs_not_logged", [f"{cid}: log every input file with its sha256 in the spec"])
    logged = set()
    for item in inputs:
        ip = vlib.resolve_inside(root, item.get("path"))
        if ip is None or not ip.is_file():
            return _unverifiable([f"Logged input {item.get('path')!r} is missing or outside the root."],
                                 "input_missing", [f"{cid}: provide input {item.get('path')}"])
        actual = vlib.sha256_file(ip)
        logged.add(item["path"])
        if actual != item.get("sha256"):
            r = vlib.mk_result([f"Input {item['path']} has sha256 {actual[:12]}..., the spec logged {str(item.get('sha256'))[:12]}...; "
                                "the data changed since the producer ran the script."],
                               checks + [{"name": "inputs_unchanged", "outcome": "fail", "detail": item["path"]}],
                               "fail", "input_changed",
                               [f"{cid}: re-run the script on the current data and update the claim, or restore the original input"])
            return r
    checks.append({"name": "inputs_unchanged", "outcome": "pass", "detail": f"{len(inputs)} input(s) match their logged sha256"})

    args = [str(a) for a in spec.get("args", [])]
    for a in args:
        if os.path.isabs(a) or ".." in Path(a).parts:
            return _unverifiable([f"Argument {a!r} is absolute or climbs out of the root."], "unsafe_argument",
                                 [f"{cid}: pass inputs as relative paths inside the root"])
        ap = vlib.resolve_inside(root, a)
        if ap is not None and ap.is_file() and a not in logged:
            return _unverifiable([f"Argument {a!r} is a file that the spec did not log with a sha256."],
                                 "input_not_logged", [f"{cid}: add {a} to the spec inputs with its sha256"])

    env = {"LC_ALL": "C.UTF-8", "PYTHONIOENCODING": "utf-8"}
    timeout = min(int(spec.get("timeout_s", 20)), 60)
    try:
        proc = subprocess.run([sys.executable, "-I", str(sp), *args], cwd=str(Path(root).resolve()), env=env,
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return _unverifiable([f"The script did not finish within {timeout}s."], "script_timeout",
                             [f"{cid}: make the script finish quickly or reduce its input"])
    if proc.returncode != 0:
        return _unverifiable([f"The script exited with code {proc.returncode}: {proc.stderr.strip()[:160]}"],
                             "script_error", [f"{cid}: fix the script so it runs cleanly on the logged inputs"])
    try:
        out = json.loads(proc.stdout, parse_float=Decimal)
        got = vlib.to_decimal(out["value"] if isinstance(out, dict) else out)
        got_unit = out.get("unit") if isinstance(out, dict) else None
    except (json.JSONDecodeError, KeyError, TypeError):
        got = None
    if got is None:
        return _unverifiable(["The script output was not JSON like {\"value\": ..., \"unit\": ...}."], "bad_output",
                             [f"{cid}: make the script print a JSON object with a numeric value"])
    checks.append({"name": "script_ran", "outcome": "pass", "detail": f"value {got}" + (f" {got_unit}" if got_unit else "")})

    claimed = vlib.to_decimal(claim.get("value"))
    if claimed is None:
        return _unverifiable(["The claim has no numeric value to compare."], "claim_value_missing",
                             [f"{cid}: state the value the claim asserts"])
    if got_unit and claim.get("unit") and str(got_unit).casefold() != str(claim["unit"]).casefold():
        r = vlib.mk_result([f"The script reports unit {got_unit!r} but the claim states {claim['unit']!r}."],
                           checks + [{"name": "unit_matches", "outcome": "fail"}], "fail", "unit_mismatch",
                           [f"{cid}: correct the unit or the script; the number may be right in the wrong unit"],
                           recomputed=str(got), claimed=str(claimed))
        return r
    cmp_ = compare(claimed, got, tolerance)
    checks.append({"name": "value_within_tolerance", "outcome": cmp_["result"], "detail": cmp_["classification"]})
    tol_txt = json.dumps(tolerance or {}) if tolerance else "exact (no tolerance in the rubric)"
    reasoning = [f"Re-ran {script} on {len(inputs)} logged input(s); it printed {got}.",
                 f"Claimed {claimed}; difference (claimed - recomputed) = {cmp_['difference']}; tolerance {tol_txt}.",
                 f"Classified as {cmp_['classification']}."]
    missing = []
    if cmp_["result"] == "fail":
        missing = [f"{cid}: claimed {claimed} but the script gives {got} (difference {cmp_['difference']}"
                   f"{', ' + cmp_['relative_difference'] if cmp_.get('relative_difference') else ''}); "
                   "correct the claim or show why the script is wrong"]
    return vlib.mk_result(reasoning, checks, cmp_["result"],
                          "recomputed_" + cmp_["classification"] if cmp_["result"] == "pass" else cmp_["classification"],
                          missing, numeric=cmp_)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--claim", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--tolerance-json", default="{}")
    a = ap.parse_args()
    claim = vlib.read_rows(a.claim)[0]
    spec = vlib.read_json(a.spec)
    ev = next((e for e in claim.get("evidence", []) if e.get("type") == "computation"), {})
    res = recompute_claim(a.root, claim, spec, json.loads(a.tolerance_json), ev.get("script"))
    print(vlib.dump(res), end="")
    sys.exit({"pass": 0, "fail": 1, "unverifiable": 2}[res["result"]])


if __name__ == "__main__":
    main()
