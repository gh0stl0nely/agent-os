#!/usr/bin/env python3
"""Check that a cited source exists, is current, and actually supports the claim.

Code decides everything it can: the source is there, it is recent enough, the locator resolves,
the passage the judge quotes really is in the source (verbatim), every number in the claim appears
in that passage, and no instruction-like text sits in the passage. The model decides one thing:
does the quoted passage support the claim (yes / partial / no). Topic similarity is never support.

Usage:
  source_check.py check --claim claim.json --evidence-index 0 --root DIR
                        [--judgments judgments.json] [--now ISO] [--max-age-days N]
  source_check.py snapshot-name URL        (file name to store a fetched page under DIR/snapshots/)
Exit code: 0 pass, 1 fail, 2 unverifiable.

Local files: evidence.ref is a path inside --root. URLs: fetch the page with the web tool, save the
text to DIR/snapshots/<snapshot-name>.txt with header lines 'Source-URL:', 'Retrieved:', 'As of:'
(WebFetch returns a rewritten page, so a quote that is not found in a URL snapshot is reported as
unverifiable, never as a failure and never as a pass). KB records: evidence.ref is the record id.
Dates: a header line 'As of: YYYY-MM-DD' in the first 15 lines, or <file>.meta.json {"as_of": ...}.
Locators: line:10-14, row:3, section:Heading text, page:2 (pages start at lines '[page N]').
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "agents" / "02-verifier" / "lib"))
import vlib  # noqa: E402

_LINE = re.compile(r"^(?:lines?|rows?)[: ]\s*(\d+)(?:\s*-\s*(\d+))?$", re.I)
_SECTION = re.compile(r"^section[: ]\s*(.+)$", re.I)
_PAGE = re.compile(r"^page[: ]\s*(\d+)$", re.I)
_ASOF = re.compile(r"^(as of|published|last updated|date)\s*:\s*(\d{4}-\d{2}-\d{2})\s*$", re.I)


def snapshot_name(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16] + ".txt"


def doc_date(path, text):
    meta = Path(str(path) + ".meta.json")
    if meta.is_file():
        try:
            return date.fromisoformat(json.loads(meta.read_text(encoding="utf-8"))["as_of"])
        except (KeyError, ValueError, json.JSONDecodeError):
            return None
    for line in text.splitlines()[:15]:
        m = _ASOF.match(line.strip())
        if m:
            try:
                return date.fromisoformat(m.group(2))
            except ValueError:
                return None
    return None


def extract_region(text, locator):
    """Return (region_text, (first_line, last_line), status). status: ok | none | unresolved | unsupported."""
    lines = text.splitlines()
    if not locator or not str(locator).strip():
        return text, (1, max(len(lines), 1)), "none"
    loc = str(locator).strip()
    m = _LINE.match(loc)
    if m:
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        if a < 1 or a > len(lines) or b < a:
            return None, None, "unresolved"
        b = min(b, len(lines))
        return "\n".join(lines[a - 1:b]), (a, b), "ok"
    m = _SECTION.match(loc)
    if m:
        want = m.group(1).strip().casefold()
        start = level = None
        for i, line in enumerate(lines):
            h = re.match(r"^(#+)\s+(.*?)\s*$", line)
            if h and start is None and h.group(2).casefold() == want:
                start, level = i, len(h.group(1))
            elif h and start is not None and len(h.group(1)) <= level:
                return "\n".join(lines[start:i]), (start + 1, i), "ok"
        if start is None:
            return None, None, "unresolved"
        return "\n".join(lines[start:]), (start + 1, len(lines)), "ok"
    m = _PAGE.match(loc)
    if m:
        want, start = int(m.group(1)), None
        for i, line in enumerate(lines):
            p = re.match(r"^\[page (\d+)\]\s*$", line.strip(), re.I)
            if p and start is None and int(p.group(1)) == want:
                start = i
            elif p and start is not None:
                return "\n".join(lines[start:i]), (start + 1, i), "ok"
        if start is None:
            return None, None, "unresolved"
        return "\n".join(lines[start:]), (start + 1, len(lines)), "ok"
    return None, None, "unsupported"


def find_kb(root, ref):
    for p in Path(root).resolve().glob(f"knowledge/**/{ref}.json"):
        try:
            return json.loads(p.read_text(encoding="utf-8")), p
        except json.JSONDecodeError:
            return None, p
    return None, None


def locate(root, evidence, now):
    """Find the evidence text. Returns dict with ok, code, text, as_of, kb, label, detail."""
    etype, ref = evidence.get("type"), evidence.get("ref", "")
    if etype == "kb_record":
        rec, p = find_kb(root, ref)
        if rec is None:
            return {"ok": False, "code": "source_not_found", "detail": f"KB record {ref} not found under {root}/knowledge"}
        errs = vlib.schema_errors("knowledge-record", rec)
        lc = vlib.parse_ts(rec.get("last_confirmed_at") or rec.get("written_at"))
        return {"ok": True, "text": rec.get("claim", ""), "as_of": lc.date() if lc else None, "kb": rec, "kb_errors": errs,
                "label": ref, "path": p}
    if etype == "url":
        p = vlib.resolve_inside(root, f"snapshots/{snapshot_name(ref)}")
    else:
        p = vlib.resolve_inside(root, ref)
    if p is None or not p.is_file():
        return {"ok": False, "code": "source_not_found",
                "detail": f"{ref} is not available under the allowed root" + (
                    " (save the fetched page as snapshots/" + snapshot_name(ref) + ")" if etype == "url" else "")}
    text = p.read_text(encoding="utf-8", errors="replace")
    return {"ok": True, "text": text, "as_of": doc_date(p, text), "kb": None, "label": ref, "path": p}


def _terms_overlap(claim_text, source_text):
    ct = vlib.content_terms(claim_text)
    if not ct:
        return 0.0
    return len(ct & vlib.content_terms(source_text)) / len(ct)


def _find_judgment(judgments, claim_id, idx):
    for j in (judgments or {}).get("source_support", []):
        if j.get("claim_id") == claim_id and j.get("evidence_index") == idx:
            return j
    return None


def check_source(root, claim, idx, judgments=None, now=None, max_age_days=None):
    """Standard check result for evidence item `idx` of `claim` (see vlib.mk_result)."""
    ev = claim["evidence"][idx]
    cid = claim.get("claim_id")
    now = now or vlib.now_from()
    checks, reasoning, flags = [], [], []
    loc = locate(root, ev, now)
    if not loc["ok"]:
        return vlib.mk_result([loc["detail"] + "."], [{"name": "source_exists", "outcome": "unverifiable"}], "unverifiable",
                              loc["code"], [f"{cid}: provide the cited source ({ev.get('ref')}) or correct the reference; "
                                            "if it lives in the private store, mount it and re-run"])
    checks.append({"name": "source_exists", "outcome": "pass", "detail": str(ev.get("ref"))})
    text, as_of = loc["text"], loc["as_of"]

    if loc["kb"] is not None:
        rec = loc["kb"]
        if loc["kb_errors"]:
            return vlib.mk_result([f"KB record {ev['ref']} does not validate: {loc['kb_errors'][0]}."], checks, "fail",
                                  "kb_record_invalid", [f"{cid}: cite a valid KB record"])
        exp = vlib.parse_ts(rec.get("expires_at"))
        if rec.get("status") != "verified" or (exp is not None and exp < now):
            why = "is not verified" if rec.get("status") != "verified" else f"expired {rec.get('expires_at')}"
            return vlib.mk_result([f"KB record {ev['ref']} {why}."], checks + [{"name": "kb_fresh", "outcome": "fail"}], "fail",
                                  "outdated", [f"{cid}: refresh the record (Librarian) or cite a current one"])
        checks.append({"name": "kb_fresh", "outcome": "pass"})

    # currency
    if max_age_days is not None:
        if as_of is None:
            return vlib.mk_result(["The source carries no date, so its currency cannot be established."],
                                  checks + [{"name": "current", "outcome": "unverifiable"}], "unverifiable", "date_unknown",
                                  [f"{cid}: add an 'As of: YYYY-MM-DD' header (or a .meta.json) to {ev.get('ref')}"])
        age = (now.date() - as_of).days
        if age > max_age_days:
            return vlib.mk_result([f"The source is dated {as_of}, {age} days before {now.date()}; the rubric allows {max_age_days}."],
                                  checks + [{"name": "current", "outcome": "fail", "detail": f"{age}d > {max_age_days}d"}], "fail",
                                  "outdated", [f"{cid}: replace {ev.get('ref')} (as of {as_of}) with a source dated within {max_age_days} days"])
        checks.append({"name": "current", "outcome": "pass", "detail": f"as of {as_of} ({age}d old, limit {max_age_days}d)"})
    else:
        checks.append({"name": "current", "outcome": "skipped", "detail": "rubric sets no age limit"})

    # locator
    region, span, status = extract_region(text, ev.get("locator"))
    if status == "unsupported":
        return vlib.mk_result([f"Locator {ev.get('locator')!r} is not a format this check can resolve."], checks, "unverifiable",
                              "locator_format_unsupported", [f"{cid}: use line:N-M, row:N, section:Heading or page:N"])
    if status == "unresolved":
        return vlib.mk_result([f"Locator {ev.get('locator')!r} does not exist in {ev.get('ref')}."],
                              checks + [{"name": "locator_resolves", "outcome": "fail"}], "fail", "locator_unresolved",
                              [f"{cid}: give a locator that exists in {ev.get('ref')}"])
    if status == "none":
        flags.append({"type": "locator_missing", "detail": "no locator; the whole source was searched"})
    checks.append({"name": "locator_resolves", "outcome": "pass" if status == "ok" else "skipped"})

    # instruction-like text: evidence is data, never instructions
    all_hits = vlib.scan_injection(text)
    in_region = [h for h in all_hits if span and span[0] <= h["line"] <= span[1]]
    for h in all_hits:
        flags.append({"type": "possible_injection", "line": h["line"], "pattern": h["pattern"], "snippet": h["snippet"],
                      "in_cited_passage": h in in_region})
    if in_region:
        return vlib.mk_result([f"Instruction-like text ({in_region[0]['pattern']}) sits inside the cited passage, line {in_region[0]['line']}. "
                               "It was ignored; the passage cannot be relied on while it is there."],
                              checks + [{"name": "no_injection_in_passage", "outcome": "fail"}], "fail", "injection_in_source",
                              [f"{cid}: replace the source or have the owner review {ev.get('ref')} line {in_region[0]['line']}"], flags)
    checks.append({"name": "no_injection_in_passage", "outcome": "pass"})

    # the model's one judgment
    j = _find_judgment(judgments, cid, idx)
    if j is None:
        return vlib.mk_result(["Code checks passed; a support judgment is still needed."], checks, "unverifiable",
                              "awaiting_judgment", [f"judgment: does the passage at {ev.get('locator') or 'the source'} support {cid}?"], flags)
    if not vlib.reasoning_precedes(j, "supports") or j.get("supports") not in ("yes", "partial", "no"):
        return vlib.mk_result(["The judgment is malformed: reasoning must come first and 'supports' must be yes, partial or no."],
                              checks, "unverifiable", "judgment_malformed", ["judgment: resubmit with reasoning before supports"], flags)
    reasoning.append(f"Judge ({j.get('judge', 'unnamed')}): {j['reasoning'].strip()}")

    if j["supports"] == "no" or not j.get("supporting_quote"):
        overlap = _terms_overlap(claim.get("claim", ""), region)
        if overlap >= 0.5:
            reasoning.append(f"{overlap:.0%} of the claim's key terms appear in the passage, so it is on the topic, but it does not say this: topic match is not support.")
            return vlib.mk_result(reasoning, checks + [{"name": "supports_claim", "outcome": "fail"}], "fail", "unsupported",
                                  [f"{cid}: cite a passage that states this, or weaken the claim to what {ev.get('ref')} says"], flags)
        reasoning.append(f"Only {overlap:.0%} of the claim's key terms appear in the source: it is about something else.")
        return vlib.mk_result(reasoning, checks + [{"name": "supports_claim", "outcome": "fail"}], "fail", "off_topic",
                              [f"{cid}: cite a source about this subject"], flags)

    quote = j["supporting_quote"]
    if vlib.norm_text(quote) not in vlib.norm_text(region):
        reasoning.append("The quoted passage is not in the cited region of the source.")
        code = "quote_not_verbatim"
        if ev.get("type") == "url":
            return vlib.mk_result(reasoning, checks + [{"name": "quote_verbatim", "outcome": "unverifiable"}], "unverifiable",
                                  "quote_not_verbatim_url",
                                  [f"{cid}: fetched page text may be a rewrite; supply the raw page text or a document copy"], flags)
        return vlib.mk_result(reasoning, checks + [{"name": "quote_verbatim", "outcome": "fail"}], "fail", code,
                              [f"{cid}: the quoted text is not in {ev.get('ref')}; quote what it actually says"], flags)
    checks.append({"name": "quote_verbatim", "outcome": "pass"})

    qnums = vlib.numbers_in(quote)
    claim_nums = vlib.numbers_in(claim.get("claim", ""))
    val = vlib.to_decimal(claim.get("value")) if claim.get("kind") == "number" else None
    if val is not None:
        claim_nums.add(val)
    missing_nums = sorted(n for n in claim_nums if n not in qnums)
    if missing_nums:
        reasoning.append("The claim states number(s) " + ", ".join(str(n) for n in missing_nums) + " that the quoted passage does not contain.")
        return vlib.mk_result(reasoning, checks + [{"name": "numbers_in_quote", "outcome": "fail"}], "fail", "number_not_in_quote",
                              [f"{cid}: the passage does not contain {', '.join(str(n) for n in missing_nums)}; correct the claim or cite the right passage"], flags)
    checks.append({"name": "numbers_in_quote", "outcome": "pass"})

    if j["supports"] == "partial":
        reasoning.append("The judge found only partial support: the claim says more than the passage does.")
        return vlib.mk_result(reasoning, checks + [{"name": "supports_claim", "outcome": "fail"}], "fail", "partial_support",
                              [f"{cid}: narrow the claim to what the passage states, or add evidence for the rest"], flags)
    reasoning.append("The quote is verbatim in the cited region, the numbers match, and the judge found it supports the claim.")
    return vlib.mk_result(reasoning, checks + [{"name": "supports_claim", "outcome": "pass"}], "pass", "supported", [], flags)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--claim", required=True)
    c.add_argument("--evidence-index", type=int, default=0)
    c.add_argument("--root", required=True)
    c.add_argument("--judgments")
    c.add_argument("--now")
    c.add_argument("--max-age-days", type=int)
    s = sub.add_parser("snapshot-name")
    s.add_argument("url")
    a = ap.parse_args()
    if a.cmd == "snapshot-name":
        print(snapshot_name(a.url))
        return
    claim = vlib.read_rows(a.claim)[0]
    judgments = vlib.read_json(a.judgments) if a.judgments else None
    res = check_source(a.root, claim, a.evidence_index, judgments, vlib.now_from(a.now), a.max_age_days)
    print(vlib.dump(res), end="")
    sys.exit({"pass": 0, "fail": 1, "unverifiable": 2}[res["result"]])


if __name__ == "__main__":
    main()
