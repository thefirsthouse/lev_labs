from __future__ import annotations

from dataclasses import dataclass

from .entities import CacheState


@dataclass
class Cache:
    state: CacheState = CacheState.IDLE
