"""FastAPI application factory.

A factory rather than a module-level `app = FastAPI()`: tests need to build an
isolated instance with its own overrides, and a global would leak state between
them. Run it with `uvicorn agentlen.interfaces.http.app:create_app --factory`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from agentlen.interfaces.http.errors import register_error_handlers
from agentlen.interfaces.http.routers import ai, metrics, service

API_PREFIX = "/api/v1"

DESCRIPTION = """
Ingestion et exploration de traces d'agents de développement IA.

Conventions transverses :

* horodatages **ISO 8601 UTC**, durées en **millisecondes** ;
* une valeur inconnue est `null`, **jamais** `0` — les agrégats sont accompagnés
  d'un objet `coverage` ;
* toutes les erreurs partagent une enveloppe unique `{"error": {...}}` ;
* les listes sont paginées via `?limit=&offset=` et renvoient
  `{items, total, limit, offset}`.
"""


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Dispose the connection pool on shutdown.

    Without this, a reloading dev server leaks a pool per restart until
    Postgres refuses new connections.
    """
    yield
    engine: AsyncEngine | None = getattr(app.state, "engine", None)
    if engine is not None:
        await engine.dispose()


def create_app(*, engine: AsyncEngine | None = None) -> FastAPI:
    """Build the application.

    `engine` is an injection point for tests and for the eventual compose
    wiring; left as None, dependencies resolve one from DATABASE_URL.
    """
    app = FastAPI(
        title="AgentLen API",
        version="0.1.0",
        description=DESCRIPTION,
        summary="Traces d'agents IA : import, normalisation, indicateurs.",
        lifespan=_lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    if engine is not None:
        app.state.engine = engine

    register_error_handlers(app)

    # Service routes stay unprefixed as well as prefixed: orchestrators and
    # uptime probes conventionally hit /health, and API.md documents the
    # versioned path. Both point at the same handler.
    versioned = APIRouter(prefix=API_PREFIX)
    versioned.include_router(service.router)
    versioned.include_router(metrics.router)
    versioned.include_router(ai.router)
    app.include_router(versioned)
    app.include_router(service.router, include_in_schema=False)

    return app
