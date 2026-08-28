from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class RateLimiter:
    limit_per_minute: int
    buckets: dict[str, deque[datetime]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def allow(self, key: str, now: datetime | None = None) -> bool:
        if self.limit_per_minute <= 0:
            return True

        current = now or datetime.now(timezone.utc)
        window_start = current - timedelta(minutes=1)

        with self._lock:
            # Trim every bucket's expired timestamps and drop any that end
            # up empty — not just this key's. A key queried only once (a
            # one-off visitor, a scanner) would otherwise never get cleaned
            # up, since nothing else would ever look at its entry again.
            stale_keys = []
            for other_key, other_bucket in self.buckets.items():
                while other_bucket and other_bucket[0] <= window_start:
                    other_bucket.popleft()
                if not other_bucket:
                    stale_keys.append(other_key)
            for stale_key in stale_keys:
                del self.buckets[stale_key]

            bucket = self.buckets.setdefault(key, deque())

            if len(bucket) >= self.limit_per_minute:
                return False

            bucket.append(current)
            return True
