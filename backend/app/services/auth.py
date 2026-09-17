"""Password hashing, access tokens and the ``get_current_user`` dependency.

This is the only module that touches ``bcrypt`` or ``jwt``; routers go through
the functions below.
"""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

ACCESS_TOKEN_TTL = timedelta(hours=24)
JWT_ALGORITHM = "HS256"
BCRYPT_ROUNDS = 12
# PyJWT warns (InsecureKeyLengthWarning) for HMAC-SHA256 keys under 32 bytes
# (RFC 7518 section 3.2); refusing shorter secrets keeps that warning out.
JWT_SECRET_MIN_LENGTH = 32
# bcrypt reads at most 72 bytes; bcrypt 5 raises rather than truncating.
BCRYPT_MAX_PASSWORD_BYTES = 72

bearer_scheme = HTTPBearer()


def get_jwt_secret() -> str:
    """The HS256 signing secret from ``JWT_SECRET``, read at call time.

    There is deliberately no development default: a baked-in string would sign
    every token with a public key. Fail loudly instead.
    """
    secret = os.environ.get("JWT_SECRET", "")
    if len(secret) < JWT_SECRET_MIN_LENGTH:
        raise RuntimeError(
            "JWT_SECRET must be set to a string of at least "
            f"{JWT_SECRET_MIN_LENGTH} characters"
        )
    return secret


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    raw = password.encode("utf-8")
    # Signup rejects anything over 72 bytes, so no stored hash can match such a
    # password; checkpw would raise ValueError on it instead of returning False.
    if len(raw) > BCRYPT_MAX_PASSWORD_BYTES:
        return False
    return bcrypt.checkpw(raw, password_hash.encode("ascii"))


def create_access_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    ttl = ACCESS_TOKEN_TTL if expires_delta is None else expires_delta
    # PyJWT 2.14 rejects a non-string "sub" on decode, hence str(user_id).
    claims = {"sub": str(user_id), "iat": now, "exp": now + ttl}
    return jwt.encode(claims, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """Return the user id carried by ``token`` or raise ``jwt.InvalidTokenError``."""
    payload = jwt.decode(
        token,
        get_jwt_secret(),
        algorithms=[JWT_ALGORITHM],
        options={"require": ["exp", "sub"]},
    )
    try:
        return int(payload["sub"])
    except ValueError as exc:
        raise jwt.InvalidTokenError("Subject is not a user id") from exc


def _invalid_token_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        user_id = decode_access_token(credentials.credentials)
    except jwt.InvalidTokenError:
        raise _invalid_token_error() from None
    user = db.get(User, user_id)
    if user is None:
        raise _invalid_token_error()
    return user
