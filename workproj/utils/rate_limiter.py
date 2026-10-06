"""Thread-safe reservation-based rate limiter."""

from __future__ import annotations

import threading
import time
from typing import Callable


class RateLimiter:
    """Ensure starts of network requests are separated by min_interval seconds."""

    def __init__(
        self,
        min_interval: float = 0.0,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval = max(0.0, float(min_interval))
        self.clock = clock
        self.sleep = sleep
        self._lock = threading.Lock()
        self._next_allowed = None  # type: float | None

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        with self._lock:
            now = self.clock()
            if self._next_allowed is None:
                wait_for = 0.0
                reserved_at = now
            else:
                wait_for = max(0.0, self._next_allowed - now)
                reserved_at = max(now, self._next_allowed)
            self._next_allowed = reserved_at + self.min_interval
        if wait_for > 0:
            self.sleep(wait_for)
