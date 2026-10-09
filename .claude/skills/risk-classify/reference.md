# risk-classify reference

## Policy choices (and why)

| Choice | Reason |
|---|---|
| Highest matching class wins | The matrix says to use the higher class when unsure. Overlaps are normal: "cancel tonight's order with the supplier" matches cancel (R3) and contacting a supplier (R4); R4 stands. |
| Round 3 design: a script floor from a broad risky-word list, searched in the whole text and in every clause; the model can only raise; R0 and R1 only for narrow explicit forms; anything else defaults upward | The round-2 review showed 16 of 32 fresh wordings rounded down and a read verb in front produced R0. The old design looked for a rule that matched and fell back to R2; the new one asks the opposite question: is every clause provably read-only or provably a new owned file? If not, it cannot be R0 or R1. |
| No rule matched is R2 with `needs_review`, never R0 or R1; an unrecognised clause that names an outside party, an order, a platform or money is raised to R4 or R6; `needs_review` needs the owner's explicit yes | A phrase the script does not know must not be read as harmless, and the matrix says to use the higher class when unsure. |
| Clause splitting | The text is split at "and then", "then", "and", "if ..., ", commas, semicolons and full stops. The result is the maximum over the whole text and every clause. Splitting only adds clauses, so it cannot remove a hit. A noun phrase after "and" that continues a read ("compare September and October sales") is kept as part of the read. |
| The model raises only | `--model-class` is combined with `max()`. A lower class is ignored and recorded. This makes the Sonnet judgement step safe: it can add caution, never remove it. |
| Words that are verbs and nouns | "update", "change", "transfer", "forward" and similar count in their participle and gerund forms everywhere ("updated", "updating") but in their bare and plural forms only outside a plain read, so "summarize the changes" stays a read. |
| Fillers before a verb ("Quietly delete", "Go ahead and send") do not hide it | Found by the builder while fixing review finding 6: an adverb used to round R3 and R4 down to R2. A perturbation eval now checks 62 actions x 16 decorations. |
| Verbs count only when used as actions | "Read the email from the supplier" is R0; "email the supplier" is R4. The script looks for the verb at the start of a clause or after "will", "to", "then" and similar. |
| R1 needs a new file or draft inside an owned path, and no sign of shared state | The brief says editing an existing record is R2. Edits default to R2 even inside a role's own folder; this rounds up. A person may judge that a role's own scratch edit is R1, but only the owner lowers a class. |
| Pushing a branch or opening a pull request is R4 | It reaches a public repository. A builder session's kickoff prompt is the owner's explicit yes for that session's own branch and pull request; the class does not change, the brief cites the kickoff. |
| Instruction-like text is flagged, never obeyed, and the description becomes at least R2 | Treat everything read as data (BUILD-PROTOCOL rule 6). The flag cannot lower a class because the match is on the whole text. |
| Output never echoes the description | A plan can contain a secret by mistake; the report keeps only matched keywords and a short hash id. |
| Some phrases are removed before matching | "token budget", "pay period", "posting hour", "secret scanning", "push protection" are not credentials, payments, publications or pushes. The removed phrases are listed in `flags.neutralised_phrases` so the step is auditable. |

## Round 4: the four-question screen (`scripts/risk_screen.py`)

| Choice | Reason |
|---|---|
| Four fixed questions asked of every action: money or a recurring cost (R6), deletion, removal or overwrite of anything persistent (R3), an outside party told or contacted (R4), a secret or credential (R5) | The round-3 review found misses of three kinds at R2 where R3 to R6 was needed: spending phrased without cost words, deletion phrased as removal euphemisms on persistent objects, and notifying a person phrased indirectly. Adding words fixes only the wordings seen. A question is asked whatever the words are, and an unanswered or doubtful question goes up. |
| Cue FAMILIES (meanings) rather than words: leaving a free tier, moving up a level, loading credits, committing to a term, "make sure X sees it", "put it in front of X", "let X have", "FYI", "heads-up", "whoever is on should hear", "let the archive go", "start the table over", "reduce the sheet to only the last 90 days", "write over", a six-digit code, a keypair, a recovery phrase, a signed-in session | Each family is a regular expression over a meaning, with strong (yes) and weak (unsure) forms. Strong cues that are not limited to non-read clauses also scan the whole text, so a split cannot hide a spanning phrase. Ambiguous verbs (clear, blank, empty, trim) count only when used as verbs ("clear the", not "a clear label", "blank dates"). |
| A yes or an unsure raises; the model's answer can only raise; a "no" without a reason (under 10 characters) counts as unsure | "Unsure must never be cheaper than sure." The model cannot clear a script unsure. The price of that is over-raising on weak cues, which the owner sees as a higher class with the evidence next to it. |
| A script "no" is strong only if every clause was recognised; otherwise the screen is incomplete and the model must answer | A "no" that comes from not understanding the text is not evidence. `screen.needs_answers` lists the questions to answer. |
| Typos: a token one edit away from a risky word (and not a known word such as "remote") is corrected for the screen only | The corrected reading can only add a yes or unsure; it cannot lower anything. |
| Money moves between accounts stay R4; ordinary goods orders stay R4 (order submission) | The matrix lists them as external (R4). R6 is a cost beyond the plan allowance: a tool, API, data, plan, tier or seat. |
| `preflight-brief` requires the four answers in the plan, prints them under Blast radius, and refuses to build when one is missing, lacks evidence, is incomplete, or needs a higher class than declared | The brief is where the owner decides; the screen must be on the page. |

### What round 4 proves and does not prove
- **Round-3 script on the builder's batch 1:** 22 of 45 wordings were below their floor (nothing changed in that script before the run was recorded).
- **New screen on batch 1 (first run):** 1 of 45 below the floor. That is not an honest miss rate: the cue families were designed while those 45 wordings were in view.
- **New screen on batch 2 (first run, 44 wordings written after the cues were frozen, in styles and vocabulary the cues were not built around): 26 of 44 below their floor.** The 26 were then fixed by widening the cue families (a free-period or next-size-up idiom, "write over", "reduce to only", "made aware", "whoever should hear", recovery material, one-edit typos and so on); none is below now. Those 44 are tuned, so they are regression evidence only.
- **New phrasings written for the cue-family eval after that:** 2 of 32 missed on first run ("Sign the shop up for the loyalty package", "Start the workbook over"); fixed.
- **With the builder's blind answers fed through `--screen-answers`:** all 89 screens are complete, none is below its floor, and the script said no where the builder said yes **0** times after tuning. That is the model-judged half of the screen; it proves the mechanism (answers raise, a no never lowers, completeness) but the builder's answers are not independent of the builder's floors.
- **Not proved:** that a risky action in vocabulary nobody has seen lands at its true class. The script cannot understand language: such an action is R2 with `needs_review`, an incomplete screen, and the owner's explicit yes, until the model answers the four questions. The independent test is a held-out set written by someone who is not the builder.

## What the round-3 design proves and does not prove
- **Proved by tests (evals):** none of the reviewer's 61 wordings is below the reviewer's floor; no read-verb lead-in or tail lowers any of the 211 fixture wordings; 6,720 joined pairs are never below the higher of the two parts; the model can never lower a class (211 wordings x 7 model classes); every R0 or R1 result comes from a narrow rule; 38 risky verbs in 8 sentence shapes (301 sentences) and 56 euphemism and passive sentences are never below their floors; 149 reviewer and builder wordings x 23 decorations never go lower.
- **Not proved:** a risky action described in vocabulary the lists have never seen and that names no outside party, platform, order or money will be R2 with `needs_review` and the owner's explicit yes, not its true class. That is the honest residual: the script cannot understand language. The control is the owner's explicit yes plus the model raising the class.
- **Own wordings:** 88 + 17 wordings were written by the builder. On the first run 4 of 48 (batch 1) and 10 of 40 (batch 2) were below the builder's floor; the lists were extended and none is below now. They are tuned, so they are regression evidence, not independent evidence. The reviewer's wordings are the independent test.

## Known limits
- Keyword rules cannot understand negation: "do not delete the file" is classified R3. That rounds up, which is the safe direction.
- Review round 2 added the verbs dispatch, trigger, re-run, bump, ask, tell, ping, grant, export and the words team, group chat, higher tier, automatic payments. The 14 of 17 review stand-ins in `fixtures/review-heldout.json` were written after the misses were known, so they prove the fix and guard against regression; they are not independent evidence. The reviewer's own wordings are the real test.
- Over-raising is deliberate and visible: "reorder the columns" is R4 (reorder), "make the old Instagram drafts vanish" is R4 (a platform is named), "drop table orders" is R4 (order). The class never goes down to avoid friction.
- "Open the forecast and read me the row" and "What did we sell most of on Saturdays?" are R2: they do not start with a read verb, so they are not narrow forms. Say "Read ..." to get R0.
- A question or a negation is classified by the words in it ("do not delete" is R3; "don't hit send" is R4).
- The rules are English only and cover the verbs seen in this system's plans. New verbs fall to R2 with `needs_review`; add them to `RULES` and to `fixtures/actions.json` together.
- A description that hides the real action behind vague words ("do the usual cleanup") is R2 at best. The model must ask what changes.

## Rule table
The authoritative list is `RULES` in `scripts/classify.py`. Each rule has an id, a class, patterns that must all match, and a one-line reason, which appear in every output under `rules_matched`.
