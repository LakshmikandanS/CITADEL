"""Central configuration for the Citadel trusted workflow zone.

Everything environment-driven lives here so that swapping an implementation
(SQLite -> Postgres, one hash strategy -> another) is a deployment change,
not a code change. Nothing in this module imports from the rest of `app`,
so it can be read by any component without creating a cycle.
"""

from __future__ import annotations

import os
from pathlib import Path

# Repository root (this file is at <root>/app/config.py)
ROOT_DIR = Path(__file__).resolve().parent.parent
VAR_DIR = ROOT_DIR / "var"


def _default_database_url() -> str:
    VAR_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(VAR_DIR / 'citadel.db').as_posix()}"


# --- Data Plane / persistence -------------------------------------------------
# design doc §8: "Postgres (or SQLite if faster to stand up)".
# SQLAlchemy is the seam: point this at postgresql+psycopg://... and nothing
# else in the codebase changes.
DATABASE_URL: str = os.environ.get("CITADEL_DATABASE_URL") or _default_database_url()

SQL_ECHO: bool = os.environ.get("CITADEL_SQL_ECHO", "").lower() in {"1", "true", "yes"}

# --- Observability ------------------------------------------------------------
# Which hash-chain strategy the single event writer uses. See
# app/observability/hashing.py for the registry of available strategies.
EVENT_HASH_STRATEGY: str = os.environ.get("CITADEL_EVENT_HASH_STRATEGY", "canonical_record_v1")

# previous_hash of the very first event in the chain. The design doc does not
# name a genesis value; 64 zeros is the conventional choice and is recorded
# here rather than buried in the writer.
GENESIS_HASH: str = "0" * 64
