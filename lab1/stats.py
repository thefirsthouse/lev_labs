from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Stats:
    total_commands: int = 0
    hits: int = 0
    misses: int = 0
    op_accesses_words: int = 0
    uso_accesses: int = 0
    bus_busy_sb_ticks: int = 0
    sb_total_ticks: int = 0
    mp_total_ticks: int = 0
    pipeline1_busy_mp_ticks: int = 0
    pipeline2_busy_mp_ticks: int = 0

    def hit_rate(self) -> float:
        return 0.0 if (self.hits + self.misses) == 0 else self.hits / (self.hits + self.misses)
