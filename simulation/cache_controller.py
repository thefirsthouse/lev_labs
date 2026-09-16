from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class CacheController:
    # queue of pipeline_ids waiting for refill completion
    pending_misses: deque[int] = field(default_factory=deque)

