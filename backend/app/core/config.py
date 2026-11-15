"""Validated environment configuration; deployment defaults fail closed."""
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.matching import MatchingWeights


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8", extra="ignore", hide_input_in_errors=True,
    )
    app_name: str = "Resume Analyzer API"
    deployment_environment: Literal["development", "production"] = "development"
    isolate_parsing: bool = False
    parser_timeout_seconds: int = Field(default=25, ge=1, le=60)
    parser_memory_mb: int = Field(default=384, ge=128, le=1024)
    app_mode: Literal["single_user", "local"] = "single_user"
    single_user_api_key: SecretStr | None = None
    single_user_id: str = Field(default="primary", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    cors_origins: list[AnyHttpUrl] = [AnyHttpUrl("http://localhost:5173")]
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0, le=50 * 1024 * 1024)
    max_docx_uncompressed_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    max_pdf_pages: int = Field(default=200, gt=0)
    max_concurrent_processing: int = Field(default=2, ge=1, le=16)
    spacy_model: str = "en_core_web_sm"
    require_ner_model: bool = False
    matching_weights: MatchingWeights = Field(default_factory=MatchingWeights)
    storage_enabled: bool = False
    database_url: SecretStr | None = None
    retention_days: int = Field(default=7, ge=1, le=365)
    retention_cleanup_interval_seconds: int = Field(default=3600, ge=1, le=86400)
    max_stored_analyses: int = Field(default=1000, ge=1, le=10000)
    max_matches_per_analysis: int = Field(default=50, ge=1, le=1000)
    report_token_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    report_signing_key: SecretStr | None = None

    @model_validator(mode="after")
    def secure_configuration(self):
        key = self.single_user_api_key.get_secret_value() if self.single_user_api_key else ""
        if key and (len(key) < 32 or key.lower().startswith(("replace", "change", "example"))):
            raise ValueError("SINGLE_USER_API_KEY must be a non-placeholder random token of at least 32 characters.")
        signing = self.report_signing_key.get_secret_value() if self.report_signing_key else ""
        if signing and (len(signing) < 32 or signing.lower().startswith(("replace", "change", "example"))):
            raise ValueError("REPORT_SIGNING_KEY must be a non-placeholder random secret of at least 32 characters.")
        if self.deployment_environment == "production":
            if self.app_mode != "single_user" or not key or not signing or not self.require_ner_model or not self.isolate_parsing:
                raise ValueError("Production requires single-user authentication, report signing, the NER model and isolated parsing.")
            if not self.cors_origins or any(o.scheme != "https" for o in self.cors_origins):
                raise ValueError("Production CORS requires explicit HTTPS frontend origins.")
        if self.storage_enabled and (not key or not self.database_url or not self.database_url.get_secret_value()):
            raise ValueError("Persistent storage requires DATABASE_URL and SINGLE_USER_API_KEY.")
        if not self.allowed_hosts or any(not host or "*" in host or "/" in host or host != host.strip() for host in self.allowed_hosts):
            raise ValueError("ALLOWED_HOSTS must contain explicit hosts.")
        for origin in self.cors_origins:
            if "*" in (origin.host or "") or origin.path not in (None, "/") or origin.query or origin.fragment or origin.username or origin.password:
                raise ValueError("CORS origins must be explicit origins without paths or credentials.")
        return self
