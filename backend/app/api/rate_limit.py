from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class RateLimiter:
    limit_per_minute: int
    buckets: dict[str, deque[datetime]] = field(default_factory=dict)

    def allow(self, key: str, now: datetime | None = None) -> bool:
        if self.limit_per_minute <= 0:
            return True

        current = now or datetime.now(timezone.utc)
        window_start = current - timedelta(minutes=1)
        bucket = self.buckets.setdefault(key, deque())

        while bucket and bucket[0] <= window_start:
            bucket.popleft()

        if len(bucket) >= self.limit_per_minute:
            return False

        bucket.append(current)
        return True
