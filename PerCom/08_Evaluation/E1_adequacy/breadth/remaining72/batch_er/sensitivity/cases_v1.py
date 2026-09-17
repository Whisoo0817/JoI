"""Additional source-derived adversarial oracles, frozen before v2 candidate edits.
Original 99 histories unchanged. Parent review prompted E20 acknowledgement-race test;
agent identified E31 second-use onset and initially held use as timing sensitivities.
"""
import runpy,copy
from pathlib import Path
base=runpy.run_path(str(Path(__file__).resolve().parents[1]/'cases.py'))
STUBS=base['STUBS'];ev=base['ev'];act=base['act'];hist=base['hist'];S=1000;M=60000
CASES=[copy.deepcopy(c) for c in base['CASES'] if c['id'] in ('E1-020','E1-031')]
CASES[0]['histories']=[hist('delayed_acknowledgement_must_reserve',[ev(20,0,WasherRequest=False,DishRequest=False,WasherRunning=False,DishRunning=False),ev(20,S,WasherRequest=True),ev(20,2*S,WasherRequest=False,DishRequest=True),ev(20,3*S,DishRequest=False),ev(20,4*S,WasherRunning=True),ev(20,8*S,WasherRunning=False),ev(20,9*S,DishRequest=True)],[act(20,S,'StartWasher'),act(20,9*S,'StartDish')],kind='boundary')]
CASES[1]['histories']=[hist('request_at_second_use_onset',[ev(31,0,BrushUse=False,Request=False),ev(31,S,BrushUse=True),ev(31,2*S,BrushUse=False),ev(31,3*S,BrushUse=True,Request=True),ev(31,4*S,BrushUse=False,Request=False)],[act(31,3*S,'On')],kind='boundary'),hist('initial_held_use_is_not_new_event',[ev(31,0,BrushUse=True,Request=False),ev(31,S,BrushUse=False),ev(31,2*S,BrushUse=True),ev(31,3*S,BrushUse=False),ev(31,4*S,Request=True)],[],kind='negative')]
