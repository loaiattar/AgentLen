"""FastAPI application factory.

A factory rather than a module-level `app = FastAPI()`: tests need to build an
isolated instance with its own overrides, and a global would leak state between
them. Run it with `uvicorn agentlen.interfaces.http.app:create_app --factory`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine

from agentlen.infrastructure.config.settings import Settings, load_settings
from agentlen.interfaces.http.auth import ApiKeyMiddleware
from agentlen.interfaces.http.errors import register_error_handlers
from agentlen.interfaces.http.routers import (
    ai,
    data_sources,
    exploration,
    files,
    imports,
    mappings,
    metrics,
    service,
)

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


def create_app(*, engine: AsyncEngine | None = None, settings: Settings | None = None) -> FastAPI:
    """Build the application.

    `engine` is an injection point for tests and for the eventual compose
    wiring; left as None, dependencies resolve one from DATABASE_URL.
    `settings` is the same for auth and CORS: tests pass an isolated instance
    rather than mutating process-wide environment.
    """
    resolved = settings or load_settings()
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
    app.state.settings = resolved

    if engine is not None:
        app.state.engine = engine

    register_error_handlers(app)

    # Last added runs first. CORS must wrap auth so a preflight (no API key)
    # is answered here, and so a 401 still carries Access-Control-* headers.
    app.add_middleware(ApiKeyMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.allowed_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["X-API-Key", "Content-Type"],
    )

    # Service routes stay unprefixed as well as prefixed: orchestrators and
    # uptime probes conventionally hit /health, and API.md documents the
    # versioned path. Both point at the same handler.
    versioned = APIRouter(prefix=API_PREFIX)
    versioned.include_router(service.router)
    versioned.include_router(metrics.router)
    versioned.include_router(ai.router)
    versioned.include_router(data_sources.router)
    versioned.include_router(files.router)
    versioned.include_router(imports.router)
    versioned.include_router(mappings.router)
    versioned.include_router(exploration.router)

    app.include_router(versioned)
    app.include_router(service.router, include_in_schema=False)

    return app
