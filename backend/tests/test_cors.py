import importlib

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app as fastapi_app, cors_origins

ORIGIN = "http://localhost:3000"


def test_cors_origins_defaults_to_the_dev_server(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert cors_origins() == [ORIGIN]


@pytest.mark.parametrize("raw", ["", "   ", " , "])
def test_cors_origins_blank_means_default(monkeypatch, raw):
    monkeypatch.setenv("CORS_ORIGINS", raw)
    assert cors_origins() == [ORIGIN]


def test_cors_origins_is_comma_separated_and_trimmed(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", " http://localhost:3000 ,https://kanban.example.com,, ")
    assert cors_origins() == [ORIGIN, "https://kanban.example.com"]


def test_simple_request_from_the_dev_origin_gets_the_allow_origin_header():
    with TestClient(fastapi_app) as client:
        response = client.get("/health", headers={"Origin": ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_preflight_allows_the_api_methods_and_headers():
    with TestClient(fastapi_app) as client:
        response = client.options(
            "/boards",
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "authorization, content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    allowed_methods = {m.strip() for m in response.headers["access-control-allow-methods"].split(",")}
    assert {"GET", "POST", "PATCH", "DELETE"} <= allowed_methods
    allowed_headers = {h.strip().lower() for h in response.headers["access-control-allow-headers"].split(",")}
    assert {"authorization", "content-type"} <= allowed_headers


def test_other_origins_get_no_allow_origin_header():
    with TestClient(fastapi_app) as client:
        response = client.get("/health", headers={"Origin": "http://evil.example"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_cors_origins_env_is_applied_at_import(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://kanban.example.com")
    reloaded = importlib.reload(main_module)
    try:
        with TestClient(reloaded.app) as client:
            ok = client.get("/health", headers={"Origin": "https://kanban.example.com"})
            denied = client.get("/health", headers={"Origin": ORIGIN})
        assert ok.headers["access-control-allow-origin"] == "https://kanban.example.com"
        assert "access-control-allow-origin" not in denied.headers
    finally:
        monkeypatch.delenv("CORS_ORIGINS")
        importlib.reload(main_module)
