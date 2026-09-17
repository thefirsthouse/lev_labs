from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from fractions import Fraction
from collections import deque
import random

MP_PER_SB = Fraction(50, 19)  # 700/266

def sb_tick(t_mp: Fraction) -> int:
    return int(t_mp * Fraction(19, 50))

class TaskType(Enum):
    MDO = auto(); MSO = auto(); UPR = auto(); DISP = auto()

class PipelineState(Enum):
    IDLE = auto(); LOOKUP = auto(); WAIT_BUS = auto(); TRANSFER = auto(); EXECUTE = auto()

class BusState(Enum):
    FREE = auto(); BUSY = auto()

class TransferType(Enum):
    MEMORY = auto(); USO = auto()

@dataclass
class Command:
    id: int
    task: TaskType
    duration: int
    status: str = 'WAITING'
    cache_hit: bool | None = None

@dataclass
class BusRequest:
    seq: int
    source: str
    transfer_type: TransferType
    duration_sb: int
    pipeline_id: int
    command_id: int

@dataclass(frozen=True)
class Event:
    resource: str
    start: Fraction
    end: Fraction
    operation: str
    command_id: int | None = None
    task: str | None = None
    detail: str = ''
    group: str = 'neutral'

    @property
    def duration(self) -> Fraction:
        return self.end - self.start

@dataclass
class Pipeline:
    id: int
    state: PipelineState = PipelineState.IDLE
    command: Command | None = None
    remaining: int = 0
    transfer_type: TransferType | None = None

class Simulator:
    """Discrete-time model based directly on the supplied variant-3 engine.

    The only structural addition is a real resource event trace consumed by the GUI.
    """
    def __init__(self, seed: int = 42, p_hit: float = .65, max_ticks: int = 1_000_000):
        self.seed, self.p_hit, self.max_ticks = seed, p_hit, max_ticks
        self.rng = random.Random(seed)
        self.global_time = Fraction(0)
        self.current_tick = 0
        self.stream_index = 0
        self.commands: list[Command] = []
        self.pipelines = [Pipeline(1), Pipeline(2)]
        self.bus_state = BusState.FREE
        self.bus_request: BusRequest | None = None
        self.bus_start_sb = 0
        self.bus_end_sb = 0
        self.bus_fifo: deque[BusRequest] = deque()
        self.cache_busy = False
        self.cache_controller_pending: deque[int] = deque()
        self.buffer_busy = False
        self.memory_busy = False
        self.uso_busy = False
        self.finished = False
        self.error: str | None = None
        self.seq = 0
        self.events: list[Event] = []
        self.log: list[str] = []
        self.hits = self.misses = 0
        self.uso_accesses = 0
        self.op_words = 0
        self.bus_busy_sb_ticks = 0
        self.lookup_seen: set[tuple[int,int]] = set()

    @property
    def total_commands(self): return len(self.commands)
    @property
    def tick_sb(self): return sb_tick(self.global_time)

    def reset(self):
        return Simulator(self.seed, self.p_hit, self.max_ticks)

    def generate_variant3(self):
        self.commands = []
        self._gen(TaskType.MDO, 30, {5:70, 2:20, 1:10})
        self._gen(TaskType.MSO, 40, {2:70, 5:20, 1:10})
        self._gen(TaskType.UPR, 30, {2:80, 1:20})
        self._gen(TaskType.DISP, self.rng.randint(10,70), {2:60, 1:40})
        self.log.append('GEN: ' + ', '.join(f'{t.name}={sum(c.task is t for c in self.commands)}' for t in TaskType))

    def generate_test(self, specs: list[tuple[TaskType,int]]):
        self.commands = [Command(i,t,d) for i,(t,d) in enumerate(specs)]
        self.log.append('TEST: ' + ', '.join(f'{c.task.name}#{c.id}({c.duration})' for c in self.commands))

    def _gen(self, task, count, dist):
        for _ in range(count):
            d = self.rng.choices(list(dist), weights=list(dist.values()), k=1)[0]
            self.commands.append(Command(len(self.commands), task, d))

    def _next_seq(self):
        s = self.seq; self.seq += 1; return s

    def _event(self, resource, start, end, op, cmd=None, task=None, detail='', group='neutral'):
        if end > start:
            self.events.append(Event(resource,start,end,op,cmd,task,detail,group))

    def _enqueue_bus(self, source, transfer_type, duration_sb, pipeline_id):
        p = self.pipelines[pipeline_id-1]
        cmd = p.command
        req = BusRequest(self._next_seq(), source, transfer_type, duration_sb, pipeline_id, cmd.id)
        self.bus_fifo.append(req)
        self.log.append(f't={self.current_tick}: FIFO + P{pipeline_id} {source}:{transfer_type.name} cmd={cmd.id}')
        if transfer_type is TransferType.MEMORY:
            self.cache_busy = True
            self.cache_controller_pending.append(pipeline_id)
        p.state = PipelineState.WAIT_BUS
        p.transfer_type = transfer_type

    def _start_bus(self):
        if self.bus_state is not BusState.FREE or not self.bus_fifo:
            return
        req = self.bus_fifo.popleft()
        now = self.global_time
        self.bus_state = BusState.BUSY
        self.bus_request = req
        self.bus_start_sb = sb_tick(now)
        self.bus_end_sb = self.bus_start_sb + req.duration_sb
        finish = Fraction(self.bus_end_sb * 50, 19)
        p = self.pipelines[req.pipeline_id-1]
        task = p.command.task.name if p.command else None
        # Real resource use is drawn on every actual resource, not on a command lane.
        self._event('SYSTEM_BUS', now, finish, 'MEMORY TRANSFER' if req.transfer_type is TransferType.MEMORY else 'USO ACCESS', req.command_id, task,
                    f'SB {self.bus_start_sb}→{self.bus_end_sb}; FIFO seq={req.seq}', 'bus')
        if req.transfer_type is TransferType.MEMORY:
            self.memory_busy = True; self.buffer_busy = True
            self._event('CACHE_CONTROLLER', now, finish, 'REFILL', req.command_id, task, 'cache miss; 4-1-1-1', 'cache_miss')
            self._event('BUFFER_ELEMENT', now, finish, 'BUFFER', req.command_id, task, '4 words', 'memory')
            self._event('MEMORY', now, finish, 'READ', req.command_id, task, 'first access 4 SB, next 1+1+1 SB', 'memory')
        else:
            self.uso_busy = True
            self._event('USO', now, finish, 'ACCESS', req.command_id, task, 'direct MP→USO through SШ', 'uso')
        self._event(f'PIPELINE_{p.id}', now, finish, 'TRANSFER', req.command_id, task, req.transfer_type.name, 'transfer')

    def _complete_bus_if_due(self, t_to: Fraction):
        if self.bus_state is not BusState.BUSY:
            return
        finish = Fraction(self.bus_end_sb * 50, 19)
        if finish > t_to:
            return
        req = self.bus_request; assert req is not None
        p = self.pipelines[req.pipeline_id-1]
        self.bus_state = BusState.FREE; self.bus_request = None
        self.bus_busy_sb_ticks += req.duration_sb
        if req.transfer_type is TransferType.MEMORY:
            self.memory_busy = self.buffer_busy = False
            self.cache_busy = False
            self.op_words += 4
            try: self.cache_controller_pending.remove(p.id)
            except ValueError: pass
            p.state = PipelineState.EXECUTE
            p.remaining = p.command.duration if p.command else 0
            if p.command:
                self._event(f'PIPELINE_{p.id}', finish, finish + p.command.duration, 'EXECUTE', p.command.id, p.command.task.name,
                            f'{p.command.duration} MP ticks after refill', 'task')
        else:
            self.uso_busy = False; self.uso_accesses += 1
            if p.command:
                p.command.status='DONE'
            p.command=None; p.state=PipelineState.IDLE; p.transfer_type=None
        self._start_bus()

    def _lookup_finish(self, p: Pipeline, boundary: Fraction):
        cmd = p.command; assert cmd
        key=(p.id,cmd.id)
        if key in self.lookup_seen: return
        self.lookup_seen.add(key)
        hit = self.rng.random() < self.p_hit
        cmd.cache_hit = hit
        self._event('CACHE', boundary-Fraction(1), boundary, 'HIT' if hit else 'MISS', cmd.id, cmd.task.name,
                    f'p_hit={self.p_hit:.0%}', 'cache_hit' if hit else 'cache_miss')
        if hit:
            self.hits += 1; p.state=PipelineState.EXECUTE; p.remaining=cmd.duration
            self._event(f'PIPELINE_{p.id}', boundary, boundary+cmd.duration, 'EXECUTE', cmd.id, cmd.task.name,
                        f'{cmd.duration} MP ticks; HIT', 'task')
            self.cache_busy=False
        else:
            self.misses += 1
            self._event(f'PIPELINE_{p.id}', boundary, boundary, 'WAIT BUS', cmd.id, cmd.task.name, '', 'wait')
            self._enqueue_bus('CACHE_CONTROLLER', TransferType.MEMORY, 7, p.id)
        p.lookup_remaining=0

    def step(self):
        if self.finished: return
        t0=self.global_time; t1=t0+1
        self._complete_bus_if_due(t1)
        self._start_bus()

        for p in self.pipelines:
            if p.state is PipelineState.LOOKUP:
                self._lookup_finish(p,t1)

        for p in self.pipelines:
            if p.state is PipelineState.EXECUTE:
                if p.remaining==1:
                    cmd=p.command; assert cmd
                    p.remaining=0
                    if cmd.task is TaskType.UPR:
                        self._enqueue_bus('MP',TransferType.USO,1,p.id)
                    else:
                        cmd.status='DONE'; p.command=None; p.state=PipelineState.IDLE; p.transfer_type=None
                elif p.remaining>1:
                    p.remaining-=1

        self._start_bus()

        for p in sorted(self.pipelines,key=lambda x:x.id):
            if p.state is PipelineState.IDLE and self.stream_index < len(self.commands):
                cmd=self.commands[self.stream_index]; self.stream_index += 1
                cmd.status='ACTIVE'; p.command=cmd; p.state=PipelineState.LOOKUP; p.lookup_remaining=1
                self.cache_busy=True
                self._event(f'PIPELINE_{p.id}',t1,t1+1,'LOOKUP',cmd.id,cmd.task.name,'1 MP tick','lookup')
                self._event('CACHE',t1,t1+1,'LOOKUP',cmd.id,cmd.task.name,'cache lookup','cache')

        self.current_tick += 1; self.global_time=t1
        if self._done(): self.finished=True
        elif self.current_tick>=self.max_ticks:
            self.finished=True; self.error='MAX_TICKS'

    def _done(self):
        return (self.stream_index>=len(self.commands)
                and all(p.state is PipelineState.IDLE for p in self.pipelines)
                and not self.bus_fifo and self.bus_state is BusState.FREE
                and not self.cache_controller_pending)

    def run_full(self):
        while not self.finished: self.step()

    def snapshot(self):
        lines=[f'Такт МП: {self.current_tick} | Такт СШ: {self.tick_sb}']
        for p in self.pipelines:
            c=f'{p.command.task.name} #{p.command.id}' if p.command else '—'
            lines.append(f'К{p.id}: {p.state.name}  {c}' + (f'  rem={p.remaining}' if p.state is PipelineState.EXECUTE else ''))
        lines += [f'СШ: {self.bus_state.name}  FIFO={len(self.bus_fifo)}',
                  f'КЭШ: {"BUSY" if self.cache_busy else "IDLE"}',
                  f'КЭШ-Контр.: pending={list(self.cache_controller_pending)}',
                  f'БЭ: {"BUSY" if self.buffer_busy else "FREE"}',
                  f'ОП: {"BUSY" if self.memory_busy else "FREE"}',
                  f'УСО: {"BUSY" if self.uso_busy else "FREE"}']
        return '\n'.join(lines)
