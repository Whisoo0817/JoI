"""Agent-derived frozen interpretations and hand-derived traces, before IR construction.
Prior20 conventions: true transitions require prior false; same-time actions unordered;
commands do not change sensed state unless listed; finite histories are not a proof.
All fixture values below are raw events/readings/state; no fixture computes control policy.
"""
from pathlib import Path
import csv
S=1000; M=60000; H=3600000
CORPUS={r['corpus_id']:r for r in csv.DictReader(open(Path(__file__).resolve().parents[2]/'corpus_100.csv',encoding='utf-8-sig'))}
CASES=[]; STUBS=[]
def add(n,fields,methods,spec,assumptions,histories,start=0,qualification=''):
 cid=f'E1-{n:03}';svc=f'E1C{n:03}';did=f'D{n:03}'
 STUBS.append({'id':svc,'descriptor':'E1 raw leaf fixture; no controller policy','values':[{'id':f,'type':t,'descriptor':f} for f,t in fields.items()], 'functions':[{'id':m,'descriptor':m,'arguments':[{'id':k,'type':t,'descriptor':k} for k,t in args],'return_type':{'type':'VOID'}} for m,args in methods.items()],'enums':[]})
 hs=[]
 for name,events,expected,horizon in histories:
  hs.append(dict(name=name,kind='nominal' if not hs else 'boundary',step_ms=1000,horizon=horizon,events=[(t,{did+'.'+k:v for k,v in u.items()}) for t,u in events],expected=[(t,svc+'.'+a,args,did) for t,a,args in expected]))
 r=CORPUS[cid]
 CASES.append(dict(id=cid,spec=spec,source_url=r['source_url'],source_locator=r['source_locator'],original_text=r['original_text'],text_form=r['text_form'],interpretation_origin='agent, not separately author audited',transcription=assumptions,alternative_bias=qualification or 'Thresholds, cadence and finite device sets instantiate parameters; alternative user choices remain untested.',qualification=qualification,stubs=[svc+' typed leaf observations/actions'],devices={did:{'category':[svc],'tags':[svc]}},t_start_ms=start,histories=hs))
def a(t,m,*args):return(t,m,list(args))
# 078: third source clause is implemented as the conservative manual-rearm reading
add(78,{'Motion':'BOOL','Lux':'DOUBLE','Light':'BOOL'},{'On':[],'Off':[]},
 'A new motion or lux crossing below100 starts a single300s run; ignore intervening triggers. After automation Off, inhibit both automatic triggers until an observed manual light-on rearms them.',
 ['C03 single-run retrigger policy; X=100 lux. Source opening-post clause3 read as manual-rearm lockout, consistent with thread reply3, not a timed debounce. Initial values are not events.','Lamp state updates and resulting lux changes are explicit observations. An On transition after own Off is manual because this controller issues no On while locked out.'],[
 ('motion_run',[(0,{'Motion':False,'Lux':200.,'Light':False}),(S,{'Motion':True}),(2*S,{'Motion':False}),(2*S,{'Light':True}),(301*S,{'Light':False})],[a(S,'On'),a(301*S,'Off')],305*S),
 ('own_off_lux_feedback_blocked',[(0,{'Motion':False,'Lux':200.,'Light':False}),(S,{'Lux':50.}),(2*S,{'Light':True,'Lux':200.}),(301*S,{'Light':False}),(302*S,{'Lux':50.}),(303*S,{'Motion':True})],[a(S,'On'),a(301*S,'Off')],610*S),
 ('manual_rearm_second_motion',[(0,{'Motion':False,'Lux':200.,'Light':False}),(S,{'Motion':True}),(2*S,{'Motion':False,'Light':True}),(301*S,{'Light':False}),(310*S,{'Light':True}),(320*S,{'Motion':True}),(321*S,{'Motion':False})],[a(S,'On'),a(301*S,'Off'),a(320*S,'On'),a(620*S,'Off')],621*S)],qualification='Qualified interpretation: manual-rearm lockout is a conservative resolution of ambiguous causal suppression; it suppresses genuine later motion until manual rearm. No universal feedback-cause inference is claimed.')
add(79,{'Value':'DOUBLE'},{'Run':[]},'Run whenever sensor value changes, or60s after the last change/run if unchanged; repeat stale runs every60s.',
 ['Source opening request and reply assert state-change trigger; omitted incidental1s script delay because normalized requirement asks cadence. Startup value is baseline, not event; a change exactly at timeout produces one Run.'],[
 ('normal_updates',[(0,{'Value':0.}),(10*S,{'Value':1.}),(20*S,{'Value':2.}),(30*S,{'Value':3.})],[a(10*S,'Run'),a(20*S,'Run'),a(30*S,'Run')],80*S),
 ('stale_repeat_then_resume',[(0,{'Value':0.}),(10*S,{'Value':1.}),(145*S,{'Value':2.})],[a(10*S,'Run'),a(70*S,'Run'),a(130*S,'Run'),a(145*S,'Run')],160*S),
 ('change_at_deadline',[(0,{'Value':0.}),(60*S,{'Value':1.})],[a(60*S,'Run'),a(120*S,'Run')],121*S)])
add(80,{'Occupants':'INTEGER'},{'ArmAway':[]},'Arm once on transition of resident count from positive to zero; rearm after return then departure.', ['Count is current raw presence-state cardinality, not event history. Initial zero does not trigger (C01/C03).'],[
 ('last_departure',[(0,{'Occupants':2}),(S,{'Occupants':1}),(2*S,{'Occupants':0})],[a(2*S,'ArmAway')],5*S),
 ('initial_empty',[(0,{'Occupants':0})],[],5*S),
 ('return_and_leave',[(0,{'Occupants':1}),(S,{'Occupants':0}),(3*S,{'Occupants':1}),(5*S,{'Occupants':0})],[a(S,'ArmAway'),a(5*S,'ArmAway')],8*S)])
add(81,{'Present':'BOOL'},{'Nag':[]},'On presence onset, send first reminder after5min; repeat every5min at most3 times while continuously present. Departure cancels immediately and new arrival resets count.',
 ['First alert delayed5min; alternative immediate first alert is not selected. At departure exactly due, cancellation wins (guard must remain true).'],[
 ('cap_three',[(0,{'Present':False}),(S,{'Present':True})],[a(301*S,'Nag'),a(601*S,'Nag'),a(901*S,'Nag')],1300*S),
 ('leave_at_deadline',[(0,{'Present':False}),(S,{'Present':True}),(301*S,{'Present':False})],[],305*S),
 ('leave_return_reset',[(0,{'Present':False}),(S,{'Present':True}),(200*S,{'Present':False}),(250*S,{'Present':True}),(600*S,{'Present':False})],[a(550*S,'Nag')],700*S)])
add(82,{'Open':'BOOL'},{'Notify':[]},'Remember each door opening time; notify on close only if that opening lasted strictly more than300s.', ['Strict more-than follows source; no notification while still open; initial open treated as existing episode observed from startup (elapsed pre-start unknown, not recovered).'],[
 ('long_then_close',[(0,{'Open':False}),(S,{'Open':True}),(302*S,{'Open':False})],[a(302*S,'Notify')],305*S),
 ('exact_five_minutes',[(0,{'Open':False}),(S,{'Open':True}),(301*S,{'Open':False})],[],305*S),
 ('short_then_long',[(0,{'Open':False}),(S,{'Open':True}),(100*S,{'Open':False}),(200*S,{'Open':True}),(501*S,{'Open':False})],[a(501*S,'Notify')],505*S)])
# Clock day indices: Monday=0 through Sunday=6. Actual clock read, not schedule fixture.
add(84,{}, {'On':[],'Off':[]},'On Sun-Thu at18:00, off21:00; Fri/Sat on19:00, off23:00; daily edges, no startup correction.', ['Calendar schedule controlled in IR; start histories Monday17:59:59. Alternate-day branches tested by separate t_start override below.'],[
 ('mon_on_off',[(0,{})],[a(S,'On'),a(3*H+S,'Off')],3*H+2*S),
 ('fri_on_off',[(0,{})],[a(H+S,'On'),a(5*H+S,'Off')],5*H+2*S),
 ('sun_on_off',[(0,{})],[a(S,'On'),a(3*H+S,'Off')],3*H+2*S)],start=18*H-S)
# Each calendar history needs its own absolute origin; runner extension uses history t_start_ms.
CASES[-1]['histories'][1]['t_start_ms']=4*24*H+18*H-S
CASES[-1]['histories'][2]['t_start_ms']=6*24*H+18*H-S
add(85,{'Temperature':'DOUBLE'},{'On':[],'Off':[]},'On downward threshold crossing below19; off upward crossing above19.5; equality and deadband do not trigger.', ['No startup reconciliation, as source says drops/raises; no Off for normal deadband fluctuation.'],[
 ('heat_then_stop',[(0,{'Temperature':20.}),(S,{'Temperature':18.9}),(2*S,{'Temperature':19.2}),(3*S,{'Temperature':19.6})],[a(S,'On'),a(3*S,'Off')],5*S),
 ('equal_thresholds',[(0,{'Temperature':19.2}),(S,{'Temperature':19.}),(2*S,{'Temperature':19.5})],[],5*S),
 ('repeat_cycle',[(0,{'Temperature':20.}),(S,{'Temperature':18.}),(2*S,{'Temperature':20.}),(3*S,{'Temperature':18.})],[a(S,'On'),a(2*S,'Off'),a(3*S,'On')],5*S)])
add(87,{'Button':'BOOL'},{'On':[],'Off':[]},'Each button rising event emits On and replaces off deadline with event+600s; at exact deadline a button takes priority. Repeated level true is one event.', ['C01 repeated On is visible; C099 event-first tie convention, replace rather than extend fixed deadline.'],[
 ('single_press',[(0,{'Button':False}),(S,{'Button':True}),(2*S,{'Button':False})],[a(S,'On'),a(601*S,'Off')],605*S),
 ('restart',[(0,{'Button':False}),(S,{'Button':True}),(2*S,{'Button':False}),(500*S,{'Button':True}),(501*S,{'Button':False})],[a(S,'On'),a(500*S,'On'),a(1100*S,'Off')],1105*S),
 ('press_at_deadline',[(0,{'Button':False}),(S,{'Button':True}),(2*S,{'Button':False}),(601*S,{'Button':True}),(602*S,{'Button':False})],[a(S,'On'),a(601*S,'On'),a(1201*S,'Off')],1205*S)])
add(88,{'Overcast':'BOOL','Rain':'BOOL','SunsetMinute':'INTEGER'},{'On':[]},'At a false-to-true change of overcast or rain, turn on only within [sunset-120min,sunset).', ['SunsetMinute is raw platform astronomy output, not the window predicate. Two conditions form OR trigger; already bad weather at window entry does not trigger.'],[
 ('inside_window',[(0,{'Overcast':False,'Rain':False,'SunsetMinute':1080}),(S,{'Overcast':True})],[a(S,'On')],5*S),
 ('outside_window',[(0,{'Overcast':False,'Rain':False,'SunsetMinute':1200}),(S,{'Rain':True})],[],5*S),
 ('sunset_boundary',[(0,{'Overcast':False,'Rain':False,'SunsetMinute':960}),(S,{'Rain':True})],[],5*S)],start=16*H-S)
add(89,{'Elevation':'DOUBLE','Light':'BOOL'},{'On':[],'Off':[]},'Replay source final startup-aware controller: evaluate at startup and directional threshold crossings; if elevation<=1.8 and light off, On; else if elevation>=-3.1 and light on, Off.', ['Uses exact numeric thresholds and priority of source final YAML; overlap[-3.1,1.8] makes source startup behavior state-dependent, explicitly not repaired. Each history starts a fresh controller, covering missed-event restart.'],[
 ('restart_night_off',[(0,{'Elevation':-10.,'Light':False})],[a(0,'On')],3*S),
 ('restart_day_on',[(0,{'Elevation':20.,'Light':True})],[a(0,'Off')],3*S),
 ('sunset_cross',[(0,{'Elevation':3.,'Light':False}),(S,{'Elevation':1.})],[a(S,'On')],3*S),
 ('sunrise_cross',[(0,{'Elevation':-4.,'Light':True}),(S,{'Elevation':-2.})],[a(S,'Off')],3*S)],qualification='Source-faithful final YAML, including overlapping threshold priority; no claim of a universally correct astronomy policy.')
add(90,{'Trigger':'BOOL','Allowed':'BOOL'},{'On':[],'Off':[]},'On trigger rising with guard true, On then Off1800s later. Ignore triggers while running; guard checked only at trigger.', ['C03 single-run convention; half-hour delay starts at On; startup trigger is not event.'],[
 ('one_run',[(0,{'Trigger':False,'Allowed':True}),(S,{'Trigger':True}),(2*S,{'Trigger':False})],[a(S,'On'),a(1801*S,'Off')],1805*S),
 ('guard_false',[(0,{'Trigger':False,'Allowed':False}),(S,{'Trigger':True}),(2*S,{'Allowed':True})],[],1805*S),
 ('retrigger_ignored',[(0,{'Trigger':False,'Allowed':True}),(S,{'Trigger':True}),(2*S,{'Trigger':False}),(100*S,{'Trigger':True})],[a(S,'On'),a(1801*S,'Off')],1805*S)])
add(93,{'Bell':'BOOL'}, {'Phone':[],'Tablet':[],'PC':[]},'On bell start three independent display workflows; phone immediate, tablet5s, PC1s. One branch delay cannot postpone another.', ['Finite three selected devices; delays5s/1s chosen to test ordering; independent reentry per branch (new triggers during that branch run ignored, C03); no join/shared state.'],[
 ('independent_delays',[(0,{'Bell':False}),(S,{'Bell':True}),(2*S,{'Bell':False})],[a(S,'Phone'),a(6*S,'Tablet'),a(2*S,'PC')],8*S),
 ('second_bell',[(0,{'Bell':False}),(S,{'Bell':True}),(2*S,{'Bell':False}),(10*S,{'Bell':True}),(11*S,{'Bell':False})],[a(S,'Phone'),a(2*S,'PC'),a(6*S,'Tablet'),a(10*S,'Phone'),a(11*S,'PC'),a(15*S,'Tablet')],18*S),
 ('no_bell',[(0,{'Bell':False})],[],8*S)],qualification='Complete via three independent Timelines; no fork-join/shared-state parallelism.')
add(94,{'Trigger':'BOOL'},{'ASet':[('Level','INTEGER')],'AOff':[],'BSet':[('Level','INTEGER')],'BOff':[]},'Two independent light sequences: A levels20,40,60 at0,1,2s then Off at5s; B level50 at0s and Off at1s. Each preserves its own sequence.', ['Parameterized request instantiated with finite two lights and explicit stepped fade, not continuous device-native fade. Shared trigger only; fixed levels/durations chosen before encoding.'],[
 ('overlap',[(0,{'Trigger':False}),(S,{'Trigger':True}),(2*S,{'Trigger':False})],[a(S,'ASet',20),a(2*S,'ASet',40),a(3*S,'ASet',60),a(6*S,'AOff'),a(S,'BSet',50),a(2*S,'BOff')],8*S),
 ('no_trigger',[(0,{'Trigger':False})],[],8*S),
 ('second_run',[(0,{'Trigger':False}),(S,{'Trigger':True}),(2*S,{'Trigger':False}),(10*S,{'Trigger':True}),(11*S,{'Trigger':False})],[a(S,'ASet',20),a(2*S,'ASet',40),a(3*S,'ASet',60),a(6*S,'AOff'),a(S,'BSet',50),a(2*S,'BOff'),a(10*S,'ASet',20),a(11*S,'ASet',40),a(12*S,'ASet',60),a(15*S,'AOff'),a(10*S,'BSet',50),a(11*S,'BOff')],18*S)],qualification='Complete for fixed two independent stepped-fade sequences; no dynamic branch creation or continuous physical fade verification.')
add(96,{'BatteryA':'DOUBLE','BatteryB':'DOUBLE','KnownA':'BOOL','KnownB':'BOOL'}, {'WarnA':[],'WarnB':[]},'Every Monday at09:00 notify for each selected battery when known value<20 or unavailable/unknown.', ['Two fixed selected sensors and one selected output device. Known is raw availability status. Independent warnings identify sensor; no dynamic discovery or aggregation hidden in fixtures.'],[
 ('low_and_unknown',[(0,{'BatteryA':19.,'BatteryB':90.,'KnownA':True,'KnownB':False})],[a(S,'WarnA'),a(S,'WarnB')],3*S),
 ('threshold_equal',[(0,{'BatteryA':20.,'BatteryB':80.,'KnownA':True,'KnownB':True})],[],3*S),
 ('available_high_unknown_a',[(0,{'BatteryA':90.,'BatteryB':25.,'KnownA':False,'KnownB':True})],[a(S,'WarnA')],3*S)],start=9*H-S,qualification='Complete for a statically selected finite set; does not establish dynamic sensor-list traversal or a combined formatted report.')
add(97,{'Bell':'BOOL','Present':'BOOL','Zone':'BOOL'}, {'Sound':[],'FlashOn':[],'FlashOff':[],'Notify':[]},'At doorbell, sound when present, flash once for1s when in selected zone, and always notify. Guards read at bell; enabled branches start together.', ['Choice of branch guard configuration and1s flash are parameters of this instance. Timed flash controlled in IR. Independent branches have no joins/state sharing.'],[
 ('all_enabled',[(0,{'Bell':False,'Present':True,'Zone':True}),(S,{'Bell':True}),(2*S,{'Bell':False})],[a(S,'Sound'),a(S,'FlashOn'),a(S,'Notify'),a(2*S,'FlashOff')],5*S),
 ('guards_disabled',[(0,{'Bell':False,'Present':False,'Zone':False}),(S,{'Bell':True})],[a(S,'Notify')],5*S),
 ('zone_only',[(0,{'Bell':False,'Present':False,'Zone':True}),(S,{'Bell':True}),(2*S,{'Zone':False,'Bell':False})],[a(S,'FlashOn'),a(S,'Notify'),a(2*S,'FlashOff')],5*S)],qualification='Complete via three independent Timelines for the declared fixed guard configuration.')
add(98,{'Power':'DOUBLE'}, {'Notify':[]},'Arm when power rises above10W; then notify after power remains below3W continuously60s; reset for next running-threshold crossing.', ['Strict running/finish comparisons; no completion notification before observed start. Initial high treated as not a rising event; threshold equality resets finish sustain.'],[
 ('one_cycle',[(0,{'Power':0.}),(S,{'Power':20.}),(10*S,{'Power':2.})],[a(70*S,'Notify')],80*S),
 ('finish_reset_at_threshold',[(0,{'Power':0.}),(S,{'Power':20.}),(10*S,{'Power':2.}),(69*S,{'Power':3.}),(71*S,{'Power':2.})],[a(131*S,'Notify')],140*S),
 ('two_cycles',[(0,{'Power':0.}),(S,{'Power':20.}),(10*S,{'Power':2.}),(100*S,{'Power':20.}),(110*S,{'Power':2.})],[a(70*S,'Notify'),a(170*S,'Notify')],180*S)])
add(100,{'Occupants':'INTEGER','Locked':'BOOL'}, {'Notify':[]},'When resident count becomes0, notify only if door unlocked at that instant. Unlocking later is not a departure trigger.', ['Raw count as080; no startup notification. Guard is checked on final departure.'],[
 ('final_departure_unlocked',[(0,{'Occupants':2,'Locked':False}),(S,{'Occupants':1}),(2*S,{'Occupants':0})],[a(2*S,'Notify')],5*S),
 ('locked_then_unlock',[(0,{'Occupants':1,'Locked':True}),(S,{'Occupants':0}),(2*S,{'Locked':False})],[],5*S),
 ('already_empty',[(0,{'Occupants':0,'Locked':False})],[],5*S)])
