import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import HTTPException, Request

from auth.config import get_auth_settings

# In memory: resets on restart and is per process. Enough for one server;
# use Redis (or the reverse proxy) when you run several workers.
_hits: Dict[str, Deque[float]] = defaultdict(deque)


def reset() -> None:
    _hits.clear()


def rate_limit(request: Request) -> None:
    """Dependency: at most AUTH_RATE_LIMIT_PER_MINUTE requests per minute per IP."""

    limit = get_auth_settings().AUTH_RATE_LIMIT_PER_MINUTE
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()

    window = _hits[key]

    while window and now - window[0] > 60:
        window.popleft()

    if len(window) >= limit:
        raise HTTPException(
            status_code=429,
            detail={"code": "rate_limited", "message": "Too many requests. Try again in a minute."},
            headers={"Retry-After": "60"},
        )

    window.append(now)
