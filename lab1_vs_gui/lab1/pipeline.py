from __future__ import annotations

from dataclasses import dataclass

from .entities import PipelineState, TransferType


@dataclass
class Pipeline:
    id: int
    state: PipelineState = PipelineState.IDLE
    command: object | None = None
    remaining: int = 0
    lookup_remaining: int = 0
    transfer_type: TransferType | None = None
    busy_mp_ticks: int = 0

    def is_active(self) -> bool:
        return self.state != PipelineState.IDLE
