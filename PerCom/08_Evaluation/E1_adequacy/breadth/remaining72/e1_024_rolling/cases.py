"""Pre-encoding sprinkler tests. Original three histories retained unchanged.
Integer-second input and requested-duration model, empty prehistory, initially off.
Positive rising requests start if there is available rolling capacity; ignore busy
requests, discard denied requests, snapshot duration at admission. Off before new
admission at the same instant. Old consumption expires continuously, not per session.
"""
from pathlib import Path
import copy, runpy
BASE = runpy.run_path(str(Path(__file__).parents[1]/'batch_er/cases.py'))
CASE = copy.deepcopy(BASE['CASE_BY_ID']['E1-024'])
STUBS = BASE['STUBS']
S=1000; W=48*3600

def event(t, **state): return (t*S, {'D24.'+k:v for k,v in state.items()})
def action(t, name): return (t*S, 'ER24.'+name, [], 'D24')
def history(name, requests, expected, horizon, extra=()):
    events=[event(0,Request=False,DurationSeconds=600)]
    for t,duration in requests:
        events += [event(t,Request=True,DurationSeconds=duration), event(t+1,Request=False)]
    events += list(extra)
    return dict(name=name,kind='rolling_boundary',events=sorted(events),expected=[action(t,a) for t,a in expected],horizon=horizon*S,step_ms=S)

CASE['histories'] += [
 history('full_budget_reject_then_exact_48h_reuse',[(1,600),(W-2,600),(W+1,900)],[(1,'On'),(601,'Off'),(W+1,'On'),(W+601,'Off')],W+605),
 history('split_consumption_expires_progressively',[(1,120),(300,480),(W+1,200),(W+300,500)],[(1,'On'),(121,'Off'),(300,'On'),(780,'Off'),(W+1,'On'),(W+121,'Off'),(W+300,'On'),(W+780,'Off')],W+782),
 history('third_window_reuses_overwritten_slots',[(1,600),(W+1,600),(2*W+1,600)],[(1,'On'),(601,'Off'),(W+1,'On'),(W+601,'Off'),(2*W+1,'On'),(2*W+601,'Off')],2*W+605),
 history('expire_during_active_run_avoids_premature_stop',[(1,600),(W+301,600)],[(1,'On'),(601,'Off'),(W+301,'On'),(W+901,'Off')],W+903),
 history('busy_trigger_ignored_duration_snapshotted',[(1,120),(50,600),(200,480)],[(1,'On'),(121,'Off'),(200,'On'),(680,'Off')],685),
 history('off_then_admit_at_same_instant',[(1,120),(121,180)],[(1,'On'),(121,'Off'),(121,'On'),(301,'Off')],305),
 history('zero_negative_duration_no_action',[(1,0),(3,-10),(5,2)],[(5,'On'),(7,'Off')],10),
 history('denied_held_request_does_not_auto_resume',[(1,600),(W+21,60)],[(1,'On'),(601,'Off'),(W+21,'On'),(W+81,'Off')],W+85,extra=[event(W-10,Request=True),event(W+20,Request=False)]),
 history('exact_600_single_second_sessions_and_601st_rejected',[(1+2*i,1) for i in range(601)],[(t,name) for i in range(600) for t,name in [(1+2*i,'On'),(2+2*i,'Off')]],1205),
]
CASE['spec'] += ' This revision implements the rolling budget at the original integer-second replay resolution; it does not delegate history or arithmetic to a backend.'
CASE['transcription'] += ['Supplemental tests use positive integer-second durations; zero/negative requests are ignored. Same-instant Off precedes new On. No pre-start watering or out-of-controller activation.']
