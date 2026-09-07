# Citadel MVP — Build Log

Running record of what each build-order step (AGENTS.md §6) actually produced,
and the decisions later steps must not contradict.

`docs/CITADEL_MVP_DESIGN.md` remains the frozen contract. This file records
*implementation* decisions made underneath it — it never overrides it.

---

## Environment

- Python 3.12, venv at `.venv/` — **use `.venv/Scripts/python`**, not the system Python.
  The venv is gitignored; on a fresh checkout it must be rebuilt (it was, on
  2026-09-07, against system Python 3.12.10).
- Installed: `sqlalchemy>=2.0`, `pydantic>=2`, `pytest` (step 3) plus
  `fastapi`, `uvicorn`, `httpx`, `PyJWT`, `bcrypt` (step 4 — `httpx` is what
  `fastapi.testclient.TestClient` needs).
- Database: SQLite at `var/citadel.db`, selected by `CITADEL_DATABASE_URL`.
  Point that at Postgres and nothing else changes (design doc §8 permits either).
- **Ollama IS installed and serving** on `localhost:11434` (the earlier note
  here was stale). Verified 2026-09-07:
  - `nomic-embed-text` — 768-dim, no truncation, clean separation on the demo
    corpus. Step 6's embedding model.
  - `hermes3` — returns schema-valid plan JSON in ~13s under `format=json`.
    **Step 7's reasoning model.**
  - `qwen3:4B` — returns an **empty** response under `format=json`; it is a
    thinking model and the reasoning trace swallows the output. Do not use it
    for structured planning without extra handling.
- **Docker is being installed** (it was absent entirely, not merely stopped).
  Step 5 (Execution Service) and §6.13's network-isolation test are the two
  things gated on it.

Run everything:

```
.venv/Scripts/python -m pytest tests/ -q
```

---

## Step 3 — `foundation-schema` — COMPLETE

**Status:** 38 passed, 19 skipped (the skips are §9 checklist items owned by
steps 4–9, present as named stubs so `pytest -v` reads as a progress board).

**Demo:** `.venv/Scripts/python -m tests.demos.step3_foundation`

### Delivered

```
app/config.py                  env-driven settings; the only place backends are named
app/ids.py                     the §3 identifier shapes (U…, T…, A…, ART…, APR…, EVT…)
app/db/base.py                 declarative base, utcnow()
app/db/engine.py               engine + SessionLocal + session_scope()
app/db/models.py               the six §3 tables
app/db/state_machines.py       the three §4 machines + Agent lifecycle + Classification lattice
app/db/transitions.py          guarded transitions + §6.11 optimistic versioning
app/observability/event_types.py   the closed 16-type §6.12 vocabulary
app/observability/hashing.py       pluggable chain strategies
app/observability/writer.py        THE single serializing writer
tests/                         one module per §9 category + test_foundation.py + demos/
```

### Decisions later steps must respect

1. **`app.observability.append_event` is the only code path that writes the
   Event table.** `tests/test_audit.py::test_append_event_is_the_only_writer_to_the_event_table`
   greps `app/` and fails if any other module constructs an `Event`. Verified
   against a negative control.

2. **Hash strategy is `canonical_record_v1`** (`CITADEL_EVENT_HASH_STRATEGY`).
   It hashes `{event_id, task_id, actor_id, event_type, payload, timestamp}`
   concatenated with `previous_hash` — a strict superset of §6.12's
   `SHA256(payload + previous_hash)`. Rationale: read literally, the formula
   does not bind `event_type`, so relabelling a `TOOL_DENIED` as a
   `TOOL_EXECUTED` would not break the chain — and the denial-path (§1.2) and
   emergency-control (§1.3) demos rest on exactly that field being
   trustworthy. The audit (BB-035) treats the formula as settled and its black
   box as *ordering*, which §6.12's single writer closes; this choice
   therefore extends the preimage without reopening a resolved question.
   `payload_only_v1` implements the literal reading and stays in the registry.
   **Confirmed by the project owner at the step 3 checkpoint.**
   Changing this invalidates any chain already written.

3. **`Event.seq`** (integer, autoincrement) is the chain's ordering key and
   primary key; **`event_id`** is the §3 display form (`EVT0001`), unique and
   derived from `seq`. Order by `seq`, never by the string — that is what keeps
   `/trace` correct past `EVT9999`.

4. **`Event.task_id` is nullable** so a system-scoped event (an admin
   `DISABLE TOOL`, §6.8) can join the one chain. All 16 §6.12 types are
   task-scoped and must set it. `get_trace(None)` returns the whole chain;
   `verify_chain` always verifies globally, because a per-task subsequence has
   gaps by construction.

5. **`append_event(..., session=...)`** enlists the event in a caller's
   transaction. §6.10's approval decision must move Approval + Artifact + Task
   and emit `APPROVAL_GRANTED` + `ARTIFACT_RELEASED` in **one** commit — use
   this, not a separate connection.

6. **`Approval` has both `state` and `decision`.** `state` is the §4 machine
   (`NOT_REQUIRED → REVIEW_REQUIRED → APPROVED/REJECTED`); `decision` is the §3
   domain field, null until a human decides. `transition_approval` sets both.
   `approver_id` is nullable with **no default** — write it once, from the
   verified session JWT, at decision time (§6.4).

7. **`Agent.task_id` is UNIQUE** — one Agent row per task (§3, BB-014) is a
   schema constraint, not a convention. Multi-agent orchestration in Phase 2
   requires dropping it deliberately.

8. **Two columns added beyond the §3 JSON**, both required by the design doc
   elsewhere, neither invented:
   - `User.password_hash` — §6.4 ("bcrypt-hashed passwords"), nullable;
     Identity (step 4) owns populating it.
   - `Task.version` — §6.11 optimistic versioning. **Distinct from
     `Artifact.version`**, which is a document revision number. Never the same
     counter.
   - `Artifact.path` — the Verifier's first check is
     `file_exists_and_readable()` (§6.10), so the location has to be recorded.

9. **State transitions go through `app/db/transitions.py`.** They validate
   against the §4 machines and never commit — the caller owns the transaction.
   `ARTIFACT` treats `RELEASED` as terminal, which is the state-machine
   backstop behind §6.10's API-layer immutability check (step 8 still owns the
   API-layer check itself).

10. **Fail closed everywhere:** unknown event type → `UnknownEventType`;
    unknown state or unlisted transition → `IllegalTransition`; unknown
    classification → `ValueError`.

### Phase-2 seams (nothing from §7 / §0's out-of-scope list was built)

| Seam | Extend by |
|---|---|
| Storage backend | Set `CITADEL_DATABASE_URL` — SQLite → Postgres, no code change |
| Event writer | Implement `append_event`/`get_trace`/`verify_chain`, call `set_writer()` — a separate event process or queue-backed writer needs no caller changes |
| Hash strategy | Register another function in `hashing.py` |
| State machines | Add states to the transition dicts; no component reads state strings directly |
| Event vocabulary | Extend `ALL_EVENT_TYPES` |

### Repo restructure

`docs/` and `.claude/` were moved from `citadel-mvp-agents/` to the repository
root (via `git mv`) and the duplicate `citadel-mvp-agents/AGENTS.md` removed,
so the layout matches AGENTS.md §4 and `.claude/agents/` is where subagents are
discoverable.

---

## Step 4 — `security-control-plane` — COMPLETE

**Status:** 85 passed, 14 skipped. The 14 skips are §9 checklist items owned by
steps 5–9. All five of step 4's own §9 Security lines pass, against the fake
`echo` tool, through the whole gateway path — which is what §8's step 4 and
C-004 ask for: ALLOW and DENY proven *before* any real tool exists.

**Demo:** `.venv/Scripts/python -m tests.demos.step4_security`
Walks the ALLOW path and all four DENY paths, prints the trace, verifies the chain.

### Delivered

```
app/identity/passwords.py      bcrypt hashing; the local user table stands in for LDAP/AD
app/identity/tokens.py         8-hour session JWT (§6.4)
app/identity/service.py        authenticate / create_user / login
app/identity/dependencies.py   current_identity, require_role, drop_client_identity
app/identity/router.py         POST /login
app/capability/tokens.py       HMAC-SHA256 capability, 5-min TTL, scoped (§6.5)
app/capability/service.py      issue_for_step — one capability per plan step
app/policy/tools.py            the canonical tool-name constants
app/policy/context.py          PolicyUser/Agent/Task/Action/Resource descriptors
app/policy/engine.py           decide() — four ordered rules, first match wins, default DENY
app/policy/tool_disabled.py    the ONE emergency control (§6.8)
app/policy/router.py           POST /admin/tools/{tool_name}/disable, admin-only
app/tool_gateway/envelope.py   the §6.6 envelope + the five closed error codes
app/tool_gateway/registry.py   backend routing table
app/tool_gateway/gateway.py    invoke() — Step A → Step B → Step C
app/tool_gateway/backends/echo.py   the fake tool, never auto-registered
tests/test_security.py         47 tests (5 checklist + 42 contract)
tests/demos/step4_security.py  the step-4 demo
```

### The contract steps 5–8 call

Two functions. Nothing else in the system may invoke a tool.

```python
from app.capability import issue_for_step
from app.policy import Tool
from app.tool_gateway import invoke, task_resource

cap = issue_for_step(task_id, agent_id, Tool.RAG_SEARCH)   # immediately before the step
envelope = invoke(
    capability_token=cap.token,
    tool=Tool.RAG_SEARCH,
    resource=some_policy_resource,      # or task_resource(task_id)
    arguments={"query": "..."},
)
```

`invoke` **never raises** for an authorization or execution failure — "denied"
is a first-class outcome (§1.2), not an exception. Always returns the §6.6
envelope. Attach a real backend with
`register_backend(Tool.RAG_SEARCH, my_backend)` and change nothing else.

### Decisions later steps must respect

1. **`resource` is required on every `invoke`, deliberately.** §6.7's two data
   rules are evaluated against it, and a default would silently pass them. A
   tool with no external target (`python.execute` computing over evidence
   already retrieved, `generate_report` rendering it) uses
   `task_resource(task_id)`, which evaluates the rules against the task's own
   classification and department. **Never** build the descriptor from
   agent-supplied arguments — that would let an agent describe its own target
   as harmless.

2. **Two separate signing secrets**, `CITADEL_SESSION_SECRET` and
   `CITADEL_CAPABILITY_SECRET`. §2 puts Identity and Capability in one process
   so a shared key would work, but a leaked capability key must not also mint
   8-hour sessions. **No dev default is committed**: if unset, a random
   per-process key is generated, so a restart invalidates outstanding tokens.
   That is the fail-closed mode; a checked-in "dev secret" is the one that
   reaches production by accident. Any real deployment must set both.

3. **The echo backend is never auto-registered anywhere.** Tests and the demo
   bind it explicitly. Auto-registering a fake would mean a real backend that
   failed to load got silently answered by an echo.

4. **Capability check and policy check stay two separate steps.** Step A is
   local (signature, expiry, operation match) with no Control Plane round-trip;
   Step B is the concrete-resource decision. The step-4 demo's section 5 is the
   proof this split matters: a capability minted *before* `disable-tool` and
   still inside its TTL is denied on its next call. Collapsing them would break
   central revocation.

5. **`error.code` is a closed set of five** — `CAPABILITY_INVALID`,
   `CAPABILITY_EXPIRED`, `POLICY_DENIED`, `TOOL_DISABLED`, `EXECUTION_ERROR`.
   A test asserts the set. Do not add codes; map new failures onto these.

6. **An execution failure is not a denial.** `EXECUTION_ERROR` comes back in
   the same envelope shape but is not recorded as `TOOL_DENIED` — otherwise a
   crashing backend would pollute the denial evidence the §1.2 demo rests on.

7. **The acting task/agent come from the capability, not the caller.** Passing
   a different `task_id` alongside a capability does not change who the call is
   attributed to.

8. **No capability revocation list**, per §6.5 — and there is a test asserting
   it stays unbuilt. The 5-minute TTL plus the independently-enforced
   `tool_disabled` check are the whole revocation story for this slice.

9. **A denial is committed independently of the caller's transaction**, so a
   caller that later rolls back cannot erase the evidence that it was denied.

10. **Step A failure short-circuits Step B.** An expired capability emits
    `CAPABILITY_CHECKED` then `TOOL_DENIED` with **no** `POLICY_DECISION`
    between them — visible as `EVT0010`/`EVT0011` in the demo trace. Anything
    reading the trace should not assume the three events always come as a triple.

11. **The admin disable event is system-scoped** (`task_id` null), which is
    what step 3's decision 4 reserved that nullability for.

### Fix applied during integration

`test_only_disable_tool_exists_as_an_emergency_control` enumerated routes via
`app.routes`, but this FastAPI version returns `_IncludedRouter` wrappers with
no `.path`, so the test raised `AttributeError`. Switched to
`create_app().openapi()["paths"]`, which is the stable surface. The app itself
was correct — it exposes exactly `/login` and
`/admin/tools/{tool_name}/disable`. This was the only failure in the step.

### Phase-2 seams

| Seam | Extend by |
|---|---|
| Identity provider | Replace `app/identity/service.py`'s user lookup; the JWT contract above it is unchanged |
| Policy | `decide()` is pure and total — swap its body for OPA/Rego without touching the gateway |
| Tool backends | `register_backend(tool, fn)`; the gateway never learns what a backend does |
| Emergency controls | `tool_disabled` is one registry behind `get_registry()`/`set_registry()` |
| Capability revocation | Add a check inside Step A; the TTL contract stays as the floor |
## Step 5 — `execution-service` — NOT STARTED
## Step 6 — `data-plane-rag` — NOT STARTED
## Step 7 — `orchestrator` — NOT STARTED
## Step 8 — `artifact-pipeline` — NOT STARTED
## Step 9 — `cli` — NOT STARTED
