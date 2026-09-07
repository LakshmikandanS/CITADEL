"""The trusted workflow zone's single FastAPI process (design doc §2).

    "CLI-facing API - Query Router - Orchestrator - Control Plane (Identity,
     Policy, Capability, Approval) - Model Router - Data Plane [...]
     Consolidating them into one FastAPI process is an explicit MVP
     simplification for build speed."

Created by step 4 because §6.4's `/login` and §6.8's
`/admin/tools/{tool_name}/disable` are the first endpoints in the system. It is
deliberately a thin assembly point: **later steps add a router import and one
`include_router` line here**, and nothing else.

Endpoints mounted so far
------------------------
  POST /login                              §6.4  Identity
  POST /admin/tools/{tool_name}/disable    §6.8  Emergency control (admin only)
  POST /task                               §6.2  Query Router role (step 7)
  POST /internal/orchestrate               §6.2  Canonical handoff (step 7)
  GET  /tasks/{id}                         §6.2  Orchestrator, sole owner (step 7)
  GET  /tasks/{id}/trace                   §6.2  Orchestrator, sole owner (step 7)
  POST /approvals/{approval_id}/decision   §6.10 The one transactional endpoint (step 8)

The Tool Gateway is intentionally NOT an HTTP endpoint. §2 puts the agent loop
and the gateway in this same process and §6.6 defines the hop as an in-process
call; exposing it over HTTP would create a second, unauthenticated route to
every tool.

Startup registers the three real tool backends (`rag.search`,
`python.execute`, `generate_report`) and ingests the demo RAG corpus, exactly
once, the same way `tests/demos/step5_execution.py`/`step6_rag.py` do it by
hand for their own throwaway processes (§6.6 Step C, §6.9).
"""

from __future__ import annotations

from fastapi import FastAPI

from app.approval.router import router as approval_router
from app.identity.router import router as identity_router
from app.orchestrator.router import router as orchestrator_router
from app.orchestrator.startup import configure as configure_orchestrator
from app.policy.router import router as admin_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Citadel — Sovereign Agentic AI Workbench (MVP vertical slice)",
        version="0.8.0",
        description=(
            "Trusted workflow zone. Every endpoint derives the acting identity "
            "from the verified session JWT (§6.4); a client-supplied user_id or "
            "approver_id in a request body is ignored."
        ),
    )
    app.include_router(identity_router)
    app.include_router(admin_router)
    app.include_router(orchestrator_router)
    app.include_router(approval_router)

    @app.on_event("startup")
    def _startup() -> None:  # pragma: no cover -- exercised by running the app for real
        configure_orchestrator()

    return app


app = create_app()
