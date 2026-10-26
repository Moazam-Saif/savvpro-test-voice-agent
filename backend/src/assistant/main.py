"""
main.py – FastAPI application factory.

Single uvicorn worker.  CORS, routers, global exception handler, startup hook.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from assistant.api.routes import demo_router, router
from assistant.clock import FixedClock, SystemClock
from assistant.config import settings
from assistant.domain.codes import CodeGenerator
from assistant.domain.repository import InMemoryBookingRepository
from assistant.domain.seed import build_closed_dates, seed_repository
from assistant.domain.service import BookingService
from assistant.sessions import SessionStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup: build the domain objects and seed fake data."""
    tz = ZoneInfo(settings.clinic_tz)

    # Clock
    if settings.assistant_now:
        from datetime import datetime
        pinned_dt = datetime.fromisoformat(settings.assistant_now)
        clock = FixedClock(at=pinned_dt)
        logger.info("Clock pinned to %s", settings.assistant_now)
    else:
        clock = SystemClock()

    # Domain
    closed_dates = build_closed_dates(clock, tz)
    code_gen = CodeGenerator(seed=None)
    repo = InMemoryBookingRepository()
    booking_service = BookingService(
        repository=repo,
        clock=clock,
        tz=tz,
        closed_dates=closed_dates,
        code_gen=code_gen,
    )

    # Seed
    seeded = seed_repository(repo, clock, tz, closed_dates, code_gen)
    logger.info("Seeded %d fake bookings", len(seeded))

    # Session store
    session_store = SessionStore()

    # Attach to app state
    app.state.clock = clock
    app.state.tz = tz
    app.state.closed_dates = closed_dates
    app.state.booking_service = booking_service
    app.state.session_store = session_store

    yield   # App runs here

    logger.info("Shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Bright Smile Dental Voice Assistant",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(router)
    if settings.demo_endpoints_enabled:
        app.include_router(demo_router)

    # Global exception handler (the brain never raises, but the API layer might)
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "type": type(exc).__name__},
        )

    return app


app = create_app()
