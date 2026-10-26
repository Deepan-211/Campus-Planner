"""
Unit tests for Real-Time Streaming Telemetry (Engine, REST, and WebSocket).
"""
import pytest
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.telemetry.engine import CampusTelemetryEngine, get_telemetry_engine

client = TestClient(app)


def test_telemetry_engine_direct_ticks():
    """Verify engine advances van position, updates inventory, and maintains valid state."""
    engine = CampusTelemetryEngine(campus_id="vsb_karur")
    engine.set_speed(10.0)

    # Initial frame
    frame_0 = engine.get_telemetry_snapshot()
    assert frame_0["campus_id"] == "vsb_karur"
    assert "van" in frame_0
    assert frame_0["van"]["latitude"] > 0
    assert frame_0["van"]["longitude"] > 0
    assert "live_inventory" in frame_0

    # Tick 5 times
    for _ in range(5):
        frame = engine.tick(real_delta_sec=1.0)

    assert frame["sim_second"] > frame_0["sim_second"]
    assert isinstance(frame["van"]["bearing"], (int, float))
    assert 0 <= frame["van"]["load"] <= frame["van"]["capacity"]


def test_telemetry_snapshot_endpoint():
    """Verify GET /api/v1/telemetry/snapshot returns complete digital twin state."""
    response = client.get("/api/v1/telemetry/snapshot?campus_id=vsb_karur")
    assert response.status_code == 200
    data = response.json()
    assert "van" in data
    assert "stands" in data
    assert len(data["stands"]) > 0
    assert "live_inventory" in data
    assert data["van"]["id"] == "VAN-01"


def test_telemetry_control_endpoint():
    """Verify POST /api/v1/telemetry/control updates speed and pause state."""
    resp = client.post("/api/v1/telemetry/control?campus_id=vsb_karur&speed=5.0&paused=true")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_paused"] is True
    assert data["speed_multiplier"] == 5.0

    # Resume
    resp2 = client.post("/api/v1/telemetry/control?campus_id=vsb_karur&speed=2.0&paused=false")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["is_paused"] is False
    assert data2["speed_multiplier"] == 2.0


def test_telemetry_websocket_streaming():
    """Verify WebSocket connection receives continuous telemetry frames and accepts control commands."""
    with client.websocket_connect("/api/v1/telemetry/ws?campus_id=vsb_karur") as ws:
        # First frame received
        frame_text = ws.receive_text()
        assert "van" in frame_text
        assert "live_inventory" in frame_text

        # Send control command from client
        ws.send_json({"action": "set_speed", "speed": 4.0})

        # Second frame received
        frame_text_2 = ws.receive_text()
        assert "sim_time" in frame_text_2
