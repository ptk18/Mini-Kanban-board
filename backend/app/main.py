from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.models  # noqa: F401  # registers every table on Base.metadata before create_all
from app.database import create_all
from app.routers import (
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
    create_all()
    yield


app = FastAPI(title="Mini Kanban API", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(boards.router)
app.include_router(columns.router)
app.include_router(labels.router)
app.include_router(members.router)
app.include_router(dashboard.router)
app.include_router(cards.router)
app.include_router(checklist.router)
app.include_router(comments.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
