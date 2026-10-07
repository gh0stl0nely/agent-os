#!/usr/bin/env python3
"""Deterministic structure check on an envelope and its claim ledger rows. Runs before anything else.

Layer 1 is the contract itself (agent-envelope and claim-ledger schemas, through contracts/validate.py),
which already rejects: status 'assumed', 'verified' without evidence or without a passing verification,
'blocked' without a reason, unknown kinds, missing fields. Layer 2 adds rules the Verifier needs and the
schemas do not enforce (validate.py skips date-time formats unless an optional package is installed).

Usage:
  structure_check.py --envelope e.json --ledger l.jsonl [--now ISO]
Exit code: 0 no rejects, 1 at least one reject.
"""
import argparse
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "agents" / "02-verifier" / "lib"))
import vlib  # noqa: E402

# code -> meaning, for the report and the SKILL.md table
CODES = {
    "ENVELOPE_INVALID": "the envelope does not fit agent-envelope.schema.json",
    "SCHEMA": "the row does not fit claim-ledger.schema.json",
    "ASSUMED_STATUS": "status 'assumed' does not exist; an unevidenced claim is 'blocked'",
    "MISSING_EVIDENCE": "the claim has no evidence items",
    "VERIFIED_WITHOUT_EVIDENCE": "marked verified with no evidence",
    "BAD_TIMESTAMP": "a timestamp is not a strict RFC 3339 date-time with an offset",
    "FUTURE_TIMESTAMP": "a timestamp is in the future",
    "DUPLICATE_ID": "two rows share a claim_id",
    "NUMBER_NO_VALUE": "a number claim has no numeric value",
    "NUMBER_NO_UNIT": "a number claim has no unit",
    "CLAIM_ROW_MISSING": "the envelope lists a claim id that has no ledger row",
    "SELF_VERIFIED": "the producer marked its own claim verified; ignored, the claim is re-verified (warn)",
    "ROW_NOT_IN_ENVELOPE": "a ledger row is not listed in the envelope (warn, not audited)",
    "MISROUTED": "the envelope is not addressed to 02-verifier (warn)",
}


def _f(claim_id, code, severity, detail):
    return {"claim_id": claim_id, "code": code, "severity": severity, "detail": detail}


def check_structure(envelope, rows, now):
    findings = []
    if not isinstance(envelope, dict):
        return [_f(None, "ENVELOPE_INVALID", "reject", "envelope is not a JSON object")]
    for e in vlib.schema_errors("agent-envelope", envelope):
        findings.append(_f(None, "ENVELOPE_INVALID", "reject", e))
    if envelope.get("to_agent") not in (None, "02-verifier"):
        findings.append(_f(None, "MISROUTED", "warn", f"to_agent is {envelope.get('to_agent')!r}"))
    seen = {}
    horizon = now + timedelta(minutes=5)
    for row in rows:
        if not isinstance(row, dict):
            findings.append(_f(None, "SCHEMA", "reject", "a ledger row is not a JSON object"))
            continue
        cid = row.get("claim_id") if isinstance(row.get("claim_id"), str) else None
        for e in vlib.schema_errors("claim-ledger", row):
            findings.append(_f(cid, "SCHEMA", "reject", e))
        if row.get("status") == "assumed":
            findings.append(_f(cid, "ASSUMED_STATUS", "reject", CODES["ASSUMED_STATUS"]))
        evidence = row.get("evidence") if isinstance(row.get("evidence"), list) else []
        if row.get("status") == "verified" and not evidence:
            findings.append(_f(cid, "VERIFIED_WITHOUT_EVIDENCE", "reject", CODES["VERIFIED_WITHOUT_EVIDENCE"]))
        elif row.get("status") in ("pending", "verified") and not evidence:
            findings.append(_f(cid, "MISSING_EVIDENCE", "reject", CODES["MISSING_EVIDENCE"]))
        if cid:
            if cid in seen:
                findings.append(_f(cid, "DUPLICATE_ID", "reject", CODES["DUPLICATE_ID"]))
            seen[cid] = row
        stamps = [("created_at", row.get("created_at"))]
        stamps += [(f"evidence[{i}].retrieved_at", e.get("retrieved_at")) for i, e in enumerate(evidence) if isinstance(e, dict)]
        if isinstance(row.get("verification"), dict):
            stamps.append(("verification.verified_at", row["verification"].get("verified_at")))
        for label, s in stamps:
            if s is None:
                continue
            ts = vlib.parse_ts(s)
            if ts is None:
                findings.append(_f(cid, "BAD_TIMESTAMP", "reject", f"{label}={s!r}"))
            elif ts > horizon:
                findings.append(_f(cid, "FUTURE_TIMESTAMP", "reject", f"{label}={s}"))
        if row.get("kind") == "number":
            if vlib.to_decimal(row.get("value")) is None:
                findings.append(_f(cid, "NUMBER_NO_VALUE", "reject", CODES["NUMBER_NO_VALUE"]))
            if not isinstance(row.get("unit"), str) or not row["unit"].strip():
                findings.append(_f(cid, "NUMBER_NO_UNIT", "reject", CODES["NUMBER_NO_UNIT"]))
        if row.get("status") == "verified":
            findings.append(_f(cid, "SELF_VERIFIED", "warn", CODES["SELF_VERIFIED"]))
    listed = envelope.get("claims") if isinstance(envelope.get("claims"), list) else []
    for cid in listed:
        if cid not in seen:
            findings.append(_f(cid, "CLAIM_ROW_MISSING", "reject", CODES["CLAIM_ROW_MISSING"]))
    for cid in seen:
        if cid not in listed:
            findings.append(_f(cid, "ROW_NOT_IN_ENVELOPE", "warn", CODES["ROW_NOT_IN_ENVELOPE"]))
    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--envelope", required=True)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--now")
    a = ap.parse_args()
    findings = check_structure(vlib.read_json(a.envelope), vlib.read_rows(a.ledger), vlib.now_from(a.now))
    print(vlib.dump({"findings": findings, "rejects": sum(f["severity"] == "reject" for f in findings)}), end="")
    sys.exit(1 if any(f["severity"] == "reject" for f in findings) else 0)


if __name__ == "__main__":
    main()
