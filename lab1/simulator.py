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
    CacheState,
    Command,
    PipelineState,
    TaskType,
    TransferType,
)
from .memory import BufferElement, Memory
from .pipeline import Pipeline
from .scheduler import SimulationConfig
from .stats import Stats
from .time_freq import sb_tick
from .trace import ResourceEvent
from .uso import USO


class Simulator:
    """Tick-accurate simulation engine based on the supplied laboratory model.

    The important addition is a resource trace. The GUI never invents activity;
    it renders ResourceEvent objects emitted by this engine.
    """

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

        self.trace_events: list[ResourceEvent] = []
        self._open_trace: dict[tuple, dict] = {}
        # First tick at which each command entered a pipeline. Used only for
        # diagnostics/progress display; simulation behaviour is unchanged.
        self.command_issue_tick: dict[int, Fraction] = {}

    # ---------- Trace API ----------
    def _trace_start(
        self,
        resource: str,
        key_extra: object,
        start: Fraction,
        operation: str,
        command_id: int | None = None,
        task: str | None = None,
        detail: str = "",
        color_group: str = "neutral",
    ) -> tuple:
        key = (resource, key_extra)
        self._open_trace[key] = {
            "resource": resource,
            "start": start,
            "operation": operation,
            "command_id": command_id,
            "task": task,
            "detail": detail,
            "color_group": color_group,
        }
        return key

    def _trace_end(self, key: tuple, end: Fraction) -> None:
        rec = self._open_trace.pop(key, None)
        if rec is None:
            return
        if end <= rec["start"]:
            return
        self.trace_events.append(
            ResourceEvent(
                resource=rec["resource"],
                start=rec["start"],
                end=end,
                operation=rec["operation"],
                command_id=rec["command_id"],
                task=rec["task"],
                detail=rec["detail"],
                color_group=rec["color_group"],
            )
        )

    def _trace_add(
        self,
        resource: str,
        start: Fraction,
        end: Fraction,
        operation: str,
        command_id: int | None = None,
        task: str | None = None,
        detail: str = "",
        color_group: str = "neutral",
    ) -> None:
        if end <= start:
            return
        self.trace_events.append(
            ResourceEvent(
                resource=resource,
                start=start,
                end=end,
                operation=operation,
                command_id=command_id,
                task=task,
                detail=detail,
                color_group=color_group,
            )
        )

    def _close_all_trace(self) -> None:
        for key in list(self._open_trace):
            self._trace_end(key, self.global_time)

    # ---------- Simulation ----------
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
        self.event_log.append(
            f"GENERATED MDO={30}, MSO={40}, UPR={30}, DISP={disp_count}, TOTAL={len(self.command_stream)}"
        )

    def generate_test(self, commands: list[tuple[TaskType, int]]) -> None:
        self.command_stream = [Command(i, task, duration) for i, (task, duration) in enumerate(commands)]
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
        # 4-1-1-1: first access = 4 SB ticks, remaining accesses = 1 each.
        return 4 + max(0, w - 1)

    def enqueue_bus_request(
        self,
        source: BusRequestSource,
        transfer_type: TransferType,
        duration_sb: int,
        pipeline_id: int,
    ) -> None:
        req = BusRequest(
            seq=self._new_seq(),
            source=source,
            transfer_type=transfer_type,
            duration_sb=duration_sb,
            pipeline_id=pipeline_id,
        )
        self.bus.fifo.append(req)
        self.event_log.append(
            f"{int(self.global_time)} BUS enqueue P{pipeline_id} {source.name}:{transfer_type.name} cmd={self.pipelines[pipeline_id-1].command.id if self.pipelines[pipeline_id-1].command else '-'} dur_sb={duration_sb}"
        )

        if transfer_type == TransferType.MEMORY:
            self.cache.state = CacheState.REFILL
        # USO becomes busy only when the FIFO request actually receives the bus.

    def _arbitrate_and_start_if_possible(self) -> None:
        if self.bus.state != BusState.FREE or not self.bus.fifo:
            return

        req = self.bus.fifo.popleft()
        now = self.global_time
        self.bus.state = BusState.BUSY
        self.bus.current_request = req
        start_sb = sb_tick(now)
        finish = Fraction((start_sb + req.duration_sb) * 50, 19)
        self.bus.current_sb_start = start_sb
        self.bus.current_sb_end = start_sb + req.duration_sb

        p = self.pipelines[req.pipeline_id - 1]
        cmd = p.command
        task_name = cmd.task.name if cmd else None
        cmd_id = cmd.id if cmd else None

        # The pipeline may have been waiting for a FIFO grant.
        if cmd_id is not None:
            wait_key = (f"PIPELINE_{p.id}", ("wait_bus", cmd_id))
            self._trace_end(wait_key, now)

        p.state = PipelineState.TRANSFER
        p.transfer_type = req.transfer_type

        transfer_label = "MEMORY TRANSFER" if req.transfer_type == TransferType.MEMORY else "USO ACCESS"
        detail = (
            f"SB {start_sb}..{start_sb + req.duration_sb}; source={req.source.name}; "
            f"duration={req.duration_sb} SB ticks"
        )

        self._trace_add(
            "SYSTEM_BUS",
            now,
            finish,
            transfer_label,
            cmd_id,
            task_name,
            detail,
            "bus",
        )
        self._trace_add(
            f"PIPELINE_{p.id}",
            now,
            finish,
            "TRANSFER",
            cmd_id,
            task_name,
            detail,
            "transfer",
        )

        if req.transfer_type == TransferType.MEMORY:
            self.memory.busy = True
            self.memory.burst_total = self.words_per_line
            self.memory.access_index = 0
            self.buffer.busy = True
            self.buffer.word_total = self.words_per_line
            self.buffer.word_index = 0
            self._trace_add(
                "CACHE_CONTROLLER",
                now,
                finish,
                "REFILL",
                cmd_id,
                task_name,
                f"pending miss; {self.words_per_line} words; 4-1-1-1",
                "cache_miss",
            )
            self._trace_add(
                "BUFFER_ELEMENT",
                now,
                finish,
                "BUFFER",
                cmd_id,
                task_name,
                f"receiving {self.words_per_line} words",
                "memory",
            )
            self._trace_add(
                "MEMORY",
                now,
                finish,
                "READ",
                cmd_id,
                task_name,
                f"{self.words_per_line} words; first=4 SB, next=1 SB",
                "memory",
            )
            self.cache.state = CacheState.REFILL
        elif req.transfer_type == TransferType.USO:
            self.uso.busy = True
            self._trace_add(
                "USO",
                now,
                finish,
                "ACCESS",
                cmd_id,
                task_name,
                f"direct MP→USO access; {req.duration_sb} SB tick(s)",
                "uso",
            )

        self.event_log.append(
            f"{int(now)} BUS start seq={req.seq} P{req.pipeline_id} {req.source.name}:{req.transfer_type.name} sb={start_sb}->{start_sb + req.duration_sb}"
        )

    def _process_bus_completion_if_in_interval(self, t_from: Fraction, t_to: Fraction) -> None:
        if self.bus.state != BusState.BUSY:
            return

        finish_time = Fraction(self.bus.current_sb_end * 50, 19)
        # A bus transfer ends at a fractional MP time because the SB is slower.
        # If that fractional endpoint falls inside the previous MP interval, the
        # next step must still retire it; otherwise a request could remain BUSY
        # forever after its SB end had already passed.
        if finish_time <= t_to:
            req = self.bus.current_request
            assert req is not None

            self.bus.state = BusState.FREE
            self.bus.current_request = None

            p = self.pipelines[req.pipeline_id - 1]
            if req.transfer_type == TransferType.MEMORY:
                self.memory.busy = False
                self.buffer.busy = False
                self.stats.op_accesses_words += self.words_per_line
                self.cache.state = CacheState.IDLE
                # A FIFO bus can complete misses in a different order from the
                # order in which pipeline ids entered the pending list. Remove
                # the completed pipeline id wherever it sits in that queue.
                try:
                    self.cache_controller.pending_misses.remove(p.id)
                except ValueError:
                    pass
                p.state = PipelineState.EXECUTE
                p.remaining = p.command.duration
                p.transfer_type = None
                cmd = p.command
                self._trace_add(
                    f"PIPELINE_{p.id}",
                    finish_time,
                    finish_time + cmd.duration,
                    "EXECUTE",
                    cmd.id,
                    cmd.task.name,
                    f"{cmd.duration} MP ticks; after MEMORY refill",
                    "task",
                )
                self.event_log.append(f"{int(finish_time)} MEMORY done P{p.id}; execute resumes")
            elif req.transfer_type == TransferType.USO:
                self.uso.busy = False
                self.stats.uso_accesses += 1
                p.state = PipelineState.IDLE
                if p.command is not None:
                    p.command.status = "DONE"
                p.command = None
                p.transfer_type = None
                self.event_log.append(f"{int(finish_time)} USO done P{p.id}")

            self.stats.bus_busy_sb_ticks += req.duration_sb

    def _issue_command_to_pipeline(self, p: Pipeline, cmd: Command, start: Fraction) -> None:
        cmd.status = "ACTIVE"
        self.command_issue_tick[cmd.id] = start
        p.command = cmd
        p.state = PipelineState.LOOKUP
        p.lookup_remaining = 1
        task_name = cmd.task.name
        self.cache.state = CacheState.LOOKUP_PENDING

        self._trace_add(
            f"PIPELINE_{p.id}",
            start,
            start + 1,
            "LOOKUP",
            cmd.id,
            task_name,
            "1 MP tick cache lookup",
            "lookup",
        )
        self._trace_add(
            "CACHE",
            start,
            start + 1,
            "LOOKUP",
            cmd.id,
            task_name,
            "cache lookup",
            "cache",
        )

    def _finish_lookup(self, p: Pipeline, decision_time: Fraction) -> None:
        p.lookup_remaining = 0
        cmd = p.command
        assert cmd is not None
        hit = self.rng.random() < self.cfg.p_hit
        cmd.cache_hit = hit

        self._trace_add(
            "CACHE",
            decision_time,
            decision_time + Fraction(1, 4),
            "HIT" if hit else "MISS",
            cmd.id,
            cmd.task.name,
            f"p_hit={self.cfg.p_hit:.0%}",
            "cache_hit" if hit else "cache_miss",
        )

        if hit:
            self.stats.hits += 1
            self.cache.state = CacheState.IDLE
            p.state = PipelineState.EXECUTE
            p.remaining = cmd.duration
            exec_end = decision_time + cmd.duration
            self._trace_add(
                f"PIPELINE_{p.id}",
                decision_time,
                exec_end,
                "EXECUTE",
                cmd.id,
                cmd.task.name,
                f"{cmd.duration} MP ticks; CACHE HIT",
                "task",
            )
        else:
            self.stats.misses += 1
            p.state = PipelineState.WAIT_BUS
            self.cache_controller.pending_misses.append(p.id)
            self._trace_start(
                f"PIPELINE_{p.id}",
                ("wait_bus", cmd.id),
                decision_time,
                "WAIT BUS",
                cmd.id,
                cmd.task.name,
                "waiting for FIFO system bus grant",
                "wait",
            )
            mem_sb = self._sb_ticks_for_memory_words(self.words_per_line)
            self.enqueue_bus_request(
                BusRequestSource.CACHE_CONTROLLER,
                TransferType.MEMORY,
                mem_sb,
                p.id,
            )
        # If no cache operation remains immediately, keep it idle/refill as appropriate.
        if self.cache_controller.pending_misses:
            self.cache.state = CacheState.REFILL if self.bus.is_busy() else self.cache.state

    def step(self) -> None:
        if self.finished:
            return

        t0 = self.global_time
        t1 = t0 + 1

        # Phase A: finish bus requests that cross this MP interval, then grant FIFO.
        self._process_bus_completion_if_in_interval(t0, t1)
        self._arbitrate_and_start_if_possible()

        # Phase B: lookups that end at this MP boundary.
        for p in self.pipelines:
            if p.state == PipelineState.LOOKUP and p.lookup_remaining == 1:
                self._finish_lookup(p, t1)

        # Phase C: executions that finish at this MP boundary.
        for p in self.pipelines:
            if p.state == PipelineState.EXECUTE and p.remaining == 1:
                p.remaining = 0
                p.busy_mp_ticks += 1
                cmd = p.command
                assert cmd is not None
                if cmd.task == TaskType.UPR:
                    self.enqueue_bus_request(
                        BusRequestSource.MP,
                        TransferType.USO,
                        self.cfg.uso_access_sb_ticks,
                        p.id,
                    )
                    p.state = PipelineState.WAIT_BUS
                    p.transfer_type = TransferType.USO
                    self._trace_start(
                        f"PIPELINE_{p.id}",
                        ("wait_bus", cmd.id),
                        t1,
                        "WAIT BUS",
                        cmd.id,
                        cmd.task.name,
                        "waiting for FIFO system bus grant to USO",
                        "wait",
                    )
                else:
                    cmd.status = "DONE"
                    p.command = None
                    p.state = PipelineState.IDLE
            elif p.state == PipelineState.EXECUTE and p.remaining > 1:
                p.remaining -= 1
                p.busy_mp_ticks += 1

        # A request may have been enqueued in Phase C.
        self._arbitrate_and_start_if_possible()

        # Phase D: issue new commands into free pipelines.
        free = [p for p in self.pipelines if p.state == PipelineState.IDLE]
        for p in sorted(free, key=lambda x: x.id):
            if self.stream_index >= len(self.command_stream):
                break
            cmd = self.command_stream[self.stream_index]
            self.stream_index += 1
            self._issue_command_to_pipeline(p, cmd, t1)

        self.stats.mp_total_ticks += 1
        self.stats.sb_total_ticks = max(self.stats.sb_total_ticks, sb_tick(t1) + 1)
        self.stats.pipeline1_busy_mp_ticks = self.pipelines[0].busy_mp_ticks
        self.stats.pipeline2_busy_mp_ticks = self.pipelines[1].busy_mp_ticks

        self.check_invariants()
        self.global_time = t1
        self.current_tick += 1

        if self.finished_condition():
            self.finished = True
            self._close_all_trace()
        elif self.current_tick >= self.cfg.max_ticks:
            self.finished = True
            self.error = "MAX_TICKS"
            self._close_all_trace()

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

    def snapshot_dict(self) -> dict:
        pipelines = []
        for p in self.pipelines:
            cmd = p.command
            pipelines.append({
                "id": p.id,
                "state": p.state.name,
                "command_id": None if cmd is None else cmd.id,
                "command_task": None if cmd is None else cmd.task.name,
                "remaining": p.remaining if p.state == PipelineState.EXECUTE else None,
                "lookup_remaining": p.lookup_remaining if p.state == PipelineState.LOOKUP else None,
                "transfer_type": None if p.transfer_type is None else p.transfer_type.name,
            })
        return {
            "tick_mp": int(self.global_time),
            "tick_sb": sb_tick(self.global_time),
            "pipelines": pipelines,
            "cache": {"state": self.cache.state.name},
            "bus": {
                "state": self.bus.state.name,
                "fifo_len": len(self.bus.fifo),
                "current": None if self.bus.current_request is None else {
                    "seq": self.bus.current_request.seq,
                    "source": self.bus.current_request.source.name,
                    "transfer_type": self.bus.current_request.transfer_type.name,
                    "pipeline_id": self.bus.current_request.pipeline_id,
                    "sb_start": self.bus.current_sb_start,
                    "sb_end": self.bus.current_sb_end,
                },
            },
            "cache_controller": {"pending_misses": list(self.cache_controller.pending_misses)},
            "buffer": {"busy": self.buffer.busy, "word_index": self.buffer.word_index, "word_total": self.buffer.word_total},
            "memory": {"busy": self.memory.busy, "access_index": self.memory.access_index, "burst_total": self.memory.burst_total},
            "uso": {"busy": self.uso.busy},
            "stats": {
                "total_commands": self.stats.total_commands,
                "hits": self.stats.hits,
                "misses": self.stats.misses,
                "hit_rate": self.stats.hit_rate(),
                "op_accesses_words": self.stats.op_accesses_words,
                "uso_accesses": self.stats.uso_accesses,
                "bus_busy_sb_ticks": self.stats.bus_busy_sb_ticks,
            },
            "finished": self.finished,
            "error": self.error,
        }

    def snapshot(self) -> str:
        s = self.snapshot_dict()
        from collections import Counter
        counts = Counter(c.task.name for c in self.command_stream)
        issued = Counter(c.task.name for c in self.command_stream if c.status != "WAITING")
        done = Counter(c.task.name for c in self.command_stream if c.status == "DONE")
        lines = [f"Такт МП: {s['tick_mp']} | Такт СШ: {s['tick_sb']}"]
        lines.append("Поток: " + ", ".join(f"{k}={counts.get(k,0)}" for k in ("MDO","MSO","UPR","DISP")))
        lines.append("Введено: " + ", ".join(f"{k}={issued.get(k,0)}" for k in ("MDO","MSO","UPR","DISP")))
        lines.append("Готово: " + ", ".join(f"{k}={done.get(k,0)}" for k in ("MDO","MSO","UPR","DISP")))
        for p in s["pipelines"]:
            cmd = "" if p["command_id"] is None else f"{p['command_task']} #{p['command_id']}"
            lines.append(f"P{p['id']}: {p['state']:12s} {cmd}")
        b = s["bus"]
        lines.append(f"СШ: {b['state']} FIFO={b['fifo_len']}")
        if b["current"]:
            c = b["current"]
            lines.append(f"  current: {c['source']}:{c['transfer_type']} P{c['pipeline_id']} SB {c['sb_start']}..{c['sb_end']}")
        lines.append(f"КЭШ: {s['cache']['state']}")
        lines.append(f"КЭШ-контроллер: pending={s['cache_controller']['pending_misses']}")
        lines.append(f"БЭ: {'BUSY' if s['buffer']['busy'] else 'FREE'}")
        lines.append(f"ОП: {'BUSY' if s['memory']['busy'] else 'FREE'}")
        lines.append(f"УСО: {'BUSY' if s['uso']['busy'] else 'FREE'}")
        return "\n".join(lines)
