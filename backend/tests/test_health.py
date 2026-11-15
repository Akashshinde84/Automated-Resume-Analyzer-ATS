from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health():
    with TestClient(create_app(Settings(_env_file=None))) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_uses_configured_origin():
    settings = Settings(_env_file=None, cors_origins=["https://example.com"])
    with TestClient(create_app(settings)) as client:
        allowed = client.options("/health", headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        })
        denied = client.get("/health", headers={"Origin": "https://untrusted.example"})
    assert allowed.headers["access-control-allow-origin"] == "https://example.com"
    assert "access-control-allow-origin" not in denied.headers
