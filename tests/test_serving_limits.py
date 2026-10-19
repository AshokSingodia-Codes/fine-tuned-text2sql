"""Unit and integration tests for serving limits, queue depth, timeouts, and metrics auth."""

import pytest
from fastapi.testclient import TestClient

from src.t2s.serving.app import app


@pytest.fixture
def client():
    return TestClient(app, headers={"X-API-Key": "demo-secret-key"})


def test_health_and_ready_endpoints(client):
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    res_ready = client.get("/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"
    assert "concurrency_limit" in res_ready.json()


def test_metrics_endpoint_behavior(client, monkeypatch):
    # In dev profile with valid API key
    res = client.get("/metrics")
    assert res.status_code == 200
    assert b"t2s_requests_total" in res.content

    # In demo profile, metrics should be disabled (403)
    monkeypatch.setenv("APP_PROFILE", "demo")
    res_demo = client.get("/metrics")
    assert res_demo.status_code == 403
    assert "disabled in demo profile" in res_demo.json()["detail"]


def test_metrics_auth_failure(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "false")
    monkeypatch.delenv("APP_PROFILE", raising=False)
    unauthed_client = TestClient(app)
    res = unauthed_client.get("/metrics")
    assert res.status_code == 401


def test_request_payload_size_limit(client):
    # Huge payload exceeding 64KB should return 413
    huge_question = "A" * 70000
    res = client.post("/v1/query", json={"db_id": "chinook_1", "question": huge_question})
    assert res.status_code == 413
    assert "payload exceeds max limit" in res.json()["detail"]


def test_valid_query_processing(client):
    res = client.post(
        "/v1/query",
        json={
            "db_id": "chinook_1",
            "question": "How many artists are in the database?",
            "enable_consensus": False,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["allowed"] is True
    assert "sql" in data
    assert "attempts" in data
    assert len(data["attempts"]) >= 1


def test_blocked_query_returns_sanitized_response(client, monkeypatch):
    from src.t2s.serving.app import service

    monkeypatch.setattr(
        service.backend,
        "generate",
        lambda prompts: [{"text": "DROP TABLE Track;", "latency_ms": 1.0, "tokens": 4}],
    )
    res = client.post(
        "/v1/query",
        json={
            "db_id": "chinook_1",
            "question": "Can you delete all tracks?",
            "enable_consensus": False,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["allowed"] is False
    assert len(data["reasons"]) > 0
    assert "attempts" in data
