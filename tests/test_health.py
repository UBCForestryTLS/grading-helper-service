from fastapi.testclient import TestClient

from src.api.app import create_app

client = TestClient(create_app())


def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_body():
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "healthy"
    assert "stage" in data
