# Reusable skills and agents on GitHub

Findings from a survey on 2026-10-07. Everything here comes from what each repository's page states; nothing was installed or run. "Verdict" is a recommendation, not a guarantee.

## Candidates

| Source | What it offers | Maps to | License | Verdict |
|---|---|---|---|---|
| [anthropics/skills](https://github.com/anthropics/skills) | Anthropic's example skills (creative, development, enterprise, document skills for PDF, DOCX, PPTX, XLSX) and install instructions for Claude Code, Claude.ai and the API | All agents (reports and files); Controller (spreadsheets) | Mostly Apache 2.0; the four document skills are source-available, not open source | Reuse. Highest trust of the list |
| [anthropics/financial-services](https://github.com/anthropics/financial-services) | Reference agents including GL Reconciler, Month-End Closer, Statement Auditor, Market Researcher, and vertical skill bundles. Installable as Cowork or Claude Code plugins, or deployed headless through the Managed Agents API | Controller (GL Reconciler, Statement Auditor, Month-End Closer); Business Advisor (Market Researcher) | Apache 2.0 | Adapt, do not adopt blindly. Built for financial-services firms; Canadian standards and sales-tax treatment are not covered as far as the page shows. Headless deployment uses an API key, which Pro does not include |
| [obra/superpowers](https://github.com/obra/superpowers) | A methodology of composable skills: brainstorming, writing-plans, verification-before-completion, systematic-debugging, subagent-driven development | Chief of Staff (planning), Verifier (verify-before-claiming-done pattern) | MIT | Borrow patterns. It targets software development, so the process ideas transfer better than the skills |
| [openaccountants/openaccountants](https://github.com/openaccountants/openaccountants) | Open tax guides for AI agents, reported as 1,883 guides across 230 jurisdictions, reviewed by named accountants, with a hosted MCP server | Tax and Household Strategist (low-trust reference only) | AGPL-3.0 for code; a separate guide license for content | Use only as a grade C reference. Canada coverage is **unconfirmed**. The project's own disclaimer says guides may be incomplete, outdated or wrong. Do **not** connect the hosted MCP server to business data. Verify every claim against CRA |
| [travisvn/awesome-claude-skills](https://github.com/travisvn/awesome-claude-skills) and similar lists | Discovery lists of community skills | Librarian (discovery) | n/a | Discovery only. Finance and marketing categories were sparse when checked. The list itself warns that skills can run arbitrary code |
| loki-mode (listed in the awesome list) | A swarm of dozens of agents | none | not checked | Not recommended. It is the opposite of the lean, measured design here |

## Skills already in your Claude setup

Wrap these with evidence and verification gates instead of rewriting them: item-ordering, reconciliation-verifier, financial-reviewer, daily-sales-report, cogs-calculator, product-cost-manager, staff-scheduler, menu-update, plus the marketing and finance skills. Mapping is in [roster.md](roster.md), Table A.

## Gap found

No Canada-specific accounting or tax skill turned up. The Librarian should build one from primary sources (CRA, Ontario Ministry of Finance, the accounting standard that applies to the corporation), graded A, with the Verifier checking it. This is also a candidate offering for other small Canadian businesses later.

## Install policy (enforced by the Guardian)

Third-party skills can contain scripts and instructions that Claude follows, so installing one is a "modify" action that gets a Preflight Brief. Rules follow the OWASP Agentic Skills Top 10 ([source](https://owasp.org/www-project-agentic-skills-top-10/)):

| Risk (OWASP ID) | Rule here |
|---|---|
| Malicious skills (AST01), supply chain (AST02) | Read every file in a skill, including scripts, before install; prefer the highest-reputation sources |
| Over-privileged skills (AST03) | Grant only the tools the skill needs; never give it secrets |
| Untrusted external instructions (AST05) | Reject skills that load instructions from live URLs after install |
| Weak isolation (AST06) | Run in a sandbox, not on the owner's main machine |
| Update drift (AST07) | Pin to a commit SHA; re-review on every update |
| Poor scanning (AST08) | Do not rely on an automated scanner alone |
| No governance (AST09) | Keep an inventory: skill, source, commit, reviewer, date approved |
