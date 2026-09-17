from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SimulationConfig:
    seed: int = 42
    p_hit: float = 0.65
    words_per_line: int = 4
    uso_access_sb_ticks: int = 1
    max_ticks: int = 1_000_000
