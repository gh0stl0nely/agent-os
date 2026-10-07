# Agent roster

Thirteen roles, each mirroring a real human role. The **Chief of Staff** is the orchestrator and the only agent that talks to the owner. Every other agent's output passes the **Verifier**, and any side effect passes the **Guardian**.

How to read the three tables: Table A is who each agent is and what it can do. Table B is what it needs to know and use, and what that costs. Table C is how it runs, who it works with, and which model it uses and why.

Type column: **Orchestrator** = plans and delegates. **Gate** = checks others. **Workflow** = fixed pipeline with model reasoning at set steps. **Agent** = free-form research and judgment. Prefer Workflow wherever the steps are known.

## Table A: role, responsibility, skills

Each skill is its own unit (own prompt, own tests, own owner agent). "Existing" means a skill already present in the owner's Claude setup that should be wrapped with evidence and verification gates rather than rewritten.

| # | Agent | Human role it mirrors | Type | Responsibility | Skills (each its own) | Existing skills to wrap | Phase |
|---|---|---|---|---|---|---|---|
| 1 | **Chief of Staff** | Chief of staff | Orchestrator | Breaks goals into tasks, routes to specialists, enforces gates, tracks budget, builds the daily brief, triages escalations to keep review at or under 30 min | plan-and-route, gate-enforce, brief-builder, budget-watch, escalation-triage | none | 0 |
| 2 | **Verifier** | Internal auditor / QA | Gate | Independently checks every claim and number; blocks anything without evidence | claim-evidence-audit, recompute-in-code, source-check, adversarial-review, golden-set-calibration | reconciliation-verifier, financial-reviewer (as domain rubrics) | 0 |
| 3 | **Guardian** | Security and compliance officer | Gate | Classifies every planned action (read / reversible / irreversible / external / secrets), blocks unsafe ones early, vets third-party skills | risk-classify, preflight-brief, secrets-hygiene, rollback-plan, skill-vetting | none | 0 |
| 4 | **Librarian** | Research librarian / analyst | Agent | Owns the knowledge base: lookup, deep research, source grading, refresh of expiring facts | kb-lookup, deep-research, source-grading, distill-and-tag, refresh-expiring | deep-research | 0 |
| 5 | **Data Steward** | Data-quality analyst | Workflow | Validates sales, inventory and waste data before anyone uses it | schema-validate, anomaly-detect, lineage-log, cross-source-reconcile | daily-sales-report (as a data source) | 0 |
| 6 | **Operations Manager** | Shop operations and inventory manager | Workflow | The nightly ordering pipeline, inventory, waste review | forecast-demand, recommend-order, submit-order, inventory-reconcile, waste-review, backtest | item-ordering, staff-scheduler, menu-update | 1 |
| 7 | **Controller** | Fractional controller / CPA reviewer | Agent | Audits the accountant's statements against source documents; drafts precise queries back to the accountant | statement-audit, bank-card-reconciliation, cutoff-accrual-check, variance-analysis, accountant-query-drafter, evidence-pack | reconciliation-verifier, financial-reviewer, cogs-calculator, product-cost-manager | 1 |
| 8 | **CFO** | Fractional CFO | Agent | Cash runway, debt service, breakeven, scenario planning | 13-week-cash-forecast, debt-scenarios, unit-economics, runway-alert | cogs-calculator, product-cost-manager | 2 |
| 9 | **Tax and Household Strategist** | Tax accountant plus household financial planner | Agent | Researches legal ways to reduce taxable income, tracks deductions with evidence, keeps the deadline calendar, models household cash flow | tax-optimization-research, deduction-evidence-tracker, deadline-calendar, household-budget | none | 2 |
| 10 | **Growth Marketer** | Social media / marketing manager | Workflow | Content ideas, calendar, copy and performance review for the shop (detail deferred) | content-ideation, calendar-build, copywriting, performance-review | marketing:* skills, social-content-engine, the Threads poster | 3 |
| 11 | **Business Advisor** | Business advisor / mentor | Agent | KPIs, pricing and margin, product mix, competitor watch, readiness for a sale in about five years | kpi-dashboard, margin-and-pricing, competitor-scan, exit-readiness-score | cogs-calculator, product-cost-manager, daily-sales-report, marketing:competitive-brief | 3 |
| 12 | **AI Learning Coach** | Mentor / coach | Agent | Plan to become a top-tier AI agent engineer: curriculum, weekly digest, build challenges | curriculum-builder, weekly-ai-digest, paper-and-doc-summary, build-challenge, portfolio-tracker | none | 3 |
| 13 | **Venture Architect** | Product strategist / venture analyst | Agent | Maps where money flows in target industries and where the owner's tools and consulting fit; turns proven internal results into case studies | money-flow-mapping, opportunity-scoring, offer-design, case-study-builder, pilot-design | marketing:competitive-brief | 3 |

## Table B: context, deep knowledge sources, tools and cost

Trust grades: **A** primary (government, standards bodies, vendor documentation, the owner's own documents), **B** reputable secondary, **C** community, **D** unverified. Anything graded C or D must be confirmed against an A source before it supports a decision. Costs marked "verify" are expected to be free but their terms have not been checked.

| # | Context it needs | Deep-knowledge sources | Tools | Cost and whether it is justified |
|---|---|---|---|---|
| 1 | Goals, autonomy matrix, review cap, agent registry, budget state | Anthropic engineering guidance on agent patterns (A) | Calendar, approvals inbox (Notion), scheduled tasks, phone push | Within plan allowance. High justification: it is the single point of contact |
| 2 | Only the claim, its evidence and the rubric (never the producer's reasoning) | The primary source cited in each claim (A) | Python for recomputation | Free in tools; token cost is the main cost. Highest justification: it replaces the owner as checker |
| 3 | Action catalogue, permission matrix, secrets policy | OWASP Top 10 for LLM applications and OWASP Agentic Skills Top 10 (A) | Password manager so secrets stay human-held; GitHub secret scanning and push protection (verify availability) | Low or free. High justification |
| 4 | Topic list, expiry rules, source-trust list | Maintains the trust grade per domain | Web search and fetch, the private knowledge-base repo | Token cost only. High justification: stops repeated research |
| 5 | Data dictionary, known past data issues | The POS and supplier system documentation (A) | Python and pandas; read-only POS access | Free. High justification: the owner cannot verify data cleanliness by hand |
| 6 | Flavours and shelf life, supplier cutoff, lead time and minimums, order / sold / waste history, brain rules, standing approval rules | Environment Canada weather (A), City of Toronto events (A), Ontario public holidays (A), supplier terms (A), own history | Weather, events and holiday feeds (expected free; verify terms); supplier portal access (see Open decisions) | Expected near zero. Very high justification: daily recurring task with a hard deadline |
| 7 | The accountant's example statements, chart of accounts, bank and card statements, invoices, prior findings | CPA Canada guidance on the applicable standards (A; confirm which standard the corporation uses and how to access it), CRA guidance (A), the accountant's own working papers (A) | The books system (confirm which), Drive, Python | Depends on the books system already paid for. Very high justification |
| 8 | Debt terms and balances, runway target, projections (private store only) | Lender agreements (A), Bank of Canada rates (A), BDC guides (B) | Python, spreadsheets | Free. High justification: debt service is the cash drain |
| 9 | Household and corporate tax position, registered-account room, deadlines (private store only) | CRA (canada.ca), Income Tax Act, Ontario Ministry of Finance (all A) | The owner's own CRA access, human-only; agent reads exports | Free. One paid CPA consult may be justified for final sign-off; the agent will flag it with reasoning. Not a licensed advisor |
| 10 | Brand voice, approved assets, asset expiry dates, past post results | Official platform documentation (A) | The existing Threads poster, Typefully connector, Canva connector | Cost of any paid scheduling tool to be justified later |
| 11 | KPIs and financials from agents 5-8 | BDC (B), Statistics Canada (A), industry benchmarks (B) | Dashboards, spreadsheets | Free. High justification: keeps the sale goal measurable |
| 12 | Current skill level, goals, projects | Anthropic docs and engineering blog (A), arXiv (B for claims) | Reading list, a sandbox repo | Free |
| 13 | Owner's skills, target industries, internal proof metrics | Payments Canada, Bank of Canada, BIS, Stripe documentation (A), industry reports (B) | Web research | Free. Strategic justification only after the foundation proves results |

## Table C: automation, collaboration, model choice

Model policy, from the Pro plan facts: Pro usage is shared across Claude and Claude Code with a five-hour session limit and a weekly cap, and Pro does not include API usage. So: **Sonnet 5.5 is the default**; **Opus 5.5** only for the Verifier on high-stakes work and for weekly or monthly strategic reviews; **Haiku 4.5** for high-volume checks and tagging. Heavy work goes into scripts. Model availability on your plan is unverified; confirm in the model picker. If Opus is unavailable, keep Sonnet and add a second review pass plus stricter deterministic checks.

| # | Automation | Works with | Model | Why |
|---|---|---|---|---|
| 1 | Daily brief at about 6:00am; event-driven triggers; weekly review | Everyone; the only agent that messages the owner | Sonnet 5.5 daily; Opus 5.5 for weekly planning and conflicting priorities | Daily routing is routine; weekly planning weighs trade-offs |
| 2 | Runs automatically after every producer output | All producers; reports to 1 | Opus 5.5 for financial, tax and cash claims; Sonnet 5.5 for routine | A weaker checker misses errors a stronger producer makes; deterministic checks run first either way |
| 3 | Runs at planning time for any task with side effects | 1, 2 and the agent that planned the action | Sonnet 5.5; Opus 5.5 for novel high-risk cases | Rule-based classification, run often |
| 4 | On demand; nightly expiry refresh; weekly topic scans | Feeds all | Sonnet 5.5 for research; Haiku 4.5 for tagging | Research needs judgment; tagging is mechanical |
| 5 | Before every pipeline (about 6:30pm) and nightly | 6, 7, 8 | Haiku 4.5 | Code does the work; the model only explains flagged items |
| 6 | Data check about 6:30pm, forecast about 6:50, recommendation about 7:10, push to owner about 7:15, answer due 7:30, nudge 7:40, submit by 7:45 (supplier cutoff 8:00). Weekly backtest | 5, 4, 2, 3, 1 | Sonnet 5.5, with the Verifier on top | Forecast math is code; the model gathers context and explains reasoning |
| 7 | Triggered when the accountant delivers statements; weekly spot checks | 5, 2, 8 | Opus 5.5 for the monthly audit; Sonnet 5.5 for routine reconciliation | Audit judgment across many documents is high-stakes |
| 8 | Weekly forecast; monthly review; runway alert on threshold | 7, 11 | Sonnet 5.5 weekly; Opus 5.5 monthly | Cash decisions are consequential but the math is code |
| 9 | Monthly; quarterly installment reminders; year-end sprint beginning in autumn | 7, 8, 2 | Opus 5.5 for annual planning; Sonnet 5.5 for deadline monitoring | Rule-heavy and high-stakes; always flag for CPA confirmation |
| 10 | Weekly planning; daily posting via the existing poster | 11, 2, 3 | Sonnet 5.5 | Creative drafting at volume |
| 11 | Monthly review; quarterly strategy | 7, 8, 10, 13 | Sonnet 5.5 monthly; Opus 5.5 quarterly | Strategy synthesis is occasional |
| 12 | Weekly digest; monthly project | 4 | Sonnet 5.5 | Summarization and planning |
| 13 | Biweekly scan; project-based sessions | 4, 11, 12 | Sonnet 5.5 for research; Opus 5.5 for strategy sessions | Occasional, high-leverage thinking |

## Collaboration rules

- Specialists never message the owner. They hand work to the Chief of Staff, who batches it.
- Producer output goes to the Verifier before it is reported. At most two revise loops, then escalation with exactly what evidence is missing.
- Any delete, edit, secret handling, spend, or public/client-facing action gets a Guardian Preflight Brief at planning time.
- Every agent checks the Librarian's knowledge base before researching, and writes new findings back with a source, date, expiry and trust grade.
- Costs above the plan allowance are never incurred silently: the Chief of Staff flags the purpose, the expected cost and whether it is justified.

## Success metrics (the proof for future clients)

| Metric | Target |
|---|---|
| Forecast error per flavour versus a naive baseline | Beat the baseline, tracked weekly |
| Share of claims with evidence | 100% |
| Audit findings the Controller catches that the accountant did not | Tracked monthly |
| Daily owner review time | 30 minutes or less |
| Re-research rate for facts already in the knowledge base | Trending to zero |
| Verifier catch rate on a seeded golden set | Reviewed monthly |
