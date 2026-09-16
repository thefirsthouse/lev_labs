from __future__ import annotations

from dataclasses import dataclass

from .entities import TaskType, Command


@dataclass
class DurationDist:
    # dict duration->weight
    weights: dict[int, int]


def generate_task_commands(task: TaskType, count: int, rng, dist: dict[int, int], start_id: int) -> list[Command]:
    durations = list(dist.keys())
    w = list(dist.values())

    cmds: list[Command] = []
    for i in range(count):
        dur = rng.choices(durations, weights=w, k=1)[0]
        cmds.append(Command(id=start_id + len(cmds), task=task, duration=dur))
    return cmds
