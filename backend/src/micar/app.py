"""FastAPI ASGI application."""

from __future__ import annotations

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from micar.api import agents as agents_api
from micar.api import anchors as anchors_api
from micar.api import artifacts as artifacts_api
from micar.api import audit as audit_api
from micar.api import auth as auth_api
from micar.api import intake as intake_api
from micar.api import mandates as mandates_api
from micar.config import get_settings

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

log = structlog.get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="MiCAR Authorization Co-Pilot",
        version="0.1.0",
        description="Internal tool for ART/EMT/CASP licensing packages.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_api.router)
    app.include_router(mandates_api.router)
    app.include_router(intake_api.router)
    app.include_router(agents_api.router)
    app.include_router(anchors_api.router)
    app.include_router(artifacts_api.router)
    app.include_router(audit_api.router)

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    log.info("micar.startup", cors_origins=settings.cors_origins_list)
    return app


app = create_app()
