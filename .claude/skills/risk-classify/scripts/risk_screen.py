"""The four-question screen (round 4).

Every planned action is put through four questions, whatever its class looks like:

  money    (a) Does this involve money or a recurring cost?                           -> R6 if yes or unsure
  deletion (b) Does this delete, remove or overwrite anything persistent?             -> R3 if yes or unsure
  outside  (c) Is an outside party told or contacted?                                 -> R4 if yes or unsure
  secret   (d) Does this involve a secret or a credential?                            -> R5 if yes or unsure

Each question is answered yes / unsure / no WITH EVIDENCE. The matrix class for a question is applied for "yes" and for "unsure".
Nothing can lower a class:
  * The script answers first, from cue FAMILIES (meanings, not single words) plus the rules that already matched.
    A strong cue is "yes", a weak cue is "unsure", and no cue is "no". A "no" is STRONG only when every clause of the action
    was recognised; if some clause was not, the "no" is WEAK and the screen is incomplete until the model answers.
  * The model answers all four from reading the action (classify.py --screen-answers). Its answer can only RAISE: a "yes" or
    "unsure" raises the class; a "no" never lowers a script "yes" or "unsure", and a "no" without evidence counts as "unsure".
  * The screen is COMPLETE when every question is answered with evidence: by the script (a yes, an unsure, or a strong no)
    or by the model. A Preflight Brief is not built from an incomplete screen.
Standard library only. Deterministic.
"""
import re

QUESTIONS = {
    "money": {"class": "R6", "text": "Does this involve money or a recurring cost?"},
    "deletion": {"class": "R3", "text": "Does this delete, remove or overwrite anything persistent?"},
    "outside": {"class": "R4", "text": "Is an outside party told or contacted?"},
    "secret": {"class": "R5", "text": "Does this involve a secret or a credential?"},
}
ORDER = ["no", "unsure", "yes"]
ANSWERS = set(ORDER)

# Rules of classify.py that already answer a question when they matched (by id).
MONEY_RULES = {"spend-verb", "spend-word", "paid-thing", "plan-upgrade", "plan-raise", "upgrade-us", "upgrade-money-context", "higher-tier", "sign-up-paid", "settle-bill",
               "on-the-card", "auto-payment", "recurring-charge", "ad-spend", "approve-spend", "beyond-allowance", "billing-noun", "unrecognised-money",
               }
DELETE_RULES = {"delete", "destroy-word", "destroy-participle", "destroy-phrase", "overwrite", "cancel", "reset-word", "force-reset"}
SECRET_RULES = {"credential-handling", "secret-noun", "login", "secret-value-in-description"}

PERSIST = (r"(?:branch(?:es)?|archives?|tables?|rows?|workbooks?|work ?sheets?|sheets?|tabs?|spreadsheets?|databases?|dbs?|records?|entries|files?|folders?|directories|buckets?|"
           r"repos?|repositor(?:y|ies)|tags?|releases?|snapshots?|backups?|logs?|exports?|pages?|docs?|documents?|drafts?|columns?|fields?|indexes|indices|caches?|volumes?|disks?|"
           r"calendars?|contacts?|notes|receipts?|statements?|invoices?|versions?|history|queues?|collections?|datasets?|ledgers?|catalogs?|catalogues?|menus?|listings?|photos?|images?|"
           r"videos?|pdfs?|workspaces?|inbox|labels?|data|lists?)")
STALE = r"(?:stale|obsolete|unused|leftover|left-?over|dead|orphan\w*|duplicate\w*|dupes?|expired|outdated|abandoned|merged|inactive|untouched|deprecated|superseded|zombie)"
# Verbs that only mean "remove" when used as a verb: they must be followed by a determiner ("clear the", "blank out the"), so the adjective
# in "rows with blank dates" or "a clear label" does not count.
AMBIGUOUS = r"(?:blank|clear|empty|empt(?:ied|ying)|drain|gut|bin|dump|kill|scrap|shed|trim|sweep|flush|scrub|toss|junk|cull|ditch)\w*"
DET = r"(?:out |away |off |up )?(?:the|all|every|any|each|that|this|those|these|our|my|its|their|stale|[\w']+'s)\b"
REMOVAL = (r"(?:prun\w*|retir\w*|decommission\w*|sunset\w*|spin\w* down|tear\w* down|rip\w* out|strip\w* out|"
           r"zero\w* out|null\w* out|clobber\w*|supersed\w*|blow\w* away|blown away|(?:take|takes|took|taken|taking) (?:[\w']+ ){0,4}?(?:off|out|away)|"
           r"let(?:s|ting)? (?:[\w'-]+ ){0,6}?go|letting go|part\w* with|free\w* up|make room|reclaim\w*|age\w* out|evict\w*|swept|thin\w* out|declutter\w*|86|eighty-?six\w*|"
           r"out to pasture|gone|start\w* (?:[\w']+ ){0,3}?over|start\w* (?:afresh|anew)|leav\w* (?:just|only)|keep\w* only|"
           r"collaps\w*|squash\w*|vacuum\w*|reformat\w*|re-?imag\w*|wipe\w*|purg\w*|nuk\w*|shred\w*|erase\w*|zap\w*|axe\w*|abandon\w*|discontinu\w*|phase\w* out|roll\w* off|"
           r"age off|weed\w* out|dispos\w*)")


def build_cues(person):
    """(question, name, strength, skip_in_read, compiled regex). Strong = yes, weak = unsure. skip_in_read: not applied to a clause that starts with a read verb."""
    P = person
    ART = r"(?:the |our |my |all |each |every |a |an |this |that |these |those )?"
    c = []

    def add(q, name, strength, skip_read, rx):
        c.append((q, name, strength, skip_read, re.compile(rx, re.I)))

    # ---------------- (a) money or a recurring cost
    add("money", "enrol-in-package", "strong", True,
        r"\b(?:enrol(?:l)?(?:ing|ed|s|ment)?|sign(?:ing|ed|s)?\b(?: [\w']+){0,4}? (?:up|on)|opt(?:ing|ed|s)? in(?:to)?|join(?:ing|ed|s)?|register(?:ing|ed|s)?)\b.{0,40}"
        r"\b(?:package|plan|tier|bundle|subscription|membership|programme|program|pro|premium|plus|paid|trial|licen[cs]e|seats?|contract|team plan|business plan|loyalty)\b")
    add("money", "move-up-a-level", "strong", True,
        r"\b(?:mov\w*|step\w*|go\w*|switch\w*|bump\w*|graduat\w*|jump\w*|trad\w*|upgrad\w*|upsiz\w*|scal\w*|bring\w*|tak\w*|put\w*|roll\w*|continu\w*|convert\w*|flip\w*|shift\w*|lift\w*)\b"
        r".{0,30}\b(?:up|onto|to|into)\b.{0,25}\b(?:tier|plan|level|package|edition|licen[cs]e)\b")
    add("money", "move-to-named-paid-level", "strong", True,
        r"\b(?:mov\w*|step\w*|go\w*|switch\w*|bump\w*|graduat\w*|jump\w*|upgrad\w*|upsiz\w*|scal\w*|bring\w*|tak\w*|put\w*|roll\w*|continu\w*|convert\w*|flip\w*|shift\w*)\b"
        r".{0,30}\b(?:onto|to|into)\s+(?:the |a |an )?(?:[\w'-]+ ){0,2}?(?:pro|premium|plus|enterprise|unlimited|paid|business|growth|max)\b(?!\w)")
    add("money", "leave-free-tier", "strong", True,
        r"\b(?:leav\w*|exit\w*|outgrow\w*|com\w* off|get\w* off|mov\w* off|graduat\w*|stop\w* using|go\w* beyond|go\w* past|exceed\w*|out of|from)\b.{0,20}\bfree\b(?: (?:tier|plan|version|trial|edition|account|plan))?")
    add("money", "pay-for-more", "strong", True,
        r"\b(?:pay(?:ing|s)?|spend(?:ing)?|shell(?:ing)? out|fork(?:ing)? out|cough(?:ing)? up|invest(?:ing)?)\b.{0,25}\b(?:for|on)\b.{0,25}\b(?:more|extra|additional|another|bigger|larger|higher|better|premium|unlimited|the (?:full|paid|pro|premium))\b"
        r"|\b(?:pay(?:ing)?|spend(?:ing)?)\s+(?:more|extra|an extra|a bit more|a little more)\b|\b(?:start|begin|commenc)\w*\s+(?:to\s+)?(?:pay\w*|bill\w*|charg\w*)\b|\bstop\w* paying\b")
    add("money", "load-credits", "strong", True,
        r"\b(?:load|loading|add|adding|top|topping|buy|put|stock|reload|reloading|refill\w*|recharge\w*)\b.{0,30}\b(?:credits?|balance|funds?|minutes|prepaid|allowance|data pack|sms pack|sticker credits?)\b")
    add("money", "next-size-up", "strong", True,
        r"\b(?:next|higher|upper|bigger|larger|fancier|better|deluxe|full|paid|family|pro|premium|plus|top)\s+(?:rung|level|size|pack|bundle|tier|plan|edition|package|licen[cs]e|subscription|version|model|option)\b"
        r"|\b(?:unlock|get|take|choose|pick|switch to|move to)\w*\s+(?:the |a )?(?:bigger|larger|full|premium|paid|pro|deluxe|family)\b"
        r"|\btake the plunge\b|\bgo for the (?:deluxe|premium|pro|paid|full|bigger|top)\b")
    add("money", "upgrade-to-bigger", "strong", True,
        r"\b(?:upgrad\w*|mov\w* up|step\w* up|go\w* up|siz\w* up)\b.{0,25}\b(?:to|onto)\b.{0,15}\b(?:the |a )?(?:bigger|larger|next|higher|better|fancier|paid|full|pro|premium|top|plus)\b(?: (?:one|plan|tier|level|version|option|model|size|pack|bundle))?")
    add("money", "beyond-the-free-period", "strong", True,
        r"\b(?:past|beyond|after|outside|out of|over)\b.{0,15}\b(?:free(?:bie)?|trial|grace)\b|\bstop\w* (?:riding|using|relying on|being on|living on|staying on)\b.{0,20}\bfree\b|\bfreebie\b")
    add("money", "commit-to-term", "strong", True,
        r"\bcommit\w* to\b.{0,25}\b(?:year|years|term|month|months|contract|subscription|plan|pack|vendor)\b|\b(?:agree|agreeing|agreed)\b.{0,25}\b(?:recurring|monthly|annual|yearly)\b|\brecurring invoices?\b")
    add("money", "buy-capacity", "strong", True,
        r"\b(?:buy|purchas\w*|order|reserve|book|rent|lease|hire|pay for)\w*\b.{0,30}\b(?:more|extra|additional|another|bigger|larger|\d+|two|three|four|five|six)\b.{0,30}\b(?:storage|space|room|capacity|seats?|chairs?|licen[cs]es?|users?|credits?|minutes|devices?|numbers?)\b"
        r"|\bbuy\w*\b.{0,15}\b(?:us|me)\b.{0,15}\b(?:room|space|time|capacity|storage)\b|\bbreathing room\b.{0,20}\b(?:storage|space|capacity)\b|\btop[ _-]?up\b|\bprepaid\b")
    add("money", "credits-then-load", "strong", True, r"\bcredits?\b.{0,60}\b(?:load|add|put|top|buy|stock|reload|refill)\w*\b")
    add("money", "more-credits", "weak", True, r"\b(?:more|extra|another|new)\s+(?:[\w-]+ ){0,2}credits?\b")
    add("money", "commitment-term", "strong", True,
        r"\b(?:annual|yearly|12[- ]month|multi[- ]year|three[- ]year|3[- ]year|two[- ]year|monthly)\b.{0,25}\b(?:contract|billing|term|commitment|agreement|subscription|package|deal)\b"
        r"|\b(?:contract|commitment|agreement)\b.{0,15}\b(?:annual|yearly|12[- ]month|multi[- ]year)\b|\b(?:start|begin|sign|renew|extend)\w*\s+(?:\w+\s+){0,3}?(?:contract|commitment|agreement)\b"
        r"|\block\w* in\b.{0,20}\b(?:rate|price|pricing|term)\b|\bmonth to month\b")
    add("money", "trial-converts", "strong", True,
        r"\btrial\b.{0,60}\b(?:paid|convert\w*|roll\w*|continu\w*|renew\w*)\b|\b(?:roll|convert|flip)\w*\b.{0,20}\b(?:into|to)\b.{0,15}\bpaid\b|\bpaid (?:version|edition|account|tier|plan|one)\b")
    add("money", "premium-edition", "strong", True,
        r"\b(?:premium|enterprise|pro|plus|business|team|growth|ultimate|unlimited) (?:edition|tier|plan|version|package|licen[cs]e|membership|account)\b|\bat (?:the )?(?:then-)?(?:current )?(?:list|retail|full) price\b")
    add("money", "extra-capacity", "weak", True,
        r"\b(?:extra|additional|more|another|new)\s+(?:seats?|users?|licen[cs]es?|logins?|locations?|stores?|devices?|terminals?|registers?|readers?|phone lines?|storage|gb|capacity|accounts?|chairs?)\b"
        r"|\bswitch\w* on\b.{0,15}\b\d+\b.{0,12}\b(?:seats?|users?|licen[cs]es?)\b")
    add("money", "raise-a-cap", "weak", True,
        r"\b(?:lift\w*|rais\w*|increas\w*|expand\w*|extend\w*|uncap\w*|unlock\w*|bigger|larger|higher|more)\b.{0,20}\b(?:cap|limit|quota|allowance|ceiling|threshold|capacity|usage|volume|rate limit)\b"
        r"|\b(?:bigger|larger|higher|more|extra|bump\w*)\s+(?:cap|limit|quota|allowance|capacity)\b|\bhitting the (?:limit|cap|quota)\b|\bstop hitting\b")
    add("money", "billing-words", "weak", True,
        r"\b(?:billed?|billing|charged?|charges|invoice me|invoiced|per (?:month|year|seat|user|call|message|sms|request)|/(?:mo|month|yr|year)|a month|each month|every month|monthly fee|monthly cost|"
        r"auto-?renew\w*|renewal|overage|pay[- ]as[- ]you[- ]go|metered|prepaid)\b")
    add("money", "amount", "weak", True, r"\$\s?\d|\b\d+(?:\.\d+)?\s?(?:dollars?|bucks|cad|usd)\b")

    # ---------------- (b) deletion, removal or overwrite of anything persistent
    add("deletion", "removal-verb-on-object", "strong", True,
        r"\b" + REMOVAL + r"\b.{0,60}\b" + PERSIST + r"\b|\b" + PERSIST + r"\b.{0,60}\b" + REMOVAL + r"\b")
    add("deletion", "removal-verb-with-determiner", "strong", True, r"\b" + AMBIGUOUS + r"\s+" + DET + r".{0,60}\b" + PERSIST + r"\b")
    add("deletion", "removal-idiom", "strong", False,
        r"\b(?:out to pasture|put (?:[\w']+ ){0,3}?out to pasture|gone from|go away|goes away|make (?:[\w']+ ){0,3}?go away|wipe the slate|clean slate|blank slate|start (?:from )?scratch|from the ground up)\b")
    add("deletion", "gone-for-good", "strong", True,
        r"\b(?:not|no longer|never) (?:exist\w*)\b|\bcease\w* to exist\b|\brest(?:s|ing)? in peace\b|\brip\b|\bfactory (?:state|settings?|reset|defaults?)\b|\bback to (?:blank|empty|zero|nothing|scratch|day one|how it started|its original|initial|square one)\b"
        r"|\bre-?init\w*\b|\bstart\w*\s+(?:the |our |a |this |that )?(?:[\w'-]+ ){0,2}?" + PERSIST + r"\s+(?:over|again|afresh|anew|from scratch)\b|\bscorched[- ]earth\b|\bburn\w* (?:it|them|the|all)\b.{0,10}\bdown\b|\braz\w*\b|\bnothing left\b|\bleav\w* (?:it|them) empty\b|\b(?:so|until) (?:that )?(?:it|they) (?:is|are) empty\b|\bwrite over\b|\bsave over\b|\bpaste over\b|\bcopy over\b.{0,25}\b(?:live|original|existing|current)\b")
    add("deletion", "cut-down-to-only", "strong", True,
        r"\b" + PERSIST + r"\b.{0,60}\b(?:reduc\w*|cut\w*|narrow\w*|shrink\w*|squeez\w*|compress\w*|condens\w*|boil\w*|pare\w*|whittl\w*|trim\w*)\b.{0,25}\bto\b.{0,12}\b(?:only|just|the last|last|latest|current|newest|most recent|header|first|top|what is current|what's current)\b"
        r"|\b(?:reduc\w*|cut\w*|narrow\w*|shrink\w*|squeez\w*|compress\w*|condens\w*|boil\w*|pare\w*|whittl\w*|trim\w*)\b.{0,60}\b" + PERSIST + r"\b.{0,25}\b(?:down )?to\b.{0,12}\b(?:only|just|the last|last|latest|current|newest|most recent|header|first|top|what is current|what's current)\b")
    add("deletion", "replace-object", "strong", True,
        r"\b(?:replac\w*|overwrit\w*|swap\w* out|supersed\w*|clobber\w*|stomp\w*)\b.{0,50}\b(?:with|by|using)\b|\b(?:replac\w*|overwrit\w*)\b.{0,40}\b" + PERSIST + r"\b")
    add("deletion", "reset-or-rebuild", "weak", True,
        r"\b(?:reset\w*|rebuild\w*|re-?creat\w*|redo\w*|regenerat\w*|restor\w*|revert\w*|roll\w* back|refresh\w*|reload\w*|re-?import\w*|re-?sync\w*|repopulat\w*|rewrit\w*)\b.{0,40}\b(?:"
        r"branch(?:es)?|archives?|tables?|rows?|workbooks?|work ?sheets?|sheets?|tabs?|spreadsheets?|databases?|dbs?|buckets?|repos?|snapshots?|backups?|collections?|datasets?|ledgers?|history)\b")
    add("deletion", "stale-object", "weak", True, r"\b" + STALE + r"\b(?: [\w'-]+){0,2} " + PERSIST + r"\b")

    # ---------------- (c) an outside party is told or contacted
    add("outside", "heads-up", "strong", True,
        r"\b(?:heads?[- ]?up|fyi|f\.y\.i\.?|shout[- ]?out|tip[- ]?off|tipped off|word to|a word with|note to|memo to|notice to|nudge to|reminder to)\b.{0,30}\b(?:" + P + r")s?\b"
        r"|\b(?:heads?[- ]?up|fyi)\b\s+(?:to |for )?(?:the |our )?[\w'-]+")
    add("outside", "make-sure-they-know", "strong", True,
        r"\b(?:make|making|ensur\w*|see|check|verify|confirm)\s+(?:sure\s+)?(?:that\s+)?" + ART + r"(?:[\w'-]+ ){0,3}?(?:" + P + r")s?\b.{0,25}\b(?:know\w*|see\w*|hear\w*|get\w*|receiv\w*|ha(?:s|ve)|is told|are told|read\w*|notic\w*|aware|informed|find\w* out)\b"
        r"|\b(?:" + P + r")s?\b.{0,25}\b(?:should|must|needs? to|will|to)\s+(?:be\s+)?(?:aware|informed|told|know|hear|see|find out|notified|briefed|reminded|warned|updated|looped in)\b")
    add("outside", "bring-up-to-speed", "strong", True,
        r"\b(?:bring|get|keep|brought|got|kept)\w*\b.{0,25}\b(?:up to speed|in the loop|in the know|posted|informed|aware)\b|\bbring\w* .{0,25} up to date\b")
    add("outside", "made-aware", "strong", True, r"\b(?:made|make|making)\s+(?:\w+\s+)?(?:aware|known)\b")
    add("outside", "whoever-should-hear", "strong", True,
        r"\b(?:whoever|anyone|everyone|everybody|someone|somebody|folks|people|those)\b.{0,40}\b(?:should|must|needs? to|will|to)\s+(?:be\s+)?(?:hear|know|see|aware|informed|told|find out|notified|briefed|reminded|warned|updated)\b")
    add("outside", "hit-up", "strong", True, r"\bhit(?:s|ting)? up\b|\binto\b.{0,15}\bhands\b|\bin the hands of\b")
    add("outside", "file-a-complaint-with", "strong", True,
        r"\b(?:file|lodge|raise|submit|make|log|send|issue)\w*\b.{0,15}\b(?:complaint|claim|dispute|grievance|report|appeal|objection|notice|request|inquiry|enquiry)\b.{0,25}\b(?:with|to|against)\b\s+" + ART + r"(?:\w+ ){0,2}?(?:" + P + r")s?\b")
    add("outside", "let-them-have", "strong", True,
        r"\blet\w*\s+" + ART + r"(?:[\w'-]+ ){0,2}?(?:" + P + r")s?\b\s+(?:have|see|get|read|view|access|look|hear|know)\b")
    add("outside", "put-in-front-of", "strong", True,
        r"\b(?:put|get|bring|hand|pass|slide|run|take|walk|present|surface|escalat\w*|rais\w*|float|flag|forward|show|relay|route|carry|deliver|circulat\w*)\w*\b.{0,50}"
        r"\b(?:in front of|to|with|by|past|before|across to|over to)\b\s+" + ART + r"(?:[\w'-]+ ){0,2}?(?:" + P + r")s?\b")
    add("outside", "reply-to-inbound", "strong", True,
        r"\b(?:answer\w*|respond\w*|repl(?:y|ies|ied|ying)|get\w* back|writ\w* back|follow\w* up|acknowledg\w*|confirm\w*|decline\w*|accept\w*|rsvp\w*|thank\w*|apolog\w*|congratulat\w*)\b.{0,40}"
        r"\b(?:email|e-mail|mail|message|msg|text|dm|voicemail|inquiry|enquiry|invite|invitation|request|quote|proposal|query|question|complaint|review|comment|thread|ticket|offer)s?\b")
    add("outside", "participle-after-party", "strong", False,
        r"\b(?:" + P + r")s?(?:'s)?\s+(?:\w+ )?(?:notified|informed|emailed|messaged|told|texted|called|contacted|reminded|updated|briefed|warned|alerted|cc'?d|looped in|invited|e-mailed|pinged)\b")
    add("outside", "get-it-to-them", "strong", True,
        r"\b(?:get|send|bring|take|carry|deliver|hand|pass|forward|relay|route|direct|push|circulate|share|slip|drop|leave)\w*\b.{0,50}\bto\b\s+" + ART + r"(?:[\w'-]+ ){0,2}?(?:" + P + r")s?\b")
    add("outside", "invite-or-accept", "strong", True,
        r"\b(?:accept\w*|decline\w*|rsvp\w*|send\w* regrets|cancel\w*|reschedul\w*)\b.{0,30}\b(?:invites?|invitations?|meeting|call|tasting|appointment)\b")

    # ---------------- (d) a secret or credential
    add("secret", "one-time-code", "strong", False,
        r"\b(?:six|6|four|4|eight|8)[- ]digits?\b|\b(?:verification|security|auth\w*|confirmation|login|sign-?in|one[- ]time|otp|mfa|2fa|sms|text)\s+(?:code|pin|passcode|digits?)\b"
        r"|\bthe code\b.{0,30}\b(?:text|sms|email|app|authenticator|arrived|sent|came)\b|\bauthenticator\b|\bmfa\b|\botp\b|\bpin code\b")
    add("secret", "keypair-or-cert", "strong", False,
        r"\bkey ?pairs?\b|\bcert(?:ificate)?s?\b.{0,20}\b(?:private|key)\b|\bpublic half\b|\bprivate half\b|\bssh\b|\bgpg\b|\bpgp\b|\bkeystore\b|\bsecret manager\b|\bvault\b|\bsigning key\b|\bwebhook (?:secret|url)\b")
    add("secret", "browser-session", "strong", False,
        r"\b(?:logged[- ]in|signed[- ]in|authenticated|active)\s+(?:browser )?(?:session|cookie|profile)s?\b|\bsession (?:cookie|token|id)s?\b|\bcookies?\b.{0,20}\b(?:export|copy|reuse|grab)\w*\b"
        r"|\b(?:export|copy|reuse|grab)\w*\b.{0,30}\b(?:cookies?|session)\b|\bbrowser profile\b")
    add("secret", "integration-string", "strong", False,
        r"\b(?:integration|connector|api|webhook|oauth|app)\s+(?:code|string|secret|value|credential|link|url|password|passcode)\b"
        r"|\b(?:long|secret|private|hidden|special|magic)\s+(?:internal[- ]integration\s+)?(?:string|code|value|link|url)\b.{0,40}\b(?:settings|dashboard|developer|integration|api|portal)\b"
        r"|\b(?:long|secret|private|hidden)\s+(?:internal[- ]integration\s+)?(?:string|code|value)\b|\binternal[- ]integration (?:code|string|value)\b"
        r"|\bconnect\w*\b.{0,30}\b(?:my|our|the|this)\s+(?:\w+ )?account\b|\bauthori[sz]e\w*\b.{0,30}\b(?:app|access|connection|integration|connector|oauth)\b|\bgrant\w*\b.{0,25}\bapi\b")
    add("secret", "recovery-material", "strong", False,
        r"\b(?:backup|recovery|reset|emergency|rescue)\s+(?:codes?|phrases?|words?|keys?|seeds?)\b|\b(?:seed (?:phrase|words?)|mnemonic|passphrase)\b|\bsigning\s+(?:thing|secret|key|string|value|token|code)\b"
        r"|\b(?:thing|string|code|value|key|link|gizmo|token) that (?:lets|allows|gives|unlocks|opens|enables)\b")
    add("secret", "rotate-a-connection", "weak", True, r"\brotat\w*\b.{0,30}\b(?:thing|connection|integration|zapier|webhook|link|app|connector|access|bot|service account)\b")
    add("secret", "config-secrets", "weak", True, r"\b(?:env(?:ironment)? (?:vars?|variables?)|config vars?|dotenv|scopes?|auth(?:entication|orization)?)\b")
    return c


def _scan(cues, scrubbed, clauses, rule_hits):
    """Run the script's half of the screen. clauses: [{n, text, read_start, owned_write, unaccounted}]. rule_hits: [(rule_id, class, clause_no)]."""
    ans = {q: {"hits": [], "strong": False, "weak": False} for q in QUESTIONS}
    # rules that already matched answer a question
    for rid, cls, n in rule_hits:
        q = None
        if rid in SECRET_RULES or cls == "R5":
            q = "secret"
        elif rid in MONEY_RULES or cls == "R6":
            q = "money"
        elif rid in DELETE_RULES:
            q = "deletion"
        elif cls == "R4" and rid not in MONEY_RULES:
            q = "outside"
        if q:
            ans[q]["hits"].append({"by": "rule", "cue": rid, "clause": n})
            ans[q]["strong"] = True
    for q, name, strength, skip_read, rx in cues:
        # whole text: strong cues that are not limited to non-read clauses (a spanning phrase must not be hidden by a split)
        if strength == "strong" and not skip_read:
            m = rx.search(scrubbed)
            if m:
                ans[q]["hits"].append({"by": "cue", "cue": name, "matched": m.group(0)[:30].strip(), "clause": 0})
                ans[q]["strong"] = True
        for c in clauses:
            if c["read_start"] and skip_read:
                continue
            if c["owned_write"] and skip_read:
                continue
            m = rx.search(c["text"])
            if m:
                ans[q]["hits"].append({"by": "cue", "cue": name, "matched": m.group(0)[:30].strip(), "clause": c["n"]})
                ans[q]["strong" if strength == "strong" else "weak"] = True
        # a strong cue that skips read clauses is also checked on the whole text when the text has no read clause at all
        if strength == "strong" and skip_read and clauses and not any(c["read_start"] for c in clauses):
            m = rx.search(scrubbed)
            if m and not any(h["cue"] == name for h in ans[q]["hits"]):
                ans[q]["hits"].append({"by": "cue", "cue": name, "matched": m.group(0)[:30].strip(), "clause": 0})
                ans[q]["strong"] = True
    return ans


def script_screen(cues, scrubbed, clauses, rule_hits, unaccounted_clauses):
    ans = _scan(cues, scrubbed, clauses, rule_hits)
    out = {}
    for q, a in ans.items():
        if a["strong"]:
            answer = "yes"
        elif a["weak"]:
            answer = "unsure"
        else:
            answer = "no"
        seen, ev = set(), []
        for h in a["hits"]:
            key = (h["cue"], h["clause"])
            if key not in seen:
                seen.add(key)
                ev.append(h)
        rec = {"answer": answer, "evidence": ev[:6]}
        if answer == "no":
            rec["strong_no"] = not unaccounted_clauses
            rec["evidence"] = [{"by": "script", "cue": "no-cue-matched",
                                "note": ("no cue family matched and every clause was recognised" if not unaccounted_clauses
                                         else f"no cue family matched, but clause(s) {', '.join(str(n) for n in unaccounted_clauses)} were not recognised, so this 'no' is weak")}]
        out[q] = rec
    return out


def clean_model_answers(raw):
    """Validate the model's (or owner's) answers. Returns (answers, problems). An answer is {answer, evidence}. A 'no' without evidence is 'unsure'."""
    answers, problems = {}, []
    if raw is None:
        return answers, problems
    if not isinstance(raw, dict):
        return answers, ["screen answers must be an object keyed by money, deletion, outside, secret"]
    for q in raw:
        if q not in QUESTIONS:
            problems.append(f"unknown screen question '{str(q)[:20]}'")
    for q in QUESTIONS:
        if q not in raw:
            continue
        v = raw[q]
        if isinstance(v, str):
            v = {"answer": v, "evidence": ""}
        if not isinstance(v, dict) or str(v.get("answer", "")).lower() not in ANSWERS:
            problems.append(f"question '{q}': answer must be yes, unsure or no")
            answers[q] = {"answer": "unsure", "evidence": "", "accepted": False, "note": "unreadable answer, counted as unsure"}
            continue
        ans = str(v["answer"]).lower()
        ev = v.get("evidence", "")
        ev = ev if isinstance(ev, str) else ""
        rec = {"answer": ans, "evidence": ev.strip()[:300], "accepted": True, "note": ""}
        if ans == "no" and len(rec["evidence"]) < 10:
            rec.update(answer="unsure", accepted=False, note="a 'no' needs a reason (at least 10 characters); counted as unsure")
        elif ans in ("yes", "unsure") and len(rec["evidence"]) < 10:
            rec["note"] = "raised, but no evidence was given"
        answers[q] = rec
    return answers, problems


def merge(script, model_answers):
    """Combine the script's answers with the model's. Returns the screen record and the list of (question, class, answer) that raise the class."""
    questions, raises, needs = {}, [], []
    for q, meta in QUESTIONS.items():
        s = script[q]
        m = model_answers.get(q)
        final = s["answer"]
        decided = "script"
        if m is not None and ORDER.index(m["answer"]) > ORDER.index(final):
            final, decided = m["answer"], "model"
        elif m is not None and m["answer"] == final:
            decided = "script and model" if final != "no" else "script and model"
        answered = final in ("yes", "unsure") or (final == "no" and (s.get("strong_no") or (m is not None and m["accepted"] and m["answer"] == "no")))
        if final == "no" and not answered:
            needs.append(q)
        questions[q] = {"question": meta["text"], "answer": final, "decided_by": decided, "class_if_not_no": meta["class"], "answered_with_evidence": answered,
                        "script": s, "model": m}
        if final in ("yes", "unsure"):
            raises.append((q, meta["class"], final))
    return {"complete": not needs, "needs_answers": needs, "questions": questions}, raises


# ---------------- typo tolerance (screen only)
TYPO_VOCAB = ("clear empty delete remove erase purge wipe destroy discard truncate overwrite publish announce subscribe subscription upgrade receipts folder folders archive archives database "
              "workbook spreadsheet branches branch snapshot snapshots backup backups document documents records tables supplier vendor customer customers accountant landlord password passwords "
              "credentials secret token premium billing invoice invoices payment payments email message notify inform remind reminder landlord wholesaler workspace workspaces exports inventory").split()
TYPO_SKIP = {"remote", "clean", "cleaner", "planned", "plain", "clearly", "emails", "emailed", "messages", "inventor", "backed", "tabled", "table", "tables", "record", "folded", "remove", "removed", "remover",
             "rooms", "token", "tokens", "secrets", "branched", "documented", "billings", "empties", "emptied", "clears", "cleared"}


def _dl1(a, b):
    """True when a and b are within one edit (substitution, insertion, deletion or adjacent swap)."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diff = [i for i in range(la) if a[i] != b[i]]
        if len(diff) == 1:
            return True
        return len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]
    if la > lb:
        a, b = b, a
    return any(b[:i] + b[i + 1:] == a for i in range(len(b)))


def fix_typos(text):
    """Replace a token that is one edit away from a risky word (and is not itself a known word) with that word. Used only for the screen."""
    known = set(TYPO_VOCAB)

    def fix(m):
        w = m.group(0)
        if len(w) < 5 or w in known or w in TYPO_SKIP:
            return w
        for v in TYPO_VOCAB:
            if _dl1(w, v):
                return v
        return w
    return re.sub(r"[a-z]+", fix, text)
