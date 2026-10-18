# Knowledge and memory rules

Agents use recorded knowledge when it is current, research when it is missing or stale, and never repeat research already done.

## Where things live

| Kind | Examples | Where |
|---|---|---|
| Public-safe | Procedures without numbers, summaries of public rules (CRA, holidays) with source links | `knowledge/` in this repo |
| Private | Statements, bank or card data, debt terms, runway, tax position, supplier prices, order history, claim rows with business numbers | The private store |
| Learned per role | What worked, what the owner rejected and why | Each role's memory (private) |
| Never stored where agents read | Passwords, API keys, tokens | Password manager and GitHub Actions secrets only |

## Memory tiers

| Tier | Holds | Lifetime |
|---|---|---|
| Working | The current task and recent results | One run |
| Episodic | Run logs, order decisions, audit sessions | Short; expires first |
| Semantic | Verified facts and preferences (`knowledge/` records) | Long, with expiry and supersession |
| Procedural | Playbooks, skills, regression cases | Versioned in git |

## Knowledge records
One JSON file per record at `knowledge/<namespace>/K-<namespace>-NNNN.json`, valid against `contracts/knowledge-record.schema.json`. Each record carries a source with `retrieved_at`, a trust grade (A primary, B reputable secondary, C community, D unverified), confidence, `expires_at`, `supersedes` when it replaces another record, and `status` (`verified`, `blocked`, `retired`). Store paraphrases and pointers, not copied passages. Anything graded C or D must be confirmed against an A source before it supports a decision.

## Retrieval: memory first, research if stale
1. Search `knowledge/` for the topic.
2. Fresh record and a low-stakes action: use it and cite its id.
3. Stale record, or a consequential action (money, tax, anything customer-facing): re-check the source first.
4. Nothing usable: research primary sources first.
5. Write the result back through the write gate and chain it to what it replaces.

Default re-verify intervals: weather and events every run; supplier terms and prices at each order; tax rules before any consequential use and at year-end; public holidays annually; AI tooling about monthly.

## Write gate
A record is written only if it cites a source, contains no secrets or unneeded personal data, is not a duplicate (near-duplicates become updates with `supersedes`), has a trust grade, and is durable (transient details stay in run logs).

## Retrieval scale
No vector search to start: Anthropic's guidance is that a knowledge base under about 200,000 tokens can go straight into the prompt with caching ([source](https://anthropic.com/news/contextual-retrieval)). Revisit when the base outgrows that or retrieval misses show up in logs.

## Learning loop
1. The owner corrects an output.
2. The correction becomes a rule (in the role's playbook or skill) and an eval case with the expected output.
3. Eval cases replay in CI and in the role's backtests.
4. Changing a shared rule or a definition is R2: it goes through a pull request.
