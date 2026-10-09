"""Shared helpers for build_brief.py and check_brief.py. Standard library plus the contracts validator (jsonschema)."""
import json
import re
import sys

sys.dont_write_bytecode = True  # a vetted or scanned folder must not gain compiled files from our own run
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]  # <repo>/.claude/skills/preflight-brief/scripts
CONTRACTS = REPO / "agent-system" / "contracts"
TEMPLATE = CONTRACTS / "preflight-brief.md"
for p in (REPO / ".claude/skills/risk-classify/scripts", REPO / ".claude/skills/secrets-hygiene/scripts", CONTRACTS):
    sys.path.insert(0, str(p))

import classify  # noqa: E402
import scan_secrets  # noqa: E402
import validate  # noqa: E402

CLASSES = classify.CLASSES
ID_RX = re.compile(r"^PF-\d{8}-\d+$")
CLAIM_RX = re.compile(r"\bC-[A-Za-z0-9._-]+\b")


def load_template():
    """Read the contract template so headings and header labels can never drift from it."""
    text = TEMPLATE.read_text(encoding="utf-8")
    m = re.search(r"```markdown\n(.*?)```", text, re.S)
    if not m:
        raise SystemExit(f"cannot find the markdown template block in {TEMPLATE}")
    body = m.group(1)
    header = re.findall(r"^- \*\*(.+?):\*\*", body, re.M)
    sections = re.findall(r"^## (.+)$", body, re.M)
    checks = re.findall(r"^- \[ \] (.+)$", body, re.M)
    if len(header) != 5 or len(sections) != 8 or len(checks) != 4:
        raise SystemExit("the preflight template changed shape; update the preflight-brief skill (propose a change request)")
    return {"header": header, "sections": sections, "checks": checks}


def load_ledger(path):
    """Return {claim_id: {'row': dict, 'schema_errors': [str]}} from a JSON Lines or JSON file of claim rows."""
    ver = validate.validator("claim-ledger")
    out = {}
    for obj in validate.load_objects(path):
        errs = [e.message for e in validate.errors_for(ver, obj)]
        cid = obj.get("claim_id") if isinstance(obj, dict) else None
        if cid:
            out[cid] = {"row": obj, "schema_errors": errs}
    return out


def claim_verdict(ledger, claim_id):
    """(ok, reason). A claim counts only if the ledger row is schema-valid, status verified, and the Verifier result is pass."""
    entry = ledger.get(claim_id)
    if entry is None:
        return False, "not found in the claim ledger"
    row = entry["row"]
    if entry["schema_errors"]:
        return False, "the ledger row does not validate: " + entry["schema_errors"][0]
    if row.get("status") != "verified":
        return False, f"ledger status is '{row.get('status')}', not 'verified'"
    v = row.get("verification") or {}
    if v.get("result") != "pass":
        return False, f"Verifier result is '{v.get('result')}', not 'pass'"
    if not row.get("evidence"):
        return False, "no evidence recorded"
    return True, ""


def idx(cls):
    return CLASSES.index(cls)


def injection_hits(text):
    clean, _ = classify.prepare(text)
    return [m.group(0)[:50] for rx in classify.INJECTION_RX for m in [rx.search(clean)] if m]


SCREEN_HEADING = "Four-question screen (risk-classify):"
SCREEN_LINE = re.compile(r"^- (money|deletion|outside|secret): (yes|no|unsure) - (.+)$")


def final_screen(c, plan_screen):
    """The answers that count, as the classifier settled them: the more cautious of the script's and the builder's. A builder's 'no'
    never hides a script 'yes', so the brief shows the script's cue names next to the builder's reason."""
    out = {}
    for q in classify.risk_screen.QUESTIONS:
        rec = c["screen"]["questions"][q]
        mine = plan_screen.get(q, {})
        ev = " ".join(str(mine.get("evidence", "")).split())
        if rec["decided_by"] == "script" and rec["script"]["answer"] != "no":
            cues = ", ".join(dict.fromkeys(e.get("cue", "?") for e in rec["script"]["evidence"]))
            ev = f"script cues: {cues}; the builder said {mine.get('answer')}: {ev}"
        out[q] = {"answer": rec["answer"], "evidence": ev}
    return out


def screen_lines(final):
    """Render the four answers that count as the lines that go under 'Blast radius'."""
    return [SCREEN_HEADING] + [f"- {q}: {final[q]['answer']} - {final[q]['evidence']}" for q in classify.risk_screen.QUESTIONS]


def parse_screen(section_text):
    """Read the four answers back out of a brief's Blast radius section. Returns {question: {answer, evidence}} (possibly partial)."""
    out = {}
    for line in section_text.splitlines():
        m = SCREEN_LINE.match(line.strip())
        if m:
            out[m.group(1)] = {"answer": m.group(2), "evidence": m.group(3).strip()}
    return out


def screen_problems(declared, text, screen):
    """Problems with a plan's or brief's screen: missing questions, missing reasons, an incomplete screen, a class below what a yes or unsure requires.
    `text` is the description the classifier reads. Returns (problems, classification)."""
    problems = []
    qs = classify.risk_screen.QUESTIONS
    if not isinstance(screen, dict):
        return ["the four-question screen is missing: answer money, deletion, outside and secret (yes, no or unsure), each with evidence"], None
    for q in qs:
        v = screen.get(q)
        if not isinstance(v, dict) or str(v.get("answer", "")).lower() not in ("yes", "no", "unsure"):
            problems.append(f"screen question '{q}' ({qs[q]['text']}) is not answered with yes, no or unsure")
        elif len(str(v.get("evidence", "")).strip()) < 10:
            problems.append(f"screen question '{q}' needs evidence (at least 10 characters) with its {v['answer']}; a 'no' without a reason counts as unsure")
    if problems:
        return problems, None
    c = classify.classify(text, screen_answers=screen)
    if c["status"] != "ok":
        return ["the classifier could not read the action"], None
    if not c["screen"]["complete"]:
        problems.append("the screen is incomplete for: " + ", ".join(c["screen"]["needs_answers"]))
    for q in qs:
        final = c["screen"]["questions"][q]["answer"]
        if final in ("yes", "unsure") and idx(qs[q]["class"]) > idx(declared):
            who = c["screen"]["questions"][q]["decided_by"]
            problems.append(f"screen question '{q}' is {final} ({who}), which needs at least {qs[q]['class']}; the declared class {declared} is below it. A class is never lowered here")
    return problems, c
