"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import dispose_engine, init_engine
from app.logging import configure_logging
from app.routers import (
    campaign_publication,
    campaigns,
    diagnostics,
    events,
    health,
    payouts,
    plans,
    platform_config,
    profiles,
    rewards,
    supporter,
    transactions,
    webhooks,
)

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, json_output=settings.environment != "local")
    init_engine(settings)

    log.info(
        "api_started",
        environment=settings.environment,
        program_id=settings.program_id,
        rpc=settings.solana_rpc_url,
    )
    try:
        yield
    finally:
        await dispose_engine()
        log.info("api_stopped")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Backr API",
        version="0.1.0",
        lifespan=lifespan,
        # Hide the schema explorer outside local dev.
        docs_url="/docs" if settings.environment == "local" else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(health.router)
    app.include_router(diagnostics.router)
    app.include_router(platform_config.router)
    app.include_router(profiles.router)
    app.include_router(plans.router)
    app.include_router(campaigns.router)
    app.include_router(campaign_publication.router)
    app.include_router(supporter.router)
    app.include_router(rewards.router)
    app.include_router(payouts.router)
    app.include_router(transactions.router)
    app.include_router(events.router)
    app.include_router(webhooks.router)

    return app


app = create_app()
