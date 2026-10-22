from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent


def _default_database_url() -> str:
    return f"sqlite:///{(BACKEND_DIR / 'careerpilot.db').as_posix()}"


def _default_asset_storage_dir() -> str:
    return str(BACKEND_DIR / "storage")


class Settings(BaseSettings):
    database_url: str = Field(default_factory=_default_database_url, alias="DATABASE_URL")
    auto_migrate: bool = Field(default=True, alias="AUTO_MIGRATE")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str | None = Field(default=None, alias="OPENAI_MODEL")
    tailoring_context_tokens: int = Field(default=128000, ge=16000, le=1000000, alias="TAILORING_CONTEXT_TOKENS")
    tavily_api_key: str | None = Field(default=None, alias="TAVILY_API_KEY")
    asset_storage_dir: str = Field(default_factory=_default_asset_storage_dir, alias="ASSET_STORAGE_DIR")
    resume_pdflatex: str | None = Field(default=None, alias="RESUME_PDFLATEX")
    backend_cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="BACKEND_CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_DIR / ".env"), str(REPO_ROOT / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("database_url")
    @classmethod
    def _anchor_relative_sqlite_path(cls, value: str) -> str:
        # A relative SQLite path would silently point at a different database
        # depending on the working directory; anchor it to the backend dir.
        prefix = "sqlite:///"
        if not value.startswith(prefix):
            return value
        raw_path = value.removeprefix(prefix)
        if not raw_path or raw_path == ":memory:" or Path(raw_path).is_absolute():
            return value
        return f"sqlite:///{(BACKEND_DIR / raw_path).resolve().as_posix()}"

    @field_validator("asset_storage_dir")
    @classmethod
    def _anchor_relative_storage_dir(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute():
            return value
        return str((BACKEND_DIR / path).resolve())

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.backend_cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
