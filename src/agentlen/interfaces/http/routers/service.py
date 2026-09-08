"""Service routes: liveness, readiness, version.

The distinction between the first two is operational, not cosmetic:

- `/health` answers "is this process alive?" and touches nothing. An
  orchestrator restarts the container when it fails, so a dependency check here
  would restart the API every time Postgres hiccuped.
- `/health/ready` answers "can this process serve traffic?" and does check
  dependencies. Failing it removes the instance from the load balancer without
  killing it.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from agentlen.infrastructure.persistence.health import check_database, head_revision
from agentlen.interfaces.http.dependencies import EngineDep

router = APIRouter(tags=["service"])

APP_VERSION = "0.1.0"


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class CheckResult(BaseModel):
    status: Literal["ok", "error", "stale", "unknown"]
    detail: str | None = None


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, CheckResult] = Field(
        description="One entry per dependency. `unknown` never blocks readiness."
    )


class VersionResponse(BaseModel):
    version: str = Field(description="Application version.")
    alembic_revision: str | None = Field(
        description="Schema revision currently applied to the database."
    )
    alembic_head: str | None = Field(description="Newest revision available on disk.")


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness — the process is up",
)
async def health() -> HealthResponse:
    """Never touches the database: this answer must not depend on anything."""
    return HealthResponse()


@router.get(
    "/health/ready",
    response_model=ReadyResponse,
    summary="Readiness — dependencies are reachable and the schema is current",
    responses={503: {"description": "A dependency is unavailable or the schema is stale."}},
)
async def health_ready(engine: EngineDep, response: Response) -> ReadyResponse:
    db = await check_database(engine)

    checks: dict[str, CheckResult] = {
        "database": CheckResult(
            status="ok" if db.reachable else "error",
            detail=None if db.reachable else f"unreachable ({db.error})",
        ),
        "migrations": CheckResult(
            status="ok" if db.migrations_up_to_date else "stale",
            detail=f"applied={db.current_revision or 'none'} head={db.head_revision or 'unknown'}",
        ),
        # Reported, but deliberately not blocking: there is no worker yet (#55),
        # and failing readiness over an unbuilt component would be dishonest.
        "worker": CheckResult(status="unknown", detail="not implemented until #55"),
    }

    if not db.is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyResponse(status="not_ready", checks=checks)
    return ReadyResponse(status="ready", checks=checks)


@router.get(
    "/version",
    response_model=VersionResponse,
    summary="Application version and applied schema revision",
)
async def version(engine: EngineDep) -> VersionResponse:
    """The applied revision is read from the database, not assumed from disk:
    knowing which schema is actually live is the point of the endpoint."""
    db = await check_database(engine)
    return VersionResponse(
        version=APP_VERSION,
        alembic_revision=db.current_revision,
        alembic_head=db.head_revision or head_revision(),
    )


def openapi_extra() -> dict[str, Any]:  # pragma: no cover - documentation helper
    return {}
