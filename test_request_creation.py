from fractions import Fraction
from simulation.scheduler import SimulationConfig
from simulation.simulator import Simulator
from simulation.entities import TaskType, Command, PipelineState

cfg = SimulationConfig(seed=42, p_hit=1.0, words_per_line=1, uso_access_sb_ticks=1)
sim = Simulator(cfg)
sim.command_stream = [Command(id=0, task=TaskType.UPR, duration=2)]
sim.stats.total_commands = 1

# Patch to trace enqueue
original_enqueue = sim.enqueue_bus_request
def traced_enqueue(*args, **kwargs):
    from simulation.time_freq import sb_tick
    print(f"    [enqueue_bus_request called at t={sim.global_time}, sb={sb_tick(sim.global_time)}]")
    return original_enqueue(*args, **kwargs)
sim.enqueue_bus_request = traced_enqueue

for i in range(6):
    print(f"\n=== Step {i} start, t={sim.global_time} ===")
    if sim.finished:
        break
    sim.step()

print(f"\nFinal: t={sim.global_time}")
if sim.bus.current_request:
    print(f"Bus: sb_start={sim.bus.current_sb_start}, sb_end={sim.bus.current_sb_end}")
    print(f"Finish time: {Fraction(sim.bus.current_sb_end * 50, 19)}")
