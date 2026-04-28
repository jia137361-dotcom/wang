from scripts.smoke_api import cleanup
from app.main import app
from fastapi.testclient import TestClient


def test_health() -> None:
    cleanup()
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
