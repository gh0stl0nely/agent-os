#!/usr/bin/env python3
"""risk-classify: give a planned action a class R0 to R6 from agent-system/contracts/autonomy-matrix.md.

Standard library only. Deterministic: the same text always gives the same class.

Usage:
  classify.py --action "Delete the old drafts"            classify one description
  classify.py --file plan.txt                              read the description from a file
  echo "..." | classify.py -                               read the description from stdin
Options:
  --model-class R3      the model's own reading of the action. It can only RAISE the script's class, never lower it.
  --envelope [--task-id T] [--from-agent A] [--to-agent B] [--preflight-id PF-YYYYMMDD-n]
        wrap the result in an agent envelope (contracts/agent-envelope.schema.json)
  --run-id RUN                                             run id for the claim row

Design (round 3: rounding down is structurally hard; see SKILL.md and reference.md)
  1. FLOOR. A broad risky-word lexicon (verbs in every inflection, euphemisms, passive forms, phrases such as
     "make X disappear" or "let the customers know") is searched in the whole text AND in every clause. The highest class
     of any hit is the floor. Nothing below it is possible.
  2. CLAUSES. The text is split at "and then", "then", "and", "if ... ,", ",", ";", "." and similar. Each clause is
     checked on its own, and the result is the highest class of the whole text and of any clause.
  3. R0 and R1 are NARROW. R0 needs every clause to be an explicit read-only form (it starts with a read verb and has
     no risky word). R1 needs every clause to be a read form or an explicit write of a NEW file in an owned path, or a
     test run. Any clause that is neither is unaccounted for, and the result is R2 with needs_review at least.
  4. UNKNOWN GOES UP. A clause nothing recognises is never R0 or R1.
  5. MODEL RAISES ONLY. --model-class (or classify(text, model_class=...)) is combined with max(); a lower class is
     recorded as ignored.
  6. Instruction-like text inside the description is data: it is flagged, never obeyed, and a flagged description is
     at least R2. A secret-like value inside the description makes the action at least R5 and is never echoed.
  7. The output never repeats the description; it reports only matched keywords, a hash id and per-clause classes.
Exit code: 0 classified, 2 blocked (no usable description or an invalid --model-class).
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
POLICY_VERSION = "3"


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
    r"\bsecrets?[- ](?:scanning|scanner|hygiene|patterns?)\b",
    r"\bpush protection\b",
    # a participle used as an adjective in front of a noun ("the supplier's published cutoff time")
    r"\bpublished (?:order|cutoff|opening|hours|help|price|pricing|rate|rates|schedule|guidance|guidelines?|page|docs?|documentation|figures?|list|terms)\b",
    r"\bsent (?:folder|items?|mail box|mailbox)\b",
    r"\b(?:phone|mobile|cell|telephone) (?:numbers?|plans? for the shop)\b",
    r"\btext (?:files?|boxes?|fields?|editor|only|columns?|strings?)\b",
    r"\bcall (?:logs?|history|list|stack|sites?|graph)\b",
    # a plural "open pull requests / issues" is a list of existing things, not the act of opening one
    r"\bopen (?:pull requests|prs|issues|tickets|orders|invoices|tasks|items)\b",
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
    # round 3: shapes that talk to the classifier or to the Guardian
    r"\bnote to (?:the )?(?:guardian|classifier|reviewer|assistant|agent)\b",
    r"\btreat (?:it|this|that) as (?:r0|r1|safe|harmless|routine|approved)\b",
    r"\bwithout (?:telling|asking|informing|notifying|alerting) the (?:owner|user|guardian)\b",
    r"\bno (?:need|reason) (?:to|for) (?:a )?(?:preflight|brief|approval|review|flag)\b",
]
INJECTION_RX = [re.compile(p, re.I) for p in INJECTION]


def prepare(text):
    """NFKC-normalise, strip invisible characters, lower-case. Returns (clean, hidden_unicode_found)."""
    norm = unicodedata.normalize("NFKC", text)
    hidden = bool(ZERO_WIDTH.search(norm))
    norm = ZERO_WIDTH.sub("", norm)
    return norm.lower(), hidden


# ---------- word forms ----------

_IRREGULAR = {
    "send": ["sent"], "buy": ["bought"], "pay": ["paid"], "write": ["wrote", "written"], "run": ["ran"],
    "give": ["gave", "given"], "take": ["took", "taken"], "make": ["made"], "tell": ["told"], "get": ["got", "gotten"],
    "shut": ["shut"], "throw": ["threw", "thrown"], "hide": ["hid", "hidden"], "put": ["put"], "let": ["let"],
    "leave": ["left"], "keep": ["kept"], "sell": ["sold"], "hold": ["held"], "set": ["set"], "undo": ["undid", "undone"],
}


def _forms(word):
    """Every common inflection of a verb: base, -s, -ed, -ing, doubled consonants, and a few irregulars."""
    w = word.lower()
    out = {w}
    if w.endswith("e"):
        out |= {w + "s", w + "d", w[:-1] + "ing"}
    elif w.endswith("y") and len(w) > 1 and w[-2] not in "aeiou":
        out |= {w[:-1] + "ies", w[:-1] + "ied", w + "ing"}
    elif w.endswith(("s", "x", "z", "ch", "sh")):
        out |= {w + "es", w + "ed", w + "ing"}
    else:
        out |= {w + "s", w + "ed", w + "ing"}
    if re.search(r"[^aeiou][aeiou][bdgklmnprt]$", w):
        out |= {w + w[-1] + "ed", w + w[-1] + "ing"}
    out |= set(_IRREGULAR.get(w, []))
    return out


def _phrase(words, kinds):
    """Regex alternatives for phrases. The FIRST word is inflected; the rest is kept as written.
    kinds: 'all' = every form; 'part' = no bare base form (-s, -ed, -ing, irregular past): for words that are also nouns;
           'ed' = only -ed / -ing / irregular past, no bare base and no -s (nouns often end in -s)."""
    alts = []
    for ph in words:
        first, _, rest = ph.partition(" ")
        fs = _forms(first)
        base = first.lower()
        if kinds == "part":
            fs = {f for f in fs if f != base}
        elif kinds == "ed":
            fs = {f for f in fs if f != base and not (f == base + "s" or f == base + "es" or (base.endswith("y") and f == base[:-1] + "ies"))}
        for f in fs:
            alts.append(re.escape(f) + ((r"\s+" + re.sub(r"\\ ", r"\\s+", re.escape(rest))) if rest else ""))
    alts = sorted(set(alts), key=len, reverse=True)
    return r"\b(?P<kw>" + "|".join(alts) + r")\b"


def FA(*words):
    """All forms."""
    return _phrase(words, "all")


def FP(*words):
    """Participles and gerunds and the -s form, but not the bare base (words that are also common nouns or adjectives)."""
    return _phrase(words, "part")


def FE(*words):
    """Only -ed, -ing and irregular past tense (verbs whose -s form is a plural noun)."""
    return _phrase(words, "ed")


# ---------- rules that look at a verb used as an action (clause start or after an auxiliary) ----------

LEAD = (r"(?:(?:pls|plz|please|kindly|hey|yo|ok|okay|so|well|now|just|also|then|first|next|finally|and|can you|could you|would you(?: mind)?|will you|do you mind|"
        r"i need you to|we need to|i want you to|let'?s|let us|you should|you need to|you must|you can|time to|go ahead and|proceed to|feel free to|be sure to|make sure to|"
        r"try to|remember to|don'?t forget to|need to|needs to|have to|has to|gotta|gonna|going to|want to|wants to|ought to|supposed to|shall we|can we|could we|should we|"
        r"we should|we could|we can|we will|we'?ll|i'?ll|i will|i'?d like to|i would like to|how about we|why not|the agent|the assistant|[a-z]+ly)\s+)*")


def V(verbs):
    """A verb used as an action: at the start of a clause, or after an auxiliary like 'will' or 'to'.
    This keeps 'read the email from the supplier' from matching the verb 'email'."""
    return (r"(?:^|[;:.\n,(]|\b(?:and|then|will|should|must|to|can|may|please|also|now|just|first|next|plans?|going)\b)\s*"
            r"(?:the (?:agent|assistant|system|skill|role)\s+)?(?:(?:will|should|must|can)\s+)?"
            # fillers between the clause start and the verb ("Quietly delete", "Go ahead and send", "pls just ping")
            + LEAD +
            r"(?:(?:again|still|simply|immediately)\s+){0,3}"
            r"(?P<kw>" + verbs + r")\b")


SECRET_NOUN = (r"\b(?P<kw>api[ _-]?keys?|api[ _-]?secrets?|api[ _-]?tokens?|(?:access|auth|refresh|bearer|session|personal access|login|service)[ _-]?tokens?|"
               r"(?:github|slack|threads|square|notion|stripe|anthropic|openai|meta|instagram) tokens?|"
               r"passwords?|passphrases?|passwd|pwds?|pass ?codes?|credentials?|creds?|secrets?|private[ _-]?keys?|ssh[ _-]?keys?|client[ _-]?secrets?|"
               r"oauth|2fa codes?|recovery codes?|one[- ]time (?:codes?|passcodes?)|log-?in details|seed phrases?|"
               r"(?:credit |debit |bank |card )?(?:card|account|routing) numbers?|cvv|cvc|iban|social insurance numbers?|"
               r"(?<!primary )(?<!foreign )(?<!sort )(?<!hash )(?<!shift )keys?(?! ?(?:metrics?|findings?|points?|takeaways?|results?|insights?|numbers?|figures?|indicators?|drivers?|terms?|dates?|accounts?|performance|steps?|decisions?|risks?|questions?|messages?|differences?|changes?|values?|[- ]value))|"
               r"(?<!\w)tokens?(?!\w))\b|(?P<kw3>\.env\b|\benv file\b|hosts\.yml|credentials?\.json|\bid_rsa\b|\.pem\b|\.p12\b|\.pfx\b|\bkeychain\b|\.netrc\b|\.npmrc\b|\.pypirc\b|aws/credentials)")
# A scan for secret PATTERNS in a diff is secrets-hygiene's own job and handles no credential value. This narrow form is
# the only exception: a scan verb, "for", and a plural or generic secret noun with no "the / old / saved / our" before it.
SECRET_SCAN_FORM = re.compile(r"^\W*(?:(?:please|kindly|just|first|then)\s+)*(?:scan|check|audit|lint|grep|search|look)\b[^,.;]{0,70}?\bfor\b "
                              r"(?:(?:any|all|leaked|exposed|hard-?coded|committed|possible|accidental)\s+)*(?:secrets?|api keys|tokens|passwords|credentials|private keys)\b"
                              r"(?=\s*$|\s*[,.;]|\s+(?:and|then)\s+(?:report|count|list|summari[sz]e|show|flag|note|log|tell me|give me)\b)")

SECRET_VERB = (r"\b(?P<kw2>create|generate|store|save|put|paste|type|enter|rotate|revoke|reset|use|share|export|set|add|copy|move|"
               r"commit|write|embed|hard-?code|echo|load|read|fetch|retrieve|send|include|pass|provide|expose|print|upload|attach|"
               r"log in|sign in)\b")

# People and organisations outside the system, plus things you can submit or cancel with them.
PERSON = (r"supplier|vendor|customer|client|accountant|staff|employee|worker|partner|landlord|bank|cra|lender|"
          r"team member|team|crew|everyone|everybody|colleague|co-?worker|group chat|channel|mailing list|subscriber|follower|audience|"
          r"family|friend|contact|lawyer|insurer|insurance|school|daycare|doctor|public|owner's partner|manager|bookkeeper|cpa|auditor|contractor|freelancer|tenant|realtor|broker|agency|plumber|electrician|tutor|neighbou?rs?|boss|intern|applicant|candidate|guest|patron|regulars|newsletter list|customer list|parents?|spouse|wife|husband|partner|kids?|children")
RECIPIENT = (r"(?P<kw2>" + PERSON + r"|order|subscription|booking|reservation|appointment)s?")
PERSON_RX = r"(?P<kw2>" + PERSON + r")s?"

PLATFORM = r"(?P<kw>threads|instagram|facebook|linkedin|twitter|tiktok|bluesky|mastodon|youtube|pinterest|social media)"

def pair(rid, cls, words, why, extra=(), base_skip=("read", "owned")):
    """Words that are verbs AND common nouns ('update', 'change', 'transfer'). The participle and gerund forms
    ('updated', 'updating') are always risky. The bare and -s forms count only in a clause that is not a plain read
    or an owned-path draft, so 'summarize the changes' stays a read."""
    return [(rid, cls, [FE(*words)] + list(extra), why, ()),
            (rid + "-base", cls, [FA(*words)] + list(extra), why, tuple(base_skip))]


# ---------- the rule table ----------
# (id, class, [regexes that must ALL match], why, skip_in)
# skip_in: kinds of clause in which the rule is not applied: "read" (a clause that starts with a read verb) and
# "owned" (an explicit write of a new file in an owned path). Rules with skip_in = () apply to every clause and to the
# whole text, so a read verb in front of a risky phrase never hides it.

_RULES = [
    # ----- R5 secrets -----
    ("credential-handling", "R5", [SECRET_NOUN, SECRET_VERB],
     "A secret noun together with a handling verb: create, store, rotate or use credentials is human only.", ()),
    ("secret-noun", "R5", [SECRET_NOUN],
     "A key, token, password, credential or credential file is named. Creating, storing, rotating, copying, reading out or using one is human only; "
     "only a scan for secret patterns (secrets-hygiene) is exempt.", ()),
    ("login", "R5", [r"\b(?P<kw>log ?in|login|sign ?in|authenticate)\b"],
     "Logging in uses credentials, which agents never type.", ()),
    # ----- R6 spend -----
    ("spend-verb", "R6", [V(r"buy|bought|purchase|purchasing|pay|paying|pays|subscribe|top[- ]?up|checkout|prepay|add credits?")],
     "Spending money beyond the plan.", ()),
    ("spend-word", "R6", [FA("buy", "purchase", "subscribe", "prepay", "renew", "top up")],
     "Buying, subscribing or renewing costs money beyond the plan.", ()),
    ("paid-thing", "R6", [r"\bpaid\b(?: [\w-]+){0,2} (?P<kw>tool|api|plan|feed|data|tier|service|model|subscription)\b"],
     "A paid tool, API or data source costs money beyond the plan.", ()),
    ("plan-upgrade", "R6", [r"\b(?P<kw>upgrad\w*|bump\w*|step\w* up|mov\w* up|level\w* up|bring\w* up|tak\w* up|go\w* up|switch\w* up|jump\w*)\b.{0,40}"
                            r"\b(?P<kw2>plan|tier|subscription|account|seat|licen[cs]e|quota|credits?|allowance|package|edition)\b"],
     "Upgrading or bumping a plan or subscription changes what is billed.", ()),
    ("plan-raise", "R6", [r"\b(?P<kw>rais\w*|boost\w*|increas\w*)\b.{0,40}\b(?P<kw2>plan|tier|subscription|quota|credits?|allowance|seats?|licen[cs]e)\b"],
     "Raising a plan, quota or allowance changes what is billed.", ()),
    ("upgrade-us", "R6", [r"\b(?P<kw>upgrad\w*)\s+(?P<kw2>us|me|ourselves|our account|my account|the account|the shop|the business)\b"],
     "Upgrading the account or 'us' changes what is billed.", ()),
    ("upgrade-money-context", "R6", [r"\b(?P<kw>upgrad\w*)\b", r"\b(?P<kw2>pricing|price|prices|billing|billed|subscription|premium|paid|cost|costs|tier|plan pricing|monthly|per month|annual|credit card|company card)\b"],
     "'Upgrade' next to pricing, billing or a tier means a change in what is paid.", ()),
    ("higher-tier", "R6", [r"\b(?P<kw>higher|premium|pro|max|enterprise|paid|bigger|next|upper|team|business|top|better|fancier|plus|annual|yearly|monthly|ultimate|growth|scale|starter|standard) (?P<kw2>tier|plan|level|package|edition|licen[cs]e)\b"],
     "A higher or paid tier costs more than the current plan.", ("read", "owned")),
    ("sign-up-paid", "R6", [FA("sign up", "signup", "enrol", "enroll", "opt in", "opt into", "join"),
                            r"\b(?P<kw2>tier|premium|paid|pro|plus|plan|subscription|card|trial|licen[cs]e|seat|membership)\b"],
     "Signing up for a plan, tier or membership commits money.", ()),
    ("settle-bill", "R6", [FA("settle", "foot", "square up", "pay off", "cover", "clear"), r"\b(?P<kw2>bill|bills|invoice|invoices|balance|tab|debt|fee|fees|rent|statement|account|loan)\b"],
     "Settling a bill, invoice or balance pays money.", ("read", "owned")),
    ("on-the-card", "R6", [r"\b(?P<kw>put|charge|bill|add|log|expense|pay|billed|charged|put)\w*\b.{0,40}\b(?:on|to|with|using|via)\b.{0,12}\b(?P<kw2>(?:company|business|credit|corporate|debit|shop|work|owner'?s?) card|card on file|payment method)\b"],
     "Putting a charge on a card spends money.", ()),
    ("auto-payment", "R6", [r"\b(?P<kw>turn on|turn\w* on|enable|set up|schedule|authori[sz]e|approve|activate|start)\b.{0,40}\b(?P<kw2>auto-?pay|automatic payments?|recurring payments?|direct debit|pre-?authori[sz]ed|standing order)\b"],
     "Setting up automatic or recurring payments commits money.", ()),
    ("recurring-charge", "R6", [r"\b(?P<kw>recurring|monthly|weekly|annual|yearly|repeating|standing|automatic)\s+(?:[\w']+\s+){0,2}?(?P<kw2>charges?|payments?|fees?|billing|debits?|transfers?|donations?)\b"],
     "A recurring charge or payment commits money.", ("read", "owned")),
    ("ad-spend", "R6", [r"\b(?P<kw>budget|spend|spending|bids?|bidding|cpc|cpm|credits?|daily limit)\b", r"\b(?P<kw2>ads?|advert\w*|campaigns?|promo\w*|boost\w*|sponsor\w*)\b"],
     "Ad budget, boosting or sponsoring spends money.", ("read", "owned")),
    ("approve-spend", "R6", [FA("approve", "authorise", "authorize", "okay", "sign off on", "greenlight"), r"\b(?P<kw2>invoice|invoices|bill|bills|payment|payments|refund|refunds|expense|expenses|payroll|purchase|purchases|timesheets?)\b"],
     "Approving an invoice, expense or payment releases money.", ("read", "owned")),
    ("beyond-allowance", "R6", [r"\b(?P<kw>beyond|over|exceed(?:s|ing)?)\b.{0,15}\b(?P<kw2>plan|allowance)\b"],
     "Going past the plan allowance is spend.", ()),
    ("billing-noun", "R6", [r"\b(?P<kw>subscription|subscriptions|billing|licen[cs]es?|seats?|premium|company card|credit card|payment method)\b"],
     "A subscription, licence, billing or a card is named in an action that is not a plain read.", ("read", "owned")),
    # ----- R4 external -----
    ("public-post", "R4", [V(r"publish|tweet|retweet|broadcast|post|repost|re-post|announce|unveil")], "Publishing leaves the system and is public.", ()),
    ("publish-word", "R4", [FA("publish", "tweet", "retweet", "broadcast", "announce", "distribute", "circulate", "disseminate", "unveil", "syndicate")],
     "Publishing, announcing or distributing reaches other people (any tense, active or passive).", ()),
    ("posted-passive", "R4", [FE("post")], "Something that is 'posted' or 'being posted' is published.", ()),
    ("social-post", "R4", [r"\b(?P<kw>post(?:s|ing|ed)?)\b.{0,60}\b(?:to|on)\b.{0,20}\b(?P<kw2>threads|instagram|facebook|linkedin|twitter|tiktok|bluesky|mastodon|social media|the (?:public )?(?:feed|account|page|channel))\b",
                          r"\b(?P<kw>public(?:ly)?)\b.{0,15}\b(?P<kw2>post)\b"],
     "A public post reaches other people.", ()),
    ("public-phrase", "R4", [r"\b(?P<kw>out there|(?:to|for) the public|public to see|publicly|go(?:es|ing)? public|made? (?:\w+ ){0,3}public|open(?:ed)? to the public|for (?:everyone|everybody|anyone|the world) to see|on the (?:internet|web)\b(?! page))\b"],
     "Putting something where the public can see it is publishing.", ()),
    ("let-know", "R4", [r"\b(?P<kw>(?:let|lets|letting|have|has|having|make|makes|making|get|gets|getting|keep|keeps|keeping) (?!me\b|us\b|it\b|this\b|that\b|the (?:agent|model|script|system|skill)\b)(?:the |our |all |each |every )?[\w']+(?: [\w']+){0,4}? (?:know|informed|aware|in the loop|posted|updated))\b"],
     "Letting someone know is contacting them.", ("owned",)),
    ("send-comm", "R4", [V(r"send|email|e-mail|message|text|dm|notify|reply|respond|forward|call|phone|ping|contact|invite|tell|ask|announce|remind|alert|inform|warn|advise|"
                           r"write to|reach out to|get in touch with|follow up with|chase|whatsapp|slack|ring|shoot|drop|mention|brief|loop in|circle back with|touch base with|talk to|speak to|chat with|check in with"),
                         r"\b" + RECIPIENT],
     "Messaging a supplier, accountant, staff member, team, customer or other outside party reaches another person.", ()),
    ("contact-verb", "R4", [V(r"message|text|dm|email|e-mail|whatsapp|slack|ping|notify|tell|inform|remind|announce|alert|warn|call|phone|ring|dial|mention|reply|respond|invite|contact")],
     "A verb that means contacting someone reaches another person, even when the person is named rather than described.", ("read",)),
    ("comm-verb-to-person", "R4", [FA("tell", "inform", "remind", "warn", "advise", "notify", "ping", "mention", "ask", "cc", "bcc", "loop in", "reach out to",
                                       "get in touch with", "follow up with", "circle back with", "touch base with", "talk to", "speak to", "check in with",
                                       "check with", "confirm with", "verify with", "chat with", "run by", "mention to", "write to"),
                                  r"\b" + PERSON_RX],
     "A communication verb together with an outside person or group reaches that person.", ("owned",)),
    ("comm-ambiguous-to-person", "R4", [FE("text", "call", "phone", "message", "contact", "email", "e-mail", "dm", "ring", "reply", "respond", "alert", "brief"),
                                         r"\b" + PERSON_RX],
     "Texting, calling, messaging or emailing an outside person or group reaches that person.", ("owned",)),
    ("comm-ambiguous-base", "R4", [FA("text", "call", "phone", "message", "contact", "email", "e-mail", "dm", "ring", "reply", "respond", "alert", "brief"),
                                    r"\b" + PERSON_RX],
     "A message, call or text to an outside person or group reaches that person.", ("read", "owned")),
    ("comm-noun-to-person", "R4", [r"\b(?P<kw>text|call|phone|message|messages|contact|dm|ring|reply|alert|brief|email|e-mail|mail|note|word)\b.{0,20}\b(?:to|for|with)\b(?: the| our| my| all| every)? " + PERSON_RX],
     "A message, call or note to an outside person or group reaches that person.", ("read", "owned")),
    ("tell-about-to-person", "R4", [r"\b(?P<kw>show|explain|describe|summari[sz]e|report|present|read out|walk(?:\s+\w+)? through|forward|relay|pass on|hand over|give|deliver|share)\w*\b.{0,60}\b(?:to|with)\b(?: the| our| my| all| every)? " + PERSON_RX],
     "Showing, explaining or handing something to an outside person or group reaches that person.", ("owned",)),
    ("out-to-person", "R4", [r"\b(?P<kw>out)\b.{0,20}\b(?:to|for)\b(?: the| our| all| every)? " + PERSON_RX],
     "Something that goes 'out to' a person or group reaches them.", ("owned",)),
    ("comm-phrase", "R4", [FA("reach out to", "get in touch with", "follow up with", "circle back with", "touch base with", "loop in", "get back to", "write to", "talk to", "speak to", "check in with", "chase up", "nudge", "ping", "buzz", "ring up")],
     "A phrase that means getting in touch with someone reaches another person.", ("owned",)),
    ("auto-outward", "R4", [r"\b(?P<kw>auto-?(?:reply|replies|responder|respond|email|message|send|post|publish|order|ordering|text|dm|renew)\w*|automatic(?:ally)? (?:reply|replies|responses?|email|message|post|order|send)\w*|out[- ]of[- ]office)\b"],
     "Anything that sends, posts, replies or orders by itself reaches other people without a person in the loop.", ()),
    ("send-word", "R4", [FA("send", "notify", "submit", "reorder", "re-order", "lodge", "dispatch", "fire off", "shoot over", "send over", "drop a line", "drop a note")],
     "Sending, notifying, submitting, reordering or dispatching leaves the system.", ()),
] + pair("send-word-amb", "R4", ["forward", "invite", "ship", "deliver"], "Forwarding, inviting, shipping or delivering reaches another person.") + [
    ("sent-out", "R4", [r"\b(?P<kw>sent (?:out|to|over|off|across|along)|texted|dm'?d|pinged|phoned)\b"],
     "Something that was 'sent out' or 'sent to' someone reaches another person.", ()),
    ("passive-comm", "R4", [r"\b(?:to be|be|being|been|should be|must be|needs? to be|gets?|got|getting|is|are|was|were|has been|have been|will be|gotta be|ought to be)\s+(?:\w+\s+)?"
                            r"(?P<kw>informed|told|reminded|replied to|responded to|contacted|called|warned|advised|alerted|invited|delivered|handed over|submitted|shipped|forwarded|notified|"
                            r"emailed|e-mailed|mailed|messaged|looped in|cc'?d|updated on|briefed|written to|asked)\b"],
     "A passive 'to be informed / emailed / submitted' means someone will be contacted or something will leave the system.", ("read", "owned")),
    ("send-message-noun", "R4", [V(r"send|deliver|forward|fire off|shoot|drop|leave|push"),
                                 r"\b(?P<kw2>messages?|e-?mails?|texts?|dms?|notes?|notifications?|alerts?|reminders?|announcements?|replies|reply|memos?|letters?|invoices?|quotes?|estimates?)\b"],
     "Sending a message, note or notice delivers something to another person.", ()),
    ("trigger-live-run", "R4", [V(r"dispatch|trigger|kick off|fire|fire off|launch|force|re-?run|rerun|run|start|execute|invoke|run now"),
                                r"\b(?P<kw2>daily[- ]post|poster(?![-\w])|post mode|publish(?:ing)? (?:job|workflow)|workflow dispatch|workflow_dispatch|(?:github )?workflow|cron job|scheduled (?:job|run|task)|pipeline)\b"],
     "Starting a workflow, scheduled job or pipeline runs real code that can post, send or change things outside the system (the daily-post workflow publishes to Threads).", ()),
    ("gh-workflow-run", "R4", [r"(?P<kw>\bgh workflow run\b|\bworkflow_dispatch\b|\bworkflows?/[\w.-]+/dispatches\b)"],
     "Dispatching a workflow runs it on GitHub.", ()),
    ("goes-out", "R4", [r"\b(?P<kw>goes? out|go(?:ing)? live|going out|went out|send(?:s|ing)? out|sent out|push(?:es|ed|ing)? out|ship(?:s|ped|ping)? out|roll(?:s|ed|ing)? out|put(?:s|ting)? out|push(?:es|ed|ing)? live|get(?:s|ting)? out)\b",
                        r"\b(?P<kw2>post|posts|message|email|order|update|newsletter|announcement|content|photo|video|story|reel|thread|menu|rota|schedule|promo|offer|notice|flyer|rate|price|prices)\b"],
     "Something that 'goes out' or 'goes live' reaches other people.", ()),
    ("share-access", "R4", [V(r"grant|give|share|invite|allow|add|provide|extend|let|hand"),
                            r"\b(?P<kw2>access|permissions?|editor|viewer|admin rights|collaborators?|guest)\b"],
     "Giving a person access or permissions reaches another person and changes who can see or edit the data.", ()),
    ("access-to-person", "R4", [r"\b(?P<kw>give|giv\w*|grant\w*|let|hand\w*|allow\w*|share\w*|open\w*|provide\w*)\b.{0,40}\b(?:access|keys?|login|permission\w*|entry|admin)\b"],
     "Handing someone access reaches another person.", ()),
    ("submit", "R4", [V(r"submit|place|file|lodge|book|reserve"), r"\b(?P<kw2>order|form|report|filing|return|application|claim|request|booking|reservation|appointment)s?\b"],
     "Submitting an order, form or filing leaves the system.", ()),
    ("share-external", "R4", [V(r"share|upload|send|post"), r"\b(?P<kw2>publicly|externally|outside|public)\b"],
     "Sharing outside the system.", ()),
    ("push-or-pr", "R4", [r"(?P<kw>\bgit push\b|\bforce[- ]push\b|\bpush(?:ing|es)?\b.{0,30}\b(?:to|onto)\b.{0,15}\b(?:remote|origin|github|the repo|upstream|branch)\b|"
                          r"\b(?:open|create|raise)\b.{0,20}\b(?:pull request|pr|issue)\b|\bgh pr create\b)"],
     "A push or pull request leaves the local clone and reaches a public repository.", ()),
    ("push-branch", "R4", [r"\b(?P<kw>push(?:ed|es|ing)?)\b.{0,40}\b(?P<kw2>branch|commits?|changes|repo|remote|origin|upstream|fork|tags?|code|gitlab|bitbucket)\b"],
     "Pushing code or a branch leaves the local clone.", ("read", "owned")),
    ("money-account", "R4", [FA("move", "shift", "send", "put", "take", "pull", "sweep", "draw", "pay", "top up", "pull out", "take out"),
                             r"\b(?P<kw2>account|accounts|savings|chequing|checking|operating|float|petty cash|till)\b", r"(?P<kw3>\d|hundred|thousand|grand|million|\bk\b)"],
     "Moving an amount between accounts leaves the system.", ("read", "owned")),
    ("cancel-external-thing", "R4", [FA("cancel", "call off", "postpone", "reschedule", "terminate"),
                                     r"\b(?P<kw2>deliver\w*|shipments?|bookings?|reservations?|appointments?|contracts?|leases?|memberships?|polic(?:y|ies)|standing orders?|catering|events?|classes|trials?|accounts?|orders?|visits?|pickups?|pick-ups?)\b"],
     "Cancelling or moving something arranged with an outside party reaches that party.", ()),
    ("cancel-external", "R4", [FA("cancel", "void", "refund", "terminate", "unsubscribe", "call off", "pull out of"), r"\b" + RECIPIENT],
     "Cancelling or refunding with an outside party reaches that party.", ()),
] + pair("money-moves", "R4", ["transfer", "wire", "withdraw", "deposit", "remit", "reimburse", "payout", "donate", "invest", "fund"],
        "Moving money to or from an account leaves the system and cannot always be undone.") + pair(
    "commit-to-others", "R4", ["accept", "sign", "countersign", "e-sign", "esign", "agree to", "hire", "onboard", "offboard"],
    "Accepting, signing, agreeing or hiring commits the business to someone outside the system.") + [
    ("platform-noun", "R4", [r"\b" + PLATFORM + r"\b"],
     "A public platform is named in an action that is not a plain read or a draft in an owned path.", ("read", "owned")),
    # ----- R3 destructive -----
    ("delete", "R3", [V(r"delete|remove|erase|wipe|purge|destroy|nuke|zap|trash|discard|drop|truncate|prune|clear out|clear|get rid of|clean up|clean out|empty|unlink|shred|rm|bin|dump|scrap|ditch|kill|axe|junk|retire|sunset|decommission")],
     "Deleting is destructive.", ()),
    ("destroy-word", "R3", [FA("delete", "remove", "erase", "wipe", "purge", "destroy", "nuke", "zap", "obliterate", "eliminate", "expunge", "decommission", "sunset",
                               "abolish", "banish", "dispose", "annihilate", "scrub", "unpublish", "unlist", "deprecate", "retire", "overwrite", "revoke", "deactivate", "cancel",
                               "terminate", "unsubscribe", "uninstall")],
     "A destructive or terminating verb in any tense, active or passive.", ()),
    ("destroy-participle", "R3", [FE("trash", "drop", "discard", "prune", "truncate", "shred", "dump", "scrap", "ditch", "kill", "axe", "junk", "empty", "clear out",
                                     "clean up", "clean out", "offload", "bin", "purge")],
     "A destructive verb used as a participle or gerund ('to be dropped', 'is being discarded').", ()),
    ("destroy-phrase", "R3", [r"\b(?P<kw>get(?:s|ting)? rid of|got rid of|gotten rid of|take(?:s|n|ing)? (?:[\w']+ ){0,6}?(?:down|offline)|took (?:[\w']+ ){0,6}?(?:down|offline)|"
                              r"pull(?:s|ed|ing)? (?:[\w']+ ){0,6}?(?:down|offline)|shut(?:s|ting)? (?:[\w']+ ){0,2}?(?:down|off)|go(?:es|ing)? away|went away|(?:be|is|are|get|gets|getting|got|make|makes|making|have|had|see|want|need)\\s+(?:\\w+\\s+){0,5}?gone|disappear\w*|vanish\w*|"
                              r"no longer (?:exist\w*|be there|around|available|needed)|(?:off|out of) the (?:books|record|system|picture)|out of existence|"
                              r"put (?:[\w']+ ){0,3}?to sleep|say(?:s|ing)? (?:good-?bye|farewell|bye) to|said (?:good-?bye|farewell) to|bid(?:s|ding)? farewell|(?:put|lay|laid|laying)(?:ing)? (?:[\w']+ ){0,3}?to rest|part(?:s|ed|ing)? ways with|(?:can|may|should|must|has to|have to|needs to|need to|will|gonna|going to) go(?! (?:ahead|live|to|on|through|back|over|up|down|away|public)\b)\b|sweep(?:s|ing)? (?:[\w']+ ){0,3}?away|tidy(?:ing)? (?:[\w']+ )?away|clear(?:s|ed|ing)? (?:out|away|off)|"
                              r"clean(?:s|ed|ing)? (?:out|up)|wipe[sd]? out|(?:sort|clear|clean|tidy|sweep|work)\w* (?:out|up|away|through)\b.{0,30}\b(?:old|stale|unused|extra|leftover|redundant|duplicate|obsolete|outdated)\b|take(?:s|n|ing)? (?:[\w']+ ){0,3}?(?:away)|take(?:s|n|ing)? (?:[\w']+ ){0,3}?out of)\b"],
     "Euphemisms for deleting: get rid of, make it disappear, take it down, put it to sleep.", ()),
    ("overwrite", "R3", [r"\b(?P<kw>overwrit(?:e|es|ing|ten))\b"],
     "Overwriting loses the old content unless a backup exists, so it is treated as destructive.", ()),
    ("cancel", "R3", [V(r"cancel|terminate|unsubscribe|deactivate|revoke")], "Cancelling cannot always be undone.", ()),
    ("force-reset", "R3", [r"(?P<kw>--force\b|\bforce[- ]push\b|\bgit reset --hard\b|\breset --hard\b|\bgit clean\b|\bbranch -d\b|\brm -r)"],
     "Force and hard-reset commands discard history or files.", ()),
    ("reset-word", "R3", [FA("reset", "rollback", "roll back", "revert to", "restore from")],
     "Resetting or rolling back discards the current state.", ("read",)),
    ("merge-main", "R3", [r"\b(?P<kw>merge|merging|merged)\b.{0,40}\b(?:into|to|onto)\s+(?:the\s+)?(?P<kw2>main|master|production|prod|default branch)\b"],
     "Merging into main is irreversible for the live repository.", ()),
    ("merge-pr", "R3", [r"(?P<kw>\bgh pr merge\b|\bsquash and merge\b|\bmerge\w*\b.{0,25}\b(?:pull requests?|prs?)\b|\bmerge #?\d+\b.{0,20}\b(?:into|to) (?:main|master)\b|\bpush\b.{0,20}\b(?:main|master)\b)"],
     "Merging a pull request or pushing to main is irreversible for the live repository.", ()),
    # ----- R2 modify shared state -----
    ("modify", "R2", [V(r"edit|modify|update|change|alter|amend|patch|rename|move|rewrite|refactor|replace|tweak|adjust|correct|fix|revise|"
                        r"reconfigure|configure|enable|disable|toggle|install|uninstall|upgrade|migrate|merge|rebase|restore|revert|"
                        r"apply|deploy|release|register|activate|set up|set")],
     "Changing something that exists changes shared state.", ()),
    ("modify-word", "R2", [FA("modify", "alter", "amend", "rename", "rewrite", "refactor", "replace", "tweak", "adjust", "revise", "reconfigure", "configure", "enable",
                              "disable", "toggle", "install", "migrate", "rebase", "revert", "apply", "deploy", "activate", "overhaul", "revamp", "rework", "relabel",
                              "recode", "reclassify", "normalise", "normalize", "reorganize", "reorganise", "restore", "edit")],
     "A verb that changes something that exists, in any tense, active or passive.", ()),
] + pair("modify-amb", "R2", ["update", "change", "patch", "move", "fix", "correct", "set up", "switch", "turn on", "turn off", "stop", "halt", "pause", "resume",
                               "restart", "reboot", "reload", "bump", "swap", "merge", "register", "clean", "tidy", "convert", "transform", "release", "sort out", "touch up", "upgrade"],
        "A verb that changes something that exists (used as a noun it is ignored inside a plain read).") + [
    ("add-to-shared", "R2", [V(r"add|append|insert"), r"\b(?:to|in|into)\b.{0,30}\b(?P<kw2>config|settings|workflow|roster|registry|contracts?|readme|claude\.md|ledger|rules?|prompts?|memory|schema)\b"],
     "Adding to a shared file or setting changes shared state.", ()),
    # ----- R1 reversible internal write -----
    ("create-owned", "R1", [r"^\W*" + LEAD + r"(?P<kw>create|write|draft|add|generate|compose|prepare|save|commit|record|log|export|dump|produce|build|make)\b",
                            r"(?P<kw2>agents/|\.claude/skills/|knowledge/|owned path|my owned|working (?:folder|directory)|scratch|local (?:branch|clone|copy)|build branch|drafts?/|fixtures?)"],
     "Creating a new file or draft inside the role's own paths is reversible.", ()),
    ("run-tests", "R1", [r"^\W*" + LEAD + r"(?P<kw>run|execute)\b",
                         r"\b(?P<kw2>tests?|evals?|validator|linter|dry[- ]run)\b"],
     "Running tests writes only logs.", ()),
]
RULES = [(rid, cls, [re.compile(p, re.I | re.M) for p in pats], why, frozenset(skip)) for rid, cls, pats, why, skip in _RULES]

SHARED_STATE_HINT = re.compile(r"\b(?:existing|shared|live|production|someone else'?s|other roles?'?s?|another role'?s?|config(?:uration)?|settings?|prompt|"
                               r"brain rule|workflow|contracts?|roster|registry|readme|claude\.md|schema|hook|permissions?|ledger)\b", re.I)

# The only clause that may be R0: it STARTS with a read verb (after optional polite fillers and adverbs).
READ_VERBS = (r"search|read|look(?:s)? (?:up|at|through|into|over)|lookup|list|summari[sz]e|review|check|query|grep|compare|analy[sz]e|inspect|view|show|find|fetch|count|"
              r"calculate|compute|verify|validate|diff|retrieve|explain|describe|scan|measure|browse|examine|audit|tally|tabulate|identify|locate|estimate|forecast|report on|report|display|print|tell me|give me|let me know")
READ_START = re.compile(r"^\W*" + LEAD + r"(?:" + READ_VERBS + r")\b", re.I)
# Words that carry no action: stripped before deciding whether a clause is empty or a read form.
COURTESY = re.compile(r"\b(?:right now|for now|today|tonight|tomorrow|this (?:morning|afternoon|evening)|as soon as possible|asap|when you (?:get|have) (?:a|the) (?:chance|moment|minute|time)|"
                      r"thanks|thank you|thx|cheers|please|kindly|if you (?:can|could|don't mind|wouldn't mind)|low priority|high priority|no rush|for me|it'?s routine|it is routine|ok|okay)\b", re.I)
NP_START = re.compile(r"^(?:the|a|an|its|their|our|my|your|his|her|last|this|that|these|those|next|each|every|all|any|both|either|neither|two|three|four|five|six|seven|eight|nine|ten|"
                      r"january|february|march|april|may|june|july|august|september|october|november|december|monday|tuesday|wednesday|thursday|friday|saturday|sunday|[a-z]+'s)\b|^\d", re.I)
STOPWORDS = set("a an the it its them they this that these those and or then if so to of for in on at is are be been was were we you i me my our can will should must may might do does did "
                "with from by as up out not no also just now again still first next".split())

SPLIT = re.compile(r"[;\n]+|(?<=[.!?])\s+|:\s+|\s[-–—]{1,2}\s|\s*,\s*|[()\[\]]|"
                   r"\s+(?:and then|and also|and after that|and|then|but|so that|so|after that|afterwards|afterward|once|when|whenever|while|before|after|if|unless|"
                   r"otherwise|else|or|plus|followed by|except|though|although|because|since|as soon as)\s+", re.I)

# An unrecognised clause that names an outside party, a platform or money is raised, not left at R2.
UNKNOWN_OUTSIDE = re.compile(r"\b(?P<kw>" + PERSON + r"|order|orders|subscription|booking|reservation|appointment|threads|instagram|facebook|linkedin|twitter|tiktok|bluesky|mastodon|youtube|social media|public)s?\b")
UNKNOWN_MONEY_SMALL = re.compile(r"(?P<kw>\$\s?\d|\b(?:dollars?|bucks|cash)\b)")
UNKNOWN_MONEY_BIG = re.compile(r"\b(?P<kw>invoices?|payroll|salary|salaries|wages?|refunds?|charges?|payments?|fees?|bills?|debt|loan)\b")
# A capitalised name after a contact verb ("text Maria", "call Dev"), matched on the original case.
NAME_COMM = re.compile(r"\b(?i:text|call|e-?mail|message|tell|ask|ping|notify|remind|dm|phone|contact|ring|inform|warn|let|reply to|write to|speak to|talk to)(?i:s|ed|ing)?\s+(?:(?i:to)\s+)?"
                       r"(?!(?i:the|a|an|my|our|your|this|that|all|each|every|any|it|him|her|them|us|me|you|everyone|everybody|someone|anyone|whoever)\b)"
                       r"(?:[A-Z][a-z]{2,}|[A-Z]{3,})\b")

INSTRUCTIONS_ONLY = re.compile(r"\b(?:write|draft|document|prepare)\b.{0,40}\b(?:instructions?|steps?|guide|checklist)\b.{0,80}\bowner\b", re.I)


def load_secret_scanner():
    try:
        sys.path.insert(0, str(SECRETS_SCRIPTS))
        import scan_secrets  # noqa: E402
        return scan_secrets
    except Exception:
        return None


SPLIT_CAPTURE = re.compile("(" + SPLIT.pattern + ")", re.I)


def split_clauses(text):
    """Split at 'and then', 'then', 'and', 'if ..., ', commas, semicolons, full stops and similar. Splitting can only ADD
    clauses; the whole text is always checked as well, so a split never removes a hit.
    Returns [(connector, clause)]; the connector is what came just before the clause ('' for the first)."""
    bits = SPLIT_CAPTURE.split(text)
    out, conn = [], ""
    for i, b in enumerate(bits):
        if i % 2 == 1:
            conn = (b or "").strip().lower()
            continue
        if b and b.strip() and re.search(r"[a-z0-9]", b, re.I):
            out.append((conn, b.strip()))
            conn = ""
    return out


def _scan_rules(segment, kind, hits, clause_no):
    """Apply every rule to one segment (the whole text or one clause). kind is 'read', 'owned', 'whole' or 'other'."""
    for rid, cls, rxs, why, skip in RULES:
        if kind in skip or (kind == "whole" and skip):
            continue  # rules limited to non-narrow clauses are applied clause by clause only
        kws, ok = [], True
        for rx in rxs:
            m = rx.search(segment)
            if not m:
                ok = False
                break
            gd = m.groupdict()
            kws += [gd[k] for k in ("kw", "kw2", "kw3") if gd.get(k)]
        if not ok:
            continue
        if rid == "secret-noun" or rid == "credential-handling":
            if SECRET_SCAN_FORM.match(segment) and not re.search(r"\b(?:the|this|that|my|our|old|new|saved|stored|existing|current)\s+(?:\w+\s+)?(?:keys?|tokens?|passwords?|credentials?|secrets?)\b", segment):
                continue
        if rid == "create-owned" and SHARED_STATE_HINT.search(segment):
            continue
        hits.append({"rule": rid, "class": cls, "keywords": sorted({k.strip()[:30] for k in kws}), "why": why, "clause": clause_no})


def classify(text, model_class=None):
    """Return the classification record for one description. Pure function apart from reading the matrix."""
    matrix = load_matrix()
    text = text if isinstance(text, str) else ""
    clean, hidden = prepare(text)
    if not clean.strip():
        return {"status": "blocked", "reason": "no action description was supplied; no class is guessed",
                "missing": ["a one-sentence description of the planned action"]}
    if model_class is not None and model_class not in CLASSES:
        return {"status": "blocked", "reason": f"--model-class must be one of {', '.join(CLASSES)}", "missing": ["a valid model class"]}

    action_id = "A-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    neutral_hits = []
    scrubbed = clean
    for pat in NEUTRAL:
        for m in re.finditer(pat, scrubbed):
            neutral_hits.append(m.group(0))
        scrubbed = re.sub(pat, " ", scrubbed)

    # ---- 1. whole text: every rule that is not limited to plain read / owned-write clauses ----
    hits = []
    _scan_rules(scrubbed, "whole", hits, 0)

    # ---- 2. each clause on its own ----
    clauses = []
    for n, (conn, seg) in enumerate(split_clauses(scrubbed), start=1):
        core = COURTESY.sub(" ", seg)
        words = [w for w in re.findall(r"[a-z][a-z0-9'_-]*", core)]
        info = {"n": n, "narrow": None, "courtesy_only": not words or all(w in STOPWORDS for w in words)}
        if info["courtesy_only"]:
            clauses.append(info)
            continue
        read_start = bool(READ_START.match(core.strip()))
        kind = "read" if read_start else "other"
        # an explicit write of a NEW file in an owned path, or a test run, is the only narrow non-read form
        owned_hits = []
        _scan_rules(seg, "other", owned_hits, n)
        owned_ids = {h["rule"] for h in owned_hits}
        owned_write = (not read_start) and bool(owned_ids & {"create-owned", "run-tests"}) and not SHARED_STATE_HINT.search(seg)
        if owned_write:
            kind = "owned"
        seg_hits = []
        _scan_rules(seg, kind, seg_hits, n)
        info["hits"] = seg_hits
        info["text"] = seg
        info["read_start"] = read_start
        info["owned_write"] = owned_write
        info["content_words"] = len([w for w in words if w not in STOPWORDS])
        info["narrow"] = "read-only" if read_start else ("owned-write" if owned_write else None)
        # "Compare September and October sales": the piece after 'and' is a noun phrase that continues the read clause
        if (not info["narrow"] and clauses and clauses[-1].get("narrow") == "read-only" and conn in ("and", ",", "or", "plus", "before", "after", "while")
                and NP_START.match(core.strip()) and len(words) <= 6 and not UNKNOWN_OUTSIDE.search(seg) and not UNKNOWN_MONEY_SMALL.search(seg)
                and not UNKNOWN_MONEY_BIG.search(seg) and not seg_hits):
            info["narrow"] = "read-only"
            info["continuation"] = True
        clauses.append(info)
        hits.extend(seg_hits)

    # a narrow clause is narrow only if nothing in it is above R1
    for c in clauses:
        if c.get("narrow") and any(CLASSES.index(h["class"]) >= 2 for h in c["hits"]):
            c["narrow"] = None

    # an unrecognised clause that names an outside party, a platform or money is raised, not left at R2
    for c in clauses:
        if c["courtesy_only"] or c.get("narrow") or c.get("hits") or c.get("content_words", 0) < 2:
            continue
        extra = []
        m = UNKNOWN_OUTSIDE.search(c["text"])
        if m:
            extra.append(("unrecognised-outside-party", "R4", m.group("kw"), "A clause nothing recognises names an outside party, order or platform, so it is treated as reaching them."))
        m = UNKNOWN_MONEY_SMALL.search(c["text"])
        if m:
            extra.append(("unrecognised-money", "R6", m.group("kw"), "A clause nothing recognises names an amount of money, so it is treated as spend."))
        m = UNKNOWN_MONEY_BIG.search(c["text"])
        if m:
            extra.append(("unrecognised-financial", "R4", m.group("kw"), "A clause nothing recognises names a bill, invoice, fee or payment, so it is treated as reaching the other party."))
        for rid, cls, kw, why in extra:
            h = {"rule": rid, "class": cls, "keywords": [kw[:30]], "why": why, "clause": c["n"]}
            c.setdefault("hits", []).append(h)
            hits.append(h)
    m = NAME_COMM.search(unicodedata.normalize("NFKC", text))
    if m:
        hits.append({"rule": "comm-verb-to-named-person", "class": "R4", "keywords": [m.group(0).split()[0].lower()[:30]], "clause": 0,
                     "why": "A contact verb followed by a capitalised name (text Maria, call Dev) reaches that person."})

    # de-duplicate hits by (rule, class, clause)
    seen, matched = set(), []
    for h in hits:
        key = (h["rule"], h["class"], h["clause"])
        if key in seen:
            continue
        seen.add(key)
        matched.append(h)
    high = [h for h in matched if CLASSES.index(h["class"]) >= 2]

    injection = []
    for rx in INJECTION_RX:
        m = rx.search(clean)
        if m:
            injection.append(m.group(0)[:50])
    scanner = load_secret_scanner()
    secret_like = bool(scanner and scanner.scan_text(text))

    live = [c for c in clauses if not c["courtesy_only"]]
    unaccounted = [c for c in live if not c["narrow"] and not [h for h in c.get("hits", [])] and c["content_words"] >= 1]
    nontrivial_unaccounted = [c for c in unaccounted if c["content_words"] >= 2]
    flags = {
        "injection": injection,
        "hidden_unicode": hidden,
        "secret_like_value_in_description": secret_like,
        "needs_review": False,
        "possible_instructions_only": False,
        "neutralised_phrases": neutral_hits,
        "unrecognised_clauses": len(nontrivial_unaccounted),
    }

    # ---- 3. the script floor ----
    rounded_up = False
    if high:
        idx = max(CLASSES.index(h["class"]) for h in high)
        floor_why = "highest class of any hit in the whole text or in any clause"
        if nontrivial_unaccounted:
            flags["needs_review"] = True
    else:
        narrow_all = bool(live) and all(c["narrow"] for c in live)
        has_owned = any(c["narrow"] == "owned-write" for c in live)
        if narrow_all and not has_owned:
            idx = CLASSES.index("R0")
            matched.append({"rule": "read-only-narrow", "class": "R0", "keywords": [], "clause": 0,
                            "why": "Every clause starts with a read verb and no risky word appears anywhere in the text."})
            floor_why = "every clause is an explicit read-only form"
        elif narrow_all and has_owned:
            idx = CLASSES.index("R1")
            floor_why = "every clause is a read form or an explicit write of a new file in an owned path"
        else:
            idx, rounded_up = CLASSES.index("R2"), True
            flags["needs_review"] = True
            matched.append({"rule": "no-rule-matched", "class": "R2", "keywords": [], "clause": 0,
                            "why": "At least one clause is neither an explicit read-only form nor an explicit new-file write in an owned path, so the text is rounded up to R2 and a person must read it."})
            floor_why = "unrecognised clause, rounded up"
    if injection or hidden:
        if idx < CLASSES.index("R2"):
            idx, rounded_up = CLASSES.index("R2"), True
        flags["needs_review"] = True
        matched.append({"rule": "tainted-description", "class": "R2", "keywords": [], "clause": 0,
                        "why": "The description contains instruction-like or hidden text. It is data, not a command; it was ignored and flagged."})
    if secret_like:
        if idx < CLASSES.index("R5"):
            idx, rounded_up = CLASSES.index("R5"), True
        matched.append({"rule": "secret-value-in-description", "class": "R5", "keywords": [], "clause": 0,
                        "why": "A secret-like value appears in the description. Agents never handle secret values."})
    script_idx = idx

    # ---- 4. the model may only raise ----
    model = {"proposed": model_class, "raised_class": False, "ignored_because_lower": False}
    if model_class is not None:
        if CLASSES.index(model_class) > idx:
            idx = CLASSES.index(model_class)
            model["raised_class"] = True
            flags["needs_review"] = True
            matched.append({"rule": "model-raised", "class": model_class, "keywords": [], "clause": 0,
                            "why": f"The model read the action and raised the class to {model_class}. A model can raise the class, never lower it."})
        elif CLASSES.index(model_class) < idx:
            model["ignored_because_lower"] = True

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
    reasoning.append(f"Script floor {CLASSES[script_idx]}: {floor_why}.")
    if len(live) > 1:
        reasoning.append(f"The text was split into {len(live)} clauses and the highest class of any clause stands.")
    if rounded_up:
        reasoning.append("The class was rounded up because the text was unclear or tainted.")
    if model["raised_class"]:
        reasoning.append(f"The model's class {model_class} is above the script floor and was used.")
    if model["ignored_because_lower"]:
        reasoning.append(f"The model proposed {model_class}, lower than the script floor {CLASSES[script_idx]}; the lower class was ignored.")
    if flags["possible_instructions_only"]:
        reasoning.append("This may only write step-by-step instructions for the owner, which the matrix allows. The class stays R5 until a person confirms no secret value is handled.")
    if injection or hidden:
        reasoning.append("Instruction-like text in the description was treated as data and not followed.")
    if flags["needs_review"]:
        reasoning.append("A person or the model must read the action and may raise the class; nothing may lower it.")

    clause_report = []
    for c in clauses:
        if c["courtesy_only"]:
            continue
        ch = [h for h in c.get("hits", [])]
        cidx = max((CLASSES.index(h["class"]) for h in ch), default=None)
        if cidx is None:
            ccls = "R0" if c["narrow"] == "read-only" else ("R1" if c["narrow"] == "owned-write" else "R2")
        else:
            ccls = CLASSES[max(cidx, 0)]
            if cidx < 2 and not c["narrow"]:
                ccls = "R2"
        clause_report.append({"n": c["n"], "class": ccls, "narrow_form": c["narrow"], "rules": sorted({h["rule"] for h in ch})})

    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "status": "ok",
        "policy_version": POLICY_VERSION,
        "action_id": action_id,
        "class": cls,
        "script_floor": CLASSES[script_idx],
        "model": model,
        "rounded_up": rounded_up,
        "decisive_rule": decisive["rule"],
        "matrix_citation": citation,
        "rules_matched": [{k: v for k, v in m.items() if k != "clause"} for m in matched],
        "clauses": clause_report,
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
    ap.add_argument("--model-class", help="the model's own class; it can only raise the script's class")
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
    res = classify(text, model_class=args.model_class)
    if res["status"] == "ok":
        res["claim_row"]["run_id"] = args.run_id
    out = envelope(res, args) if (args.envelope and res["status"] == "ok") else res
    print(json.dumps(out, indent=2))
    sys.exit(0 if res["status"] == "ok" else 2)


if __name__ == "__main__":
    main()
