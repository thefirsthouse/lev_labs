from __future__ import annotations

from collections import deque
from fractions import Fraction
import random

from .bus import Bus
from .cache import Cache
from .cache_controller import CacheController
from .entities import (
    BusRequest,
    BusRequestSource,
    BusState,
    Command,
    PipelineState,
    TaskType,
    TransferType,
)
from .memory import BufferElement, Memory
from .pipeline import Pipeline
from .scheduler import SimulationConfig
from .stats import Stats
from .time_freq import sb_tick, to_ns
from .uso import USO


class Simulator:
    def __init__(self, cfg: SimulationConfig) -> None:
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self.global_time: Fraction = Fraction(0)
        self.command_stream: list[Command] = []
        self.stream_index: int = 0
        self.pipelines = [Pipeline(1), Pipeline(2)]
        self.cache = Cache()
        self.cache_controller = CacheController()
        self.bus = Bus()
        self.memory = Memory()
        self.buffer = BufferElement()
        self.uso = USO()
        self.seq_counter = 0
        self.stats = Stats()
        self.event_log: list[str] = []
        self.finished = False
        self.error: str | None = None
        self.current_tick = 0
        self.words_per_line = cfg.words_per_line

    def reset(self) -> None:
        self.__init__(self.cfg)

    def generate_variant3(self) -> None:
        self.command_stream = []
        self.command_stream += self._gen_task(TaskType.MDO, 30, {5: 70, 2: 20, 1: 10})
        self.command_stream += self._gen_task(TaskType.MSO, 40, {2: 70, 5: 20, 1: 10})
        self.command_stream += self._gen_task(TaskType.UPR, 30, {2: 80, 1: 20})
        disp_count = self.rng.randint(10, 70)
        self.command_stream += self._gen_task(TaskType.DISP, disp_count, {2: 60, 1: 40})
        for cmd in self.command_stream:
            cmd.status = "WAITING"
            cmd.cache_hit = None
        self.stats.total_commands = len(self.command_stream)

    def _gen_task(self, task: TaskType, count: int, dist: dict[int, int]) -> list[Command]:
        start_id = len(self.command_stream)
        durations = list(dist.keys())
        w = list(dist.values())
        cmds: list[Command] = []
        for _ in range(count):
            dur = self.rng.choices(durations, weights=w, k=1)[0]
            cmds.append(Command(id=start_id + len(cmds), task=task, duration=dur))
        return cmds

    def _new_seq(self) -> int:
        s = self.seq_counter
        self.seq_counter += 1
        return s

    def _sb_ticks_for_memory_words(self, w: int) -> int:
        return 4 + max(0, w - 1)

    def enqueue_bus_request(self, source: BusRequestSource, transfer_type: TransferType, duration_sb: int, pipeline_id: int) -> None:
        req = BusRequest(
            seq=self._new_seq(),
            source=source,
            transfer_type=transfer_type,
            duration_sb=duration_sb,
            pipeline_id=pipeline_id,
        )
        self.bus.fifo.append(req)

    def _arbitrate_and_start_if_possible(self) -> None:
        if self.bus.state != BusState.FREE or not self.bus.fifo:
            return

        req = self.bus.fifo.popleft()
        self.bus.state = BusState.BUSY
        self.bus.current_request = req
        # Bus transfer starts at the current SB boundary corresponding to the simulation time.
        # The bus is granted exactly when it becomes free, so start_sb is derived from current global_time.
        start_sb = sb_tick(self.global_time)
        self.bus.current_sb_start = start_sb
        self.bus.current_sb_end = start_sb + req.duration_sb

        if req.transfer_type == TransferType.MEMORY:
            self.memory.busy = True
            self.buffer.busy = True
            self.buffer.word_total = self.words_per_line
            self.buffer.word_index = 0
        elif req.transfer_type == TransferType.USO:
            self.uso.busy = True

        p = self.pipelines[req.pipeline_id - 1]
        p.state = PipelineState.TRANSFER
        p.transfer_type = req.transfer_type

    def _process_bus_completion_if_in_interval(self, t_from: Fraction, t_to: Fraction) -> None:
        if self.bus.state != BusState.BUSY:
            return

        finish_time = Fraction((self.bus.current_sb_end) * 50, 19)
        if t_from < finish_time <= t_to:
            req = self.bus.current_request
            self.bus.state = BusState.FREE
            self.bus.current_request = None

            if req.transfer_type == TransferType.MEMORY:
                self.memory.busy = False
                self.buffer.busy = False
                self.stats.op_accesses_words += self.words_per_line

                p = self.pipelines[req.pipeline_id - 1]
                if self.cache_controller.pending_misses and self.cache_controller.pending_misses[0] == p.id:
                    self.cache_controller.pending_misses.popleft()
                
                p.state = PipelineState.EXECUTE
                p.remaining = p.command.duration
                p.transfer_type = None

            elif req.transfer_type == TransferType.USO:
                self.uso.busy = False
                self.stats.uso_accesses += 1
                p = self.pipelines[req.pipeline_id - 1]
                p.state = PipelineState.IDLE
                if p.command is not None:
                    p.command.status = "DONE"
                p.command = None
                p.transfer_type = None

            self.stats.bus_busy_sb_ticks += req.duration_sb

    def step(self) -> None:
        if self.finished:
            return

        t0 = self.global_time
        t1 = t0 + 1

        # Phase A: process bus completions
        self._process_bus_completion_if_in_interval(t0, t1)
        self._arbitrate_and_start_if_possible()

        # Phase B: Process ongoing work & check completions
        # Lookups that are finishing
        for p in self.pipelines:
            if p.state == PipelineState.LOOKUP and p.lookup_remaining == 1:
                p.lookup_remaining = 0
                # Lookup completed, do cache verdict
                hit = self.rng.random() < self.cfg.p_hit
                cmd = p.command
                cmd.cache_hit = hit

                if hit:
                    self.stats.hits += 1
                    p.state = PipelineState.EXECUTE
                    p.remaining = cmd.duration
                else:
                    self.stats.misses += 1
                    p.state = PipelineState.WAIT_BUS
                    self.cache_controller.pending_misses.append(p.id)
                    mem_sb = self._sb_ticks_for_memory_words(self.words_per_line)
                    self.enqueue_bus_request(BusRequestSource.CACHE_CONTROLLER, TransferType.MEMORY, mem_sb, p.id)

        # Execute that is finishing
        for p in self.pipelines:
            if p.state == PipelineState.EXECUTE and p.remaining == 1:
                p.remaining = 0
                p.busy_mp_ticks += 1
                # Execute completed
                cmd = p.command
                if cmd.task == TaskType.UPR:
                    self.enqueue_bus_request(BusRequestSource.MP, TransferType.USO, self.cfg.uso_access_sb_ticks, p.id)
                    p.state = PipelineState.WAIT_BUS
                    p.transfer_type = TransferType.USO
                else:
                    cmd.status = "DONE"
                    p.command = None
                    p.state = PipelineState.IDLE
            elif p.state == PipelineState.EXECUTE and p.remaining > 1:
                # Still executing
                p.remaining -= 1
                p.busy_mp_ticks += 1

        # Phase C: arbitrate again for new requests
        self._arbitrate_and_start_if_possible()

        # Phase D: issue new commands to free pipelines
        free = [p for p in self.pipelines if p.state == PipelineState.IDLE]
        for p in sorted(free, key=lambda x: x.id):
            if self.stream_index >= len(self.command_stream):
                break
            cmd = self.command_stream[self.stream_index]
            self.stream_index += 1
            cmd.status = "ACTIVE"
            p.command = cmd
            p.state = PipelineState.LOOKUP
            p.lookup_remaining = 1

        # Stats & finish
        self.stats.mp_total_ticks += 1
        self.stats.sb_total_ticks = max(self.stats.sb_total_ticks, sb_tick(t1) + 1)
        self.stats.pipeline1_busy_mp_ticks = self.pipelines[0].busy_mp_ticks
        self.stats.pipeline2_busy_mp_ticks = self.pipelines[1].busy_mp_ticks
        self.check_invariants()
        self.global_time = t1
        self.current_tick += 1

        if self.finished_condition():
            self.finished = True
        elif self.current_tick >= self.cfg.max_ticks:
            self.finished = True
            self.error = "MAX_TICKS"

    def check_invariants(self) -> None:
        active_pipes = sum(1 for p in self.pipelines if p.state != PipelineState.IDLE)
        assert active_pipes <= 2
        if self.bus.state == BusState.BUSY:
            assert self.bus.current_request is not None
        for p in self.pipelines:
            if p.command is not None:
                assert p.command.status != "DONE" or p.state == PipelineState.IDLE
                assert p.remaining >= 0
                assert p.lookup_remaining >= 0

    def finished_condition(self) -> bool:
        if self.stream_index < len(self.command_stream):
            return False
        if any(p.state != PipelineState.IDLE for p in self.pipelines):
            return False
        if self.bus.fifo or self.bus.state == BusState.BUSY:
            return False
        if self.cache_controller.pending_misses:
            return False
        return True

    def run_steps(self, n: int) -> None:
        for _ in range(n):
            if self.finished:
                break
            self.step()

    def run_full(self) -> None:
        while not self.finished:
            self.step()

    def snapshot(self) -> str:
        p1, p2 = self.pipelines
        lines = []
        lines.append(f"Такт МП: {int(self.global_time)} | Такт СШ: {sb_tick(self.global_time)} | t={self.global_time}")
        for p in (p1, p2):
            cmd = p.command
            cmd_str = "" if cmd is None else f"{cmd.task.name} #{cmd.id} dur={cmd.duration}" 
            rem = p.lookup_remaining if p.state == PipelineState.LOOKUP else (p.remaining if p.state == PipelineState.EXECUTE else "")
            lines.append(f"P{p.id}: {p.state.name:12s} {cmd_str:20s} {('rem=' + str(rem)) if rem!='' else ''}")
        lines.append(f"Bus: {self.bus.state.name} fifo={len(self.bus.fifo)}")
        if self.bus.fifo:
            for i, req in enumerate(list(self.bus.fifo)[:5]):
                lines.append(f"  [{i}]: seq={req.seq} {req.source.name}->{req.transfer_type.name} P{req.pipeline_id}")
        lines.append(f"Контроллер: pending={list(self.cache_controller.pending_misses)}")
        return "\n".join(lines)
