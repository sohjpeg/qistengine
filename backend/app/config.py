"""Central configuration. All settings load from environment with the QIST_ prefix."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QIST_",
        env_file=(".env", str(BACKEND_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    env: str = "development"
    database_url: str = "sqlite:///./data/qistengine.db"
    model_dir: str = "./app/ml/artifacts"
    cors_origins: str = "http://localhost:3000"
    ocr_engine: str = "auto"  # auto | tesseract | fallback
    max_upload_mb: int = 10
    seed: int = 42

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def model_dir_path(self) -> Path:
        p = Path(self.model_dir)
        if not p.is_absolute():
            p = (BACKEND_ROOT / p).resolve()
        return p

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def sqlite_path(self) -> Path | None:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            return None
        raw = self.database_url[len(prefix):]
        p = Path(raw)
        if not p.is_absolute():
            p = (BACKEND_ROOT / p).resolve()
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
