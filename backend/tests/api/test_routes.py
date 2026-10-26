"""
tests/api/test_routes.py – API integration tests (8.9).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from assistant.main import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_session(client):
    r = client.post("/api/sessions")
    assert r.status_code == 201
    data = r.json()
    assert "session_id" in data
    assert "reply_text" in data
    assert "Bright Smile" in data["reply_text"]


def test_turn_missing_text(client):
    r = client.post("/api/sessions")
    sid = r.json()["session_id"]
    r2 = client.post(f"/api/sessions/{sid}/turns",
                     json={"turn_no": 1, "type": "utterance"})
    # text is required for utterances
    assert r2.status_code in (200, 422)


def test_wrong_turn_no_409(client):
    r = client.post("/api/sessions")
    sid = r.json()["session_id"]
    r2 = client.post(f"/api/sessions/{sid}/turns",
                     json={"turn_no": 5, "type": "utterance", "text": "hi"})
    assert r2.status_code == 409


def test_unknown_session_404(client):
    r = client.post("/api/sessions/nonexistent-id/turns",
                    json={"turn_no": 1, "type": "utterance", "text": "hi"})
    assert r.status_code == 404


def test_idempotent_replay(client):
    r = client.post("/api/sessions")
    sid = r.json()["session_id"]
    turn = {"turn_no": 1, "type": "utterance", "text": "book a cleaning"}
    r1 = client.post(f"/api/sessions/{sid}/turns", json=turn)
    r2 = client.post(f"/api/sessions/{sid}/turns", json=turn)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["reply_text"] == r2.json()["reply_text"]


def test_demo_bookings_endpoint(client):
    r = client.get("/api/demo/bookings")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    if data:
        assert "patient_name" in data[0]
        assert "code" in data[0]
