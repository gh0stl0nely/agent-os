#!/usr/bin/env python3
"""Check a rollback plan for an R2+ action, or render one into the text a Preflight Brief needs.

  check_rollback.py --plan rollback.json            # structured plan (see fixtures/rollbacks.json)
  check_rollback.py --text "<Rollback section>" --action-class R3   # free text, e.g. from a brief
  check_rollback.py --brief BRIEF.md                # reads the Rollback section and the class from a brief
  check_rollback.py --plan rollback.json --render   # also print the Rollback paragraph for the brief

Statuses: pass (no findings) or flagged (one or more findings; exit 1). Exit 2 = unreadable input.
Every plan must carry a test step. A plan that has none, or whose test step cannot really be run, is flagged.
Plan fields: action, action_class (R2-R6), steps[], owner, duration_minutes, test_step, test_where
  (copy|scratch|sandbox|dry-run|documentation|live), backup{what,where} (R3), irreversible{why} (optional),
  external_recall (R4: how the effect is recalled or limited).
"""
import argparse
import json
import re
import sys

sys.dont_write_bytecode = True  # a vetted or scanned folder must not gain compiled files from our own run
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / ".claude/skills/risk-classify/scripts"))
sys.path.insert(0, str(REPO / ".claude/skills/secrets-hygiene/scripts"))
import classify  # noqa: E402
import scan_secrets  # noqa: E402

CLASSES = classify.CLASSES
VAGUE_STEP = re.compile(r"^\s*(?:just\s+|simply\s+)?(?:undo|revert|roll\s?back|reverse|fix|restore|redo|repair)(?:\s+(?:it|this|that|the\s+change|the\s+changes|everything|them))?\s*[.!]?\s*$", re.I)
VAGUE_WORDS = re.compile(r"\b(?:as needed|if necessary|somehow|tbd|to be decided|etc\.?|and so on|whatever works|figure it out|as appropriate)\b", re.I)
UNTESTABLE = re.compile(r"\b(?:no test|not tested|cannot be tested|can't be tested|untestable|not testable|skip(?:ped)? (?:the )?test|test later|assume[sd]? (?:it )?works?|n/?a|none|nothing to test|will work)\b", re.I)
VERIFY_VERB = re.compile(r"\b(?:confirm|check|compare|verify|list|diff|reproduce|read|inspect|open|restore one|match(?:es)?)\b", re.I)
WHERE_OK = {"copy", "scratch", "sandbox", "dry-run", "documentation"}
WHERE_ALL = WHERE_OK | {"live"}
OWNER_RX = re.compile(r"\b(?:the\s+)?(?:owner|librarian|verifier|guardian|chief of staff|operations manager|data steward|controller|growth marketer|[a-z]+(?:\s[a-z]+)?\s+agent|\d{2}-[a-z-]+)\b[^.]{0,30}\b(?:does|do|runs?|performs?|makes?)\b", re.I)
DURATION_RX = re.compile(r"\b(?:in|within|under|about|around|takes?|roughly)\b[^.]{0,25}\b\d+(?:\.\d+)?\s*(?:seconds?|minutes?|mins?|hours?|hrs?|days?)\b|\b(?:one|two|three|four|five|ten|fifteen|thirty)\s+(?:minutes?|hours?)\b", re.I)
TEST_MARK = re.compile(r"\btest\s*:\s*(\S.{14,})", re.I)
DECLARED_IRREVERSIBLE = re.compile(r"\b(?:not reversible|irreversible|cannot be undone|can't be undone|no way to undo|permanent)\b", re.I)


def clean(text):
    return classify.prepare(text)[0]


class Report:
    def __init__(self):
        self.findings = []

    def add(self, check, detail):
        self.findings.append({"check": check, "detail": detail})


def judge_step(r, i, step):
    s = clean(step) if isinstance(step, str) else ""
    if len(s.split()) < 5 or VAGUE_STEP.match(s):
        r.add("vague-step", f"step {i} is too vague to carry out ('{s[:40]}'); name the thing, the place and the action")
    elif VAGUE_WORDS.search(s):
        r.add("vague-step", f"step {i} leaves the work open ('{VAGUE_WORDS.search(s).group(0)}'); say exactly what to do")


def judge_test(r, test, where, cls):
    t = clean(test or "")
    if not t.strip():
        r.add("no-test-step", "there is no test step; a rollback that cannot be tested is flagged. Say how to prove the rollback works before it is needed")
        return
    if UNTESTABLE.search(t):
        r.add("untestable", "the test step says the rollback cannot be, or was not, tested; if it truly cannot be, say the action is irreversible and justify it")
    if len(t.split()) < 6 or not VERIFY_VERB.search(t):
        r.add("weak-test", "the test step must say what to run and what result proves the rollback works (confirm, compare, check, list...)")
    if where is not None and where not in WHERE_ALL:
        r.add("test-where", f"test_where '{where}' is not one of {sorted(WHERE_ALL)}")
    elif where == "live" and CLASSES.index(cls) >= 3:
        r.add("test-on-live", f"a {cls} rollback must not be tested on the live target; use a copy, a scratch folder, a sandbox, or the vendor's documentation")


def check_plan(plan):
    r = Report()
    if not isinstance(plan, dict):
        r.add("input", "the plan must be a JSON object")
        return result(r, None)
    cls = plan.get("action_class")
    if cls not in CLASSES[2:]:
        r.add("class", "action_class must be R2 to R6; rollback plans are for those classes")
        cls = "R2"
    full = json.dumps(plan, ensure_ascii=False)
    inj = [m.group(0)[:50] for rx in classify.INJECTION_RX for m in [rx.search(clean(full))] if m]
    if inj:
        r.add("instruction-like-text", "instruction-like text inside the plan was treated as data and not followed: " + "; ".join(inj))
    if hits := scan_secrets.scan_text(full):
        r.add("secrets", f"{len(hits)} secret-like value(s) in the plan (rule {hits[0]['rule']}); the value is not repeated")
    if not plan.get("action") or len(clean(str(plan.get("action")))) < 10:
        r.add("action", "state the action this rollback undoes")
    else:
        c = classify.classify(str(plan["action"]))
        if c["status"] == "ok" and CLASSES.index(c["class"]) > CLASSES.index(cls):
            r.add("class", f"the action computes to {c['class']}, above the declared {cls}; the higher class stands")
            cls = c["class"]

    irr = plan.get("irreversible")
    steps = plan.get("steps") or []
    if irr:
        why = clean(str(irr.get("why", ""))) if isinstance(irr, dict) else ""
        if len(why) < 30:
            r.add("irreversible-unjustified", "an action declared irreversible needs a reason (30+ characters) why it is still worth doing, and what limits the damage")
        else:
            r.add("irreversible-declared", "this action is declared irreversible; the owner must see that in the brief. A test of the limiting step is still required")
    if not steps and not irr:
        r.add("no-steps", "list the exact rollback steps in order")
    for i, s in enumerate(steps, 1):
        judge_step(r, i, s)
    if not plan.get("owner") or len(str(plan["owner"]).strip()) < 3:
        r.add("no-owner", "name who performs the rollback")
    d = plan.get("duration_minutes")
    if not isinstance(d, (int, float)) or isinstance(d, bool) or d <= 0:
        r.add("no-duration", "give duration_minutes as a number greater than 0")
    judge_test(r, plan.get("test_step"), plan.get("test_where"), cls)
    if plan.get("test_where") is None and plan.get("test_step"):
        r.add("test-where", "say where the test runs: copy, scratch, sandbox, dry-run, documentation or live")

    b = plan.get("backup")
    if cls == "R3" and not irr:
        if not isinstance(b, dict) or not b.get("what") or not b.get("where"):
            r.add("no-backup", "an R3 action needs a backup taken first: say what is saved and where")
    if cls == "R4" and not irr and not str(plan.get("external_recall", "")).strip():
        r.add("no-external-recall", "an R4 action reaches another person: say how it is recalled or limited (delete, edit window, cancel before cutoff), or declare it irreversible")
    if cls == "R5" and not any(re.search(r"revok|rotat|reset|disable", clean(str(s)), re.I) for s in steps):
        r.add("r5-no-revoke", "an R5 rollback is revoking or rotating at the provider; say so")
    if cls == "R6" and not any(re.search(r"cancel|refund|stop|unsubscrib", clean(str(s)), re.I) for s in steps):
        r.add("r6-no-cancel", "an R6 rollback must say how to cancel and what, if anything, is refunded")
    return result(r, cls)


def result(r, cls):
    return {"status": "flagged" if r.findings else "pass", "action_class": cls, "findings": r.findings}


def check_text(text, cls):
    """Free-text Rollback section (as in a brief)."""
    r = Report()
    t = clean(text or "")
    if cls not in CLASSES[2:]:
        r.add("class", "class must be R2 to R6")
        cls = "R2"
    if len(t) < 30:
        r.add("thin", "the Rollback section is too thin: give exact steps, who does them, how long they take")
    if DECLARED_IRREVERSIBLE.search(t) and len(DECLARED_IRREVERSIBLE.sub("", t).strip()) < 40:
        r.add("irreversible-unjustified", "'not reversible' needs a reason and a limit on the damage")
    for i, sent in enumerate(s for s in re.split(r"(?<=[.!?])\s+", t) if VAGUE_STEP.match(s)):
        r.add("vague-step", f"vague rollback sentence: '{sent[:40]}'")
    if VAGUE_WORDS.search(t):
        r.add("vague-step", f"the text leaves the work open ('{VAGUE_WORDS.search(t).group(0)}')")
    if not OWNER_RX.search(t):
        r.add("no-owner", "name who does the rollback, e.g. 'The owner does this ...'")
    if not DURATION_RX.search(t):
        r.add("no-duration", "say how long the rollback takes, e.g. 'in about five minutes'")
    m = TEST_MARK.search(t)
    if not m:
        r.add("no-test-step", "there is no test step; add 'Test: ...' saying how to prove the rollback works before it is needed")
    else:
        judge_test(r, m.group(1), "copy", cls)  # the text form cannot say where; the test must still be real
    inj = [m.group(0)[:50] for rx in classify.INJECTION_RX for m in [rx.search(t)] if m]
    if inj:
        r.add("instruction-like-text", "instruction-like text inside the rollback was treated as data and not followed: " + "; ".join(inj))
    if hits := scan_secrets.scan_text(text or ""):
        r.add("secrets", f"{len(hits)} secret-like value(s) (rule {hits[0]['rule']}); the value is not repeated")
    return result(r, cls)


def render(plan):
    steps = " ".join(f"{i}. {s.rstrip('.')}." for i, s in enumerate(plan["steps"], 1)) if plan.get("steps") else ""
    own = plan.get("owner", "the owner")
    dur = plan.get("duration_minutes")
    head = steps or (f"Not reversible. {plan['irreversible']['why']}" if plan.get("irreversible") else "")
    bits = [head, f"{own} does this in about {int(dur)} minutes." if dur else "", f"Test: {plan.get('test_step', '').rstrip('.')}."]
    if plan.get("backup"):
        bits.insert(1, f"Backup first: {plan['backup']['what']}, kept at {plan['backup']['where']}.")
    if plan.get("external_recall"):
        bits.insert(1, f"Recall: {plan['external_recall']}")
    return " ".join(b for b in bits if b)


def brief_parts(text):
    sec = re.search(r"^## Rollback\s*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    cls = re.search(r"^- \*\*Action class:\*\*\s*(R[0-6])", text, re.M)
    return (sec.group(1).strip() if sec else ""), (cls.group(1) if cls else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan")
    g.add_argument("--text")
    g.add_argument("--brief")
    ap.add_argument("--action-class")
    ap.add_argument("--render", action="store_true")
    a = ap.parse_args()
    try:
        if a.plan:
            plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
            res = check_plan(plan)
            if a.render and res["status"] == "pass":
                res["rollback_text"] = render(plan)
        elif a.brief:
            text, cls = brief_parts(Path(a.brief).read_text(encoding="utf-8"))
            res = check_text(text, a.action_class or cls)
        else:
            res = check_text(a.text, a.action_class)
    except (OSError, ValueError) as e:
        print(json.dumps({"status": "error", "error": e.__class__.__name__}))
        sys.exit(2)
    print(json.dumps(res, indent=2))
    sys.exit(0 if res["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
