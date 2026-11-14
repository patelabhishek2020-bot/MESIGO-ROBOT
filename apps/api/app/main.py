"""Mesigo AI FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import agents, approvals, audit, auth, brain, interface, monitor, system, wizard
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.db.session import AsyncSessionLocal
from app.middleware.security import RequestContextMiddleware, SecurityHeadersMiddleware
from app.services.bootstrap import ensure_bootstrap

setup_logging()
logger = get_logger("main")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("startup", app=settings.app_name, version=__version__, env=settings.environment)
    async with AsyncSessionLocal() as session:
        try:
            await ensure_bootstrap(session)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("bootstrap_failed")
            raise
    yield
    logger.info("shutdown")


app = FastAPI(
    title="Mesigo AI API",
    description="Import-Export Business Operating System — Central Brain & foundation APIs",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)

register_exception_handlers(app)

app.include_router(system.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(wizard.router, prefix="/api/v1")
app.include_router(brain.router, prefix="/api/v1")
app.include_router(agents.router, prefix="/api/v1")
app.include_router(approvals.router, prefix="/api/v1")
app.include_router(interface.router, prefix="/api/v1")
app.include_router(monitor.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "app": settings.app_name,
        "version": __version__,
        "docs": "/docs" if not settings.is_production else None,
        "health": "/health",
    }
