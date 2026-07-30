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

    # The web client is a separate origin (Next.js on :3000), so the session and
    # CSRF cookies only travel if credentialed CORS is on and the origin is
    # named explicitly -- the spec forbids "*" with credentials.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
    from app.modules.eligibility.router import router as eligibility_router
    from app.modules.identity.router import router as auth_router
    from app.modules.ingestion.router import router as tenders_router
    from app.modules.matching.router import router as matches_router
    from app.modules.profiles.router import router as profiles_router
    from app.modules.runledger.router import router as runledger_router

    app.include_router(tenders_router)
    app.include_router(auth_router)
    app.include_router(matches_router)
    app.include_router(profiles_router)
    app.include_router(eligibility_router)
    app.include_router(runledger_router)
    return app


app = create_app()
