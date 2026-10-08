from fastapi.testclient import TestClient

from app.errors import PROBLEM_MEDIA_TYPE
from app.main import create_app
from tests.conftest import make_test_settings


def test_live(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_with_database(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_without_database_is_503() -> None:
    settings = make_test_settings(
        database_url="postgresql+psycopg://nobody:nothing@127.0.0.1:1/none",
        db_connect_timeout_s=1,
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    assert response.json()["detail"] == "Database is not reachable."
