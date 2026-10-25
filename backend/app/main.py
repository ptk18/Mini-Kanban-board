import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401  # registers every table on Base.metadata before create_all
from app.database import prepare_database
from app.routers import (
    ai,
    auth,
    boards,
    cards,
    checklist,
    columns,
    comments,
    dashboard,
    labels,
    members,
)
from app.services.auth import get_jwt_secret


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Refuse to serve anything without a usable signing secret.
    get_jwt_secret()
    prepare_database()
    yield


DEFAULT_CORS_ORIGINS = "http://localhost:3000"


def cors_origins() -> list[str]:
    """Browser origins allowed to call the API, from ``CORS_ORIGINS``
    (comma-separated). Defaults to the Next.js dev server."""
    raw = os.environ.get("CORS_ORIGINS", "")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or [DEFAULT_CORS_ORIGINS]


app = FastAPI(title="Mini Kanban API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth.router)
app.include_router(boards.router)
app.include_router(columns.router)
app.include_router(labels.router)
app.include_router(members.router)
app.include_router(dashboard.router)
app.include_router(ai.router)
app.include_router(cards.router)
app.include_router(checklist.router)
app.include_router(comments.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
