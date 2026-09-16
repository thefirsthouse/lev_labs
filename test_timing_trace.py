from fractions import Fraction
from simulation.scheduler import SimulationConfig
from simulation.simulator import Simulator
from simulation.entities import TaskType, Command, PipelineState

cfg = SimulationConfig(seed=42, p_hit=1.0, words_per_line=1, uso_access_sb_ticks=1)
sim = Simulator(cfg)
sim.command_stream = [Command(id=0, task=TaskType.UPR, duration=2)]
sim.stats.total_commands = 1

# Patch to trace
original_arb = sim._arbitrate_and_start_if_possible
def traced_arb():
    from simulation.time_freq import sb_tick
    print(f"    [arbitrate called at t={sim.global_time}, sb={sb_tick(sim.global_time)}]")
    return original_arb()
sim._arbitrate_and_start_if_possible = traced_arb

for i in range(6):
    print(f"\n=== Step {i} start, t={sim.global_time} ===")
    p = sim.pipelines[0]
    print(f"  P1: {p.state.name}, rem={p.remaining if p.state == PipelineState.EXECUTE else p.lookup_remaining}")
    if sim.finished:
        break
    sim.step()
    print(f"  After step: t={sim.global_time}")

print(f"\nFinal: t={sim.global_time}, uso={sim.stats.uso_accesses}")
