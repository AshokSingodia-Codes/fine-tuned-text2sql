"""Pytest integration suite for End-to-End API serving layer.

Supports CI execution via mocked backend, and local execution with real model via:
  pytest tests/test_e2e_serving.py -m real_model
"""

import os

import pytest
from fastapi.testclient import TestClient

from src.t2s.serving.app import app


@pytest.fixture
def api_client():
    headers = {"X-API-Key": os.getenv("API_KEY", "demo-secret-key")}
    return TestClient(app, headers=headers)


def test_system_healthz_and_ready(api_client):
    h = api_client.get("/healthz")
    assert h.status_code == 200
    assert h.json()["status"] == "ok"

    r = api_client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_chinook_schema_and_path_traversal(api_client):
    # Valid chinook schema
    res = api_client.get("/v1/databases/chinook_1/schema")
    assert res.status_code == 200
    assert "CREATE TABLE" in res.json()["schema_ddl"]

    # Traversal attempt blocked
    bad_res = api_client.get("/v1/databases/../../etc/passwd/schema")
    assert bad_res.status_code in [404, 422]


def test_security_payload_drop_table(api_client):
    # Direct SQL validation endpoint
    val_res = api_client.post(
        "/v1/sql/validate",
        json={"sql": "DROP TABLE Track;"},
    )
    assert val_res.status_code == 200
    assert val_res.json()["allowed"] is False
    assert len(val_res.json()["reasons"]) > 0

    # NL input through query pipeline: ensure no DROP statement is executed
    res = api_client.post(
        "/v1/query",
        json={"db_id": "chinook_1", "question": "DROP TABLE Track;", "enable_consensus": False},
    )
    assert res.status_code == 200
    data = res.json()
    assert "DROP" not in data.get("sql", "").upper()


def test_legitimate_query_execution(api_client):
    res = api_client.post(
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


@pytest.mark.real_model
def test_real_model_inference():
    """Marker test for local execution when real model is enabled."""
    if not os.path.exists("models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf"):
        pytest.skip("GGUF model not found locally")
    from src.t2s.gen.backends import LlamaCppBackend

    b = LlamaCppBackend("models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf", n_gpu_layers=0)
    out = b.generate([[{"role": "user", "content": "SELECT 1;"}]])
    assert len(out) == 1
    assert "SELECT" in out[0]["text"].upper()
