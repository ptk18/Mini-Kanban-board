from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.schemas.auth import normalise_email
from app.schemas.board import BoardOut
from app.schemas.common import as_utc


class MemberOut(BaseModel):
    """One ``board_members`` row with the user's public fields. Email is
    included: members of a private board share it to invite each other."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    email: str = Field(validation_alias="user_email")
    display_name: str = Field(validation_alias="user_display_name")
    role: Literal["owner", "member"]
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_utc(self, value: datetime) -> datetime:
        return as_utc(value)


class InviteByEmail(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _normalise(cls, value: str) -> str:
        # Same normalisation as login: a malformed email is simply "no such user".
        return normalise_email(value)


class InviteOut(BaseModel):
    board_id: int
    invite_token: str
    # The frontend route that consumes the token (#11 / #23).
    invite_path: str


class JoinOut(BaseModel):
    board: BoardOut
    joined: bool
