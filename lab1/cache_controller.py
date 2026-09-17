from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class CacheController:
    pending_misses: deque[int] = field(default_factory=deque)
