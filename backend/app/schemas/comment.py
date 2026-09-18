from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.schemas.common import as_utc

CONTENT_MIN_LENGTH = 1
CONTENT_MAX_LENGTH = 5000


def _validate_content(value: str) -> str:
    value = value.strip()
    if not CONTENT_MIN_LENGTH <= len(value) <= CONTENT_MAX_LENGTH:
        raise ValueError(
            f"content must be {CONTENT_MIN_LENGTH}-{CONTENT_MAX_LENGTH} characters"
        )
    return value


class CommentCreate(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def _content(cls, value: str) -> str:
        return _validate_content(value)


class CommentUpdate(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def _content(cls, value: str) -> str:
        return _validate_content(value)


class AuthorOut(BaseModel):
    """The subset of ``User`` a comment exposes. No email: other members only
    need a name to show next to the comment."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    card_id: int
    author: AuthorOut = Field(validation_alias="user")
    content: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def _serialize_utc(self, value: datetime) -> datetime:
        return as_utc(value)
