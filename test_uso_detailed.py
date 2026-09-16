from fractions import Fraction
from simulation.scheduler import SimulationConfig
from simulation.simulator import Simulator
from simulation.entities import TaskType, Command
from simulation.time_freq import sb_tick

cfg = SimulationConfig(seed=42, p_hit=1.0, words_per_line=1, uso_access_sb_ticks=1)
sim = Simulator(cfg)
sim.command_stream = [Command(id=0, task=TaskType.UPR, duration=2)]
sim.stats.total_commands = 1

for i in range(8):
    t0 = sim.global_time
    t1 = t0 + 1
    print(f"\n=== Before Step {i}, t={t0} ===")
    print(f"Bus: {sim.bus.state.name}")
    if sim.bus.current_request:
        finish = Fraction(sim.bus.current_sb_end * 50, 19)
        print(f"  current_sb_start={sim.bus.current_sb_start}, current_sb_end={sim.bus.current_sb_end}")
        print(f"  finish_time={finish} ≈ {float(finish)}")
        print(f"  Will finish in ({t0}, {t1}]? {t0 < finish <= t1}")
    
    if sim.finished:
        print("FINISHED")
        break
    sim.step()

print(f"\nFinal: t={sim.global_time}, USO accesses={sim.stats.uso_accesses}")
