"""FastAPI application factory.

Thin by design: it mounts routers, middleware, and exception handlers. Business
logic lives in modules (05 §2). Routers are added here as each module lands.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import settings
from app.core.db import engine
from app.core.errors import register_exception_handlers


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
