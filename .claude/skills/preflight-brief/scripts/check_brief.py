#!/usr/bin/env python3
"""Check a Preflight Brief for completeness against agent-system/contracts/preflight-brief.md.

  check_brief.py BRIEF.md --ledger ledger.jsonl

Rejects (exit 1) when anything is missing or wrong, including a hand-written brief whose Evidence table says
'pass' for a claim the ledger does not show as verified. Without --ledger no claim can be confirmed, so the
brief is rejected as unverifiable. Exit 0 = pass, 1 = reject, 2 = usage or read error.
"""
import argparse
import json
import re
import sys

sys.dont_write_bytecode = True  # a vetted or scanned folder must not gain compiled files from our own run
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brief_common as bc  # noqa: E402

PLACEHOLDER = re.compile(r"<[A-Za-z][^>\n]{2,80}>")


def parse(text):
    lines = text.splitlines()
    title = next((l for l in lines if l.startswith("# ")), "")
    header, sections, cur = {}, {}, None
    for l in lines:
        if l.startswith("## "):
            cur = l[3:].strip()
            sections[cur] = []
        elif cur is None:
            m = re.match(r"^- \*\*(.+?):\*\*\s*(.*)$", l)
            if m:
                header[m.group(1)] = m.group(2).strip()
        else:
            sections[cur].append(l)
    return title, header, {k: "\n".join(v).strip() for k, v in sections.items()}


def table_rows(body):
    rows = []
    for l in body.splitlines():
        if l.strip().startswith("|"):
            cells = [c.strip() for c in l.strip().strip("|").split("|")]
            if len(cells) >= 3 and not set(cells[0]) <= set("-: ") and cells[0].lower() != "claim id":
                rows.append(cells)
    return rows


def check(text, ledger=None):
    """Return {'status': 'pass'|'reject', 'problems': [{'check','detail'}], 'claims_checked': [...]}."""
    tpl = bc.load_template()
    problems = []

    def bad(check_id, detail):
        problems.append({"check": check_id, "detail": detail})

    title, header, sections = parse(text)
    if not title.startswith("# Preflight:") or len(title) < 20 or PLACEHOLDER.search(title):
        bad("title", "the title must be '# Preflight: <the action in one line>' with real content")
    for label in tpl["header"]:
        v = header.get(label, "")
        if not v:
            bad("header", f"'{label}' is missing or empty")
        elif PLACEHOLDER.search(v):
            bad("placeholder", f"'{label}' still has template placeholder text")
    if header.get(tpl["header"][0]) and not bc.ID_RX.match(header[tpl["header"][0]]):
        bad("brief-id", "Brief id must look like PF-YYYYMMDD-n")
    cls = header.get(tpl["header"][2], "")
    m = re.match(r"^(R[0-6])\b(?!.*\|)", cls)
    declared = m.group(1) if m else None
    if declared is None:
        bad("class", "Action class must be one class, R2 to R6")
    elif bc.idx(declared) < 2:
        bad("class", f"{declared} does not need a Preflight Brief; a brief is for R2 and above")
    if header.get(tpl["header"][3]) and not re.search(r"\d{4}-\d{2}-\d{2}", header[tpl["header"][3]]):
        bad("deadline", "Decision needed by must contain a date (YYYY-MM-DD)")

    if list(sections) != tpl["sections"]:
        bad("sections", "sections must be exactly, in order: " + "; ".join(tpl["sections"]) + f" (found: {list(sections)})")
    for name in tpl["sections"]:
        body = sections.get(name, "")
        if not body:
            bad("section-empty", f"section '{name}' is missing or empty")
        elif PLACEHOLDER.search(body):
            bad("placeholder", f"section '{name}' still has template placeholder text")

    # evidence and ledger
    ev_body = sections.get(tpl["sections"][2], "")
    rows = table_rows(ev_body)
    table_ids = []
    if not rows:
        bad("evidence", "the Evidence table has no claim rows")
    for cells in rows:
        cid = cells[0]
        table_ids.append(cid)
        if not re.fullmatch(r"C-[A-Za-z0-9._-]+", cid):
            bad("evidence", f"'{cid}' is not a claim id (C-...)")
        if cells[1].lower() != "pass":
            bad("evidence", f"{cid}: Verifier result is '{cells[1]}', only 'pass' is accepted")
        if not cells[2]:
            bad("evidence", f"{cid}: Source is empty")
    cited = set(bc.CLAIM_RX.findall(text))
    for cid in sorted(cited - set(table_ids)):
        bad("evidence", f"{cid} is cited in the brief but is not in the Evidence table")
    if not set(bc.CLAIM_RX.findall(sections.get(tpl["sections"][1], ""))):
        bad("why", "the Why section must cite at least one claim id")
    if ledger is None:
        bad("ledger", "no claim ledger was supplied, so no Verifier pass can be confirmed; the brief is unverifiable")
    else:
        for cid in dict.fromkeys(table_ids):
            ok, why = bc.claim_verdict(ledger, cid)
            if not ok:
                bad("claim-not-verified", f"{cid}: {why}")

    alts = [l for l in sections.get(tpl["sections"][3], "").splitlines() if re.match(r"^\s*(?:[-*]|\d+[.)])\s+\S", l)]
    if not alts:
        bad("alternatives", "list at least one alternative")
    elif not any("do nothing" in a.lower() for a in alts):
        bad("alternatives", "alternatives must include 'do nothing'")

    rb = sections.get(tpl["sections"][5], "")
    if rb and re.search(r"not reversible", rb, re.I) and len(re.sub(r"(?i)not reversible", "", rb).strip()) < 20:
        bad("rollback", "'not reversible' needs a reason it is still justified")
    if rb and len(rb) < 15:
        bad("rollback", "Rollback is too thin: give the exact steps, who does them, and how long they take")
    cost = sections.get(tpl["sections"][6], "")
    if declared == "R6" and cost and not re.search(r"\d", cost):
        bad("cost", "an R6 brief must state an amount, not only words")

    safety = sections.get(tpl["sections"][7], "")
    for label in tpl["checks"]:
        line = next((l for l in safety.splitlines() if label in l), None)
        if line is None:
            bad("safety", f"the safety check '{label}' is missing")
        elif not (re.match(r"^- \[x\]", line, re.I) or re.search(r"N/A:\s*\S.{9,}", line)):
            bad("safety", f"'{label}' must be checked, or marked N/A with a reason")

    if scan := bc.scan_secrets.scan_text(text):
        bad("secrets", f"{len(scan)} secret-like value(s) found, first at line {scan[0]['line']} (rule {scan[0]['rule']}); the value is not repeated")
    inj = bc.injection_hits(text)
    if inj:
        bad("instruction-like-text", "instruction-like text found inside the brief and treated as data: " + "; ".join(inj))
    if declared and bc.idx(declared) >= 2 and title:
        c = bc.classify.classify(title[2:] + ". " + sections.get(tpl["sections"][0], ""))
        if c["status"] == "ok" and bc.idx(c["class"]) > bc.idx(declared):
            bad("class", f"declared {declared} is below the computed class {c['class']} (rule {c['decisive_rule']})")

    return {"status": "reject" if problems else "pass", "problems": problems, "claims_checked": list(dict.fromkeys(table_ids))}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brief")
    ap.add_argument("--ledger")
    a = ap.parse_args()
    try:
        text = Path(a.brief).read_text(encoding="utf-8")
        ledger = bc.load_ledger(a.ledger) if a.ledger else None
    except (OSError, ValueError) as e:
        print(json.dumps({"status": "error", "error": e.__class__.__name__}))
        sys.exit(2)
    res = check(text, ledger)
    print(json.dumps(res, indent=2))
    sys.exit(0 if res["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
