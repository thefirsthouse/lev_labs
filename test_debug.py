from fractions import Fraction
from simulation.scheduler import SimulationConfig
from simulation.simulator import Simulator
from simulation.entities import TaskType, Command

cfg = SimulationConfig(seed=42, p_hit=1.0, words_per_line=4)
sim = Simulator(cfg)
sim.command_stream = [Command(id=0, task=TaskType.MDO, duration=1)]
sim.stats.total_commands = 1

for i in range(5):
    print(f"\n=== Step {i}, t={sim.global_time} ===")
    p1 = sim.pipelines[0]
    print(f"P1: state={p1.state.name}, lookup_rem={p1.lookup_remaining}, exec_rem={p1.remaining}, cmd={p1.command.id if p1.command else None}")
    if sim.finished:
        print("FINISHED")
        break
    sim.step()

print(f"\nFinal time: {sim.global_time}")
