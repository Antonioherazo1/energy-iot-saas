from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any

_last_messages: deque[dict[str, Any]] = deque(maxlen=5)
_lock = Lock()


def add_message(topic: str, device_code: str, payload: dict[str, Any]) -> None:
    entry = {
        "topic": topic,
        "device_code": device_code,
        "payload": payload,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    with _lock:
        _last_messages.appendleft(entry)


def get_last_messages() -> list[dict[str, Any]]:
    with _lock:
        return list(_last_messages)
