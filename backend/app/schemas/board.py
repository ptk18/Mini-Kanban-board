from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

from app.schemas.column import ColumnOut
from app.schemas.common import as_utc

NAME_MIN_LENGTH = 1
NAME_MAX_LENGTH = 100


def _validate_name(value: str) -> str:
    value = value.strip()
    if not NAME_MIN_LENGTH <= len(value) <= NAME_MAX_LENGTH:
        raise ValueError(f"name must be {NAME_MIN_LENGTH}-{NAME_MAX_LENGTH} characters")
    return value


class BoardCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _validate_name(value)


class BoardUpdate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _validate_name(value)


class BoardOut(BaseModel):
    """A board as the calling user sees it; ``role`` is theirs, not a column
    of the table, so the router fills it in."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    role: Literal["owner", "member"]
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def _serialize_utc(self, value: datetime) -> datetime:
        return as_utc(value)


class BoardDetailOut(BoardOut):
    columns: list[ColumnOut]
