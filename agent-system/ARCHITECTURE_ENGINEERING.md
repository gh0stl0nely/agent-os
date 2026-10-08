# Agent OS: System Engineering & Optimization Manual

This document establishes the binding architectural constraints for the `agent-os` ecosystem. To prevent runaway token consumption, hallucinations, and distributed state corruption, all workflows, code modules, and engineering tools must strictly adhere to these four core pillars.

---

## 1. Context & Routing Engineering (Token Conservation)

To avoid overloading the LLM's context window with unnecessary information and wasting tokens, the system implements an **Intent-Based Semantic Router** pattern rather than letting a single massive agent guess what to do.

### Architecture Constraints
* **The Orchestrator Gate:** The Chief of Staff (`agent-system/agents/chief-of-staff/`) acts as a strict, low-token traffic controller. Its only cognitive function is classification.
* **Single-Topic Execution:** The router prompt must evaluate incoming webhook triggers or schedule crons and output exactly *one* target string matching a key in the agent roster (e.g., `["cfo", "accountant", "social-poster", "none"]`).
* **Static Context Registries:** We do not use vector embeddings (RAG) for core operations. Instead, agents look up an explicit file-based sitemap (`agent-system/state/registry.json`) contained in the private state repository. If a file is not in the registry, the agent cannot scan for it.

---

## 2. Stateful Determinism & Structural Sanity

We reject free-roaming, open-ended conversation loops. Every agent execution turn must be treated as a single state transition in a **Finite State Machine (FSM)**.

### Technical Infrastructure Guards
* **Native JSON Schema Enforcement:** Every call to the Anthropic API via n8n or Python must utilize Anthropic’s native `tool_choice` or structured output mode, referencing a strict schema file inside the `agent-system/contracts/` directory.
* **The Infrastructure-Enforced One-Turn Rule:** Worker agents operate on a rigid input-process-output model. They are passed isolated context ➔ perform exactly one cognitive pass ➔ return a structured JSON block ➔ terminate immediately. They have zero historical context of previous agent turns.
* **System Circuit Breaker:** If an agent loop hits `MAX_RECURSION = 3` or outputs an unparseable payload, the execution layer must immediately write an explicit lock file to `agent-system/state/CIRCUIT_BREAKER.lock` and halt all other cron workflows. System execution remains paralyzed until the owner manually deletes the lock file.

---

## 3. The "Compute-with-Code, Reason-with-Model" Directive

Large Language Models are non-deterministic and terrible at precise data mutation, arithmetic, and API protocols. They are highly efficient at synthesis, translation, and intent evaluation.

### Division of Labor Matrix

| Operational Task | Execution Layer (Deterministic Code / n8n) | Cognitive Layer (Claude API) |
| :--- | :--- | :--- |
| **Data Fetching** | Pulls files from GitHub; queries databases via SQL; executes OAuth handshakes. | *Prohibited.* |
| **Mathematics & Accounting**| Recomputes spreadsheet sums; executes ledger math via Python/Pydantic data types. | *Prohibited.* |
| **Content Synthesis** | *Prohibited.* | Drafts brand-voice copy; summarizes logs; maps human intent. |
| **Validation & Verification** | Confirms file hashes match; checks JSON field existence via Pydantic validators. | Cross-references conceptual claims against raw textual evidence. |

---

## 4. Technology Stack & Secrets Philosophy

To ensure frictionless portability, eliminate platform lock-in, and maintain a lightweight footprint, the ecosystem relies on a decoupled, code-first tool philosophy.

### Core Stack Boundaries
* **The Code Layer (Python):** Python is the definitive engine for all deterministic execution, API scripts, and data contracts. We prioritize libraries like Pydantic that offer native type-checking to serve as our validation gates.
* **Monorepo Directory Mapping:** Built skills and custom scripts are strictly banned from floating in hidden runtime folders (such as `.claude/skills/`). All functional assets must reside explicitly within the main codebase tree under `agent-system/core/` or `agent-system/agents/<role>/scripts/` to ensure local n8n access.
* **The Orchestration Layer (Local n8n):** We utilize a self-hosted, local n8n instance to act as our stateless event bus and cron-heartbeat generator. n8n is responsible for running timers and executing localized Python scripts.
* **The Secrets Rule:** All API tokens (Anthropic, Meta, etc.) must live strictly inside the orchestration engine's encrypted local credential manager. Credentials must never be hardcoded into Python scripts or versioned inside Git repositories.
