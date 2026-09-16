from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from collections import deque

from .entities import BusRequest, BusState


@dataclass
class Bus:
    state: BusState = BusState.FREE
    current_request: BusRequest | None = None
    current_sb_start: int = 0
    current_sb_end: int = 0
    fifo: deque[BusRequest] = None

    def __post_init__(self) -> None:
        if self.fifo is None:
            self.fifo = deque()

    def is_busy(self) -> bool:
        return self.state == BusState.BUSY


