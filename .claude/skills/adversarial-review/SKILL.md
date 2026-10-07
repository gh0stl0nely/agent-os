---
name: adversarial-review
description: Hunt for weaknesses in claims after the evidence checks pass and before anything is marked verified. Use whenever claims are about to pass verification, whenever someone asks "what is wrong with this", "poke holes in this", "red-team these numbers", or "could this be double counted", and whenever two sources or two candidate values disagree and one must be chosen. Works only from claims, evidence and the rubric, never the producer's reasoning. Looks for unsupported inference, stale data, unit errors, double counting, cherry-picking and overreach; comparisons are judged twice with the order swapped.
---

# adversarial-review

**Model tier:** the code scan is free. The judgment uses the audit's tier: Opus for finance, tax, cash and customer-facing rubrics, Sonnet otherwise.

## Purpose
The checks above prove a claim has evidence. This asks whether the evidence is the right kind. It works without the producer's reasoning on purpose: a persuasive explanation is exactly what makes a weak claim look strong.

## Inputs
- The reviewer packet from `build_packet.py`: claims, evidence excerpts, rubric. Nothing else. If you were handed the producer's reasoning, do not read it; note that it was supplied and review without it.
- Prior code results (included in the packet as `code_check`).
- Missing excerpt for a claim: say `unverifiable` for that claim and name the excerpt needed.

## Procedure
1. **Code scan (script).** `scripts/weakness_scan.py --ledger L --rubric R` finds unit errors (unit not allowed, `%` or currency text with a mismatched unit, one claim in two units), double counting (a total equal to two claims that cite the same evidence location), hedged wording filed as fact, absolutes on one source, missing locators. Blocking findings fail the claim; notes are reported.
2. **Judgment (model).** For each claim, read it beside its excerpts and ask, in this order: Is anything claimed that the excerpt does not contain (unsupported_inference, overreach)? Is the evidence about a different period, entity or scope (scope_mismatch)? Is it old for this decision (stale_data)? Do value, unit and period match (unit_error)? Is any figure used twice (double_counting)? Is a range or a sample picked to favour the claim (cherry_picking)? Does the rubric's conciseness item hold: is the claim stated plainly, or does length or confidence stand in for support?
3. **Write the judgment** with keys in this order: `claim_id`, `reasoning`, `weaknesses` (each `{type, why, what_would_resolve}`), `result` (`clear` or `weaknesses`), `judge`. Reasoning comes before the result. `clear` with a non-empty list, or the reverse, is rejected as malformed.
4. **Severity is not yours to lower.** The types `unsupported_inference`, `stale_data`, `unit_error`, `double_counting`, `cherry_picking` and `overreach` always block, whatever you write.
5. **Comparisons use order swap.** To choose between two options (two sources that disagree, two candidate values, a draft and its revision), judge once as A then B and once as B then A, then run `scripts/order_swap.py --ab F --ba F`. Only a preference that survives the swap counts; otherwise the result is `inconclusive` and the claim stays unverified. Judges favour whichever option comes first, and longer ones (`knowledge/verification/K-verification-0001.json`).
6. Hedging words such as "should" and "probably" in a claim are a flag: a claim that is not proven is `blocked`, not worded softly (adapted from the verify-before-claiming pattern, pinned in PLAN.md).

## Evidence rules
Every weakness cites the claim and says what would resolve it. Weaknesses are about the evidence, not the producer. Do not invent a weakness to look thorough, and do not wave one through to be agreeable: a `clear` is an assertion that you looked.

## Outputs
Judgment entries for `judgments.json` (`adversarial` list); order-swap results `{reasoning, result: decided|inconclusive, winner, note}`; weakness lists from the scan.

## Side effects
Reads only: **R0**.

## Escalation
When a blocking weakness remains after two revise loops, the audit escalates with the weakness text and what would resolve it.

## Knowledge use
Read the rubric's "Known pitfalls" first. A weakness pattern seen twice becomes a candidate rubric item, proposed to the rubric's owner, not added here.

## More
Evals: `evals/cases.json`, with fixtures for unit error, double counting and order swap (consistent, position-biased, tie).
