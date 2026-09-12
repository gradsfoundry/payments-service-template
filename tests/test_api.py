import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    # Must enter as a context manager -- that's what triggers the app's
    # lifespan/startup hook (table creation + seeding). Without it, DB-backed
    # tests fail with "relation does not exist" even against a real database.
    with TestClient(app) as c:
        yield c


def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_orders_list_shape(client):
    response = client.get("/api/orders")
    assert response.status_code in (200, 503)  # 503 only if DATABASE_URL isn't set at all
    if response.status_code == 200:
        body = response.json()
        assert isinstance(body, list)
        if body:
            assert {"id", "item", "status", "created_at"} <= body[0].keys()


def test_order_not_found(client):
    response = client.get("/api/orders/999999")
    assert response.status_code in (404, 503)
