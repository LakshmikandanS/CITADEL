"""Shared fixtures.

The database URL is set here, before any `app` module is imported, so the
suite never touches the developer's working database.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TEST_DB = Path(tempfile.gettempdir()) / "citadel_test.db"
os.environ.setdefault("CITADEL_DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")

import pytest  # noqa: E402

from app.db import init_db  # noqa: E402
from app.db.engine import SessionLocal  # noqa: E402
from app.db.models import Task, User  # noqa: E402
from app.db.state_machines import Classification, Role  # noqa: E402


@pytest.fixture
def db():
    """A clean schema for every test. The event chain is global state by
    design, so it has to start empty or one test's chain would extend
    another's."""
    init_db.reset()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def engineer(db):
    user = User(
        user_id="U123",
        username="j.rao",
        roles=[Role.ENGINEER],
        clearance=Classification.CONFIDENTIAL,
        department="maintenance",
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def task(db, engineer):
    row = Task(
        task_id="T123",
        user_id=engineer.user_id,
        classification=Classification.CONFIDENTIAL,
        requirements={"needs_rag": True, "needs_document_generation": True},
    )
    db.add(row)
    db.commit()
    return row
