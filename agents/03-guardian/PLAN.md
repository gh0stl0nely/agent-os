# Plan: 03 Guardian

Written 2026-10-07 before any skill was built. Base commit of this repo when planning: `7633838`.

## Mission, in my own words

Guardian is a gate that runs at planning time, never at execution time. When any agent plans an action, Guardian does five jobs:

1. Gives the action a class (R0 to R6) and cites the matrix rule behind it. Unsure means the higher class.
2. For R2 and above, turns the plan into a complete Preflight Brief. It refuses to complete one that cites a claim without a Verifier pass.
3. Checks every plan, diff and file for secrets and tells the owner, step by step, how to store them safely. It never touches a secret value.
4. For R2 and above, writes a rollback plan with a test step, and flags any rollback that cannot be tested.
5. Reviews any third-party skill against the OWASP Agentic Skills Top 10 before it is installed, and records it in an inventory pinned to a commit SHA.

Guardian never approves anything. It prepares the brief; the owner decides. It also ships proposals the owner can install (hooks, a GitHub settings checklist). Installing or changing settings is the owner's R2 action, not Guardian's.

## Assumptions

- The class table in `contracts/autonomy-matrix.md` is complete and final. Where an action fits two rows, the higher class wins (that is the matrix's own tie-break rule).
- "Never rounds down" means: on any fixture the classifier output is greater than or equal to the expected class, and for the fixtures marked ambiguous it must equal the expected class.
- Scanning is done by a stdlib-only Python script, so it adds no dependency and no supply-chain risk, and it runs in CI and in hooks without installs. The contract validator needs `jsonschema`, which is already a stated requirement of `validate.py`.
- Skills here are instructions plus scripts. The classifier and scanner scripts are the source of truth for the class and for findings; the model explains and handles cases the script flags as ambiguous.
- Hooks are proposals. They can only be tested here with simulated hook input (JSON on stdin) and temporary git repositories.
- The repo's owner is a personal GitHub account (`gh0stl0nely`), not an organization. That matters for which bypass options exist, and it must be verified before the checklist claims anything.

## Reusable work looked at

| Item | Looked at | Decision | Pin |
|---|---|---|---|
| `agent-system/contracts/*` and `reusable-skills.md` install policy | Read in full | **Adopt** as the spec. Guardian builds to them and changes none | repo `7633838` |
| OWASP Top 10 for LLM Applications (2025 list, LLM01 to LLM10) | Page read 2026-10-07 | **Adopt** as a checklist source for `risk-classify` reasoning and the adversarial evals | web page, no SHA |
| OWASP Agentic Skills Top 10 (AST01 to AST10, v1.0 2026 edition) | Page read 2026-10-07 | **Adopt** as the checklist for `skill-vetting`. Each item becomes one named check with pass or fail evidence | web page, no SHA |
| `anthropics/skills`, `obra/superpowers`, awesome lists, `loki-mode` | Only what `reusable-skills.md` states | **Reject** for this role. No overlap with the five skills, and nothing was installed or run | none |
| Third-party secret scanners (for example gitleaks) | Not examined | **Reject for now**: a stdlib script keeps the dependency count at zero. Revisit if the pattern list proves too thin; any adoption goes through `skill-vetting` | none |

No SHA exists for web pages. If a later step clones a third-party repo, its SHA goes in `agents/03-guardian/skill-inventory.md`.

## Risks

| Risk | Mitigation |
|---|---|
| Committing a token-like string by accident while building the secrets tests | Seeded fake secrets are built at test time from fragments; no token-shaped literal is committed. The scanner's own pattern file is the one place that holds patterns, and it holds regular expressions, not secrets. Self-scan the diff before every commit |
| Scanner flags the contract examples (acceptance criterion 3) | Run the scanner over `contracts/examples/` in the test suite; it must report zero findings |
| Classifier rounds down on a phrasing it has not seen | Default class is R2 when no rule matches with confidence; keyword rules are checked from the highest class downward; fixtures include ambiguous and adversarial phrasings |
| A planned action's description contains a hidden instruction (criterion 8) | The classifier treats the description as data: it detects instruction-like text, ignores it for classification, and flags it. The flag never lowers a class |
| Branch protection on `main` breaks the daily poster, which commits `bloor-assets/state.json` to `main` | Research the bypass options for a personal repo first. Test the mechanics of the safe option locally. Do not edit the poster's workflow; propose the change as a separate owner-approved R2 step |
| Free-tier limits on a private repo (secret scanning and push protection are paid features there) | Verify against GitHub's docs and state it. This repo is public, so say what applies to public and what would change if the repo went private |
| Hooks block legitimate work or are bypassed by a different tool name | Tests include allowed commands; document hooks as a second layer, not the only one |
| Over-building | Keep each skill to the brief's table. No extra roles, no extra skills |

## Skills to build, in order

1. `risk-classify` (everything else depends on classes). Script: `classify.py`. Fixture list of 30+ actions.
2. `secrets-hygiene`. Script: `scan_secrets.py`. Tests build seeded fakes at run time.
3. `preflight-brief`. Script: `check_brief.py`, checks completeness and requires Verifier passes on cited claim ids.
4. `rollback-plan`. Script: `check_rollback.py`, flags a plan with no test step or a test that cannot run.
5. `skill-vetting`. Script: `vet_skill.py`, reads every file in a skill folder and returns pass or fail per AST item. Includes a sample skill with a hidden malicious instruction.

Then the deliverables beyond skills: hooks with tests, the owner setup checklist, the skill inventory format and first entries, the knowledge records under `knowledge/security/`, `EVAL-REPORT.md`, `CARD.md`.

## Questions for the owner

Kept in `QUESTIONS.md`. The two from the brief (how approvals are delivered and batched; which routine actions a standing approval could safely cover), plus anything the research turns up that is not in the repo.
