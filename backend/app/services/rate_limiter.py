import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_WINDOW_SECONDS = 300
_MAX_PER_KEY = 10
_MAX_PER_IP = 40

_attempts_by_key: dict[str, deque[float]] = defaultdict(deque)
_attempts_by_ip: dict[str, deque[float]] = defaultdict(deque)


def _prune(bucket: deque[float], now: float) -> None:
    while bucket and now - bucket[0] > _WINDOW_SECONDS:
        bucket.popleft()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_auth_rate_limit(request: Request, key: str) -> None:
    now = time.monotonic()
    ip = _client_ip(request)

    key_bucket = _attempts_by_key[key]
    _prune(key_bucket, now)
    if len(key_bucket) >= _MAX_PER_KEY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos, espera unos minutos",
        )

    ip_bucket = _attempts_by_ip[ip]
    _prune(ip_bucket, now)
    if len(ip_bucket) >= _MAX_PER_IP:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos desde esta red, espera unos minutos",
        )

    key_bucket.append(now)
    ip_bucket.append(now)
