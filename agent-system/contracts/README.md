# Contracts

The shared interfaces between roles. Builder sessions run in parallel and cannot talk to each other, so these files are what keeps their work compatible. Read all of them before building. Builders may not edit them.

| File | Defines |
|---|---|
| [autonomy-matrix.md](autonomy-matrix.md) | Action classes R0 to R6, who approves each, the early-flag rule, standing approvals |
| [preflight-brief.md](preflight-brief.md) | The template for flagging any R2+ action at planning time |
| [skill-standard.md](skill-standard.md) | How every skill is laid out, written, evidenced, tested; the agent card |
| [claim-ledger.schema.json](claim-ledger.schema.json) | One claim plus its evidence and verification. No "assumed" status exists |
| [knowledge-record.schema.json](knowledge-record.schema.json) | One sourced fact, rule or decision in the knowledge base |
| [agent-envelope.schema.json](agent-envelope.schema.json) | The message one agent hands another; R2+ side effects must cite a Preflight Brief |
| [validate.py](validate.py) | Validates files against the schemas; `python3 validate.py` runs the bundled examples |
| [examples/](examples) | Valid and invalid examples. Names starting `<schema>.valid` must pass; `<schema>.invalid` must fail |

## Rules the schemas enforce

- A claim can be `verified` only with at least one evidence item and a passing verification.
- A `blocked` claim must say why.
- A side effect of class R2 or higher must carry a `preflight_id`.
- Trust grades are A, B, C or D. Knowledge records always carry a source, a trust grade and an expiry.

## Changing a contract

A builder who needs a change writes `agent-system/change-requests/NN-<role>-<topic>.md` (a new file, never an edit) stating what is needed, why, and which examples would change. The owner or the design session decides. Until a change is approved, build to the current contract and note the gap in your PR.
