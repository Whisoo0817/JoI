"""Independent parent-review sensitivities frozen before candidate repair.
Original cases.py and its52 histories are unchanged; these expose gaps in the first encoding.
"""
from pathlib import Path
import importlib.util,copy
s=importlib.util.spec_from_file_location('community_frozen_original',Path(__file__).with_name('cases.py'));o=importlib.util.module_from_spec(s);s.loader.exec_module(o)
by={c['id']:c for c in o.CASES}; CASES=[]
def add(n,name,events,expected,horizon,start=None):
 c=copy.deepcopy(by[f'E1-{n:03}']);did=f'D{n:03}';svc=f'E1C{n:03}'
 c['histories']=[dict(name=name,kind='parent_review_sensitivity',step_ms=1000,horizon=horizon,events=[(t,{did+'.'+k:v for k,v in u.items()}) for t,u in events],expected=[(t,svc+'.'+m,args,did) for t,m,args in expected])]
 if start is not None:c['t_start_ms']=start
 CASES.append(c)
add(78,'initial_true_then_new_motion',[(0,{'Motion':True,'Lux':200.,'Light':False}),(1000,{'Motion':False}),(2000,{'Motion':True}),(3000,{'Motion':False,'Light':True}),(302000,{'Light':False})],[(2000,'On',[]),(302000,'Off',[])],305000)
add(84,'startup_inside_window_no_on_but_scheduled_off',[(0,{})],[(2*o.H,'Off',[])],2*o.H+1000,start=19*o.H)
add(87,'held_button_still_expires_at_ten_minutes',[(0,{'Button':False}),(1000,{'Button':True}),(700000,{'Button':False})],[(1000,'On',[]),(601000,'Off',[])],705000)
add(96,'startup_mid_scheduled_minute_is_not_schedule_edge',[(0,{'BatteryA':19.,'BatteryB':90.,'KnownA':True,'KnownB':False})],[],20000,start=9*o.H+30000)
