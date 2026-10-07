#!/usr/bin/env python3
"""Code-side weakness scan for adversarial review. It reads claims, evidence and the rubric only.
It never sees why the producer believes the claim.

Rules (each returns {type, severity, claim_id, why, what_would_resolve, source: 'code'}):
  unit_error      blocking  unit not in the rubric's allowed units; '%' or a currency symbol in the claim text
                            with a unit that does not match; same claim text with two different units
  double_counting blocking  an aggregate claim (total, sum, combined...) equals the sum of two claims that cite
                            the same evidence location, which may be one figure counted twice
  double_counting note      two claims with the same value and unit cite the same evidence location
  hedged_claim    note      'should', 'probably', 'roughly'... in a claim presented as fact or number
  overreach_risk  note      absolutes ('always', 'never', 'every') backed by a single evidence item
  single_source   note      high-stakes rubric and only one evidence item
  locator_missing note      document or URL evidence with no locator

The model's judged weaknesses are merged in by the audit (see SKILL.md). The types below always block,
whatever severity the judge writes, so a judge cannot talk a claim past the gate.

Usage: weakness_scan.py --ledger l.jsonl --rubric r.md
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "agents" / "02-verifier" / "lib"))
import vlib  # noqa: E402

BLOCKING_TYPES = {"unsupported_inference", "stale_data", "unit_error", "double_counting", "cherry_picking", "overreach"}
JUDGED_TYPES = BLOCKING_TYPES | {"scope_mismatch", "other"}
_AGG = re.compile(r"\b(total|sum|combined|overall|altogether|aggregate)\b", re.I)
_HEDGE = re.compile(r"\b(should|probably|likely|maybe|perhaps|roughly|i think|seems?)\b", re.I)
_ABS = re.compile(r"\b(always|never|every|all|none|guaranteed)\b", re.I)
_CURRENCY = re.compile(r"^[A-Za-z]{3}$|^(dollars?|euros?|pounds?)$", re.I)
_PERCENT_UNITS = {"%", "percent", "pct", "percentage", "percentage points"}


def _w(cid, typ, sev, why, fix):
    return {"type": typ, "severity": sev, "claim_id": cid, "why": why, "what_would_resolve": fix, "source": "code"}


def _keys(row):
    return {(e.get("type"), e.get("ref"), e.get("locator")) for e in row.get("evidence", []) if isinstance(e, dict)}


def scan(row, rows, rubric):
    cid, out = row["claim_id"], []
    text, unit, kind = row.get("claim", ""), row.get("unit"), row.get("kind")
    cfg = rubric["config"]
    if kind == "number" and isinstance(unit, str):
        allowed = cfg.get("allowed_units")
        if allowed and unit not in allowed:
            out.append(_w(cid, "unit_error", "blocking", f"unit {unit!r} is not one of the units this rubric allows {allowed}",
                          "state the claim in an allowed unit, or have the rubric owner add it"))
        if "%" in text and unit.casefold() not in _PERCENT_UNITS:
            out.append(_w(cid, "unit_error", "blocking", f"the claim speaks of a percentage but its unit is {unit!r}",
                          "make the unit and the claim text agree"))
        if re.search(r"[$€£]", text) and not _CURRENCY.match(unit):
            out.append(_w(cid, "unit_error", "blocking", f"the claim speaks of money but its unit is {unit!r}",
                          "use a currency code such as CAD"))
        for other in rows:
            if (other is not row and other.get("kind") == "number" and other.get("unit") != unit
                    and vlib.norm_text(other.get("claim")) == vlib.norm_text(text)):
                out.append(_w(cid, "unit_error", "blocking",
                              f"{other['claim_id']} makes the same claim in unit {other.get('unit')!r}", "settle on one unit"))
    if kind == "number":
        v = vlib.to_decimal(row.get("value"))
        for other in rows:
            if other is row or other.get("kind") != "number" or v is None:
                continue
            if (vlib.to_decimal(other.get("value")) == v and other.get("unit") == unit
                    and vlib.norm_text(other.get("claim")) != vlib.norm_text(text) and _keys(row) & _keys(other)):
                out.append(_w(cid, "double_counting", "note",
                              f"{other['claim_id']} has the same value and unit and cites the same evidence location",
                              "confirm these are two different quantities"))
        if _AGG.search(text) and v is not None:
            pool = [r for r in rows if r is not row and r.get("kind") == "number" and r.get("unit") == unit]
            for i, b in enumerate(pool):
                for c in pool[i + 1:]:
                    bv, cv = vlib.to_decimal(b.get("value")), vlib.to_decimal(c.get("value"))
                    if bv is not None and cv is not None and bv + cv == v and _keys(b) & _keys(c):
                        out.append(_w(cid, "double_counting", "blocking",
                                      f"this total equals {b['claim_id']} + {c['claim_id']}, and both cite the same evidence location; "
                                      "it may be one figure counted twice",
                                      "show that the two figures are distinct (different rows or periods) or remove the duplicate"))
    if kind in ("fact", "number") and _HEDGE.search(text):
        out.append(_w(cid, "hedged_claim", "note", "the claim is hedged in its wording but filed as a fact or number",
                      "state the uncertainty in the confidence field, or make the claim a recommendation"))
    evid = [e for e in row.get("evidence", []) if isinstance(e, dict)]
    if _ABS.search(text) and len(evid) == 1:
        out.append(_w(cid, "overreach_risk", "note", "an absolute word is backed by a single evidence item",
                      "show the evidence covers every case, or soften the wording"))
    if (cfg.get("stakes") == "high" or cfg.get("domain") in vlib.HIGH_STAKES_DOMAINS) and len(evid) == 1:
        out.append(_w(cid, "single_source", "note", "high-stakes domain with one evidence item", "add an independent second source"))
    for i, e in enumerate(evid):
        if e.get("type") in ("document", "url") and not e.get("locator"):
            out.append(_w(cid, "locator_missing", "note", f"evidence[{i}] has no locator", "say where in the source the support is"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--rubric", required=True)
    a = ap.parse_args()
    rows = vlib.read_rows(a.ledger)
    rubric = vlib.load_rubric(a.rubric)
    res = {r["claim_id"]: scan(r, rows, rubric) for r in rows}
    print(vlib.dump(res), end="")
    sys.exit(1 if any(w["severity"] == "blocking" for ws in res.values() for w in ws) else 0)


if __name__ == "__main__":
    main()
