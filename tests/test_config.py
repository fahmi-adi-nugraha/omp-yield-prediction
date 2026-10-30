from __future__ import annotations

from pydantic import SecretStr

from omp_yield.config import Settings


def test_connection_url_encodes_credentials() -> None:
    settings = Settings(
        db_host="db.example",
        db_port=1444,
        db_user="ds user",
        db_password=SecretStr("p@ss/word"),
        db_database="omp demo",
        db_encrypt=True,
        db_trust_server_certificate=True,
    )
    url = settings.mssql_url
    assert url.startswith("mssql://ds+user:p%40ss%2Fword@db.example:1444/omp+demo?")
    assert "encrypt=true" in url
    assert "trust_server_certificate=true" in url


def test_safe_target_has_no_password() -> None:
    settings = Settings(
        db_host="localhost",
        db_port=1433,
        db_user="omp_ds_readonly",
        db_password=SecretStr("secret"),
        db_database="omp_as_demo",
    )
    assert settings.safe_target == "omp_ds_readonly@localhost:1433/omp_as_demo"
    assert "secret" not in settings.safe_target
