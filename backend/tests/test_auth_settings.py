"""Token configuration regression checks use synthetic secrets only."""
from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import ValidationError
import pytest

from app.core.config import Settings
from app.main import create_app


def test_default_dotenv_path_is_independent_of_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert Settings.model_config["env_file"] == Path(__file__).resolve().parents[1] / ".env"


def test_dotenv_token_loaded_and_authenticated_without_history(tmp_path, monkeypatch):
    monkeypatch.delenv("SINGLE_USER_API_KEY", raising=False)
    key = "synthetic-owner-" + "x" * 40
    env = tmp_path / ".env"
    env.write_text(f'SINGLE_USER_API_KEY={key}\nCORS_ORIGINS=["http://localhost:5173"]\n', encoding="utf-8")
    settings = Settings(_env_file=env, app_mode="single_user", storage_enabled=False)
    assert settings.single_user_api_key.get_secret_value() == key
    assert key not in repr(settings)
    with TestClient(create_app(settings)) as client:
        for authorization in (None, "Bearer incorrect", key, "Basic " + key):
            headers = {"Authorization": authorization} if authorization else {}
            response = client.get("/api/v1/analyses?limit=1", headers=headers)
            assert response.status_code == 401
            assert key not in response.text
        response = client.get("/api/v1/analyses?limit=1", headers={"Authorization": "Bearer " + key})
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "storage_disabled"
        preflight = client.options("/api/v1/resumes/analyze", headers={"Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"})
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"


@pytest.mark.parametrize("suffix", [" ", "\n", "\t", "\x00", "é"])
def test_unusable_bearer_token_configuration_is_rejected(suffix):
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, single_user_api_key="synthetic-" + "x" * 40 + suffix)
    assert "synthetic-" not in str(exc.value)
