"""Design doc section 9 -- Audit.

    [ ] Every event type in section 6.12's list is actually emitted at least
        once during the happy-path run
    [ ] /trace shows the denial-path event (TOOL_DENIED) and the
        emergency-control event, not only the happy path
    [ ] The hash chain is unbroken end to end for one full task run

The hash-chain third is fully testable after step 3 (foundation-schema) and is
covered here. The first two need a real run through the Orchestrator and the
CLI and are marked skip until steps 7 and 9 land.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models import Event
from app.observability import (
    ALL_EVENT_TYPES,
    ChainBroken,
    EventType,
    UnknownEventType,
    append_event,
    get_trace,
    verify_chain,
)
from app.observability import hashing
from app.observability.writer import EventWriter


# --------------------------------------------------------------------------
# Hash chain -- section 9 Audit, third checkbox
# --------------------------------------------------------------------------


def test_chain_is_unbroken_across_a_run_of_events(db, task):
    for event_type in ALL_EVENT_TYPES:
        append_event(task.task_id, "A123", event_type, {"note": event_type.lower()})

    events = get_trace(task.task_id)
    assert len(events) == len(ALL_EVENT_TYPES)
    assert verify_chain(task.task_id) is True


def test_each_event_links_to_its_predecessor(db, task):
    for i in range(5):
        append_event(task.task_id, "A123", EventType.ACTION_REQUESTED, {"i": i})

    events = get_trace(task.task_id)
    for previous, current in zip(events, events[1:]):
        assert current.previous_hash == previous.hash


def test_first_event_links_to_the_genesis_hash(db, task):
    from app import config

    event = append_event(task.task_id, None, EventType.TASK_CREATED, {})
    assert event.previous_hash == config.GENESIS_HASH
    assert event.event_id == "EVT0001"
    assert event.seq == 1


def test_event_ids_are_sequential_in_the_doc_format(db, task):
    for i in range(3):
        append_event(task.task_id, "A123", EventType.TOOL_EXECUTED, {"i": i})
    assert [e.event_id for e in get_trace(task.task_id)] == [
        "EVT0001",
        "EVT0002",
        "EVT0003",
    ]


def test_tampering_with_a_payload_breaks_the_chain(db, task):
    append_event(task.task_id, "A123", EventType.TOOL_DENIED, {"reason": "POLICY_DENIED"})
    append_event(task.task_id, "A123", EventType.STATE_COMMITTED, {})

    # Rewrite history directly in the table, bypassing the writer.
    row = db.execute(select(Event).where(Event.seq == 1)).scalar_one()
    row.payload = {"reason": "ALLOWED"}
    db.commit()

    with pytest.raises(ChainBroken, match="tampered content"):
        verify_chain(task.task_id)


def test_tampering_with_an_event_type_breaks_the_chain(db, task):
    """The demo's central claim is that a denial is recorded as a denial.
    Relabelling TOOL_DENIED as TOOL_EXECUTED must break the chain."""
    append_event(task.task_id, "A123", EventType.TOOL_DENIED, {"reason": "POLICY_DENIED"})
    append_event(task.task_id, "A123", EventType.STATE_COMMITTED, {})

    row = db.execute(select(Event).where(Event.seq == 1)).scalar_one()
    row.event_type = EventType.TOOL_EXECUTED
    db.commit()

    with pytest.raises(ChainBroken, match="tampered content"):
        verify_chain(task.task_id)


def test_deleting_an_event_breaks_the_chain(db, task):
    for i in range(3):
        append_event(task.task_id, "A123", EventType.ACTION_REQUESTED, {"i": i})

    row = db.execute(select(Event).where(Event.seq == 2)).scalar_one()
    db.delete(row)
    db.commit()

    with pytest.raises(ChainBroken, match="sequence gap"):
        verify_chain(task.task_id)


def test_chain_spans_tasks_and_system_scoped_events(db, task):
    """An admin DISABLE TOOL has no task_id; it must still be in the one
    chain, and a per-task trace must not be mistaken for the whole chain."""
    append_event(task.task_id, "A123", EventType.TASK_CREATED, {})
    append_event(None, "U-admin", EventType.POLICY_DECISION, {"tool_disabled": True})
    append_event(task.task_id, "A123", EventType.TOOL_DENIED, {})

    assert len(get_trace(task.task_id)) == 2
    assert len(get_trace(None)) == 3
    assert verify_chain(task.task_id) is True


# --------------------------------------------------------------------------
# Writer contract -- foundation-schema's own "Done when"
# --------------------------------------------------------------------------


def test_writer_rejects_an_event_type_outside_the_vocabulary(db, task):
    with pytest.raises(UnknownEventType):
        append_event(task.task_id, "A123", "TOOL_MAYBE_ALLOWED", {})


def test_event_can_be_enlisted_in_a_callers_transaction(db, task):
    """Section 6.10 needs Approval + Artifact + Task + two events in one
    commit; a rollback must take the events with it."""
    session = db
    append_event(task.task_id, "A123", EventType.APPROVAL_GRANTED, {}, session=session)
    session.rollback()
    assert get_trace(task.task_id) == []


def test_append_event_is_the_only_writer_to_the_event_table():
    """Grep the application for direct Event inserts. Only writer.py may
    construct an Event row -- foundation-schema's "Done when" asks for exactly
    one such code path, so this asserts it rather than trusting convention."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    # `Event(` as a constructor call, not `class Event(Base)` and not an
    # annotation like `-> Event:` or `list[Event]`.
    construction = re.compile(r"(?<!class )(?<![\w.\[])Event\(")

    offenders = []
    for path in (root / "app").rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel == "app/observability/writer.py":
            continue  # the one sanctioned writer
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("*"):
                continue
            if construction.search(line) and not stripped.startswith("class Event"):
                offenders.append(f"{rel}:{lineno}")
    assert offenders == [], f"direct Event construction outside the writer: {offenders}"


# --------------------------------------------------------------------------
# Hash strategy seam
# --------------------------------------------------------------------------


@pytest.mark.parametrize("strategy_name", hashing.available())
def test_every_hash_strategy_produces_a_verifiable_chain(db, strategy_name):
    """The strategy is swappable (config.EVENT_HASH_STRATEGY); whichever is
    selected must write and verify a consistent chain."""
    from app.observability import writer as writer_module

    previous = writer_module.set_writer(EventWriter(strategy_name=strategy_name))
    try:
        append_event("T123", "A123", EventType.TASK_CREATED, {"s": strategy_name})
        append_event("T123", "A123", EventType.TOOL_EXECUTED, {"s": strategy_name})
        assert verify_chain("T123") is True
    finally:
        writer_module.set_writer(previous)


def test_literal_formula_does_not_bind_event_type_but_default_does():
    """Documents exactly what the default strategy buys over the doc-literal
    one, so the choice stays visible rather than folklore."""
    record_denied = {
        "event_id": "EVT0001",
        "task_id": "T123",
        "actor_id": "A123",
        "event_type": "TOOL_DENIED",
        "payload": {"reason": "POLICY_DENIED"},
        "timestamp": "2026-09-06T10:00:00+00:00",
    }
    record_executed = dict(record_denied, event_type="TOOL_EXECUTED")
    prev = "0" * 64

    literal = hashing.get_strategy("payload_only_v1")
    canonical = hashing.get_strategy("canonical_record_v1")

    assert literal(record_denied, prev) == literal(record_executed, prev)
    assert canonical(record_denied, prev) != canonical(record_executed, prev)


# --------------------------------------------------------------------------
# Not yet buildable -- these need steps 7 and 9
# --------------------------------------------------------------------------


@pytest.mark.skip(reason="needs the Orchestrator (step 7) and CLI (step 9)")
def test_every_event_type_emitted_during_the_happy_path_run():
    """Section 9 Audit: every type in section 6.12's list emitted at least
    once during one happy-path run."""


@pytest.mark.skip(reason="needs the CLI /trace (step 9)")
def test_trace_shows_denial_and_emergency_control_events():
    """Section 9 Audit: /trace shows TOOL_DENIED and the emergency-control
    event, not only the happy path."""
