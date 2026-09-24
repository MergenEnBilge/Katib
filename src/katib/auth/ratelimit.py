"""In-process limiter for failed logins, per account and per address."""

import time
from collections import defaultdict, deque
from collections.abc import Callable


class LoginLimiter:
    """Blocks a key after `max_failures` failures inside `window` seconds."""

    def __init__(
        self,
        max_failures: int = 5,
        window: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.window = window
        self._clock = clock
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def _trim(self, key: str) -> deque[float]:
        recent = self._failures[key]
        cutoff = self._clock() - self.window
        while recent and recent[0] <= cutoff:
            recent.popleft()
        return recent

    def retry_after(self, key: str) -> int:
        """Seconds until `key` may try again, or 0 when it may try now."""
        recent = self._trim(key)
        if len(recent) < self.max_failures:
            return 0
        return max(1, int(recent[0] + self.window - self._clock()) + 1)

    def fail(self, key: str) -> None:
        self._trim(key).append(self._clock())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
