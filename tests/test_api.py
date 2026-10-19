"""Unit tests for FastAPI endpoints using TestClient."""

import os

from fastapi.testclient import TestClient

from src.t2s.serving.app import app

client = TestClient(app)


def test_health_and_readiness_endpoints():
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "ok"}

    res_ready = client.get("/ready")
    assert res_ready.status_code == 200
    data = res_ready.json()
    assert data["status"] == "ready"
    assert data["model_loaded"] is True
    assert "concurrency_limit" in data


def test_metrics_endpoint():
    res = client.get("/metrics", headers={"X-API-Key": "demo-secret-key"})
    assert res.status_code == 200
    assert "t2s_requests_total" in res.text


def test_list_databases_endpoint():
    res = client.get("/v1/databases")
    assert res.status_code == 200
    data = res.json()
    assert "databases" in data
    assert data["total"] > 0
    db_ids = [d["db_id"] for d in data["databases"]]
    assert "concert_singer" in db_ids


def test_validate_sql_endpoint():
    # Valid query
    res_valid = client.post("/v1/sql/validate", json={"sql": "SELECT name FROM students;"})
    assert res_valid.status_code == 200
    assert res_valid.json()["allowed"] is True

    # Malicious query
    res_invalid = client.post("/v1/sql/validate", json={"sql": "DROP TABLE students;"})
    assert res_invalid.status_code == 200
    assert res_invalid.json()["allowed"] is False


def test_query_endpoint_with_auth():
    os.environ["DISABLE_AUTH"] = "true"
    payload = {
        "db_id": "concert_singer",
        "question": "How many singers are there?",
    }
    res = client.post("/v1/query", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "request_id" in data
    assert data["db_id"] == "concert_singer"
    assert "sql" in data


def test_feedback_endpoint():
    payload = {
        "request_id": "test-id-123",
        "rating": 1,
        "comment": "Great query!",
    }
    res = client.post("/v1/feedback", json=payload)
    assert res.status_code == 200
    assert res.json() == {"status": "feedback_recorded"}


def test_model_info_endpoint():
    res = client.get("/v1/model/info")
    assert res.status_code == 200
    data = res.json()
    assert data["model_name"] == "Qwen2.5-Coder-3B-Instruct"
