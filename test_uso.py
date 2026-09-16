from fractions import Fraction
from simulation.scheduler import SimulationConfig
from simulation.simulator import Simulator
from simulation.entities import TaskType, Command

cfg = SimulationConfig(seed=42, p_hit=1.0, words_per_line=1, uso_access_sb_ticks=1)
sim = Simulator(cfg)
sim.command_stream = [Command(id=0, task=TaskType.UPR, duration=2)]
sim.stats.total_commands = 1

for i in range(10):
    print(f"\n=== Step {i}, t={sim.global_time} ===")
    p1 = sim.pipelines[0]
    print(f"P1: state={p1.state.name}, lookup_rem={p1.lookup_remaining}, exec_rem={p1.remaining}, cmd={p1.command.id if p1.command else None}")
    print(f"Bus: {sim.bus.state.name}, fifo={len(sim.bus.fifo)}")
    if sim.finished:
        print("FINISHED")
        break
    sim.step()

print(f"\nFinal time: {sim.global_time}")
print(f"USO accesses: {sim.stats.uso_accesses}")
