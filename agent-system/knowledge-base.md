# Knowledge base, retrieval and the learning loop

Goal: agents use recorded knowledge when it is current, research when it is missing or stale, and never repeat research they have already done.

## 1. Where things live

This repo is public, so storage is split.

| Kind | Examples | Where |
|---|---|---|
| Public-safe | Design docs, agent prompts and procedures without numbers, summaries of public rules (CRA, holidays) with source links | This repo, under `knowledge/` |
| Private | Financial statements, bank or card data, debt terms, runway, tax position, supplier prices, order history, claim ledger rows that contain business numbers | A **private repo** (recommended: versioned, diffable, plain files) |
| Human inbox | Approval requests, the daily brief | Notion, holding no sensitive details beyond what the decision needs |
| Never stored anywhere agents read | Passwords, API keys, tokens | Password manager and GitHub Actions secrets only |

## 2. Memory tiers

Adapted from published agent-memory design guidance ([source](https://hidekazu-konishi.com/entry/ai_agent_memory_design_guide.html)).

| Tier | What it holds | Lifetime | Concrete form |
|---|---|---|---|
| Working | The current task, plan, recent results | One run, pruned aggressively | The agent's context |
| Episodic | What happened: run logs, order decisions, audit sessions | Short; expires first | `episodes/` log files with an `expires_at` |
| Semantic | Verified facts and preferences | Long, but subject to staleness checks and supersession | `facts/` records (schema below) |
| Procedural | Brain rules, playbooks, skills, regression cases | Versioned, never auto-deleted | `procedures/` and the skills themselves |

## 3. Record schema

Every semantic record is a small file with front matter:

| Field | Purpose |
|---|---|
| `id` | Stable identifier other records and the ledger cite |
| `type` | fact, preference, rule, decision |
| `namespace` | Isolation per agent or domain (tax, ordering, audit) so each agent loads only what it needs |
| `claim` | The statement, in our own words |
| `source` | URL or document id, plus where in it, and `retrieved_at` |
| `trust_grade` | A primary, B reputable secondary, C community, D unverified |
| `confidence` | How sure, and whether stated by the owner or inferred |
| `written_at`, `last_confirmed_at`, `expires_at` | Freshness |
| `supersedes` | The id this record replaces, so updates chain instead of duplicating |
| `status` | verified, blocked (assumed or unevidenced), or retired |
| `owner_agent` | Who maintains it |

Store paraphrases and pointers, not copied passages.

## 4. Retrieval policy: memory first, research if stale

Flow chart: see diagram 4 in [architecture.md](architecture.md).

1. Search the knowledge base for the topic first.
2. If a record exists and is fresh, and the action is low stakes, use it and cite the record id.
3. If it is stale, or the action is consequential (money, tax, anything customer-facing), re-check the source before using it.
4. If the source changed or nothing exists, research primary sources (grade A first).
5. Pass the write gate (below), save the result, and chain it to what it replaces.

Proposed default lifetimes, to be tuned per domain:

| Domain | Re-verify |
|---|---|
| Weather and events | Every run |
| Supplier terms and prices | At each order |
| Tax rules and deadlines | Before any consequential use, and at year-end |
| Public holidays | Annually |
| AI tooling and news | About monthly |

## 5. Do we need RAG yet?

Not at the start. Anthropic's guidance on Contextual Retrieval says that a knowledge base under about 200,000 tokens (roughly 500 pages) can be placed directly in the prompt, with prompt caching to keep it cheap, and needs no retrieval system ([source](https://anthropic.com/news/contextual-retrieval)). The namespaces above keep each agent's load small.

Upgrade path, triggered when the base outgrows that size or when logged retrieval misses show up:

| Step | Reported effect on retrieval failures (same source) |
|---|---|
| Contextual embeddings (prepend explanatory context to each chunk before embedding) | 5.7% down to 3.7% |
| Plus contextual BM25 keyword search | down to 2.9% |
| Plus reranking | down to 1.9% |

The same source reports that retrieving 20 chunks beat 5 or 10. Measure on our own questions before adopting any of this.

## 6. Write gate

A fact is written only if it:
- cites a source (no source means status `blocked`),
- contains no secrets or unnecessary personal data,
- is not a duplicate (near-duplicates become updates with `supersedes`),
- has a trust grade, and
- is durable (transient details stay in the episodic tier).

## 7. Verification design

Research on LLM judges reports several weaknesses: self-preference when a model judges its own family, bias toward longer answers, position bias, calibration drift, and invented rationales ([source](https://zylos.ai/research/2026-04-10-llm-as-judge-production-agent-verification-2026/)). Mitigations used here:

- **External evidence first.** Recompute numbers in code, confirm the cited source exists and says what is claimed, then use the model for judgment.
- **Rubrics** that include conciseness as a scored item, and structured output with reasoning before the verdict.
- **Order-swap double evaluation** when comparing alternatives.
- **Golden set**: seeded known errors, run monthly to calibrate the Verifier against known answers.
- **Bounded loops**: at most two revisions, then escalate to the owner with exactly what is missing.
- **Same-family limit.** Cross-family judging is the standard fix but needs a second provider and API access, which is outside a Pro-only setup. The Chief of Staff would flag any such spend with reasoning before it happens.

## 8. Learning loop

1. The owner corrects an output.
2. The correction becomes a **brain rule** (procedural memory) and a **regression case** (an input with the expected output).
3. Regression cases replay before relevant runs and in weekly backtests.
4. Metrics are logged per agent (see [roster.md](roster.md)).
5. Changing a brain rule or prompt is a "modify" action, so the Guardian produces a Preflight Brief first and the change is versioned.

Example for ordering: "Slightly off per flavour" becomes a backtest. Replay past weeks, record the error per flavour, then learn which signal (weekday, weather, holiday, event, flavour history) improves it.

## 9. Sources used

- Anthropic, Contextual Retrieval: https://anthropic.com/news/contextual-retrieval
- Anthropic, Building effective agents: https://www.anthropic.com/engineering/building-effective-agents
- AI agent memory design guide: https://hidekazu-konishi.com/entry/ai_agent_memory_design_guide.html
- LLM-as-judge in production: https://zylos.ai/research/2026-04-10-llm-as-judge-production-agent-verification-2026/
