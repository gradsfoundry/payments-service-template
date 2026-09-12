import uuid

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


def test_get_seeded_account(client):
    response = client.get("/api/accounts/1")
    assert response.status_code == 200
    body = response.json()
    assert {"id", "name", "balance_cents"} <= body.keys()


def test_account_not_found(client):
    response = client.get("/api/accounts/999999")
    assert response.status_code in (404, 503)


def test_payment_moves_balance(client):
    before_sender = client.get("/api/accounts/1").json()["balance_cents"]
    before_receiver = client.get("/api/accounts/2").json()["balance_cents"]

    response = client.post(
        "/api/payments",
        json={"from_account_id": 1, "to_account_id": 2, "amount_cents": 500},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 201
    payment = response.json()
    assert payment["status"] == "completed"

    assert client.get("/api/accounts/1").json()["balance_cents"] == before_sender - 500
    assert client.get("/api/accounts/2").json()["balance_cents"] == before_receiver + 500


def test_idempotency_key_prevents_double_payment(client):
    key = str(uuid.uuid4())
    before = client.get("/api/accounts/1").json()["balance_cents"]

    first = client.post(
        "/api/payments",
        json={"from_account_id": 1, "to_account_id": 2, "amount_cents": 100},
        headers={"Idempotency-Key": key},
    )
    second = client.post(
        "/api/payments",
        json={"from_account_id": 1, "to_account_id": 2, "amount_cents": 100},
        headers={"Idempotency-Key": key},  # same key -- simulates a client retry
    )

    assert first.status_code == 201
    assert second.json()["id"] == first.json()["id"]  # same payment returned, not a new one
    after = client.get("/api/accounts/1").json()["balance_cents"]
    assert after == before - 100  # money moved ONCE, not twice


def test_insufficient_funds_rejected(client):
    response = client.post(
        "/api/payments",
        json={"from_account_id": 1, "to_account_id": 2, "amount_cents": 999_999_999},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 402


def test_cannot_pay_self(client):
    response = client.post(
        "/api/payments",
        json={"from_account_id": 1, "to_account_id": 1, "amount_cents": 100},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 400


def test_payment_not_found(client):
    response = client.get("/api/payments/999999")
    assert response.status_code in (404, 503)
