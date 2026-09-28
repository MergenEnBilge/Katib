"""In-process limiter for failed logins, per account and per address."""

import time
from collections import deque
from collections.abc import Callable


class LoginLimiter:
    """Blocks a key after `max_failures` failures inside `window` seconds.

    `retry_after` is checked on every attempt, not only failed ones, so it must never create an
    entry for a key that has no failures -- otherwise looking a key up at all, which anyone can
    force just by trying to log in, would grow this dict forever.
    """

    def __init__(
        self,
        max_failures: int = 5,
        window: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.window = window
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}

    def _trim(self, key: str) -> deque[float]:
        recent = self._failures.get(key)
        if recent is None:
            return deque()
        cutoff = self._clock() - self.window
        while recent and recent[0] <= cutoff:
            recent.popleft()
        if not recent:
            del self._failures[key]
        return recent

    def retry_after(self, key: str) -> int:
        """Seconds until `key` may try again, or 0 when it may try now."""
        recent = self._trim(key)
        if len(recent) < self.max_failures:
            return 0
        return max(1, int(recent[0] + self.window - self._clock()) + 1)

    def fail(self, key: str) -> None:
        recent = self._trim(key)
        recent.append(self._clock())
        self._failures[key] = recent

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
