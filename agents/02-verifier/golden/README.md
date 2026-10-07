# Golden set

Synthetic seeded-error cases for the Verifier, used by the `golden-set-calibration` skill. Nothing here is real
business data. `root/` holds the shared fixtures (scripts, CSVs, source documents, knowledge records); `cases/` holds one
JSON file per case; `build_cases.py` regenerates both (run it only to add cases: changing a case or its expected
result changes the measuring stick, which is a shared-state change and needs a Preflight Brief).

Run: `python3 .claude/skills/golden-set-calibration/scripts/run_golden.py [--save LABEL] [--compare latest]`

## Layers

| Layer | Meaning |
|---|---|
| `code` | The code checks alone must catch it (no model judgment needed). A miss exits non-zero. |
| `code-after-judgment` | A model judgment is present but wrong or incomplete (for example "supports: yes" with a number the quote lacks); the code re-checks the judgment and still catches it. |
| `model-judged-replay` | Only a model judgment can catch it. The recorded judgment was written by the builder who wrote the case, so the result is a replay, not an independent measurement. A fresh session supplies real judgments with `--judgments FILE` (case id to `{source_support, adversarial}`). |
| `control` | A clean case that must pass. A failure is a false positive. |

Structural types (`missing_evidence`, `verified_without_evidence`, `assumed_status`, `malformed_row`) must be caught 100%
by code alone.

## Cases

| Case | Error type | Layer | What it models |
|---|---|---|---|
| G-01 | wrong_arithmetic | code | Claims 310.00 where the script gives 300.00. |
| G-02 | wrong_arithmetic | code | Off by one cent: 299.99 against 300.00 is material, not rounding. |
| G-03 | wrong_arithmetic | code | Decimal slip: 30000.00 against 300.00. |
| G-04 | wrong_unit | code | Hours reported as minutes: right digits, wrong unit. |
| G-05 | wrong_unit | code | Claims USD where the script reports CAD. |
| G-06 | wrong_unit | code | Money text with the unit 'count'. |
| G-07 | stale_source | code | Terms dated 2025-01-10 cited in October 2026 (limit 400 days). |
| G-08 | stale_source | code | Price list dated 2024-06-30. |
| G-09 | stale_source | code | Knowledge record that expired on 2026-06-01. |
| G-10 | source_not_supporting | model-judged-replay | On-topic source, wrong figure: minimum order 24 vs 12. |
| G-11 | source_not_supporting | model-judged-replay | Off-topic source: shop hours cited for a supplier cutoff. |
| G-12 | source_not_supporting | model-judged-replay | Claim says all items; the policy covers unopened items only. |
| G-13 | source_not_supporting | code-after-judgment | The judge wrongly says yes; the code still catches the wrong number. |
| G-14 | source_not_supporting | code-after-judgment | The judge invents a quote that is not in the source. |
| G-15 | unsupported_inference | model-judged-replay | A forecast drawn from past Saturdays that the passage does not support. |
| G-16 | unsupported_inference | model-judged-replay | One average cited as proof that demand is stable (the support judge says yes, the adversarial reviewer catches it). |
| G-17 | cherry_picking | model-judged-replay | Quotes the two rising Saturdays and leaves out the third. |
| G-18 | double_counting | code | A total built from two claims that cite the same evidence location. |
| G-19 | double_counting | model-judged-replay | The script sums two rows that are the same store (the input says so). |
| G-20 | missing_evidence | code | A pending claim with no evidence at all. |
| G-21 | missing_evidence | code | A recommendation with no evidence. |
| G-22 | missing_evidence | code | A decision with no evidence. |
| G-23 | verified_without_evidence | code | Marked verified with an empty evidence list. |
| G-24 | verified_without_evidence | code | Marked verified but its own verification says fail. |
| G-25 | verified_without_evidence | code | Marked verified with no verification block at all. |
| G-26 | assumed_status | code | Status 'assumed' with no evidence (the example in contracts/). |
| G-27 | assumed_status | code | Status 'assumed' even though evidence is attached. |
| G-28 | malformed_row | code | A timestamp that is not a date (validate.py alone does not catch this). |
| G-29 | malformed_row | code | A number claim with no unit. |
| G-30 | malformed_row | code | The envelope lists a claim that has no ledger row. |
| G-31 | malformed_row | code | A retrieval time in the future. |
| G-32 | fabricated_source | code | Cites a document that does not exist. |
| G-33 | injection_in_evidence | code | A planted instruction inside the cited passage. |
| G-34 | self_verified | code | The producer marks its own wrong number verified; the Verifier ignores that. |
| G-C1 | control | control | Clean number: exact match. |
| G-C2 | control | control | Clean document claim. |
| G-C3 | control | control | Rounding only: 2.67 shown for a true 2.665 (rubric allows 2 decimals). |
| G-C4 | control | control | Two different quantities that happen to be equal, cited from different lines: no double counting. |
| G-C5 | control | control | Valid, unexpired knowledge record. |
| G-C6 | injection_ignored | control | Planted instruction in a different section from the cited one: flagged, ignored, claim still passes on its merits. |

## Adding a case
When the owner catches an error the Verifier missed, add a case with the owner's correction as the expected result
(synthetic stand-in data only; never paste the real figures). Do not remove or loosen a case to raise a rate.
