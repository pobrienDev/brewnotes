import pytest
from pydantic import ValidationError

from app.config import MIN_SECRET_KEY_LENGTH, Settings

DATABASE_URL = "postgresql+psycopg://u:p@localhost/db"
SECRET = "s" * MIN_SECRET_KEY_LENGTH


def production_settings(
    *,
    secret_key: str = SECRET,
    public_base_url: str = "https://brewnotes.example/",
    google_client_secret: str | None = "d",
) -> Settings:
    return Settings(
        _env_file=None,
        database_url=DATABASE_URL,
        secret_key=secret_key,
        public_base_url=public_base_url,
        github_client_id="a",
        github_client_secret="b",
        google_client_id="c",
        google_client_secret=google_client_secret,
    )


def test_defaults_to_production() -> None:
    settings = production_settings()
    assert settings.app_env == "production"
    assert settings.is_production
    assert settings.public_base_url == "https://brewnotes.example"


def test_production_refuses_short_secret() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        production_settings(secret_key="short")


def test_production_refuses_placeholder_secret() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        production_settings(secret_key="change-me-" + "x" * 40)


def test_production_refuses_missing_oauth_secret() -> None:
    with pytest.raises(ValidationError, match="GOOGLE_CLIENT_SECRET"):
        production_settings(google_client_secret=None)


def test_production_refuses_http_base_url() -> None:
    with pytest.raises(ValidationError, match="https"):
        production_settings(public_base_url="http://brewnotes.example")


def test_development_allows_missing_oauth() -> None:
    settings = Settings(
        _env_file=None,
        app_env="development",
        database_url=DATABASE_URL,
        secret_key=SECRET,
        public_base_url="http://localhost:5173",
    )
    assert settings.is_development
    assert settings.github_client_id is None


def test_allowed_hosts_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_HOSTS", "brewnotes.example, www.brewnotes.example")
    settings = production_settings()
    assert settings.allowed_hosts == ["brewnotes.example", "www.brewnotes.example"]
