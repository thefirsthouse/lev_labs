from fractions import Fraction
from simulation.scheduler import SimulationConfig
from simulation.simulator import Simulator
from simulation.entities import TaskType, Command
from simulation.time_freq import sb_tick

cfg = SimulationConfig(seed=42, p_hit=0.0, words_per_line=1)
sim = Simulator(cfg)
sim.command_stream = [Command(id=0, task=TaskType.MDO, duration=1)]
sim.stats.total_commands = 1

for i in range(15):
    t = int(sim.global_time)
    sb = sb_tick(sim.global_time)
    p = sim.pipelines[0]
    print(f"t={t:2d} sb={sb} P1:{p.state.name:12s} Bus:{sim.bus.state.name:4s}", end="")
    
    if sim.bus.current_request:
        finish = Fraction(sim.bus.current_sb_end * 50, 19)
        print(f" sb_end={sim.bus.current_sb_end} finish={float(finish):.2f}", end="")
    print()
    
    if sim.finished:
        print("FINISHED")
        break
    sim.step()

print(f"\nFinal: t={sim.global_time}")
