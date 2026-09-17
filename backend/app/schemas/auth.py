import re
from typing import Literal

from pydantic import BaseModel, field_validator

from app.schemas.user import UserOut

# A shape check, not RFC 5322: exactly one "@" with non-empty text on both sides,
# no whitespace, and a "." somewhere in the domain part.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
EMAIL_MIN_LENGTH = 3
EMAIL_MAX_LENGTH = 254
# bcrypt reads at most 72 bytes of input, and bcrypt 5 raises instead of truncating.
PASSWORD_MIN_BYTES = 8
PASSWORD_MAX_BYTES = 72
DISPLAY_NAME_MIN_LENGTH = 1
DISPLAY_NAME_MAX_LENGTH = 100


def normalise_email(value: str) -> str:
    return value.strip().lower()


class SignupRequest(BaseModel):
    email: str
    password: str
    display_name: str

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        value = normalise_email(value)
        if not EMAIL_MIN_LENGTH <= len(value) <= EMAIL_MAX_LENGTH:
            raise ValueError(
                f"email must be {EMAIL_MIN_LENGTH}-{EMAIL_MAX_LENGTH} characters"
            )
        if not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("email must look like name@domain.tld")
        return value

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        size = len(value.encode("utf-8"))
        if not PASSWORD_MIN_BYTES <= size <= PASSWORD_MAX_BYTES:
            raise ValueError(
                f"password must be {PASSWORD_MIN_BYTES}-{PASSWORD_MAX_BYTES} bytes of UTF-8"
            )
        return value

    @field_validator("display_name")
    @classmethod
    def _validate_display_name(cls, value: str) -> str:
        value = value.strip()
        if not DISPLAY_NAME_MIN_LENGTH <= len(value) <= DISPLAY_NAME_MAX_LENGTH:
            raise ValueError(
                f"display_name must be {DISPLAY_NAME_MIN_LENGTH}-{DISPLAY_NAME_MAX_LENGTH} "
                "characters"
            )
        return value


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        # No shape check: a malformed email is a failed login, not a 422.
        return normalise_email(value)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserOut
