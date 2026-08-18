"""SecureLock API entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import audit as audit_routes
from app.api import auth as auth_routes
from app.api import papers as paper_routes
from app.api import questions as question_routes
from app.config import settings
from app.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("securelock")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    settings.resolve_contract_addresses()
    logger.info("SecureLock API starting (%s)", settings.environment)
    logger.info("Database: %s", settings.database_url.split("://")[0])
    if settings.question_contract_address:
        logger.info("QuestionRegistry: %s", settings.question_contract_address)
        logger.info("PaperTimeLock:    %s", settings.paper_contract_address)
    else:
        logger.warning(
            "Contracts not deployed. Run: cd blockchain && npm run deploy:local"
        )
    yield


app = FastAPI(
    title="SecureLock API",
    version="1.0.0",
    description=(
        "Blockchain-backed examination paper security.\n\n"
        "Question content is AES-256-GCM encrypted at rest and never returned "
        "without an authorised, audited read. Final paper release is gated by a "
        "smart contract that evaluates `block.timestamp` -- never the client clock."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Never leak a stack trace to a client; never crash the process."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. The incident has been logged."},
    )


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


for router in (auth_routes.router, question_routes.router, paper_routes.router, audit_routes.router):
    app.include_router(router, prefix=settings.api_prefix)
