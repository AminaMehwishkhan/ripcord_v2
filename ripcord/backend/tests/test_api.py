import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import turn

client = TestClient(app)


def test_health_reports_the_engine():
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["risk_engine"] in ("learned-v2", "rules-v1")


def test_scenarios_list_has_both_kinds():
    data = client.get("/api/scenarios").json()
    assert len(data) >= 10
    assert {"id", "title", "spoken", "source", "has_replies"} <= set(data[0])
    assert any(s["source"] == "scripted" for s in data)


def test_assess_clear_vs_wrong_length():
    def body(text, conf=0.97):
        return {"transcript": text, "words": [{"text": t, "confidence": conf} for t in text.split()]}
    clear = client.post("/api/assess", json=body("my order number is one five eight zero")).json()
    short = client.post("/api/assess", json=body("my order number is one five zero", 0.5)).json()
    assert clear["entity"]["value"] == "1580" and clear["risk"]["should_clarify"] is False and clear["question"] is None
    assert short["entity"]["value"] == "150" and short["risk"]["should_clarify"] is True
    assert short["question"] is not None and short["risk"]["reasons"]
    assert short["risk"]["risk_score"] > clear["risk"]["risk_score"]


def test_assess_without_a_number():
    r = client.post("/api/assess", json={"transcript": "hello there", "words": []}).json()
    assert r == {"entity": None, "risk": None, "question": None}


def test_assess_rejects_bad_confidence():
    assert client.post("/api/assess", json={"transcript": "x", "words": [{"text": "x", "confidence": 3}]}).status_code == 422


def test_benchmark_endpoint():
    r = client.get("/api/benchmark")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert "policies" in r.json()


def test_websocket_session_and_unknown_scenario():
    with client.websocket_connect("/ws/session") as ws:
        ws.send_text(json.dumps({"action": "start_session", "ripcord_enabled": True}))
        assert ws.receive_json()["type"] == "state"
        ws.send_text(json.dumps({"action": "run_mock_scenario", "scenario_id": 99999}))
        assert ws.receive_json()["type"] == "error"
        ws.send_text("not json")
        assert ws.receive_json()["type"] == "error"
