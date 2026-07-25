"""FastAPI application factory.

Thin by design: it mounts routers, middleware, and exception handlers. Business
logic lives in modules (05 §2). Routers are added here as each module lands.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.db import engine
from app.core.errors import register_exception_handlers
from app.core.ratelimit import RateLimitMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Startup/shutdown hook. Kept minimal; the pipeline runs in workers, not here.
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="ADERA API",
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    @app.get("/healthz", tags=["ops"])
    async def healthz() -> dict[str, object]:
        """Liveness + dependency check.

        Returns ok=False with per-dependency status rather than raising, so an
        uptime probe can distinguish "app down" from "Postgres down".
        """
        checks: dict[str, bool] = {}

        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["db"] = True
        except Exception:
            checks["db"] = False

        return {"ok": all(checks.values()), "checks": checks}

    register_exception_handlers(app)

    # Middleware. Order matters: Starlette runs them outermost-first, so the rate
    # limiter is added FIRST (making it outermost) and rejects a flood before CORS
    # or any router work happens.
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        # Cookie auth (05 §3) means credentialed cross-origin requests, which the
        # CORS spec forbids combining with a "*" origin -- hence the explicit list.
        allow_credentials=True,
        allow_methods=["*"],
        # X-CSRF-Token is the double-submit header; without it every unsafe request
        # from the browser client would be blocked by preflight, not by CSRF.
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    # Routers mounted here as modules land.
    from app.modules.identity.router import router as auth_router
    from app.modules.ingestion.router import router as tenders_router
    from app.modules.matching.router import router as matches_router
    from app.modules.runledger.router import router as runledger_router

    app.include_router(tenders_router)
    app.include_router(auth_router)
    app.include_router(matches_router)
    app.include_router(runledger_router)
    return app


app = create_app()
