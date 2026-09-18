from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from app.schemas.common import as_utc

NAME_MIN_LENGTH = 1
NAME_MAX_LENGTH = 100


def _validate_name(value: str) -> str:
    value = value.strip()
    if not NAME_MIN_LENGTH <= len(value) <= NAME_MAX_LENGTH:
        raise ValueError(f"name must be {NAME_MIN_LENGTH}-{NAME_MAX_LENGTH} characters")
    return value


class ColumnCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return _validate_name(value)


class ColumnUpdate(BaseModel):
    """Partial update; ``position`` is the target index within the board
    (0-based, contiguous), its upper bound is checked by the router."""

    name: str | None = None
    position: int | None = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _validate_name(value)

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "ColumnUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one of name, position is required")
        return self


class ColumnOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    board_id: int
    name: str
    position: int
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_utc(self, value: datetime) -> datetime:
        return as_utc(value)
