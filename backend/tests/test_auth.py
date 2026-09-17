from datetime import timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.services.auth as auth_service
from app.main import app as fastapi_app
from app.models import User
from app.services.auth import (
    ACCESS_TOKEN_TTL,
    create_access_token,
    decode_access_token,
    get_jwt_secret,
    hash_password,
    verify_password,
)

JWT_SECRET = "test-only-jwt-secret-not-for-production-0123456789"
SIGNUP_BODY = {
    "email": "Ada@Example.com ",
    "password": "correct horse",
    "display_name": " Ada ",
}
USER_OUT_KEYS = {"id", "email", "display_name", "created_at"}
SECRET_KEYS = {"password", "password_hash"}


def signup(client: TestClient, **overrides):
    return client.post("/auth/signup", json={**SIGNUP_BODY, **overrides})


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def assert_unauthorized(response, detail: str) -> None:
    assert response.status_code == 401
    assert response.json() == {"detail": detail}
    assert response.headers["WWW-Authenticate"] == "Bearer"


# --- POST /auth/signup -------------------------------------------------------


def test_signup_creates_user_and_returns_token(client, session):
    response = signup(client)

    assert response.status_code == 201
    body = response.json()
    assert body.keys() == {"access_token", "token_type", "user"}
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str)
    assert body["user"].keys() == USER_OUT_KEYS
    assert body["user"]["id"] == 1
    assert body["user"]["email"] == "ada@example.com"
    assert body["user"]["display_name"] == "Ada"
    assert body["user"]["created_at"].endswith(("Z", "+00:00"))
    assert not SECRET_KEYS & body.keys()
    assert not SECRET_KEYS & body["user"].keys()

    user = session.get(User, 1)
    assert user.email == "ada@example.com"
    assert user.display_name == "Ada"
    assert user.password_hash.startswith("$2b$")
    assert user.password_hash != "correct horse"
    assert decode_access_token(body["access_token"]) == user.id


def test_signup_same_password_gets_different_hashes(client, session):
    assert signup(client).status_code == 201
    assert signup(client, email="bob@example.com").status_code == 201

    hashes = session.scalars(select(User.password_hash)).all()
    assert len(hashes) == 2
    assert hashes[0] != hashes[1]
    assert all(verify_password("correct horse", h) for h in hashes)


@pytest.mark.parametrize(
    "email", ["ada@example.com", "ADA@example.com", "  Ada@Example.com\t"]
)
def test_signup_duplicate_email_returns_409(client, session, email):
    assert signup(client).status_code == 201

    response = signup(client, email=email, display_name="Other")

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}
    assert session.scalar(select(User).where(User.email == "ada@example.com"))
    assert len(session.scalars(select(User)).all()) == 1


def test_signup_maps_concurrent_insert_integrity_error_to_409(client, session):
    """The unique-constraint race: the SELECT sees nothing but the INSERT fails."""
    assert signup(client).status_code == 201
    original_scalar = session.scalar

    def scalar_returning_none_once(*args, **kwargs):
        session.scalar = original_scalar
        return None

    # The request runs on this same session (client fixture), so the router's
    # pre-check SELECT is the patched call; only the commit sees the duplicate.
    session.scalar = scalar_returning_none_once
    try:
        response = signup(client)
    finally:
        session.scalar = original_scalar

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}
    assert not session.in_transaction()
    assert len(session.scalars(select(User)).all()) == 1


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"email": "not-an-email"}, id="email-without-at"),
        pytest.param({"email": "a@b"}, id="email-without-dot-in-domain"),
        pytest.param({"email": "a@@b.com"}, id="email-two-ats"),
        pytest.param({"email": "a b@example.com"}, id="email-with-space"),
        pytest.param({"email": "@example.com"}, id="email-empty-local-part"),
        pytest.param({"email": "a@" + "b" * 250 + ".com"}, id="email-too-long"),
        pytest.param({"password": "1234567"}, id="password-7-bytes"),
        pytest.param({"password": "a" * 73}, id="password-73-bytes"),
        pytest.param({"password": "\U0001f511" * 19}, id="password-76-bytes-emoji"),
        pytest.param({"display_name": "   "}, id="display-name-blank"),
        pytest.param({"display_name": "x" * 101}, id="display-name-too-long"),
    ],
)
def test_signup_rejects_invalid_body_with_422(client, session, overrides):
    response = signup(client, **overrides)

    assert response.status_code == 422
    assert list(response.json().keys()) == ["detail"]
    assert isinstance(response.json()["detail"], list)
    assert session.scalars(select(User)).all() == []


@pytest.mark.parametrize("missing", ["email", "password", "display_name"])
def test_signup_missing_field_returns_422(client, missing):
    body = {k: v for k, v in SIGNUP_BODY.items() if k != missing}

    response = client.post("/auth/signup", json=body)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", missing]


def test_signup_accepts_boundary_passwords(client):
    assert signup(client, password="12345678").status_code == 201
    assert (
        signup(client, email="b@example.com", password="a" * 72).status_code == 201
    )
    assert (
        signup(client, email="c@example.com", password="\U0001f511" * 18).status_code
        == 201
    )


def test_signup_ignores_unknown_keys(client):
    response = signup(client, is_admin=True)

    assert response.status_code == 201
    assert "is_admin" not in response.json()["user"]


# --- POST /auth/login --------------------------------------------------------


def test_login_returns_token_for_normalised_email(client):
    user_id = signup(client).json()["user"]["id"]

    response = client.post(
        "/auth/login", json={"email": "ADA@example.com", "password": "correct horse"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body.keys() == {"access_token", "token_type", "user"}
    assert body["token_type"] == "bearer"
    assert body["user"].keys() == USER_OUT_KEYS
    assert body["user"]["id"] == user_id
    assert not SECRET_KEYS & body.keys()
    assert not SECRET_KEYS & body["user"].keys()
    assert decode_access_token(body["access_token"]) == user_id


def test_login_wrong_password_and_unknown_email_are_indistinguishable(client):
    signup(client)

    wrong = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "wrong horse"}
    )
    unknown = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "correct horse"}
    )
    malformed = client.post(
        "/auth/login", json={"email": "not an email", "password": "correct horse"}
    )

    for response in (wrong, unknown, malformed):
        assert_unauthorized(response, "Invalid email or password")
    assert wrong.json() == unknown.json() == malformed.json()
    assert wrong.headers["WWW-Authenticate"] == unknown.headers["WWW-Authenticate"]


def test_login_with_over_72_byte_password_is_401_not_500(client):
    signup(client)

    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "a" * 100}
    )

    assert_unauthorized(response, "Invalid email or password")


@pytest.mark.parametrize("missing", ["email", "password"])
def test_login_missing_field_returns_422(client, missing):
    body = {k: v for k, v in {"email": "a@b.co", "password": "pw"}.items() if k != missing}

    response = client.post("/auth/login", json=body)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", missing]


# --- GET /auth/me ------------------------------------------------------------


def test_me_returns_user_out_for_signup_and_login_tokens(client):
    signup_token = signup(client).json()["access_token"]
    login_token = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "correct horse"}
    ).json()["access_token"]

    for token in (signup_token, login_token):
        response = client.get("/auth/me", headers=auth_header(token))

        assert response.status_code == 200
        body = response.json()
        assert body.keys() == USER_OUT_KEYS
        assert body == {
            "id": 1,
            "email": "ada@example.com",
            "display_name": "Ada",
            "created_at": body["created_at"],
        }
        assert body["created_at"].endswith(("Z", "+00:00"))
        assert not SECRET_KEYS & body.keys()


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="no-header"),
        pytest.param({"Authorization": "Basic YWRhOnB3"}, id="basic-scheme"),
        pytest.param({"Authorization": "Bearer"}, id="bearer-without-token"),
        pytest.param({"Authorization": "Bearer "}, id="bearer-with-trailing-space"),
    ],
)
def test_me_without_bearer_credentials_is_not_authenticated(client, headers):
    response = client.get("/auth/me", headers=headers)

    assert_unauthorized(response, "Not authenticated")


def test_me_with_garbage_token_is_401(client):
    response = client.get("/auth/me", headers=auth_header("not.a.jwt"))

    assert_unauthorized(response, "Invalid or expired token")


def test_me_with_token_signed_by_other_secret_is_401(client, monkeypatch):
    user_id = signup(client).json()["user"]["id"]
    monkeypatch.setenv("JWT_SECRET", "another-secret-that-is-also-long-enough-123456")
    foreign_token = create_access_token(user_id)
    monkeypatch.setenv("JWT_SECRET", JWT_SECRET)

    response = client.get("/auth/me", headers=auth_header(foreign_token))

    assert_unauthorized(response, "Invalid or expired token")


def test_me_with_expired_token_is_401(client):
    user_id = signup(client).json()["user"]["id"]
    expired = create_access_token(user_id, expires_delta=timedelta(seconds=-1))

    response = client.get("/auth/me", headers=auth_header(expired))

    assert_unauthorized(response, "Invalid or expired token")


def test_me_with_token_for_deleted_user_is_401(client, session):
    body = signup(client).json()
    session.delete(session.get(User, body["user"]["id"]))
    session.commit()

    response = client.get("/auth/me", headers=auth_header(body["access_token"]))

    assert_unauthorized(response, "Invalid or expired token")


@pytest.mark.parametrize(
    "claims",
    [
        pytest.param({"sub": "abc"}, id="non-integer-sub"),
        pytest.param({"sub": 1}, id="integer-sub"),
        pytest.param({}, id="missing-sub"),
    ],
)
def test_me_with_malformed_sub_is_401(client, claims):
    signup(client)
    token = jwt.encode({"exp": 4102444800, **claims}, JWT_SECRET, algorithm="HS256")

    response = client.get("/auth/me", headers=auth_header(token))

    assert_unauthorized(response, "Invalid or expired token")


def test_me_rejects_unsigned_and_missing_exp_tokens(client):
    signup(client)
    unsigned = jwt.encode({"sub": "1", "exp": 4102444800}, "", algorithm="none")
    no_exp = jwt.encode({"sub": "1"}, JWT_SECRET, algorithm="HS256")

    for token in (unsigned, no_exp):
        assert_unauthorized(
            client.get("/auth/me", headers=auth_header(token)),
            "Invalid or expired token",
        )


# --- app.services.auth -------------------------------------------------------


def test_access_token_claims(client):
    body = signup(client).json()

    payload = jwt.decode(body["access_token"], JWT_SECRET, algorithms=["HS256"])

    assert payload.keys() == {"sub", "iat", "exp"}
    assert payload["sub"] == str(body["user"]["id"])
    assert isinstance(payload["sub"], str)
    assert abs((payload["exp"] - payload["iat"]) - ACCESS_TOKEN_TTL.total_seconds()) <= 60
    assert ACCESS_TOKEN_TTL == timedelta(hours=24)
    assert jwt.get_unverified_header(body["access_token"])["alg"] == "HS256"
    assert decode_access_token(body["access_token"]) == body["user"]["id"]


def test_module_constants():
    assert auth_service.JWT_ALGORITHM == "HS256"
    assert auth_service.ACCESS_TOKEN_TTL == timedelta(hours=24)


def test_hash_password_uses_bcrypt_cost_12_by_default(monkeypatch):
    monkeypatch.undo()  # drop the autouse cost-4 patch for this test only

    assert auth_service.BCRYPT_ROUNDS == 12
    hashed = hash_password("x")
    assert hashed.startswith("$2b$12$")
    assert verify_password("x", hashed)
    assert not verify_password("y", hashed)


def test_hash_password_under_tests_uses_cost_4():
    assert hash_password("x").startswith("$2b$04$")


@pytest.mark.parametrize(
    "value",
    [pytest.param(None, id="unset"), pytest.param("", id="empty"), pytest.param("x" * 31, id="31-chars")],
)
def test_get_jwt_secret_rejects_unset_empty_and_short(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("JWT_SECRET")
    else:
        monkeypatch.setenv("JWT_SECRET", value)

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        get_jwt_secret()


def test_get_jwt_secret_accepts_32_chars(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "x" * 32)

    assert get_jwt_secret() == "x" * 32


def test_lifespan_fails_without_jwt_secret(monkeypatch):
    monkeypatch.delenv("JWT_SECRET")

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        with TestClient(fastapi_app):
            pass


def test_openapi_lists_auth_routes_with_bearer_scheme(client):
    spec = client.get("/openapi.json").json()

    assert {"/auth/signup", "/auth/login", "/auth/me"} <= spec["paths"].keys()
    assert spec["paths"]["/auth/signup"]["post"]["tags"] == ["auth"]
    assert spec["paths"]["/auth/login"]["post"]["tags"] == ["auth"]
    assert spec["paths"]["/auth/me"]["get"]["tags"] == ["auth"]
    assert spec["paths"]["/auth/me"]["get"]["security"] == [{"HTTPBearer": []}]
    assert spec["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }
