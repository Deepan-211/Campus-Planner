"""
FastAPI WebSocket and Server-Sent Events (SSE) telemetry endpoints for CampusRide Planner.
Provides bi-directional continuous real-time streaming of moving van coordinates,
live dock inventory levels, and rider checkout/return feeds.
"""
import asyncio
import json
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Request
from fastapi.responses import StreamingResponse

from backend.telemetry.engine import get_telemetry_engine

logger = logging.getLogger(__name__)
telemetry_router = APIRouter(prefix="/api/v1/telemetry", tags=["Real-Time Telemetry"])


@telemetry_router.websocket("/ws")
async def telemetry_websocket(
    websocket: WebSocket,
    campus_id: Optional[str] = Query(default="vsb_karur")
):
    """
    Bi-directional WebSocket streaming live telemetry at 1Hz.
    Supports client commands to toggle play/pause, adjust simulation speed, or switch campuses.
    """
    await websocket.accept()
    active_campus = campus_id or "vsb_karur"
    engine = get_telemetry_engine(active_campus)

    async def client_listener():
        """Listen for incoming control commands from the frontend."""
        nonlocal engine, active_campus
        try:
            while True:
                msg_text = await websocket.receive_text()
                try:
                    payload = json.loads(msg_text)
                    action = payload.get("action")
                    if action == "set_speed":
                        engine.set_speed(float(payload.get("speed", 2.0)))
                    elif action == "set_pause":
                        engine.set_pause(bool(payload.get("paused", False)))
                    elif action == "switch_campus":
                        new_campus = payload.get("campus_id")
                        if new_campus:
                            active_campus = new_campus
                            engine = get_telemetry_engine(new_campus)
                except Exception as ex:
                    logger.warning("Error processing client telemetry command: %s", ex)
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass

    listener_task = asyncio.create_task(client_listener())

    try:
        while True:
            # Advance simulation by 1.0 second real time and emit telemetry frame
            frame = engine.tick(real_delta_sec=1.0)
            await websocket.send_text(json.dumps(frame))
            await asyncio.sleep(1.0)
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        listener_task.cancel()


@telemetry_router.get("/stream")
async def telemetry_sse_stream(
    request: Request,
    campus_id: Optional[str] = Query(default="vsb_karur")
):
    """
    Server-Sent Events (SSE) streaming fallback for browsers/environments
    that prefer EventSource over WebSockets.
    """
    engine = get_telemetry_engine(campus_id or "vsb_karur")

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            frame = engine.tick(real_delta_sec=1.0)
            yield f"data: {json.dumps(frame)}\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@telemetry_router.get("/snapshot")
def get_telemetry_snapshot(campus_id: Optional[str] = Query(default="vsb_karur")):
    """Retrieve instantaneous digital twin state snapshot."""
    engine = get_telemetry_engine(campus_id or "vsb_karur")
    return engine.get_telemetry_snapshot()


@telemetry_router.post("/control")
def control_telemetry(
    campus_id: Optional[str] = Query(default="vsb_karur"),
    speed: Optional[float] = Query(default=None),
    paused: Optional[bool] = Query(default=None),
):
    """Adjust simulation playback speed or toggle pause via REST."""
    engine = get_telemetry_engine(campus_id or "vsb_karur")
    if speed is not None:
        engine.set_speed(speed)
    if paused is not None:
        engine.set_pause(paused)
    return engine.get_telemetry_snapshot()
