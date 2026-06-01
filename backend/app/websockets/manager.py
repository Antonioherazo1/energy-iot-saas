import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, set[WebSocket]] = defaultdict(set)
        self.loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[channel].add(websocket)

    def disconnect(self, channel: str, websocket: WebSocket) -> None:
        self.active_connections[channel].discard(websocket)
        if not self.active_connections[channel]:
            self.active_connections.pop(channel, None)

    async def broadcast(self, channel: str, payload: dict) -> None:
        stale_connections: list[WebSocket] = []
        for websocket in self.active_connections.get(channel, set()):
            try:
                await websocket.send_json(payload)
            except RuntimeError:
                stale_connections.append(websocket)
        for websocket in stale_connections:
            self.disconnect(channel, websocket)

    def broadcast_threadsafe(self, channel: str, payload: dict) -> None:
        if self.loop is None:
            logger.debug("WebSocket event loop is not ready; skipping channel %s", channel)
            return

        future = asyncio.run_coroutine_threadsafe(self.broadcast(channel, payload), self.loop)
        future.add_done_callback(self._log_broadcast_error)

    @staticmethod
    def _log_broadcast_error(future: asyncio.Future) -> None:
        try:
            future.result()
        except Exception:
            logger.exception("WebSocket broadcast failed")


websocket_manager = WebSocketManager()
