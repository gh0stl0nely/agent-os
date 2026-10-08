# agent-os (Core AI Monorepo)

This repository is a unified, modular monolith designed to run a small business and household using a team of specialized AI roles under a strict "Compute with Code, Reason with the Model" paradigm.

## Operational Protocol for Builder Sessions
1. **Scope Alignment:** Your prompt must specify your target agent role (e.g., "04 CFO", "06 Operations Manager"). Do not modify folders or tools belonging to other agent scopes.
2. **Follow Code Protocols:** Strictly adhere to the guidelines inside `agent-system/ARCHITECTURE_ENGINEERING.md` and `agent-system/BUILD-PROTOCOL.md`.
3. **The PR Pipeline:** All modifications must be submitted via isolated pull requests. Never attempt to merge your own engineering branch; a separate review session handles code audits.

## Core System Non-Negotiables
* **No Claim Without Evidence:** Every analytical conclusion or transaction ledger must explicitly map back to a verified textual source, computation, or owner context directive. Handwaving or "assuming" data is a system fault.
* **Preflight Escalation Boundary:** Deleting tracking data, mutating global agent states, handling raw encryption keys, or triggering external live actions (posting, ordering, messaging) requires an explicit, human-readable Preflight Brief at planning time.
* **Absolute Git Privacy:** This repository is a public monorepo framework. Commitment of active API tokens, raw passwords, banking ledgers, tax metrics, or personal PII is completely prohibited. Use localized, synthetic data fixtures. Real business contexts reside exclusively in the private state store.
* **Deterministic Logic Split:** Mathematics, data validation, and accounting metrics are handled exclusively by localized code scripts. The model processor is strictly reserved for intent routing, conceptual research, and brand-voice synthesis.
* **Circuit Breaker Aware:** Every executable script or API worker module must natively inspect `agent-system/state/CIRCUIT_BREAKER.lock` before starting. If this lock file is present, execution must immediately crash and abort to prevent cascading state corruption.

## Engineering Stack & Commands
* **Core Language:** Clean, minimalist Python. Every cross-agent data contract must use Pydantic classes for type-checking. Standalone Node.js/TypeScript assets are banned.
* **File Location Boundary:** Executable scripts and skills belong inside `agent-system/core/` or `agent-system/agents/<role>/scripts/`. Do not write code inside hidden runtime dot-directories (like `.claude/skills/`).
* **Run System Verification Tests:** `pytest agent-system/tests/`
* **Execute Schema Integrity Audits:** `python3 agent-system/core/validator.py --check-all`
* **Enforce Unified Code Formatting:** `black agent-system/`

## Context Ingestion Matrix
@agent-system/OWNER-CONTEXT.md
@agent-system/contracts/autonomy-matrix.md
