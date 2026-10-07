# Change request: contract gaps found by the Verifier build (role 02)

**From:** builder session for role 02 Verifier, branch `build/02-verifier`
**Touches shared files:** `agent-system/contracts/validate.py`, `claim-ledger.schema.json`, `agent-envelope.schema.json`, `README.md` (contracts). I did not edit any of them.
**Priority:** 1 is a correctness gap that affects every role; 2 and 3 are conveniences the Verifier works around today.

## 1. `validate.py` does not check `date-time` fields unless an optional package is installed

**What happens.** `validate.py` builds its validator with `FormatChecker()`. The `date-time` format is only enforced when the optional package `rfc3339-validator` is installed. Without it, any string passes. Reproduce:

```
python3 - <<'PY'
import json, tempfile, subprocess
row = {"claim_id": "C-x", "run_id": "r", "agent": "a", "claim": "c", "kind": "fact",
       "evidence": [{"type": "document", "ref": "x", "retrieved_at": "not a date"}],
       "status": "pending", "created_at": "garbage"}
f = tempfile.mktemp(suffix=".json"); json.dump(row, open(f, "w"))
print(subprocess.run(["python3", "agent-system/contracts/validate.py", "claim-ledger", f], capture_output=True, text=True).stdout)
PY
```

Prints `object 1: ok`. A producer can therefore hand over a ledger with unparseable or future-dated timestamps, and "is this source current?" depends on those dates.

**Why it matters.** Source freshness and "retrieved before it was claimed" checks cannot be trusted if the dates are not dates.

**Interim fix in this PR.** The Verifier's own structure check (`structure_check.py`) parses every timestamp strictly (RFC 3339) and rejects bad or future ones (`BAD_TIMESTAMP`, `FUTURE_TIMESTAMP`). It does not import or modify the contract validator beyond calling it by path. I did not `pip install` anything.

**Requested change (pick one).**
- (a) Add `rfc3339-validator` to the repo's install notes and CI, and make `validate.py` exit with an error if it is missing (so a missing package cannot silently weaken the gate); or
- (b) add a small strict RFC 3339 check inside `validate.py` itself, with an `invalid-bad-timestamp` example.

## 2. Computation evidence cannot carry the input hashes the recompute check needs

**What happens.** To trust a re-run, the Verifier needs to know exactly which input files the producer's script was given, and their hash, so it can detect an input that changed afterwards. The `evidence` object has `additionalProperties: false` and only `type`, `ref`, `locator`, `retrieved_at`, `script`. There is nowhere to put the inputs.

**Interim fix in this PR.** The producer hands over a separate spec file per claim (`{claim_id, script, args, inputs: [{path, sha256}], timeout_s}`), described in `.claude/skills/recompute-in-code/SKILL.md`. A number claim without a spec is reported `unverifiable: no_spec`; one with unlogged inputs is `unverifiable: inputs_not_logged`.

**Requested change.** Add to the `evidence` definition, for `type: computation`, optional `args` (array of strings) and `inputs` (array of `{path, sha256}`), so the spec travels inside the ledger row and cannot get separated from the claim.

## 3. The envelope has no field for per-claim results

**What happens.** A result envelope can say `status` and list `claims`, but not which claims passed or failed. The Verifier returns the checked rows (with `status`, `verification`) as a separate ledger file and writes a full report; the envelope's `inputs` points at the report as `audit-report://<task_id>`.

**Requested change.** Add an optional `verdicts` array to the envelope: `[{claim_id, result: pass|fail|unverifiable, reason_code}]`. That lets the Chief of Staff route work without opening a second file.

## 4. Notes (no change requested; for the Chief of Staff and the Knowledge Steward)

- **Knowledge-record files are assumed to be JSON files** under `knowledge/<namespace>/K-<namespace>-NNNN.json`, as the schema and the examples suggest (`knowledge-base.md` does not fix a file layout). `source-check` finds a `kb_record` by globbing `knowledge/**/<id>.json` under its root, validates it against `knowledge-record.schema.json`, and treats a record that is not `verified` or is past `expires_at` as outdated. If the Knowledge Steward stores records differently, tell the Verifier role.
- **Rubric shape.** `agents/02-verifier/rubrics/_SHAPE.md` defines the fixed shape domain roles supply. If the Controller or CFO need a field it lacks (for example per-currency tolerances), they should ask through this folder.
- **Revision routing.** Every output envelope is addressed to `01-chief-of-staff`, as the brief says. `audit.py --revision-to producer` addresses revisions to the producer instead. See `agents/02-verifier/QUESTIONS.md` (question 3).

## 5. A compiled Python cache is tracked on `main` (suggestion only; not changed)

`scripts/__pycache__/post_threads.cpython-313.pyc` is tracked on `main`. That folder belongs to the live Threads poster, not the Verifier. An earlier commit on this branch deleted it by accident while untracking the Verifier's own Python caches; the PR #1 review caught that, and it is restored byte for byte. Whether it should stay tracked is the poster's maintainer's decision. If not: `git rm --cached scripts/__pycache__/post_threads.cpython-313.pyc` plus a `__pycache__/` line in the root `.gitignore` (a shared file). The Verifier's own folders ignore their caches with local `.gitignore` files. `agents/02-verifier/check_scope.py` now fails any branch of this role that deletes or modifies a file outside its lane.
