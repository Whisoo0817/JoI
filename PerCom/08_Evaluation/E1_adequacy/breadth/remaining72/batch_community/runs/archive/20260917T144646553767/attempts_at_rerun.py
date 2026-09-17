"""Community IR encodings written after FREEZE.json and frozen_cases.json."""
ATTEMPTS={}
def atom(n,f):return f'E1C{n:03}[D{n:03}].{f}'
def call(n,m,**args):return {'op':'call','target':atom(n,m),'args':args}
def wait(cond,**kw):return {'op':'wait','cond':cond,'edge':'none',**kw}
def read(v,src):return {'op':'read','var':v,'src':src}
def iff(cond,yes,no=None):return {'op':'if','cond':cond,'then':yes,**({'else':no} if no else {})}
def delay(sec):return {'op':'delay','duration':f'{sec} SEC'}
def cycle(body,**kw):return {'op':'cycle','until':None,'period':'0 MSEC','body':body,**kw}
def ir(body):return {'timeline':[{'op':'start_at','anchor':'now'},*body]}
def entry(n,body=None,autos=None,label='complete',reason='All fixed source clauses encoded; empirical traces are finite.'):
 ATTEMPTS[f'E1-{n:03}']={'label':label,'label_reason':reason,'automations':autos or [{'name':'main','ir':ir(body)}]}
def edge(cond,body):return [wait(f'not ({cond})'),cycle([wait(cond),*body,wait(f'not ({cond})')])]
def transition(fields,body):
 return [cycle([*[read('prev'+str(i),f) for i,f in enumerate(fields)],wait(' or '.join(f'{f} != $prev{i}' for i,f in enumerate(fields))),*body])]
#078 manual-rearm control: after first automation Off, no trigger until manual On.
n=78;mo=atom(n,'Motion');lu=atom(n,'Lux');li=atom(n,'Light')
trig=f'({mo} == true and $pm == false) or ({lu} < 100 and $pl >= 100)'
scan=[read('pm',mo),read('pl',lu),wait(trig)]
entry(n,[cycle([*scan,call(n,'On'),delay(300),call(n,'Off'),wait(f'{li} == false'),wait(f'{li} == true')])],label='complete for qualified manual-rearm interpretation',reason='Conservative lockout explicitly fixed before encoding; genuine later motion is inhibited until manual rearm.')
#079 raw sensor state changes with timeout and repeated runs.
n=79;v=atom(n,'Value')
entry(n,[cycle([read('old',v),wait(f'{v} != $old',timeout='60 SEC'),call(n,'Run')])])
#080 raw occupancy departure edges
entry(80,edge(f'{atom(80,"Occupants")} == 0',[call(80,'ArmAway')]))
#081 count3 with cancel-first guarded time waits
n=81;p=atom(n,'Present')
entry(n,edge(f'{p} == true',[cycle([wait(f'{p} == false',timeout='300 SEC',on_timeout=[call(n,'Nag')]),iff(f'{p} == false',[{'op':'break'}])],count='k',until='$k >= 3')]))
#082 timestamp snapshot, strict > duration
n=82;o=atom(n,'Open')
entry(n,[cycle([wait(f'{o} == true'),read('opened','Clock.Timestamp'),wait(f'{o} == false'),iff('Clock.Timestamp - $opened > 300',[call(n,'Notify')])])])
#084 edges of schedule windows; avoids cron-erasure caveat.
day='Clock.Weekday';hour='Clock.Hour'
window=f"(({day} != 'friday' and {day} != 'saturday') and {hour} >= 18 and {hour} < 21) or (({day} == 'friday' or {day} == 'saturday') and {hour} >= 19 and {hour} < 23)"
entry(84,[cycle([wait(window),call(84,'On'),wait(f'not ({window})'),call(84,'Off')])])
#085 two independent threshold edges, combined snapshot loop preserves true crossing
n=85;t=atom(n,'Temperature')
entry(n,transition([t],[iff(f'{t} < 19 and $prev0 >= 19',[call(n,'On')]),iff(f'{t} > 19.5 and $prev0 <= 19.5',[call(n,'Off')])]))
#087 replacement deadline. After initial edge, inner cycle waits for press OR deadline.
n=87;b=atom(n,'Button')
entry(n,[wait(f'{b} == false'),cycle([wait(f'{b} == true'),call(n,'On'),read('pressed','Clock.Timestamp'),wait(f'{b} == false'),cycle([wait(f'{b} == true or Clock.Timestamp >= $pressed + 600'),iff(f'{b} == true',[call(n,'On'),read('pressed','Clock.Timestamp'),wait(f'{b} == false')],[call(n,'Off'),{'op':'break'}])])])])
#088 clock window calculated from raw sunset minute
n=88;ov=atom(n,'Overcast');ra=atom(n,'Rain');su=atom(n,'SunsetMinute');now='(Clock.Hour * 60 + Clock.Minute)'
entry(n,transition([ov,ra],[iff(f'(({ov} == true and $prev0 == false) or ({ra} == true and $prev1 == false)) and {now} >= {su} - 120 and {now} < {su}',[call(n,'On')])]))
#089 source final YAML startup branch and numeric-state crossings
n=89;e=atom(n,'Elevation');l=atom(n,'Light')
actions=[iff(f'{e} <= 1.8 and {l} == false',[call(n,'On')],[iff(f'{e} >= -3.1 and {l} == true',[call(n,'Off')])])]
entry(n,[*actions,*transition([e],[iff(f'({e} < 1.8 and $prev0 >= 1.8) or ({e} > -3.1 and $prev0 <= -3.1)',actions)])],label='complete for source final-YAML interpretation',reason='Reproduces source startup branch priority even in overlapping elevation range; not a repaired astronomy rule.')
#090 trigger-only guard, single-run delay
n=90;tr=atom(n,'Trigger');allowed=atom(n,'Allowed')
entry(n,edge(f'{tr} == true',[iff(f'{allowed} == true',[call(n,'On'),delay(1800),call(n,'Off')])]))
#093,094 independent workflows
n=93
entry(n,autos=[{'name':m,'ir':ir(edge(f'{atom(n,"Bell")} == true',([delay(d)] if d else [])+[call(n,m)]))} for m,d in [('Phone',0),('Tablet',5),('PC',1)]],label='complete via independent Timelines',reason='Three fixed branches share trigger only; own delay does not block others.')
n=94
entry(n,autos=[{'name':'A','ir':ir(edge(f'{atom(n,"Trigger")} == true',[call(n,'ASet',Level=20),delay(1),call(n,'ASet',Level=40),delay(1),call(n,'ASet',Level=60),delay(3),call(n,'AOff')]))},{'name':'B','ir':ir(edge(f'{atom(n,"Trigger")} == true',[call(n,'BSet',Level=50),delay(1),call(n,'BOff')]))}],label='complete via fixed independent stepped-fade Timelines',reason='Static two-light stepped-fade configuration fixed before encoding; no dynamic fork/join.')
#096 calendar guard and fixed sensor selection unrolled
n=96;due="Clock.Weekday == 'monday' and Clock.Hour == 9 and Clock.Minute == 0"
entry(n,[cycle([wait(due),*[iff(f'{atom(n,"Known"+k)} == false or {atom(n,"Battery"+k)} < 20',[call(n,'Warn'+k)]) for k in ('A','B')],wait(f'not ({due})')])],label='complete for fixed selected sensor set',reason='Two static sensors and selected notification output; no dynamic collection enumeration.')
#097 independent enabled action branches
n=97;bell=f'{atom(n,"Bell")} == true'
entry(n,autos=[{'name':'sound','ir':ir(edge(bell,[iff(f'{atom(n,"Present")} == true',[call(n,'Sound')])]))},{'name':'flash','ir':ir(edge(bell,[iff(f'{atom(n,"Zone")} == true',[call(n,'FlashOn'),delay(1),call(n,'FlashOff')])]))},{'name':'notify','ir':ir(edge(bell,[call(n,'Notify')]))}],label='complete via independent Timelines',reason='Fixed guard configuration, no shared state/join; pulse timing inside IR.')
#098 separate start crossing and resettable sustained finish
n=98;p=atom(n,'Power')
entry(n,[wait(f'{p} <= 10'),cycle([wait(f'{p} > 10'),wait(f'{p} < 3',**{'for':'60 SEC'}),call(n,'Notify'),wait(f'{p} <= 10')])])
#100 departure edge followed by guard
entry(100,edge(f'{atom(100,"Occupants")} == 0',[iff(f'{atom(100,"Locked")} == false',[call(100,'Notify')])]))
