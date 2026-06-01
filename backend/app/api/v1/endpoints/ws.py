import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websockets.manager import websocket_manager

router = APIRouter()


@router.websocket("/devices/{device_id}")
async def device_websocket(websocket: WebSocket, device_id: uuid.UUID) -> None:
    await websocket_manager.connect(str(device_id), websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(str(device_id), websocket)


@router.websocket("/dashboard")
async def dashboard_websocket(websocket: WebSocket) -> None:
    channel = "dashboard"
    await websocket_manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        websocket_manager.disconnect(channel, websocket)
