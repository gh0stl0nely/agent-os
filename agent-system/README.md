# Agent system: design

Status: **design stage** (written 2026-10-07). Nothing here is built yet except the Threads poster that already lives in `bloor-assets/` and `scripts/`.

This folder is the shared blueprint for a team of specialized AI agents, each mirroring a real human role, that run a small business and a household with as little manual work as possible and with proof behind every decision.

| File | What it answers |
|---|---|
| [roster.md](roster.md) | Who the 13 agents are: role, skills, context, knowledge sources, tools and cost, automation, collaboration, model choice |
| [architecture.md](architecture.md) | How they connect: system map, verification gate, nightly ordering timeline, knowledge lookup, execution layers (all diagrams render on GitHub) |
| [knowledge-base.md](knowledge-base.md) | Memory, retrieval (RAG), freshness rules, and the learning loop |
| [reusable-skills.md](reusable-skills.md) | Existing GitHub skill repos worth reusing, with license, trust verdict, and install rules |

## The problem this design solves

The existing skills produce answers with no evidence trail, no verification gate, and shallow research. The owner ends up as the human verifier, spelling out reasoning the AI should have produced. So the foundation is not "more agents". It is:

1. A **Verifier** that checks every claim against evidence before anything reaches the owner.
2. A **claim-evidence ledger**: every decision records what was concluded, from which source, when, and how it was checked.
3. A **Librarian** that checks stored knowledge first and researches only when knowledge is missing or stale.
4. A **Guardian** that plans side-effecting actions early and flags them before anything runs.
5. Scheduled, hands-off runs, with the owner reviewing at most 30 minutes a day.

## Design principles

- **Workflows before agents.** Where the steps are known (the nightly order), use a fixed pipeline with reasoning at defined steps. Use free-roaming agents only where the path is unpredictable. (Anthropic's guidance: start simple, add complexity only when measurement shows it helps.)
- **Compute with code, reason with the model.** Forecast math, reconciliations and tax arithmetic run as scripts and are logged. The model researches, judges and explains.
- **No claim without evidence.** "Assumed" is a blocked status. If evidence is missing, the agent escalates with exactly what is missing.
- **Escalate early, never mid-action.** Deleting, editing, handling secrets, spending, or anything customer-facing gets a Preflight Brief (what, why, evidence, rollback, risk) at planning time.
- **Memory first, research if stale.** Every stored fact carries a source, date, expiry and trust grade.
- **Every correction becomes a rule and a test.** Corrections turn into a brain rule plus a regression case replayed on later runs.
- **Prove it on ourselves first.** Backtests and audit logs give each agent a measurable track record. That record is the evidence needed before offering any of this to other businesses.

## Phases

| Phase | Agents | Why this order |
|---|---|---|
| 0 Foundation | Chief of Staff, Verifier, Guardian, Librarian, Data Steward | Everything else depends on gates, memory and clean data |
| 1 Sharpest pains | Operations Manager (7:30pm order), Controller (audit the accountant) | Daily manual work and the biggest verification burden |
| 2 Money | CFO, Tax and Household Strategist | Cash protection; tax year-end has a Dec 31 clock |
| 3 Growth | Growth Marketer, Business Advisor, AI Learning Coach, Venture Architect | Valuable, but they rely on the foundation and on data from phases 1-2 |

Time-sensitive: tax planning has a December 31 deadline for many moves. The Librarian can start the tax research pass during Phase 0, before the Tax agent is automated.

## Changes from the earlier chat proposal

These come from checking facts after the first draft:

1. **Knowledge base moves out of Notion-only.** This repo is **public**, so financial or personal data cannot live here. Recommended: a **private repo** for the knowledge base and ledger (versioned, diffable, agents read plain files), with Notion kept only as the human-facing approvals inbox. See [knowledge-base.md](knowledge-base.md).
2. **No vector database at the start.** Anthropic's guidance is that a knowledge base under about 200,000 tokens can go straight into the prompt (with prompt caching). Retrieval upgrades come later, triggered by size or measured misses.
3. **The Verifier is not enough on its own.** Research on LLM judges reports self-preference bias when a model checks its own model family. Mitigation: deterministic checks (recompute in code, confirm the source exists) run before any model-based review. See [knowledge-base.md](knowledge-base.md).
4. **Model usage is rebalanced.** Claude Pro limits are shared across Claude and Claude Code, with a five-hour session limit and a weekly cap, and Pro does not include API usage. Default to Sonnet 5.5; use Opus 5.5 only where stakes justify it; push heavy lifting into scripts that cost no tokens. See [roster.md](roster.md).
5. **Order submission is an open decision.** The supplier portal is password-gated, and agents are not allowed to type passwords. See Open decisions below.

## Already built (keep and reuse)

The Threads auto-poster in `bloor-assets/`, `scripts/post_threads.py` and `.github/workflows/daily-post.yml` already follows several of these principles: a pause switch, per-file expiry in `manifest.json`, the access token held as a GitHub Actions secret, and a guard against posting twice in a day. It becomes the executor for the Growth Marketer, with the Guardian reviewing anything new before it is queued.

## Open decisions (owner input needed)

1. **Private store.** Create a private repo (recommended) for the knowledge base and ledger, or use Notion only?
2. **Order submission at 7:45pm.** Options: (A) the agent prepares the exact order and a cart link, and you tap to submit; (B) the agent drives your already-signed-in browser, which requires that browser to be running and you to have logged in yourself; (C) ask the supplier whether they accept orders by email or another channel. Also decide the fallback if you have not answered by 7:45.
3. **Where each job runs.** Deterministic steps (data pulls, math, posting) can run free on GitHub Actions as the poster does today. Reasoning steps need Claude scheduled tasks and use Pro allowance. Whether scheduled tasks are included on your plan is unverified.
4. **Notifications.** Phone push for the 7:15 and 7:40 order prompts, plus an optional high-priority channel.
5. **Books.** Which system holds the shop's books, and in what format does the accountant deliver statements?
6. **Models.** Confirm in the model picker which models your plan actually offers.

## What must never be committed here

Secrets, tokens, passwords, financial statements, bank or card data, tax filings, income figures, debt terms, runway numbers, supplier prices or order history, staff personal data, health or family data. This repo is public; those belong in the private store.
