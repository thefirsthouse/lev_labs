from __future__ import annotations

from dataclasses import dataclass
# from fractions import Fraction


@dataclass
class SimulationConfig:
    seed: int = 42
    p_hit: float = 0.65
    words_per_line: int = 4
    uso_access_sb_ticks: int = 1
    max_ticks: int = 1_000_000

    # durations and arbitration assumptions are encoded in model
