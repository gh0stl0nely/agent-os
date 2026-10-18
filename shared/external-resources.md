# External skills and repos

Third-party skills and repos a role may use. Everything here comes from each repository's page unless the verdict says it was reviewed. A verdict is a recommendation, not a guarantee.

## Candidates

| Source | What it offers | For | License | Verdict |
|---|---|---|---|---|
| [anthropics/skills](https://github.com/anthropics/skills) | Anthropic's example skills, including PDF, DOCX, PPTX, XLSX | All roles (files and reports) | Mostly Apache 2.0; the four document skills are source-available | Reuse. Highest trust |
| [anthropics/financial-services](https://github.com/anthropics/financial-services) | Reference agents: GL Reconciler, Month-End Closer, Statement Auditor, Market Researcher | controller, business-advisor | Apache 2.0 | Adapt. Built for US financial firms; Canadian standards and sales tax not covered as far as the page shows |
| [obra/superpowers](https://github.com/obra/superpowers) | Planning, verification-before-completion and debugging patterns | verifier, chief-of-staff | MIT (repo page; not independently confirmed) | Borrow patterns; it targets software development. In use by the verifier: the `verification-before-completion` pattern, read at commit `8ca22dba9a94f28898bbce59f2537ff4d87c747d`, adapted into `recompute-in-code` and the hedging-word lint in `adversarial-review`. No text copied |
| [anthropics/skills](https://github.com/anthropics/skills) `skill-creator` | Skill authoring guidance | All roles (building skills) | Apache 2.0 | In use as a read-only authoring guide, read at commit `683bc88e56f3e09ba94f7055977f3d3aa499f202`. Not vendored |
| [openaccountants/openaccountants](https://github.com/openaccountants/openaccountants) | Open tax guides with a hosted MCP server | tax-household-strategist | AGPL-3.0 code; separate content license | Grade C reference only. Canada coverage unconfirmed. Never connect its MCP server to business data |
| [charlie947/social-media-skills](https://github.com/charlie947/social-media-skills) | Voice, post writing, hooks, carousels, analytics | growth-marketer | MIT | Not yet reviewed. Reel analysis needs Apify and Gemini keys |
| [browser-use/video-use](https://github.com/browser-use/video-use) | Edits raw footage into a finished video; needs ffmpeg and an ElevenLabs key | video-editor | MIT | Not yet reviewed. Pauses for plan approval by design |
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | HTML to rendered video; needs Node 22+, ffmpeg, headless Chrome | video-editor | Apache 2.0 | Not yet reviewed |
| [Gentleman-Programming/engram](https://github.com/Gentleman-Programming/engram) | Per-agent memory over MCP, SQLite file | Any role's learned memory | MIT | Not yet reviewed. Memory files belong in the private store |
| [travisvn/awesome-claude-skills](https://github.com/travisvn/awesome-claude-skills) | Discovery list | Discovery only | n/a | Lists can include skills that run arbitrary code |

## Skills already in the owner's Claude account
Wrap these instead of rewriting them: item-ordering, reconciliation-verifier, financial-reviewer, daily-sales-report, cogs-calculator, product-cost-manager, staff-scheduler, menu-update, social-poster. They hold private business lessons, so they are exported to the private store, never this repo. Which role wraps which is in `ROLES.md`.

## Gap
No Canada-specific accounting or tax skill was found. Build one from primary sources (CRA, Ontario Ministry of Finance, the accounting standard the corporation uses), graded A and checked by the Verifier.

## Install rules
Installing a third-party skill is R2: it changes what agents can do. Rules follow the OWASP Agentic Skills Top 10 ([source](https://owasp.org/www-project-agentic-skills-top-10/)):

| Risk | Rule |
|---|---|
| Malicious skills, supply chain | Read every file, including scripts, before install; prefer high-reputation sources |
| Over-privileged skills | Grant only the tools the skill needs; never give it secrets |
| Untrusted external instructions | Reject skills that load instructions from live URLs after install |
| Weak isolation | Run where a mistake cannot reach the owner's main machine |
| Update drift | Pin to a commit; re-review on every update |
| No governance | Record each installed skill here: source, commit, reviewer, date approved |
