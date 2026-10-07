# Architecture

All diagrams are Mermaid and render directly on GitHub. Names match [roster.md](roster.md).

## 1. System map

The Chief of Staff delegates and is the only agent that talks to the owner. Every producer output goes through the Verifier. Anything with a side effect goes through the Guardian. Knowledge is looked up before it is researched.

```mermaid
flowchart TB
    You(["You: 30 min per day review"])

    subgraph CP["Control plane"]
        CoS["Chief of Staff - ORCHESTRATOR"]
        Ver["Verifier"]
        Gua["Guardian"]
    end

    subgraph KP["Knowledge plane"]
        Lib["Librarian"]
        DS["Data Steward"]
        KB[("Knowledge base and claim ledger")]
    end

    subgraph BO["Business operations"]
        Ops["Operations Manager"]
        Ctl["Controller - CPA-level auditor"]
        CFO["CFO - cash and debt"]
        Tax["Tax and Household Strategist"]
        Gro["Growth Marketer"]
        Adv["Business Advisor"]
    end

    subgraph GR["Growth of you"]
        Coach["AI Learning Coach"]
        Ven["Venture Architect"]
    end

    Ext["Outside world: supplier portal, social platforms, accountant, CRA"]

    You <-->|"brief, approvals, corrections"| CoS
    CoS -->|"delegates"| BO
    CoS -->|"delegates"| GR
    BO -->|"claims plus evidence"| Ver
    GR -->|"claims plus evidence"| Ver
    Ver -->|"verified or blocked"| CoS
    BO -->|"planned side effects"| Gua
    Gua -->|"preflight brief"| CoS
    Gua -->|"approved actions only"| Ext
    BO <-->|"look up before researching"| Lib
    GR <-->|"look up before researching"| Lib
    Lib <--> KB
    DS -->|"validated data"| Ops
    DS -->|"validated data"| Ctl
    DS -->|"validated data"| CFO
    You -->|"corrections become brain rules"| KB
```

## 2. Verification gate

Deterministic checks run first because a model checking its own model family can share its blind spots. The Verifier then asks one question per claim: is there evidence? Two revise loops at most, then escalate with exactly what is missing.

```mermaid
flowchart LR
    P["Producer agent output"] --> D["Deterministic checks: recompute in code, schema, source exists"]
    D -->|fail| R["Revise - max 2 loops"]
    D -->|pass| V["Verifier: does every claim have evidence?"]
    V -->|"all claims evidenced"| G{"Has side effects?"}
    V -->|"gaps found"| R
    R --> P
    R -->|"still failing"| E["Escalate to you with exactly what is missing"]
    G -->|no| I["Approvals inbox and daily brief"]
    G -->|yes| GB["Guardian: preflight brief with plan, evidence, rollback"]
    GB --> I
    I --> Y(["You approve"])
    Y --> X["Execute the action and log it to the ledger"]
```

## 3. Nightly ordering pipeline

The hard clock: numbers by 7:30pm, order submitted by 7:45pm, supplier cutoff at 8:00pm. Times are proposals to be tuned during the build. The Guardian's plan includes the cost and how the order can be cancelled or changed.

```mermaid
sequenceDiagram
    autonumber
    participant S as Scheduler
    participant DS as Data Steward
    participant Lib as Librarian
    participant Ops as Operations Manager
    participant V as Verifier
    participant G as Guardian
    participant You
    participant Sup as Supplier portal

    S->>DS: 18:30 validate sales, stock and waste data
    DS-->>Ops: clean data or blocking issues
    S->>Lib: 18:40 refresh weather, events and holidays
    Lib-->>Ops: dated facts with sources
    Ops->>Ops: 18:50 forecast per flavour in code, then write the reasoning
    Ops->>V: 19:10 recommended order with evidence
    V-->>Ops: verified, or revise - max 2 loops
    Ops->>G: order plan with cost and how to cancel or change it
    G->>You: 19:15 push with the recommendation and why
    alt you approve before 19:30
        You-->>G: approve
    else no answer yet
        G->>You: 19:40 second push
    end
    Note over G,You: If still no answer, apply the fallback rule you chose in advance
    G->>Sup: by 19:45 submit the approved order only
    Sup-->>Ops: confirmation
    Ops->>Ops: log order, reasoning and sources to the ledger
    Note over Sup: Supplier cutoff 20:00
```

How the order reaches the supplier is an open decision (see [README.md](README.md)): the portal is password-gated and agents are not allowed to type passwords.

## 4. Knowledge lookup: memory first, research if stale

```mermaid
flowchart TD
    Q["Agent needs a fact"] --> S["Search the knowledge base first"]
    S --> F{"Found?"}
    F -->|no| R["Deep research on primary sources"]
    F -->|yes| T{"Fresh? check expires_at and last_confirmed_at"}
    T -->|"fresh and low stakes"| U["Use it and cite the record id"]
    T -->|"stale or consequential action"| C["Re-check the source"]
    C --> D{"Source changed?"}
    D -->|no| K["Update last_confirmed_at"]
    K --> U
    D -->|yes| R
    R --> W["Write gate: cited, no secrets, no duplicate, trust grade set"]
    W -->|passes| N["Save new record that supersedes the old one"]
    N --> U
    W -->|fails| B["Mark blocked and escalate if it matters"]
```

## 5. Execution layers

On Claude Pro, usage is shared and capped, and Pro does not include API usage. So scripts that need no model run on a free scheduler (the existing Threads poster already runs this way on GitHub Actions), and only reasoning steps use the Claude allowance. Whether scheduled tasks are available on the owner's plan is unverified.

```mermaid
flowchart LR
    subgraph DET["Deterministic layer: scripts, no tokens"]
        A1["Pull data, validate, recompute, forecast math"]
        A2["Post approved content, enforce pause switch and expiry"]
    end
    subgraph LLM["Reasoning layer: Claude scheduled tasks, uses plan allowance"]
        B1["Research, judgment, explanations"]
        B2["Verifier and Chief of Staff review"]
    end
    DET -->|"facts and numbers with lineage"| LLM
    LLM -->|"approved instructions only"| DET
```

## Attention routing

| Tier | When | How |
|---|---|---|
| Normal | Most output | One approvals inbox, reviewed once or twice a day |
| Time-critical | The 7:30pm order | Phone push at about 7:15 and again at about 7:40, plus the fallback rule |
| Critical | Runway alert, security issue | A high-priority push channel (tool choice and pricing to be verified before relying on it) |
