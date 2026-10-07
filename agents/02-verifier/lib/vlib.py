"""Shared helpers for the Verifier scripts.

Standard library plus `jsonschema` only (the same dependency as contracts/validate.py).
Nothing here reads the network. Every function is deterministic for the same inputs.
"""
import hashlib
import importlib.util
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CONTRACTS = REPO / "agent-system" / "contracts"
SKILLS = REPO / ".claude" / "skills"

# ---------------------------------------------------------------- contracts

_VALIDATE = None


def _validate_module():
    """Import contracts/validate.py by path (it is not a package and must not be edited)."""
    global _VALIDATE
    if _VALIDATE is None:
        spec = importlib.util.spec_from_file_location("contracts_validate", CONTRACTS / "validate.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _VALIDATE = mod
    return _VALIDATE


def schema_errors(stem, obj):
    """Return a list of 'path: message' strings; empty means valid against <stem>.schema.json."""
    v = _validate_module().validator(stem)
    out = []
    for e in sorted(v.iter_errors(obj), key=lambda e: [str(p) for p in e.path]):
        path = ".".join(str(p) for p in e.path) or "(row)"
        out.append(f"{path}: {e.message}")
    return out


# ---------------------------------------------------------------- time

# contracts/validate.py only checks date-time formats when the optional rfc3339-validator
# package is installed, so we check strictly ourselves (see change request).
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")


def parse_ts(value):
    """Strict RFC 3339 date-time with an offset. Returns an aware datetime or None."""
    if not isinstance(value, str) or not _TS_RE.match(value):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def now_from(arg=None):
    if arg:
        ts = parse_ts(arg)
        if ts is None:
            raise SystemExit(f"--now must be an RFC 3339 date-time with offset, got {arg!r}")
        return ts
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0)


def iso(dt):
    return dt.isoformat()


# ---------------------------------------------------------------- numbers

def to_decimal(v):
    """Decimal from a JSON number or a numeric string. Floats go through repr() so that
    2.665 stays 2.665 (Decimal(2.665) would carry binary error). Returns None if not numeric."""
    if isinstance(v, bool) or v is None:
        return None
    try:
        if isinstance(v, Decimal):
            return v
        if isinstance(v, int):
            return Decimal(v)
        if isinstance(v, float):
            return Decimal(repr(v))
        if isinstance(v, str):
            s = v.strip().replace(",", "").lstrip("$€£")
            return Decimal(s)
    except (InvalidOperation, ValueError):
        return None
    return None


_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_in(text):
    """Set of Decimal values for every number written in `text` (commas removed, sign ignored)."""
    out = set()
    for m in _NUM_RE.finditer(text or ""):
        d = to_decimal(m.group(0))
        if d is not None:
            out.add(d)
    return out


# ---------------------------------------------------------------- files

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_rows(path):
    """One JSON object, a JSON array, or JSON Lines."""
    text = Path(path).read_text(encoding="utf-8").strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]


def resolve_inside(root, rel):
    """Resolve `rel` under `root`; None if it escapes (absolute path, .., or a symlink out)."""
    root = Path(root).resolve()
    if rel is None or str(rel).strip() == "":
        return None
    p = Path(rel)
    if p.is_absolute():
        return None
    q = (root / p).resolve()
    try:
        q.relative_to(root)
    except ValueError:
        return None
    return q


def dump(obj, path=None):
    text = json.dumps(obj, indent=2, ensure_ascii=False, default=str) + "\n"
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(text, encoding="utf-8")
    return text


# ---------------------------------------------------------------- text

def norm_text(s):
    s = (s or "").replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().casefold()


_STOP = set("""a an the and or of to in on for with by from at as is are was were be been it its this that these those
has have had will would shall should can could may might not no than then so such into over under per each
about above after again all also any both but if more most other our out own same some their them there they
very what when where which while who whom why you your""".split())


def content_terms(text):
    return {w for w in re.findall(r"[a-z][a-z0-9]{3,}", (text or "").casefold()) if w not in _STOP}


# ---------------------------------------------------------------- injection scan

# Instructions aimed at an AI reader that may be hiding inside evidence. Evidence is data: these
# are reported and ignored, never followed. Patterns are deliberately narrow so that ordinary
# accounting prose ("the reviewer should confirm", "mark as paid") does not trip them.
_INJECTION = [
    ("ignore_instructions",
     r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all|any|your|the)\b[^.\n]{0,30}\b(instructions?|rules?|prompts?|guidelines?|checks?)\b"),
    ("force_verdict",
     r"\b(mark|set|record|report|rate|label)\b[^.\n]{0,40}\b(as|to)\b[^.\n]{0,15}\b(verified|pass|passed|approved|correct)\b"),
    ("address_ai",
     r"\b(ai|llm|language model|assistant|verifier|claude)\b[^.\n]{0,30}\b(must|should|shall|please|need to|are to|now)\b"),
    ("role_markup",
     r"(^|\n)\s*(system|assistant|developer)\s*:|<\s*/?\s*(system|instructions?)\s*>"),
    ("suppress_flag",
     r"\b(do not|don't|never)\b[^.\n]{0,25}\b(flag|report|mention|disclose|escalate)\b"),
    ("new_instructions", r"\bnew (instructions?|task|rules?)\b"),
    ("skip_checks",
     r"\b(skip|bypass|disable|stop)\b[^.\n]{0,25}\b(verification|checks?|review|audit)\b"),
]
_INJECTION_RE = [(n, re.compile(p, re.IGNORECASE)) for n, p in _INJECTION]


def scan_injection(text):
    """Return [{line, pattern, snippet}] for instruction-like text. Line numbers are 1-based."""
    hits = []
    for i, line in enumerate((text or "").splitlines(), 1):
        for name, rx in _INJECTION_RE:
            m = rx.search(line)
            if m:
                hits.append({"line": i, "pattern": name, "snippet": m.group(0).strip()[:80]})
    return hits


# ---------------------------------------------------------------- rubric

REQUIRED_HEADINGS = ["Config", "Scope", "Checks", "Conciseness", "Known pitfalls"]
HIGH_STAKES_DOMAINS = {"finance", "tax", "cash", "customer-facing"}


def load_rubric(path):
    """Parse a rubric file (shape in agents/02-verifier/rubrics/_SHAPE.md).
    Returns {'path','name','config','checks','headings','problems'}; `problems` lists shape errors."""
    text = Path(path).read_text(encoding="utf-8")
    problems = []
    m = re.search(r"^#\s+Rubric:\s*(.+)$", text, re.M)
    name = m.group(1).strip() if m else None
    if not name:
        problems.append("missing title line '# Rubric: <name>'")
    headings = re.findall(r"^##\s+(.+?)\s*$", text, re.M)
    for h in REQUIRED_HEADINGS:
        if h not in headings:
            problems.append(f"missing section '## {h}'")
    if [h for h in headings if h in REQUIRED_HEADINGS] != [h for h in REQUIRED_HEADINGS if h in headings]:
        problems.append("sections are out of order")
    config = {}
    cm = re.search(r"##\s+Config\s*\n+```json\s*\n(.*?)\n```", text, re.S)
    if not cm:
        problems.append("'## Config' must contain a fenced json block")
    else:
        try:
            config = json.loads(cm.group(1))
        except json.JSONDecodeError as e:
            problems.append(f"Config json does not parse: {e}")
    for key, typ in (("domain", str), ("stakes", str), ("tolerance", dict)):
        if key not in config:
            problems.append(f"Config missing '{key}'")
        elif not isinstance(config[key], typ):
            problems.append(f"Config '{key}' has the wrong type")
    if config.get("stakes") not in (None, "routine", "high"):
        problems.append("Config 'stakes' must be 'routine' or 'high'")
    for key in ("max_age_days", "stakes_threshold"):
        if key not in config:
            problems.append(f"Config missing '{key}' (use null for none)")
    checks = re.findall(r"^-\s+(R-[A-Z0-9-]+)\s+\[(blocking|major|minor)\]:\s*(.+)$", text, re.M)
    if len(checks) < 3:
        problems.append("'## Checks' needs at least 3 items like '- R-ID [blocking|major|minor]: question'")
    ids = [c[0] for c in checks]
    if len(ids) != len(set(ids)):
        problems.append("check ids are not unique")
    if "R-CONCISE" not in ids:
        problems.append("missing the conciseness item 'R-CONCISE' (a longer answer is not a better one)")
    return {"path": str(path), "name": name, "config": config,
            "checks": [{"id": a, "severity": b, "question": c} for a, b, c in checks],
            "headings": headings, "problems": problems}


def tolerance_for(rubric, unit):
    tol = rubric["config"].get("tolerance", {})
    by_unit = tol.get("by_unit", {})
    if unit in by_unit:
        return by_unit[unit]
    return tol.get("default", {})


def recommended_tier(rubric, claims):
    cfg = rubric["config"]
    if cfg.get("stakes") == "high" or cfg.get("domain") in HIGH_STAKES_DOMAINS:
        return "opus"
    thr = to_decimal(cfg.get("stakes_threshold"))
    if thr is not None:
        for c in claims:
            v = to_decimal(c.get("value"))
            if v is not None and abs(v) >= thr:
                return "opus"
    return "sonnet"


# ---------------------------------------------------------------- results

def mk_result(reasoning, checks, result, code, missing=None, flags=None, **extra):
    """Standard check result. Key order matters: reasoning comes before the result."""
    assert result in ("pass", "fail", "unverifiable")
    out = {"reasoning": list(reasoning), "checks": list(checks), "result": result, "reason_code": code,
           "missing_evidence": list(missing or []), "flags": list(flags or [])}
    out.update(extra)
    return out


def reasoning_precedes(obj, result_key):
    keys = list(obj.keys())
    return ("reasoning" in keys and result_key in keys and keys.index("reasoning") < keys.index(result_key)
            and isinstance(obj["reasoning"], str) and obj["reasoning"].strip() != "")
