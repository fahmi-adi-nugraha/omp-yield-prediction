"""Application settings loaded from environment variables and dotenv files."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_local_env() -> None:
    """Load a local env file without overriding variables already in the shell.

    The repository ships with the demo DB credentials in ``docker-build/.env``.
    That file is a convenience fallback for local development only. Production
    deployments should provide ``OMP_DB_*`` environment variables directly or
    point ``OMP_ENV_FILE`` at a managed secrets file.
    """

    configured = os.getenv("OMP_ENV_FILE")
    if configured:
        candidates = [Path(configured)]
    else:
        candidates = [
            Path(".env"),
            Path.home() / ".config" / "omp-yield" / "env",
            Path("docker-build/.env"),
        ]
    for path in candidates:
        if path.is_file():
            load_dotenv(path, override=False)
            if configured:
                break


_load_local_env()


class Settings(BaseSettings):
    """Runtime configuration for DB access and query safety limits."""

    model_config = SettingsConfigDict(
        env_prefix="OMP_",
        extra="ignore",
        case_sensitive=False,
    )

    db_host: str = Field(default="localhost")
    db_port: int = Field(default=1433, ge=1, le=65535)
    db_user: str = Field(default="omp_ds_readonly")
    db_password: SecretStr = Field(default_factory=lambda: SecretStr(""))
    db_database: str = Field(default="omp_as_demo")
    db_encrypt: bool = Field(default=True)
    db_trust_server_certificate: bool = Field(default=True)
    db_query_timeout_seconds: int = Field(default=30, ge=1, le=3600)
    query_row_limit: int = Field(default=1000, ge=1, le=100_000)

    @property
    def mssql_url(self) -> str:
        """Build a ConnectorX MSSQL connection URL."""

        password = self.db_password.get_secret_value()
        if not password:
            raise ValueError(
                "OMP_DB_PASSWORD is empty. Set it in the environment or in .env."
            )

        user = quote_plus(self.db_user)
        secret = quote_plus(password)
        database = quote_plus(self.db_database)
        host = self.db_host
        params = [
            f"encrypt={'true' if self.db_encrypt else 'false'}",
            f"trust_server_certificate={'true' if self.db_trust_server_certificate else 'false'}",
        ]
        return f"mssql://{user}:{secret}@{host}:{self.db_port}/{database}?{'&'.join(params)}"

    @property
    def safe_target(self) -> str:
        """Human-readable connection target with no credentials."""

        return f"{self.db_user}@{self.db_host}:{self.db_port}/{self.db_database}"
