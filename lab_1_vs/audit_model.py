from collections import Counter
from lab1.simulator import Simulator
from lab1.scheduler import SimulationConfig

for hit in (0.65, 0.85):
    sim = Simulator(SimulationConfig(seed=42, p_hit=hit))
    sim.generate_variant3()
    generated = Counter(c.task.name for c in sim.command_stream)
    while not sim.finished:
        sim.step()
    done = Counter(c.task.name for c in sim.command_stream if c.status == 'DONE')
    resources = Counter(e.resource for e in sim.trace_events)
    print(f'CACHE={hit:.0%}')
    print('generated:', dict(generated))
    print('done:', dict(done))
    print('ticks_mp:', sim.current_tick)
    print('hit/miss:', sim.stats.hits, sim.stats.misses)
    print('USO accesses:', sim.stats.uso_accesses)
    print('resources:', dict(resources))
    assert generated == Counter({'MDO':30, 'MSO':40, 'UPR':30, 'DISP':10})
    assert done == generated
    assert sim.stats.uso_accesses == 30
    required = {'PIPELINE_1','PIPELINE_2','CACHE','CACHE_CONTROLLER','SYSTEM_BUS','BUFFER_ELEMENT','MEMORY','USO'}
    assert required <= set(resources)
print('MODEL AUDIT: OK')
