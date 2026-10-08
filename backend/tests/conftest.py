"""Shared fixtures. API tests run against a real Postgres test database built from the
migrations; each test runs inside a transaction that is rolled back at the end."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Connection, Engine
from sqlalchemy.orm import Session

from alembic import command
from app.config import MIN_SECRET_KEY_LENGTH, Settings
from app.db import create_engine_from_settings, get_db
from app.main import create_app
from app.security.oauth import build_oauth
from tests.fakes import FakeProviders

# Tests talk to the app over https so Secure, __Host- prefixed cookies behave as in production.
BASE_URL = "https://testserver"
# Every unsafe request must carry our own Origin (CSRF check).
CSRF = {"Origin": BASE_URL}

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    # Fall back to the .env file the developer uses locally.
    base = Settings()
    if not base.test_database_url:
        pytest.exit("TEST_DATABASE_URL is not set", returncode=2)
    return base.test_database_url


def make_test_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": _test_database_url(),
        "secret_key": "t" * MIN_SECRET_KEY_LENGTH,
        "public_base_url": BASE_URL,
        "allowed_hosts": ["testserver"],
        "log_level": "WARNING",
        "github_client_id": "gh-client-id",
        "github_client_secret": "gh-client-secret",
        "google_client_id": "google-client-id.apps.googleusercontent.com",
        "google_client_secret": "google-client-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


@pytest.fixture(scope="session")
def settings() -> Settings:
    return make_test_settings()


@pytest.fixture(scope="session")
def migrated_database(settings: Settings) -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def engine(settings: Settings, migrated_database: None) -> Iterator[Engine]:
    engine = create_engine_from_settings(settings)
    yield engine
    engine.dispose()


@pytest.fixture
def db_connection(engine: Engine) -> Iterator[Connection]:
    with engine.connect() as connection:
        transaction = connection.begin()
        yield connection
        transaction.rollback()


@pytest.fixture
def app(settings: Settings, db_connection: Connection) -> Iterator[FastAPI]:
    application = create_app(settings)

    def override_get_db() -> Iterator[Session]:
        with (
            Session(bind=db_connection, join_transaction_mode="create_savepoint") as session,
            session.begin(),
        ):
            yield session

    application.dependency_overrides[get_db] = override_get_db
    fake = FakeProviders(google_client_id=settings.google_client_id or "")
    application.state.oauth = build_oauth(settings, transport=fake.transport)
    application.state.fake_providers = fake
    yield application
    application.state.engine.dispose()


@pytest.fixture
def providers(app: FastAPI) -> FakeProviders:
    fake: FakeProviders = app.state.fake_providers
    return fake


def make_client(app: FastAPI) -> TestClient:
    """A browser: its own cookie jar, redirects left to the test to inspect."""
    return TestClient(app, base_url=BASE_URL, raise_server_exceptions=False, follow_redirects=False)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with make_client(app) as test_client:
        yield test_client
