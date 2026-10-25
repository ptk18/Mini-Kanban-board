from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok_and_a_version(monkeypatch):
    monkeypatch.delenv("APP_VERSION", raising=False)
    monkeypatch.delenv("RENDER_GIT_COMMIT", raising=False)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "dev"}


def test_health_reports_the_deployed_commit(monkeypatch):
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123")
    assert client.get("/health").json()["version"] == "abc123"
    # An explicit APP_VERSION (e.g. from a Docker build arg) wins.
    monkeypatch.setenv("APP_VERSION", "v1.2.3")
    assert client.get("/health").json()["version"] == "v1.2.3"
