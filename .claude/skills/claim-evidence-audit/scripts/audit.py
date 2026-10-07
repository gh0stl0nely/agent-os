#!/usr/bin/env python3
"""Claim-evidence audit: the Verifier's orchestrator.

Order of work (deterministic first, model second):
  1 structure   contract schemas + Verifier-only rules                       (structure_check.py)
  2 evidence    computation -> recompute; document/url/kb/owner -> source-check (recompute.py, source_check.py)
  3 injection   instruction-like text in claims and evidence is reported and ignored
  4 weaknesses  code-side scan (weakness_scan.py), then the model's adversarial judgment
  5 decision    a claim passes only if at least one evidence item was actually checked and passed, no item failed,
                and no blocking weakness was found. Anything that could not be checked is 'unverifiable', never a pass.

If the code checks already fail a claim, the audit finishes at once (no model tokens spent). Otherwise it stops with
phase 'awaiting_judgment' and writes judgment-request.json; rerun with --judgments to finish.

Usage:
  audit.py --envelope e.json --ledger l.jsonl --root DIR --rubric r.md --out OUTDIR
           [--specs specs.json] [--judgments judgments.json] [--now ISO] [--revision-to producer]
Exit code: 0 ok, 10 needs_revision, 11 blocked, 12 escalate, 20 awaiting_judgment, 2 internal error.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
SK = HERE.parents[2]
sys.path.insert(0, str(HERE.parents[4] / "agents" / "02-verifier" / "lib"))
for d in ("claim-evidence-audit", "recompute-in-code", "source-check", "adversarial-review"):
    sys.path.insert(0, str(SK / d / "scripts"))
import build_packet  # noqa: E402
import recompute  # noqa: E402
import source_check  # noqa: E402
import structure_check  # noqa: E402
import vlib  # noqa: E402
import weakness_scan  # noqa: E402

VERIFIER = "02-verifier"
EXIT = {"ok": 0, "needs_revision": 10, "blocked": 11, "escalate": 12, "awaiting_judgment": 20}


def load_specs(path):
    if not path:
        return {}
    data = vlib.read_json(path)
    if isinstance(data, dict) and "claim_id" in data:
        data = [data]
    if isinstance(data, dict):
        return data
    return {s.get("claim_id"): s for s in data}


def _adv_judgment(judgments, cid):
    """Return (judgment or None, problem or None)."""
    for j in (judgments or {}).get("adversarial", []):
        if j.get("claim_id") != cid:
            continue
        if not vlib.reasoning_precedes(j, "result") or j.get("result") not in ("clear", "weaknesses"):
            return None, "adversarial judgment is malformed: reasoning must come first, result must be clear or weaknesses"
        ws = j.get("weaknesses") or []
        if (j["result"] == "clear") != (len(ws) == 0):
            return None, "adversarial judgment contradicts itself: result and weaknesses list disagree"
        return j, None
    return None, None


def _judged_weaknesses(cid, j):
    out = []
    for w in j.get("weaknesses") or []:
        typ = w.get("type") if w.get("type") in weakness_scan.JUDGED_TYPES else "other"
        sev = "blocking" if typ in weakness_scan.BLOCKING_TYPES else "note"
        out.append({"type": typ, "severity": sev, "claim_id": cid, "why": str(w.get("why", "")),
                    "what_would_resolve": str(w.get("what_would_resolve", "")), "source": "judge"})
    return out


def evaluate_claim(row, rows, ctx):
    """Return the per-claim report entry. Key order puts reasoning before result."""
    cid = row.get("claim_id")
    rubric, now = ctx["rubric"], ctx["now"]
    rejects = [f for f in ctx["findings"] if f["claim_id"] == cid and f["severity"] == "reject"]
    base = {"claim_id": cid, "reasoning": [], "checks": [], "weaknesses": [], "result": None, "reason_codes": [],
            "missing_evidence": [], "flags": [], "passing_methods": []}
    if row.get("status") == "retired":
        base.update(result="skipped", reasoning=["Claim is retired; nothing to verify."])
        return base
    if rejects:
        base.update(result="invalid", reason_codes=sorted({f["code"] for f in rejects}),
                    reasoning=["Structure check rejected this row before any evidence was read."] + [f["detail"] for f in rejects][:6],
                    missing_evidence=[f"{cid}: fix {f['code']}: {f['detail']}" for f in rejects])
        return base
    if row.get("status") == "blocked":
        base.update(result="unverifiable", reason_codes=["producer_blocked"],
                    reasoning=[f"The producer already marked this claim blocked: {row.get('blocked_reason')}"],
                    missing_evidence=[f"{cid}: {row.get('blocked_reason')}"])
        return base

    for f in ctx["findings"]:
        if f["claim_id"] == cid and f["severity"] == "warn":
            base["flags"].append({"type": f["code"].lower(), "detail": f["detail"]})
    for h in vlib.scan_injection(row.get("claim", "")):
        base["flags"].append({"type": "possible_injection", "where": "claim text", **h})

    results = []
    for i, ev in enumerate(row["evidence"]):
        if ev["type"] == "computation":
            if row["kind"] != "number":
                res = vlib.mk_result(["Computation evidence on a claim that is not a number cannot be compared with a value."], [],
                                     "unverifiable", "computation_not_comparable",
                                     [f"{cid}: add a document or KB record that supports this claim"])
            else:
                spec = ctx["specs"].get(cid)
                if spec is not None and ev.get("script") and spec.get("script") != ev.get("script"):
                    res = vlib.mk_result([f"The recompute spec runs {spec.get('script')!r}, not the script this evidence item cites."], [],
                                         "unverifiable", "no_spec", [f"{cid}: supply a spec for script {ev.get('script')}"])
                else:
                    res = recompute.recompute_claim(ctx["root"], row, spec, vlib.tolerance_for(rubric, row.get("unit")), ev.get("script"))
        else:
            res = source_check.check_source(ctx["root"], row, i, ctx["judgments"], now, rubric["config"].get("max_age_days"))
        res["evidence_index"], res["evidence_type"] = i, ev["type"]
        results.append(res)
        base["checks"].append({"evidence_index": i, "evidence_type": ev["type"], "result": res["result"],
                               "reason_code": res["reason_code"], "checks": res["checks"]})
        base["reasoning"] += [f"evidence[{i}] ({ev['type']}): {t}" for t in res["reasoning"]]
        base["flags"] += res.get("flags", [])
        ctx["code_checks"][(cid, i)] = res

    fails = [r for r in results if r["result"] == "fail"]
    awaiting = [r for r in results if r["reason_code"] == "awaiting_judgment"]
    passes = [r for r in results if r["result"] == "pass"]
    det_w = weakness_scan.scan(row, rows, rubric)
    base["weaknesses"] += det_w
    blocking_det = [w for w in det_w if w["severity"] == "blocking"]

    if fails or blocking_det:
        base["result"] = "fail"
        base["reason_codes"] = sorted({r["reason_code"] for r in fails} | {w["type"] for w in blocking_det})
        base["missing_evidence"] = [m for r in fails for m in r["missing_evidence"]] + [
            f"{cid}: {w['why']}; {w['what_would_resolve']}" for w in blocking_det]
        base["reasoning"].append("At least one check failed, so the claim cannot pass.")
        return base
    unchecked = [r for r in results if r["result"] == "unverifiable" and r["reason_code"] != "awaiting_judgment"]
    if unchecked:
        # Every cited item has to be checkable. A real source next to a missing or unreadable one is not a pass:
        # the producer cited something the Verifier could not check, so the claim goes back with that item named.
        for r in unchecked:
            base["flags"].append({"type": "unverifiable_evidence", "evidence_index": r["evidence_index"],
                                  "evidence_type": r["evidence_type"], "reason_code": r["reason_code"]})
        base["result"] = "unverifiable"
        base["reason_codes"] = sorted({r["reason_code"] for r in unchecked} | {"unchecked_evidence_item"})
        base["missing_evidence"] = [m for r in unchecked for m in r["missing_evidence"]] or [
            f"{cid}: evidence[{r['evidence_index']}] could not be checked" for r in unchecked]
        base["reasoning"].append(
            f"{len(unchecked)} of {len(results)} cited evidence item(s) could not be checked "
            f"({', '.join('evidence[%d]: %s' % (r['evidence_index'], r['reason_code']) for r in unchecked)}). "
            "A claim does not pass while any item it cites is unchecked, whatever the other item(s) show.")
        return base
    if awaiting:
        base["result"] = "pending"
        base["reason_codes"] = ["awaiting_judgment"]
        base["reasoning"].append("Code checks passed so far; the model's support judgment is still needed.")
        return base
    if not passes:
        base["result"] = "unverifiable"
        base["reason_codes"] = sorted({r["reason_code"] for r in results}) or ["no_checkable_evidence"]
        base["missing_evidence"] = [m for r in results for m in r["missing_evidence"]] or [f"{cid}: no evidence could be checked"]
        base["reasoning"].append("No evidence item could be checked and passed, so the claim is unverifiable. It is not passed.")
        return base

    adv, problem = _adv_judgment(ctx["judgments"], cid)
    if adv is None:
        base["result"] = "pending"
        base["reason_codes"] = ["awaiting_adversarial_review" if not problem else "adversarial_judgment_malformed"]
        base["reasoning"].append(problem or "Evidence checks passed; adversarial review is still needed before a pass.")
        return base
    jw = _judged_weaknesses(cid, adv)
    base["weaknesses"] += jw
    base["reasoning"].append(f"Adversarial review ({adv.get('judge', 'unnamed')}): {adv['reasoning'].strip()}")
    jb = [w for w in jw if w["severity"] == "blocking"]
    if jb:
        base["result"] = "fail"
        base["reason_codes"] = sorted({w["type"] for w in jb})
        base["missing_evidence"] = [f"{cid}: {w['why']}; {w['what_would_resolve']}" for w in jb]
        return base
    base["result"] = "pass"
    base["reason_codes"] = ["verified"]
    kinds = {r["evidence_type"] for r in passes}
    base["passing_methods"] = sorted(kinds)
    return base


def _method(kinds):
    if len(kinds) > 1:
        return "cross-checked"
    k = next(iter(kinds))
    return {"computation": "recomputed", "owner_statement": "owner-confirmed"}.get(k, "source-checked")


def _out_row(row, c, now):
    r = copy.deepcopy(row)
    r.pop("verification", None)
    r.pop("blocked_reason", None)
    if c["result"] == "pass":
        r["status"] = "verified"
        r["verification"] = {"method": _method(set(c["passing_methods"])), "verifier": VERIFIER, "verified_at": vlib.iso(now),
                             "result": "pass", "notes": " | ".join(c["reasoning"])[:600]}
    elif c["result"] in ("fail", "unverifiable", "invalid"):
        r["status"] = "blocked"
        r["blocked_reason"] = ("; ".join(c["missing_evidence"]) or "; ".join(c["reason_codes"]))[:600]
        if c["result"] in ("fail", "unverifiable"):
            r["verification"] = {"method": "source-checked" if c["result"] == "fail" else "cross-checked", "verifier": VERIFIER,
                                 "verified_at": vlib.iso(now), "result": c["result"], "notes": " | ".join(c["reasoning"])[:600]}
            if row.get("status") == "blocked":
                r["blocked_reason"] = row.get("blocked_reason") or r["blocked_reason"]
    else:  # pending or skipped: leave as the producer sent it
        r["status"] = row.get("status") if row.get("status") != "verified" else "pending"
    return r


def audit(envelope, rows, root, rubric, judgments=None, specs=None, now=None, revision_to="chief-of-staff", inputs_read=None):
    now = now or vlib.now_from()
    findings = structure_check.check_structure(envelope, rows, now)
    env_ok = isinstance(envelope, dict) and not any(f["code"] == "ENVELOPE_INVALID" for f in findings)
    task_id = envelope.get("task_id") if isinstance(envelope, dict) and isinstance(envelope.get("task_id"), str) else "T-unknown"
    listed = envelope.get("claims", []) if env_ok else []
    loops_left = ((envelope.get("constraints") or {}).get("revise_loops_left", 2)) if env_ok else 2
    producer = envelope.get("from_agent", "unknown") if env_ok else "unknown"
    tier = vlib.recommended_tier(rubric, [r for r in rows if isinstance(r, dict)])
    ctx = {"rubric": rubric, "now": now, "root": root, "specs": specs or {}, "judgments": judgments, "findings": findings, "code_checks": {}}

    report = {"task_id": task_id, "phase": None, "now": vlib.iso(now), "producer": producer, "rubric": rubric["name"],
              "recommended_model_tier": tier, "inputs_read": inputs_read or {}, "structure_findings": findings, "claims": [],
              "injection_flags": [], "summary": {}, "unemittable_rows": []}
    audited = [r for r in rows if isinstance(r, dict) and r.get("claim_id") in listed] if env_ok else []
    claim_reports = {}
    if env_ok:
        for row in audited:
            claim_reports[row.get("claim_id")] = evaluate_claim(row, rows, ctx)
        for cid in listed:
            if cid not in claim_reports:  # listed but no row: structure_check already rejected it
                claim_reports[cid] = {"claim_id": cid, "reasoning": ["The envelope lists this claim but the ledger has no row for it."],
                                      "checks": [], "weaknesses": [], "result": "invalid", "reason_codes": ["CLAIM_ROW_MISSING"],
                                      "missing_evidence": [f"{cid}: supply the ledger row"], "flags": [], "passing_methods": []}
    report["claims"] = list(claim_reports.values())
    for c in report["claims"]:
        for f in c["flags"]:
            if f.get("type") == "possible_injection":
                report["injection_flags"].append({"claim_id": c["claim_id"], **f})

    results = [c["result"] for c in report["claims"]]
    nonpass = [c for c in report["claims"] if c["result"] in ("fail", "unverifiable", "invalid")]
    pending = [c for c in report["claims"] if c["result"] == "pending"]
    report["summary"] = {k: results.count(k) for k in ("pass", "fail", "unverifiable", "invalid", "pending", "skipped")}

    injected = any("injection_in_source" in c["reason_codes"] for c in report["claims"])
    if not env_ok:
        status, phase = "blocked", "final"
    elif nonpass:
        status, phase = ("escalate" if (loops_left == 0 or injected) else "needs_revision"), "final"
    elif pending:
        status, phase = "awaiting_judgment", "awaiting_judgment"
    else:
        status, phase = "ok", "final"
    report["phase"] = phase

    out_rows = []
    for row in audited:
        c = claim_reports[row["claim_id"]]
        if c["result"] == "invalid":
            report["unemittable_rows"].append({"claim_id": row.get("claim_id"), "reason_codes": c["reason_codes"]})
            continue
        r = _out_row(row, c, now)
        errs = vlib.schema_errors("claim-ledger", r)
        if errs:  # never write a row that breaks the contract
            report["unemittable_rows"].append({"claim_id": row.get("claim_id"), "reason_codes": ["OUTPUT_SCHEMA"], "errors": errs})
            continue
        out_rows.append(r)

    missing = [m for c in nonpass for m in c["missing_evidence"]]
    ids = [c["claim_id"] for c in report["claims"] if isinstance(c["claim_id"], str) and c["claim_id"].startswith("C-")]
    n = len(report["claims"])
    to_agent = "01-chief-of-staff" if revision_to == "chief-of-staff" or status != "needs_revision" else producer
    summary = ", ".join(f"{v} {k}" for k, v in report["summary"].items() if v)
    out_env = {"task_id": task_id, "from_agent": VERIFIER,
               "to_agent": "02-verifier" if status == "awaiting_judgment" else to_agent,
               "goal": ("The audit could not run because the envelope does not fit the contract; nothing was verified."
                        if status == "blocked" else
                        f"Model judgments needed for {len(pending)} claim(s) from {producer}." if status == "awaiting_judgment"
                        else f"Verification result for {n} claim(s) from {producer}: {summary}."
                        + (f" Return to {producer} for revision." if status == "needs_revision" else "")),
               "status": "requested" if status == "awaiting_judgment" else status,
               "inputs": [f"audit-report://{task_id}"],
               "constraints": {"model_tier": tier, "revise_loops_left": (max(loops_left - 1, 0) if status == "needs_revision"
                                                                            else (0 if status == "escalate" else loops_left))},
               "claims": ids, "created_at": vlib.iso(now)}
    esc = []
    if status == "escalate":
        why = ("instruction-like text was found inside evidence the claims rely on" if injected else
               "the two revise loops are used up and claims are still not verified")
        esc.append({"reason": f"Escalated to the owner: {why}. Claims: " + ", ".join(c["claim_id"] for c in nonpass) + ".",
                    "missing_evidence": missing or ["review of the flagged evidence"]})
    if report["injection_flags"] and status != "escalate":
        first = report["injection_flags"][0]
        esc.append({"reason": f"Instruction-like text found in evidence or claim text ({len(report['injection_flags'])} hit(s)); it was ignored.",
                    "missing_evidence": [f"{first['claim_id']}: owner or producer to review the flagged text ('{first.get('snippet', '')}')"]})
    if esc:
        out_env["escalations"] = esc
    if status == "blocked":
        out_env["escalations"] = [{"reason": "The audit could not run: the envelope does not fit the contract.",
                                   "missing_evidence": [f["detail"] for f in findings if f["code"] == "ENVELOPE_INVALID"][:5] or ["a valid envelope"]}]
    errs = vlib.schema_errors("agent-envelope", out_env)
    if errs:
        raise SystemExit(f"internal error: the audit produced an envelope that breaks the contract: {errs}")

    packet = None
    if status == "awaiting_judgment":
        packet = build_packet.build_packet(envelope, rows, rubric, root, now, {c["claim_id"] for c in pending}, ctx["code_checks"], ctx["specs"])
        packet["needed"] = {c["claim_id"]: [f"source_support[{x['evidence_index']}]" for x in c["checks"] if x["reason_code"] == "awaiting_judgment"]
                            + ["adversarial"] for c in pending}
    return {"status": status, "phase": phase, "envelope": out_env, "rows": out_rows, "report": report, "packet": packet}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--envelope", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--rubric", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--specs")
    ap.add_argument("--judgments")
    ap.add_argument("--now")
    ap.add_argument("--revision-to", choices=["chief-of-staff", "producer"], default="chief-of-staff")
    a = ap.parse_args()
    rubric = vlib.load_rubric(a.rubric)
    if rubric["problems"]:
        sys.exit("rubric does not fit the shape: " + "; ".join(rubric["problems"]))
    try:
        envelope, rows = vlib.read_json(a.envelope), vlib.read_rows(a.ledger)
    except (OSError, json.JSONDecodeError) as e:
        sys.exit(f"cannot read the envelope or ledger: {e}")
    read = {"files": [a.envelope, a.ledger, a.rubric] + [p for p in (a.specs, a.judgments) if p],
            "evidence_refs": sorted({e.get("ref") for r in rows if isinstance(r, dict) for e in r.get("evidence", []) if isinstance(e, dict)} - {None})}
    res = audit(envelope, rows, a.root, rubric, vlib.read_json(a.judgments) if a.judgments else None,
                load_specs(a.specs), vlib.now_from(a.now), a.revision_to, read)
    out = Path(a.out)
    vlib.dump(res["report"], out / "audit-report.json")
    vlib.dump(res["envelope"], out / "audit-envelope.json")
    (out / "audit-ledger.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in res["rows"]), encoding="utf-8")
    if res["packet"] is not None:
        vlib.dump(res["packet"], out / "judgment-request.json")
    rep = res["report"]
    print(f"status={res['status']} phase={res['phase']} claims={rep['summary']} tier={rep['recommended_model_tier']} -> {out}")
    sys.exit(EXIT[res["status"]])


if __name__ == "__main__":
    main()
