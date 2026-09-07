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

Still to be mounted by their owning steps
-----------------------------------------
  POST /task, GET /tasks/{id}, GET /tasks/{id}/trace   step 7 (Orchestrator,
        the sole owner of task status per §6.2/C-005)
  POST /approvals/{approval_id}/decision              step 8 (§6.10)

The Tool Gateway is intentionally NOT an HTTP endpoint. §2 puts the agent loop
and the gateway in this same process and §6.6 defines the hop as an in-process
call; exposing it over HTTP would create a second, unauthenticated route to
every tool.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.identity.router import router as identity_router
from app.policy.router import router as admin_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Citadel — Sovereign Agentic AI Workbench (MVP vertical slice)",
        version="0.4.0",
        description=(
            "Trusted workflow zone. Every endpoint derives the acting identity "
            "from the verified session JWT (§6.4); a client-supplied user_id or "
            "approver_id in a request body is ignored."
        ),
    )
    app.include_router(identity_router)
    app.include_router(admin_router)
    return app


app = create_app()
