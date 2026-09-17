from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class ResourceEvent:
    resource: str
    start: Fraction
    end: Fraction
    operation: str
    command_id: int | None = None
    task: str | None = None
    detail: str = ""
    color_group: str = "neutral"

    @property
    def duration(self) -> Fraction:
        return self.end - self.start
