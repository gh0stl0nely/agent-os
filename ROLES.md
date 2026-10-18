# Roles

Every role we plan to build, in build order. A role is built when it has a definition in `.claude/agents/<id>.md`; from then on, that file is the source of truth and the entry here stays short.

Statuses: `planned` (not started), `building`, `active`, `paused`, `retired`. `python3 contracts/check_roles.py` checks that this list and the definitions agree.

| Order | Role | Status | Owner pain it removes |
|---|---|---|---|
| 1 | [verifier](#verifier) | active | Owner acting as the human checker of AI output |
| 2 | [operations-manager](#operations-manager) | planned | 1. Nightly order is "slightly off" per flavour |
| 3 | [growth-marketer](#growth-marketer) | planned | 4. Deciding what to post and posting it |
| 4 | [controller](#controller) | planned | 2. Verifying the accountant's statements by hand |
| 5 | [tax-household-strategist](#tax-household-strategist) | planned | 5. Tax and household finances (Dec 31 deadline) |
| 6 | [cfo](#cfo) | planned | 5. Cash runway and debt service |
| 7 | [video-editor](#video-editor) | planned | 4. Turning footage into reels |
| 8 | [chief-of-staff](#chief-of-staff) | planned | Review time under 30 min/day once 3+ roles run |
| 9 | [business-advisor](#business-advisor) | planned | KPIs, pricing and margin |
| 10 | [ai-learning-coach](#ai-learning-coach) | planned | 6. Learning to use AI agents for business impact |
| 11 | [venture-architect](#venture-architect) | planned | Long-term venture goals |

Fields: **Trigger** (what starts it), **Runs on** (`cloud` = Claude scheduled task, `server` = an always-on machine with its own tools, `local-device` = the owner's computer), **Can call** (roles it may invoke directly), **Connectors** (MCP servers it may use), **Skills** (planned; existing ones in the owner's Claude account to wrap are marked "wraps"), **External** (third-party repos, pinned and vetted per `shared/external-resources.md`), **Autonomy max** (highest action class it takes without the owner's yes), **Done when** (how a run is judged).

Models: Sonnet by default, Opus where stated, Haiku for high-volume mechanical checks. A caller can request Opus for a single high-stakes call.

---

### verifier
- **Status:** active
- **Mission:** Independently check every claim and number against its evidence before anything reaches the owner. Never fixes the producer's work; never passes what it could not check.
- **Trigger:** called by other roles after they produce numbers, facts or recommendations.
- **Runs on:** wherever the caller runs (scripts need Python and `jsonschema` only).
- **Model:** Sonnet; Opus for finance, tax, cash and customer-facing claims.
- **Can call:** none. Gates never call producers.
- **Skills:** claim-evidence-audit, recompute-in-code, source-check, adversarial-review, golden-set-calibration.
- **Autonomy max:** R1.
- **Done when:** every claim is verified, blocked with a reason, or escalated with the missing evidence named.
- **Definition:** `.claude/agents/verifier.md`

### operations-manager
- **Status:** planned (next)
- **Mission:** Prepare tonight's supplier order per flavour, with evidence for every quantity.
- **Trigger:** daily. Data check 18:30, forecast 18:50, recommendation 19:10, to the owner 19:15, answer due 19:30, nudge 19:40, submit by 19:45 (supplier cutoff 20:00, Toronto time). Weekly backtest.
- **Runs on:** cloud.
- **Model:** Sonnet. Forecast math is code.
- **Can call:** verifier.
- **Connectors:** Square (read), Notion (read: inventory).
- **Skills:** forecast-demand, recommend-order, inventory-reconcile, waste-review, backtest; wraps item-ordering. Data validation runs as scripts inside the pipeline.
- **External:** Environment Canada weather, City of Toronto events, Ontario holidays (terms to verify).
- **Autonomy max:** R1, prepare only. Submitting the order is R4: the owner submits, or a standing approval covers it.
- **Open decision:** how the order reaches the supplier (prepared cart link, signed-in browser, or another channel) and the fallback at 19:45.
- **Done when:** a verified order with per-flavour quantity and reasoning reaches the owner by 19:15, and forecast error beats a naive baseline in the weekly backtest.

### growth-marketer
- **Status:** planned
- **Mission:** Plan and write the shop's social posts in the owner's voice and keep the Threads queue filled.
- **Trigger:** weekly planning; the existing poster publishes daily at 11:00.
- **Runs on:** cloud.
- **Model:** Sonnet.
- **Can call:** verifier (facts in posts: flavours, dates, prices).
- **Connectors:** Typefully, Canva.
- **Skills:** content-ideation, copywriting, performance-review; wraps social-poster and the caption rules in `bloor-assets/README.md`.
- **External:** charlie947/social-media-skills (MIT; not yet vetted).
- **Autonomy max:** R1 for drafts. Queued posts publish automatically, so changing the queue is R4: the owner approves each batch.
- **Done when:** the queue covers the next 14 days and every post passes the caption rules and uses only facts from current graphics or the menu.

### controller
- **Status:** planned
- **Mission:** Audit the accountant's monthly statements against source documents and draft precise questions back to the accountant.
- **Trigger:** when statements arrive; weekly spot checks.
- **Runs on:** cloud.
- **Model:** Opus for the monthly audit; Sonnet for routine reconciliation.
- **Can call:** verifier.
- **Connectors:** QuickBooks (read), Google Drive (read), Gmail (read).
- **Skills:** statement-audit, bank-card-reconciliation, cutoff-accrual-check, variance-analysis, accountant-query-drafter; wraps reconciliation-verifier, financial-reviewer, cogs-calculator.
- **External:** anthropics/financial-services (Apache 2.0; adapt, built for US financial firms).
- **Autonomy max:** R1. Sending anything to the accountant is R4.
- **Open decision:** the books system and the format of the accountant's statements.
- **Done when:** every statement line is tied to a source document or flagged with a drafted question.

### tax-household-strategist
- **Status:** planned (time-sensitive: many year-end moves close December 31)
- **Mission:** Research legal ways to reduce taxable income, track deductions with evidence, keep the deadline calendar, model household cash flow. Not a licensed advisor; every recommendation is flagged for CPA confirmation.
- **Trigger:** monthly; quarterly installment reminders; year-end sprint in autumn.
- **Runs on:** cloud.
- **Model:** Opus for annual planning; Sonnet for deadline monitoring.
- **Can call:** verifier.
- **Sources:** CRA, the Income Tax Act, Ontario Ministry of Finance (all grade A).
- **External:** openaccountants/openaccountants as a grade C reference only; never connect its MCP server to business data.
- **Autonomy max:** R1.
- **Done when:** each recommendation cites grade A sources and carries its deadline and dollar effect.

### cfo
- **Status:** planned
- **Mission:** Cash runway, debt service, breakeven and scenario planning.
- **Trigger:** weekly forecast, monthly review, alert when runway crosses a threshold.
- **Runs on:** cloud.
- **Model:** Sonnet weekly; Opus monthly.
- **Can call:** verifier.
- **Connectors:** QuickBooks (read), Square (read).
- **Skills:** 13-week-cash-forecast, debt-scenarios, unit-economics, runway-alert; wraps cogs-calculator, product-cost-manager.
- **Autonomy max:** R1.
- **Done when:** the forecast is recomputed in code and every assumption cites its source.

### video-editor
- **Status:** planned
- **Mission:** Turn raw footage into short captioned vertical reels for social.
- **Trigger:** a GitHub issue labelled `role:video-editor`.
- **Runs on:** server. It needs ffmpeg and the ElevenLabs API, which the cloud network blocks.
- **Model:** Sonnet.
- **Can call:** none.
- **External:** browser-use/video-use (MIT), heygen-com/hyperframes (Apache 2.0). Neither vetted yet.
- **Autonomy max:** R1.
- **Done when:** a 9:16 `final.mp4` with captions, checked at every cut, is linked on the issue.

### chief-of-staff
- **Status:** planned (build once 3+ roles run on a schedule)
- **Mission:** Daily brief, routing between roles, budget watch, and batching everything that needs the owner into one review of 30 minutes or less.
- **Trigger:** daily about 06:00; weekly review.
- **Runs on:** cloud.
- **Model:** Sonnet daily; Opus weekly.
- **Can call:** all active roles.
- **Autonomy max:** R1.

### business-advisor
- **Status:** planned (later)
- **Mission:** KPIs, pricing and margin, product mix, competitor watch, exit readiness.
- **Trigger:** monthly; quarterly strategy.
- **Can call:** verifier.

### ai-learning-coach
- **Status:** planned (later)
- **Mission:** Curriculum, weekly AI digest and build challenges toward becoming a top-tier AI agent engineer.
- **Trigger:** weekly digest; monthly project.

### venture-architect
- **Status:** planned (later)
- **Mission:** Map where money flows in target industries, where the owner's tools and consulting fit, and turn proven internal results into case studies.
- **Trigger:** biweekly scan; project sessions.
- **Can call:** verifier.

---

## Built as mechanisms, not agents

These were roles in the first design. They work better as rules, scripts or config that every role uses, because a rule enforced in config cannot be talked around and adds no agent to manage.

| Was | Now |
|---|---|
| Guardian | Each definition's `tools` and `mcpServers`, scoped credentials, and Claude Code hooks (hook policy to be carried over from PR #2). The autonomy matrix still decides what needs the owner's yes. |
| Librarian | The `knowledge/` folder and its rules (`shared/knowledge.md`). Each role checks it before researching. A periodic freshness and cleanup pass can become a role later. |
| Data Steward | Validation scripts inside each pipeline that uses the data. |
