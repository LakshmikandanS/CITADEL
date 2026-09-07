# Citadel MVP — Build Log

Running record of what each build-order step (AGENTS.md §6) actually produced,
and the decisions later steps must not contradict.

`docs/CITADEL_MVP_DESIGN.md` remains the frozen contract. This file records
*implementation* decisions made underneath it — it never overrides it.

---

## Environment

- Python 3.12.5, venv at `.venv/` — **use `.venv/Scripts/python`**, not the system Python.
- Installed: `sqlalchemy>=2.0`, `pydantic>=2`, `pytest`.
- Database: SQLite at `var/citadel.db`, selected by `CITADEL_DATABASE_URL`.
  Point that at Postgres and nothing else changes (design doc §8 permits either).
- **Ollama is not installed** — step 7 (Orchestrator) needs it for reasoning +
  embeddings per §8. Install and pull models before starting step 7.
- **Docker daemon is not running** — step 5 (Execution Service) needs it. Start
  Docker Desktop before starting step 5.

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

## Step 4 — `security-control-plane` — NOT STARTED
## Step 5 — `execution-service` — NOT STARTED
## Step 6 — `data-plane-rag` — NOT STARTED
## Step 7 — `orchestrator` — NOT STARTED
## Step 8 — `artifact-pipeline` — NOT STARTED
## Step 9 — `cli` — NOT STARTED
