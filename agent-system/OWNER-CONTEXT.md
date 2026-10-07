# Owner context (public-safe)

Everything a builder session needs to know about the owner, without sensitive details. This file is the shared memory of the owner interview. If something here is wrong or missing, put it in `QUESTIONS.md` for your role; do not guess.

## Who and why

- A software engineer who uses AI daily and has a technical background in building.
- Owns an early-stage mochi donut shop (Isabella's Donuts, Bloor St W, Toronto), incorporated, run alongside a full-time remote job. One hired staff member; the owner and a partner do most of the work. Plan: sell the shop in about five years.
- 1 to 2 year goal: work remotely on their own venture. That means AI agent consulting, plus tools that use AI to solve real business problems and sit in the flow of money in an industry (think the way payment networks and banks sit in the flow of money).
- Long-term goal: be a top-tier AI product engineer who controls agents around real business purposes, adds value systematically, cuts manual work, and eventually helps other businesses do the same. Therefore the system must be proven on the owner's own life and shop first, with measurable evidence, and be open to customization per business.
- Location and rules: Toronto, Ontario; CRA and Ontario rules.

## The core problem

Existing skills give answers with no verification gate and no proof of why a decision was made. The owner becomes the human verifier and has to spell out reasoning the AI should produce itself. The AI also does not research deeply or put itself in the right context for the online tools it could use. The fix is verification gates, evidence trails, autonomous in-depth research, and scheduled hands-off runs.

## Pain points (in the owner's priority order)

1. **Nightly order** for the shop: numbers must be done by 7:30pm and the order submitted by 7:45pm (supplier cutoff 8:00pm). Current output is "slightly off" per flavour, either over or under on certain flavours. The owner is not asking about perfection; they want evidence-based reasoning and a measurable track record.
2. **Verifying the accountant's monthly statements** by hand and correcting the AI's verification. The accountant is a CPA, three months in, generally good; occasional assumptions seem to come from missing context. Goal now: audit quality at CPA-level domain knowledge, never handwaving. Longer term: possibly replace the accountant.
3. **Inventory checks** done manually (data is kept in Notion).
4. **Content and posting** for the shop on social media: deciding what to post and posting it. Detail deferred.
5. **Cash and tax:** monitor cash runway and debt service; reduce taxable income by every legal means (not evasion); household finances. Figures stay in the private store.
6. **Learning:** become a top-1% expert at using AI agents for business impact.

## Owner rules (verbatim intent)

- Agents may act autonomously. But before anything dangerous (deleting, modifying, storing secrets or API keys, anything client-facing such as public posts) the agent must flag it EARLY with a clear, safe plan, research and proof, not during the action.
- Never handwave. Every claim is verified with actual proof.
- Escalate to the owner only when evidence or context genuinely cannot be gathered by the agent.
- Research once, store it, reuse it. Future agents refer to stored research instead of repeating it. But use both recorded memory (latest info) and fresh research when needed.
- Budget: stay on Claude Pro. If a task needs more budget, the agent flags it with reasoning on purpose and whether it is truly justified.
- Review time: at most 30 minutes a day; up to an hour only if justified (when the agent cannot reason or review on its own).
- Privacy: only sensitive material such as API keys that could be exploited must stay out of reach. This is for the owner's own life and business for now.
- Each role should be created by one specialized Claude session, with the same context as the design session.

## Existing assets

- Threads auto-poster (this repo), a queue of posts with images and a video.
- A set of Claude skills in the owner's own Claude account, including: item-ordering, reconciliation-verifier, financial-reviewer, daily-sales-report, cogs-calculator, product-cost-manager, staff-scheduler, menu-update, tip and pay-period skills. They are not in this repo. They hold private business knowledge (accumulated pitfalls, rules, lessons), so they are to be exported to the **private store**, never this repo.
- Data sources named so far: the shop's POS (Square per the existing skills), a Notion workspace for inventory, a Shopify-based supplier ordering portal (password-gated), the accountant's monthly statements, bank and card statements.
- Connectors available in the owner's Claude account include Gmail, Calendar, Drive, Notion, QuickBooks, Square, Canva and a social scheduler (availability varies by session).

## Decisions already made

- Orchestrator model: a Chief of Staff agent is the only one that talks to the owner.
- Knowledge base: private repo for sensitive content (to be created by the owner); this public repo holds design, procedures without numbers, and summaries of public rules.
- Models: Sonnet 5.5 default; Opus 5.5 only where the brief says so; Haiku 4.5 for high-volume checks.

## Open decisions (do not decide for the owner)

- How the nightly order reaches the supplier (prepared cart link, signed-in browser, or another channel) and the fallback if the owner has not answered by 7:45pm.
- Whether the private store is a private GitHub repo.
- The system the shop's books live in and the format of the accountant's deliverables.
- Which models and scheduled-task features the owner's plan actually includes.
- How the owner wants phone notifications delivered.
