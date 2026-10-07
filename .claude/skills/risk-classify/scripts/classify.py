#!/usr/bin/env python3
"""risk-classify: give a planned action a class R0 to R6 from agent-system/contracts/autonomy-matrix.md.

Standard library only. Deterministic: the same text always gives the same class.

Usage:
  classify.py --action "Delete the old drafts"            classify one description
  classify.py --file plan.txt                              read the description from a file
  echo "..." | classify.py -                               read the description from stdin
Options:
  --envelope [--task-id T] [--from-agent A] [--to-agent B] [--preflight-id PF-YYYYMMDD-n]
        wrap the result in an agent envelope (contracts/agent-envelope.schema.json)
  --run-id RUN                                             run id for the claim row

Policy (see SKILL.md):
  * The class is the HIGHEST class of any rule that matches (the matrix says: when unsure, use the higher class).
  * No rule matched -> R2 and needs_review (it is never rounded down to R0 or R1); a dangerous word anywhere in such
    an action (delete, send, publish, pay, merge ...) raises it to R3, R4 or R6.
  * needs_review and flagged descriptions need the owner's explicit yes.
  * Instruction-like text inside the description is treated as data: it is flagged, never obeyed,
    and a flagged description is at least R2.
  * A secret-like value inside the description makes the action at least R5 and is never echoed.
  * The output never repeats the description; it reports only matched keywords and a hash id.
Exit code: 0 classified, 2 blocked (no usable description).
"""
import argparse
import hashlib
import json
import re
import sys

sys.dont_write_bytecode = True  # a vetted or scanned folder must not gain compiled files from our own run
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]  # <repo>/.claude/skills/risk-classify/scripts
MATRIX = REPO / "agent-system" / "contracts" / "autonomy-matrix.md"
SECRETS_SCRIPTS = REPO / ".claude" / "skills" / "secrets-hygiene" / "scripts"
CLASSES = ["R0", "R1", "R2", "R3", "R4", "R5", "R6"]
SCRIPT_REL = ".claude/skills/risk-classify/scripts/classify.py"


def load_matrix():
    """Parse the class table from the matrix file so every citation quotes the real row."""
    rows = {}
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 4 and re.match(r"^R[0-6]\b", cells[0]):
            cls = cells[0][:2]
            rows[cls] = {"name": cells[0][3:], "meaning": cells[1], "examples": cells[2], "rule": cells[3]}
    if sorted(rows) != CLASSES:
        raise SystemExit(f"cannot parse all seven classes from {MATRIX}")
    return rows


# ---------- text preparation ----------

ZERO_WIDTH = re.compile("[\u200b-\u200f\u2060-\u2064\ufeff\u202a-\u202e\u2066-\u2069\U000e0000-\U000e007f]")

# Phrases that look like actions but are not. Removed before rule matching; the list is part of the output.
NEUTRAL = [
    r"\btoken (?:budget|usage|limits?|count|cost)s?\b",
    r"\bpay[- ]periods?\b",
    r"\bposting (?:hour|window|time|queue|schedule)s?\b",
    r"\bsecret[- ](?:scanning|scanner|hygiene|patterns?)\b",
    r"\bpush protection\b",
]

INJECTION = [
    r"ignore (?:all |any |the |your )?(?:previous|prior|above|earlier|preceding)? ?(?:instructions|rules|guidance|matrix|guardian|policy)",
    r"disregard (?:the |all |any |your )?(?:autonomy matrix|rules|instructions|guardian|preflight|policy)",
    r"\b(?:you are|you're) now\b",
    r"\bsystem(?: prompt| message)?\s*:",
    r"\b(?:classify|mark|label|treat|rate|call) (?:this|it|the action)(?: as)? (?:r0|r1|safe|harmless|low[- ]risk|approved|routine)",
    r"\bpre-?approved\b",
    r"\balready (?:approved|authori[sz]ed)\b",
    r"\b(?:owner|user|admin|anthropic|guardian) (?:has |have )?(?:already )?(?:approved|authori[sz]ed|signed off)\b",
    r"\bskip (?:the )?(?:preflight|guardian|review|approval|classification|safety|checks?)\b",
    r"\b(?:do not|don't|never) (?:flag|mention|tell|report|log|escalate|warn)\b",
    r"\boverride (?:the |all |any )?(?:rules?|matrix|guardian|policy|checks?|class)\b",
    r"\b(?:new|updated|real) instructions?\s*:",
    r"<\s*/?\s*(?:system|instructions?|admin)\s*>",
    r"\bjailbreak\b",
    r"\breveal (?:the |your )?(?:system )?prompt\b",
    r"\bact as\b",
]
INJECTION_RX = [re.compile(p, re.I) for p in INJECTION]


def prepare(text):
    """NFKC-normalise, strip invisible characters, lower-case. Returns (clean, hidden_unicode_found)."""
    norm = unicodedata.normalize("NFKC", text)
    hidden = bool(ZERO_WIDTH.search(norm))
    norm = ZERO_WIDTH.sub("", norm)
    return norm.lower(), hidden


# ---------- rules ----------

def V(verbs):
    """A verb used as an action: at the start of a clause, or after an auxiliary like 'will' or 'to'.
    This keeps 'read the email from the supplier' from matching the verb 'email'."""
    return (r"(?:^|[;:.\n,(]|\b(?:and|then|will|should|must|to|can|may|please|also|now|just|first|next|plans?|going)\b)\s*"
            r"(?:the (?:agent|assistant|system|skill|role)\s+)?(?:(?:will|should|must|can)\s+)?"
            # fillers between the clause start and the verb ("Quietly delete", "Go ahead and send", "Just quickly remove")
            r"(?:(?:go ahead and|proceed to|feel free to|be sure to|make sure to|try to)\s+)?"
            r"(?:(?:[a-z]+ly|just|also|now|then|please|first|next|again|still|simply|immediately|finally|kindly)\s+){0,3}"
            r"(?P<kw>" + verbs + r")\b")


SECRET_NOUN = (r"\b(?P<kw>api[ _-]?keys?|api[ _-]?secrets?|(?:access|auth|refresh|bearer|session|personal access)[ _-]?tokens?|"
               r"(?:github|slack|threads|square|notion|stripe|anthropic|openai|meta|instagram) tokens?|"
               r"passwords?|passphrases?|passwd|credentials?|secrets?|private[ _-]?keys?|ssh[ _-]?keys?|client[ _-]?secrets?|"
               r"oauth|2fa codes?|recovery codes?|one[- ]time (?:codes?|passcodes?))\b")
SECRET_VERB = (r"\b(?P<kw2>create|generate|store|save|put|paste|type|enter|rotate|revoke|reset|use|share|export|set|add|copy|move|"
               r"commit|write|embed|hard-?code|echo|load|read|fetch|retrieve|send|include|pass|provide|expose|print|upload|attach|"
               r"log in|sign in)\b")

RECIPIENT = (r"(?P<kw2>supplier|vendor|customer|client|accountant|staff|employee|worker|partner|landlord|bank|cra|lender|"
             r"team member|team|crew|everyone|everybody|colleague|co-?worker|group chat|channel|mailing list|subscriber|follower|audience|"
             r"family|friend|contact|lawyer|insurer|insurance|school|daycare|doctor|"
             r"order|subscription|booking|reservation|appointment)s?")

# (id, class, [regexes that must ALL match], why)
RULES = [
    # R5 secrets
    ("credential-handling", "R5", [SECRET_NOUN, SECRET_VERB],
     "A secret noun together with a handling verb: create, store, rotate or use credentials is human only."),
    ("login", "R5", [r"\b(?P<kw>log ?in|login|sign ?in|authenticate)\b"],
     "Logging in uses credentials, which agents never type."),
    # R6 spend
    ("spend-verb", "R6", [V(r"buy|bought|purchase|purchasing|pay|paying|pays|subscribe|top[- ]?up|checkout|prepay|add credits?")],
     "Spending money beyond the plan."),
    ("paid-thing", "R6", [r"\bpaid\b(?: [\w-]+){0,2} (?P<kw>tool|api|plan|feed|data|tier|service|model|subscription)\b"],
     "A paid tool, API or data source costs money beyond the plan."),
    ("plan-upgrade", "R6", [r"\b(?P<kw>upgrade|bump|raise|boost|increase|step up|move up|level up|jump|switch up)\b.{0,40}\b(?P<kw2>plan|tier|subscription|account|seat|licen[cs]e|quota|credits?|allowance)\b"],
     "Upgrading or bumping a plan or subscription changes what is billed."),
    ("higher-tier", "R6", [r"\b(?P<kw>higher|premium|pro|max|enterprise|paid|bigger|next|upper|team|business) (?P<kw2>tier|plan)\b"],
     "A higher or paid tier costs more than the current plan."),
    ("auto-payment", "R6", [r"\b(?P<kw>turn on|enable|set up|schedule|authori[sz]e|approve|activate|start)\b.{0,40}\b(?P<kw2>auto-?pay|automatic payments?|recurring payments?|direct debit|pre-?authori[sz]ed|standing order)\b"],
     "Setting up automatic or recurring payments commits money."),
    ("beyond-allowance", "R6", [r"\b(?P<kw>beyond|over|exceed(?:s|ing)?)\b.{0,15}\b(?P<kw2>plan|allowance)\b"],
     "Going past the plan allowance is spend."),
    # R4 external
    ("public-post", "R4", [V(r"publish|tweet|retweet|broadcast")], "Publishing leaves the system and is public."),
    ("social-post", "R4", [r"\b(?P<kw>post(?:s|ing)?)\b.{0,60}\b(?:to|on)\b.{0,20}\b(?P<kw2>threads|instagram|facebook|linkedin|twitter|tiktok|bluesky|mastodon|social media|the (?:public )?(?:feed|account|page|channel))\b",
                          r"\b(?P<kw>public(?:ly)?)\b.{0,15}\b(?P<kw2>post)\b"],
     "A public post reaches other people."),
    ("send-comm", "R4", [V(r"send|email|e-mail|message|text|dm|notify|reply|respond|forward|call|phone|ping|contact|invite|tell|ask|announce|remind|alert|inform|warn|advise|"
                           r"write to|reach out to|get in touch with|follow up with|chase|whatsapp|slack|ring|shoot|drop"),
                         r"\b" + RECIPIENT],
     "Messaging a supplier, accountant, staff member, team, customer or other outside party reaches another person."),
    ("contact-verb", "R4", [V(r"message|text|dm|email|e-mail|whatsapp|slack|ping|notify|tell|inform|remind|announce|alert|warn")],
     "A verb that means contacting someone reaches another person, even when the person is named rather than described."),
    ("send-message-noun", "R4", [V(r"send|deliver|forward|fire off|shoot|drop|leave|push"),
                                 r"\b(?P<kw2>messages?|e-?mails?|texts?|dms?|notes?|notifications?|alerts?|reminders?|announcements?|replies|reply|memos?|letters?|invoices?|quotes?|estimates?)\b"],
     "Sending a message, note or notice delivers something to another person."),
    ("trigger-live-run", "R4", [V(r"dispatch|trigger|kick off|fire|fire off|launch|force|re-?run|rerun|run|start|execute|invoke|run now"),
                                r"\b(?P<kw2>daily[- ]post|poster(?![-\w])|post mode|publish(?:ing)? (?:job|workflow)|workflow dispatch|workflow_dispatch|(?:github )?workflow|cron job|scheduled (?:job|run|task)|pipeline)\b"],
     "Starting a workflow, scheduled job or pipeline runs real code that can post, send or change things outside the system (the daily-post workflow publishes to Threads)."),
    ("gh-workflow-run", "R4", [r"(?P<kw>\bgh workflow run\b|\bworkflow_dispatch\b|\bworkflows?/[\w.-]+/dispatches\b)"],
     "Dispatching a workflow runs it on GitHub."),
    ("goes-out", "R4", [r"\b(?P<kw>goes? out|go(?:ing)? live|going out|send(?:s|ing)? out|push(?:es|ed|ing)? out|ship(?:s|ped|ping)? out)\b",
                        r"\b(?P<kw2>post|posts|message|email|order|update|newsletter|announcement|content|photo|video|story|reel|thread)\b"],
     "Something that 'goes out' or 'goes live' reaches other people."),
    ("share-access", "R4", [V(r"grant|give|share|invite|allow|add|provide|extend"),
                            r"\b(?P<kw2>access|permissions?|editor|viewer|admin rights|collaborators?|guest)\b"],
     "Giving a person access or permissions reaches another person and changes who can see or edit the data."),
    ("submit", "R4", [V(r"submit|place|file|lodge"), r"\b(?P<kw2>order|form|report|filing|return|application|claim|request)s?\b"],
     "Submitting an order, form or filing leaves the system."),
    ("share-external", "R4", [V(r"share|upload|send|post"), r"\b(?P<kw2>publicly|externally|outside|public)\b"],
     "Sharing outside the system."),
    ("push-or-pr", "R4", [r"(?P<kw>\bgit push\b|\bforce[- ]push\b|\bpush(?:ing|es)?\b.{0,30}\b(?:to|onto)\b.{0,15}\b(?:remote|origin|github|the repo|upstream|branch)\b|"
                          r"\b(?:open|create|raise)\b.{0,20}\b(?:pull request|pr|issue)\b|\bgh pr create\b)"],
     "A push or pull request leaves the local clone and reaches a public repository."),
    ("cancel-external", "R4", [V(r"cancel|void|refund|terminate"), r"\b" + RECIPIENT],
     "Cancelling or refunding with an outside party reaches that party."),
    # R3 destructive
    ("delete", "R3", [V(r"delete|remove|erase|wipe|purge|destroy|nuke|zap|trash|discard|drop|truncate|prune|clear out|get rid of|clean up|empty|unlink|shred|rm")],
     "Deleting is destructive."),
    ("overwrite", "R3", [r"\b(?P<kw>overwrit(?:e|es|ing|ten))\b"],
     "Overwriting loses the old content unless a backup exists, so it is treated as destructive."),
    ("cancel", "R3", [V(r"cancel|terminate|unsubscribe|deactivate|revoke")], "Cancelling cannot always be undone."),
    ("force-reset", "R3", [r"(?P<kw>--force\b|\bforce[- ]push\b|\bgit reset --hard\b|\breset --hard\b|\bgit clean\b|\bbranch -d\b|\brm -r)"],
     "Force and hard-reset commands discard history or files."),
    ("merge-main", "R3", [r"\b(?P<kw>merge|merging|merged)\b.{0,40}\b(?:into|to|onto)\s+(?:the\s+)?(?P<kw2>main|master|production|prod|default branch)\b",
                          r"(?P<kw>\bgh pr merge\b|\bsquash and merge\b|\bmerge (?:the |this |that |my )?(?:pull request|pr)\b|\bpush\b.{0,20}\b(?P<kw2>main|master)\b)"],
     "Merging into main is irreversible for the live repository."),
    # R2 modify shared state
    ("modify", "R2", [V(r"edit|modify|update|change|alter|amend|patch|rename|move|rewrite|refactor|replace|tweak|adjust|correct|fix|revise|"
                        r"reconfigure|configure|enable|disable|toggle|install|uninstall|upgrade|migrate|merge|rebase|restore|revert|"
                        r"apply|deploy|release|register|activate|set up|set")],
     "Changing something that exists changes shared state."),
    ("add-to-shared", "R2", [V(r"add|append|insert"), r"\b(?:to|in|into)\b.{0,30}\b(?P<kw2>config|settings|workflow|roster|registry|contracts?|readme|claude\.md|ledger|rules?|prompts?|memory|schema)\b"],
     "Adding to a shared file or setting changes shared state."),
    # R1 reversible internal write (only with an owned-path hint and no shared-state hint)
    ("create-owned", "R1", [V(r"create|write|draft|add|generate|compose|prepare|save|commit|record|log|export|dump|produce|build|make"),
                            r"(?P<kw2>agents/|\.claude/skills/|knowledge/|owned path|my owned|working (?:folder|directory)|scratch|local (?:branch|clone|copy)|build branch|drafts?/|fixtures?)"],
     "Creating a new file or draft inside the role's own paths is reversible."),
    ("run-tests", "R1", [V(r"run|execute"), r"\b(?P<kw2>tests?|evals?|validator|linter|dry[- ]run)\b"],
     "Running tests writes only logs."),
    # R0 read
    ("read-only", "R0", [V(r"search|read|fetch|look up|lookup|list|summari[sz]e|review|check|open|query|grep|compare|analy[sz]e|inspect|view|show|find|scan|measure|count|calculate|compute|verify|validate|diff|browse|retrieve|explain|describe|report")],
     "Read-only access to data or the public web."),
]
RULES = [(rid, cls, [re.compile(p, re.I | re.M) for p in pats], why) for rid, cls, pats, why in RULES]
SHARED_STATE_HINT = re.compile(r"\b(?:existing|shared|live|production|someone else'?s|other roles?'?s?|another role'?s?|config(?:uration)?|settings?|prompt|"
                               r"brain rule|workflow|contracts?|roster|registry|readme|claude\.md|schema|hook|permissions?|ledger)\b", re.I)
# When NO rule recognised the action, the classifier is unsure, and the matrix says to use the higher class when unsure.
# These words are searched anywhere in the text (not only as a verb at the start of a clause). They can only RAISE a
# class that would otherwise be the unsure R2; they never apply to an action a rule did recognise.
SAFETY_NET = [
    ("R6", re.compile(r"\b(?P<kw>buy|purchase|pay|paying|subscribe|upgrade|bump|top[- ]?up|prepay|renew)\b", re.I)),
    ("R4", re.compile(r"\b(?P<kw>send|email|publish|post|dispatch|trigger|submit|message|notify|text|forward|invite|announce|reply|tell|ask|order|share|upload|call)\b", re.I)),
    ("R3", re.compile(r"\b(?P<kw>delete|remove|erase|wipe|purge|destroy|cancel|overwrite|drop|truncate|discard|merge|reset|revoke|terminate)\b", re.I)),
]
INSTRUCTIONS_ONLY = re.compile(r"\b(?:write|draft|document|prepare)\b.{0,40}\b(?:instructions?|steps?|guide|checklist)\b.{0,80}\bowner\b", re.I)


def load_secret_scanner():
    try:
        sys.path.insert(0, str(SECRETS_SCRIPTS))
        import scan_secrets  # noqa: E402
        return scan_secrets
    except Exception:
        return None


def classify(text):
    """Return the classification record for one description. Pure function apart from reading the matrix."""
    matrix = load_matrix()
    text = text if isinstance(text, str) else ""
    clean, hidden = prepare(text)
    if not clean.strip():
        return {"status": "blocked", "reason": "no action description was supplied; no class is guessed",
                "missing": ["a one-sentence description of the planned action"]}

    action_id = "A-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    neutral_hits = []
    scrubbed = clean
    for pat in NEUTRAL:
        for m in re.finditer(pat, scrubbed):
            neutral_hits.append(m.group(0))
        scrubbed = re.sub(pat, " ", scrubbed)

    matched = []
    for rid, cls, rxs, why in RULES:
        kws = []
        ok = True
        for rx in rxs:
            m = rx.search(scrubbed)
            if not m:
                ok = False
                break
            gd = m.groupdict()
            kws += [gd[k] for k in ("kw", "kw2") if gd.get(k)]
        if not ok:
            continue
        if rid == "create-owned" and SHARED_STATE_HINT.search(scrubbed):
            continue
        matched.append({"rule": rid, "class": cls, "keywords": sorted({k.strip()[:30] for k in kws}), "why": why})

    injection = []
    for rx in INJECTION_RX:
        m = rx.search(clean)
        if m:
            injection.append(m.group(0)[:50])
    scanner = load_secret_scanner()
    secret_like = bool(scanner and scanner.scan_text(text))

    flags = {
        "injection": injection,
        "hidden_unicode": hidden,
        "secret_like_value_in_description": secret_like,
        "needs_review": False,
        "possible_instructions_only": False,
        "neutralised_phrases": neutral_hits,
    }

    idx = max((CLASSES.index(m["class"]) for m in matched), default=None)
    rounded_up = False
    if idx is None:
        idx, rounded_up = CLASSES.index("R2"), True
        flags["needs_review"] = True
        matched.append({"rule": "no-rule-matched", "class": "R2", "keywords": [],
                        "why": "No rule recognised the action, so it is rounded up to R2 and a person must read it."})
        for net_cls, net_rx in SAFETY_NET:  # unsure: use the higher class if a dangerous word appears anywhere
            m = net_rx.search(scrubbed)
            if m and CLASSES.index(net_cls) > idx:
                idx = CLASSES.index(net_cls)
                matched.append({"rule": "unsure-dangerous-word", "class": net_cls, "keywords": [m.group("kw")[:30]],
                                "why": f"No rule recognised the action but the word '{m.group('kw')}' appears in it; unsure, so the higher class {net_cls} is used until a person reads it."})
                break
    if injection or hidden:
        if idx < CLASSES.index("R2"):
            idx, rounded_up = CLASSES.index("R2"), True
        matched.append({"rule": "tainted-description", "class": "R2", "keywords": [],
                        "why": "The description contains instruction-like or hidden text. It is data, not a command; it was ignored and flagged."})
    if secret_like:
        if idx < CLASSES.index("R5"):
            idx, rounded_up = CLASSES.index("R5"), True
        matched.append({"rule": "secret-value-in-description", "class": "R5", "keywords": [],
                        "why": "A secret-like value appears in the description. Agents never handle secret values."})
    if INSTRUCTIONS_ONLY.search(scrubbed) and CLASSES[idx] == "R5":
        flags["possible_instructions_only"] = True

    cls = CLASSES[idx]
    row = matrix[cls]
    decisive = next(m for m in sorted(matched, key=lambda m: -CLASSES.index(m["class"])) if m["class"] == cls)
    citation = (f"agent-system/contracts/autonomy-matrix.md, row {cls} ({row['name']}): {row['meaning']}. Rule: {row['rule']}")
    requires = {
        "preflight_brief": idx >= 2,
        "rollback_plan": idx >= 2,
        # an action the classifier was unsure about or that carried instruction-like text needs the owner's explicit yes
        # whatever its class: "unsure" must never be cheaper than "sure"
        "owner_explicit_yes": cls in ("R3", "R4") or bool(flags["needs_review"] or injection or hidden),
        "human_only": cls == "R5",
        "cost_flag_by_chief_of_staff": cls == "R6",
        "default_if_no_answer": "nothing happens" if idx >= 2 else "not applicable",
    }
    reasoning = [f"Class {cls} from rule '{decisive['rule']}': {decisive['why']}"]
    others = sorted({m["class"] for m in matched if m["class"] != cls})
    if others:
        reasoning.append("Other rules also matched (" + ", ".join(others) + "); the highest class wins.")
    if rounded_up:
        reasoning.append("The class was rounded up because the text was unclear or tainted.")
    if flags["possible_instructions_only"]:
        reasoning.append("This may only write step-by-step instructions for the owner, which the matrix allows. The class stays R5 until a person confirms no secret value is handled.")
    if injection or hidden:
        reasoning.append("Instruction-like text in the description was treated as data and not followed.")
    if flags["needs_review"]:
        reasoning.append("A person or the model must read the action and may raise the class; nothing may lower it.")

    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "status": "ok",
        "action_id": action_id,
        "class": cls,
        "rounded_up": rounded_up,
        "decisive_rule": decisive["rule"],
        "matrix_citation": citation,
        "rules_matched": matched,
        "requires": requires,
        "flags": flags,
        "reasoning": " ".join(reasoning),
        "claim_row": {
            "claim_id": "C-risk-" + action_id[2:],
            "run_id": "run-unset",
            "agent": "03-guardian",
            "claim": f"Planned action {action_id} is class {cls} under the autonomy matrix (rule {decisive['rule']}).",
            "kind": "fact",
            "value": cls,
            "evidence": [{"type": "computation", "ref": SCRIPT_REL, "locator": "rule " + decisive["rule"],
                          "retrieved_at": now, "script": SCRIPT_REL}],
            "status": "pending",
            "confidence": "low" if (rounded_up or flags["needs_review"]) else "high",
            "created_at": now,
        },
    }


def envelope(result, args):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    env = {"task_id": args.task_id, "from_agent": "03-guardian", "to_agent": args.to_agent,
           "goal": "Classify one planned action under the autonomy matrix", "status": "ok",
           "claims": [result["claim_row"]["claim_id"]], "created_at": now}
    cls = result["class"]
    desc = f"Planned action {result['action_id']} classified {cls}"
    if CLASSES.index(cls) >= 2:
        if args.preflight_id:
            env["side_effects"] = [{"class": cls, "description": desc, "preflight_id": args.preflight_id}]
        else:
            env["status"] = "blocked"
            env["escalations"] = [{"reason": f"Class {cls} needs a Preflight Brief at planning time, before anything runs.",
                                   "missing_evidence": ["a Preflight Brief id for this action"]}]
    else:
        env["side_effects"] = [{"class": cls, "description": desc}]
    return env


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--action")
    ap.add_argument("--file")
    ap.add_argument("source", nargs="?", help="'-' to read stdin")
    ap.add_argument("--envelope", action="store_true")
    ap.add_argument("--task-id", default="T-unset")
    ap.add_argument("--from-agent", default="unknown")
    ap.add_argument("--to-agent", default="unknown")
    ap.add_argument("--preflight-id")
    ap.add_argument("--run-id", default="run-unset")
    args = ap.parse_args()
    if args.action is not None:
        text = args.action
    elif args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.source == "-":
        text = sys.stdin.read()
    else:
        text = ""
    res = classify(text)
    if res["status"] == "ok":
        res["claim_row"]["run_id"] = args.run_id
    out = envelope(res, args) if (args.envelope and res["status"] == "ok") else res
    print(json.dumps(out, indent=2))
    sys.exit(0 if res["status"] == "ok" else 2)


if __name__ == "__main__":
    main()
