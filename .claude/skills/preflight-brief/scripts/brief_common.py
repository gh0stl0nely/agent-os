"""Shared helpers for build_brief.py and check_brief.py. Standard library plus the contracts validator (jsonschema)."""
import json
import re
import sys
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
