from collections import Counter
from lab1.model import Simulator
for hit in (.65,.85):
    s=Simulator(42,hit); s.generate_variant3(); gen=Counter(c.task.name for c in s.commands); s.run_full(); done=Counter(c.task.name for c in s.commands if c.status=='DONE'); res=Counter(e.resource for e in s.events); tasks=Counter(e.task for e in s.events)
    print('hit',hit,'generated',dict(gen),'done',dict(done),'ticks',s.current_tick,'H/M',s.hits,s.misses,'USO',s.uso_accesses,'resources',dict(res))
    assert gen['MDO']==30 and gen['MSO']==40 and gen['UPR']==30 and 10<=gen['DISP']<=70
    assert done==gen and s.uso_accesses==30
    assert {'PIPELINE_1','PIPELINE_2','CACHE','CACHE_CONTROLLER','SYSTEM_BUS','BUFFER_ELEMENT','MEMORY','USO'} <= set(res)
print('AUDIT OK')
