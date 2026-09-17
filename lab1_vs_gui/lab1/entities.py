from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TaskType(Enum):
    MDO = auto()
    MSO = auto()
    UPR = auto()
    DISP = auto()


class PipelineState(Enum):
    IDLE = auto()
    LOOKUP = auto()
    WAIT_BUS = auto()
    TRANSFER = auto()
    EXECUTE = auto()


class BusState(Enum):
    FREE = auto()
    BUSY = auto()


class CacheState(Enum):
    IDLE = auto()
    LOOKUP_PENDING = auto()
    REFILL = auto()


class BusRequestSource(Enum):
    CACHE_CONTROLLER = auto()
    MP = auto()


class TransferType(Enum):
    MEMORY = auto()
    USO = auto()


@dataclass
class Command:
    id: int
    task: TaskType
    duration: int
    status: str = "WAITING"
    cache_hit: bool | None = None


@dataclass
class BusRequest:
    seq: int
    source: BusRequestSource
    transfer_type: TransferType
    duration_sb: int
    pipeline_id: int
