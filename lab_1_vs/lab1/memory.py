from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Memory:
    busy: bool = False
    burst_total: int = 0
    access_index: int = 0


@dataclass
class BufferElement:
    busy: bool = False
    word_index: int = 0
    word_total: int = 0
