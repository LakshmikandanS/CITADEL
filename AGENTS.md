# AGENTS.md — Citadel MVP (Sovereign Agentic AI Workbench, vertical slice)

This file is the entry point for any coding agent (Claude Code, Cursor, Codex CLI, Windsurf,
Aider, or a human) working in this repository. Read this fully before writing code.

## 0. Source of truth

**`docs/CITADEL_MVP_DESIGN.md` is the frozen implementation contract.** Every schema, state
machine, endpoint contract, and pseudocode block in it is meant to be typed in directly, not
redesigned. If anything in this AGENTS.md or in a subagent file ever conflicts with that
document, the document wins — fix the AGENTS.md, not the code.

`docs/CITADEL_BLACKBOX_AUDIT.md` and `docs/architecture/00`–`14` are background only: they
describe the full production-scale architecture and the gaps found in it. The MVP design doc
already resolved every one of those gaps for this slice (see its §7 Closure Matrix) and
explicitly **retires** some of the older shapes in `docs/architecture/` (e.g. the old
Model Router response shape in `02_QUERY_MODEL_ROUTER.md`). Do not resurrect a superseded shape
because it appears in the background docs — the MVP doc's version always wins.

## 1. What we are building

One scenario, end to end, for a live demo:

> A maintenance engineer asks Citadel to identify Pump P-101's recent maintenance history from
> internal (CONFIDENTIAL) documents and generate a short summary report, which a human approver
> then releases.

Two more paths are **mandatory**, not optional polish:
- A **denial path**: the agent attempts an out-of-scope retrieval (wrong department ACL) and is
  refused before any data leaves the Data Plane.
- An **emergency-control path**: an admin runs `disable-tool python.execute` and a subsequent
  attempt is denied even with an otherwise-valid capability token.

Full walkthroughs of all three: `docs/CITADEL_MVP_DESIGN.md` §1.

## 2. The one architectural rule that governs everything

> Agents do not get direct authority. They request capabilities; the control plane decides
> whether those capabilities may be used.

No component ever lets an agent read arbitrary files, query arbitrary data, call an arbitrary
model, touch the host filesystem, reach the network, or mutate shared state directly. Every one
of those is a policy-checked operation that goes through the Tool Gateway.

## 3. Trust zones (§2 of the design doc)

```
┌───────────── TRUSTED WORKFLOW ZONE (one FastAPI process) ─────────────┐
│ CLI-facing API · Query Router · Orchestrator · Control Plane          │
│ (Identity, Policy, Capability, Approval) · Model Router · Data Plane  │
│ (Postgres + vector store, RAG)                                        │
│ Never runs adversarial code. Consolidated into one process for MVP    │
│ build speed — this does NOT weaken the boundary that actually matters.│
└──────────────────────────────┬─────────────────────────────────────────┘
                                │ HTTP, over a Docker network the sandbox
                                │ zone has no other route out of
                                ▼
┌───────────── ISOLATED EXECUTION ZONE (separate process) ──────────────┐
│ Execution Service — the ONLY thing in the system holding a Docker     │
│ socket. Spawns one-shot python.execute containers: no Docker socket,  │
│ no host mount, no network route to Postgres/vector store/internet,    │
│ resource + time limits, destroyed immediately after the call returns. │
└─────────────────────────────────────────────────────────────────────────┘
```

The Control Plane is **not** process-isolated from the Orchestrator in this slice — that's a
stated, deliberate MVP limitation (design doc §2), not an oversight. The one boundary that must
be real is the one around code execution, because `python.execute` is the only capability that
runs content Citadel itself did not author.

## 4. Repository layout

```
citadel-mvp/
├── AGENTS.md                     ← this file
├── docs/
│   ├── CITADEL_MVP_DESIGN.md     ← frozen contract, single source of truth
│   ├── CITADEL_BLACKBOX_AUDIT.md ← background only
│   └── architecture/00-14...     ← background only, partially superseded
├── .claude/agents/                ← one subagent per build-order step, see §6
├── app/                            ← the trusted workflow zone (one FastAPI app)
│   ├── db/                         ← models.py: User, Task, Agent, Event, Artifact, Approval
│   ├── observability/              ← single serializing event writer + hash chain
│   ├── identity/                   ← /login, JWT issuance/verification
│   ├── policy/                     ← Policy Engine, tool_disabled table
│   ├── capability/                 ← capability token issuance/verification
│   ├── tool_gateway/               ← the authorization spine (§6.6)
│   ├── model_router/                ← static lookup table, manifest
│   ├── orchestrator/                 ← /task intake (Query Router role), plan, agent loop, revision
│   ├── data_plane/                    ← ingestion, embeddings, ACL-filtered retrieval
│   ├── artifact/                       ← generation, Verifier, immutability
│   └── approval/                       ← the one transactional decision endpoint
├── execution_service/               ← separate process, the ONLY Docker-socket holder
├── cli/                               ← `citadel` CLI (login, /task, /status, /approve, /trace, admin)
├── data/                               ← sample docs + mandatory .meta.json ACL sidecars
├── tests/                              ← mirrors docs/CITADEL_MVP_DESIGN.md §9 exactly
└── docker-compose.yml                   ← wires the two trust zones together
```

## 5. Suggested stack (concrete on purpose — nothing left to decide mid-build)

FastAPI (trusted zone) · Postgres, or SQLite if faster to stand up · a local vector store
(Chroma or Qdrant) · Docker SDK for Python inside the Execution Service · a locally-served
open-weight model via Ollama for reasoning + embeddings.

## 6. Build order and subagents

Build in this order — each step should run and be demoable before the next begins. Each step
has a matching subagent under `.claude/agents/` that owns exactly that slice of the contract,
so you're never asking one agent to hold the whole 650-line spec in its head at once.

| Step | Subagent | Deliverable | Proves |
|---|---|---|---|
| 1 | *(you, first)* | Inspect any existing code/repo structure before writing anything new | No blind overwrites |
| 2 | *(you, first)* | Treat `docs/CITADEL_MVP_DESIGN.md` as frozen | One source of truth |
| 3 | `foundation-schema` | `User, Task, Agent, Event, Artifact, Approval` tables + the single Observability writer | Every later step has somewhere to record itself |
| 4 | `security-control-plane` | Identity → Policy → Capability → Tool Gateway, tested with a fake echo tool | ALLOW and DENY both work *before* any real tool exists |
| 5 | `execution-service` | Execution Service + one-shot `python.execute` container, no Docker socket inside it | The one real process boundary is real |
| 6 | `data-plane-rag` | Ingestion with mandatory ACL sidecar → embed → ACL/classification-filtered retrieval | Evidence is never returned unfiltered |
| 7 | `orchestrator` | Task intake → plan → agent loop → real tool calls through the Tool Gateway → finish/revise | The whole PLAN→ACT→OBSERVE loop, for real |
| 8 | `artifact-pipeline` | generate → verify → approve → release, state machines enforced | The full happy path, end to end |
| 9 | `cli` | `login`, `/task`, `/status`, `/approve`, `/trace`, `admin disable-tool` | The demo is drivable by a human |
| — | `qa-tester` | Runs after every step above; owns `tests/` and the final DoD script | Nothing regresses silently |

Each step should conclude with the relevant rows of the design doc's §9 Testing Checklist
passing before moving to the next — `qa-tester` is the one to invoke for that.

## 7. Explicitly not building in this slice

Multi-agent orchestration / agent-to-agent delegation, GPU scheduling or model fallback chains,
crash recovery / checkpoint-resume, a real policy DSL or RBAC×ABAC combination logic beyond 4
static rules, per-connection network attribution, backup/restore, retention/purge, every
emergency control except `DISABLE TOOL`, a production identity provider (LDAP/AD) or token
revocation lists, and distributed event ordering (one serializing writer is enough at this
scale). Kubernetes, Kafka, Redis, a distributed scheduler, a multi-agent framework, Docker-socket
access for agents, direct agent writes to shared state, internet access for the execution zone,
an LLM-as-judge verifier, and a polished dashboard are all out of scope too. None of this is an
accidental omission — see the design doc's §7 Closure Matrix and §10.

## 8. Definition of done

One documented startup sequence demonstrates, in order: an authenticated task submission
reaching the Query Router; the Orchestrator producing a structured plan; an agent action passing
capability and policy checks; a sandboxed `python.execute` call with no Docker socket inside it;
ACL-filtered evidence retrieval; a generated, structurally-verified artifact; a human approval
that atomically releases it; **and**, separately, an out-of-scope retrieval attempt that is
denied without executing, **and** a `DISABLE TOOL` command that revokes a capability's practical
effect immediately — with `/trace` showing the complete, hash-chained event history for all three
of those runs.

## 9. Conventions for every subagent

- Never invent a schema, endpoint shape, or state name that isn't in `docs/CITADEL_MVP_DESIGN.md`.
  If something genuinely isn't specified, say so and propose the smallest addition rather than
  guessing silently.
- Every mutating endpoint derives identity from the verified session JWT, never from the request
  body — this applies with no exception, including the approval endpoint.
- Every tool call goes through the Tool Gateway. There is no code path where an agent calls
  `rag.search`, `python.execute`, or `generate_report` directly.
- Every event goes through the single Observability writer in `app/observability/`. No other
  module computes or appends to the hash chain.
- Fail closed by default: an unmatched policy check is `DENY`, an unmatched verification check
  fails the artifact, an unmatched model/tool call fails the task. No silent passes.
