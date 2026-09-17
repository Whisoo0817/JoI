"""Timeline candidates written after FREEZE_MANIFEST.json; no oracle changes.
All ER members are typed leaf values/actions, never policy or history services.
"""
ATTEMPTS={}
def src(n,f): return f'ER{n}[D{n}].{f}'
def call(n,f,args=None): return {'op':'call','target':src(n,f),'args':args or {}}
def wait(cond,**kw): return {'op':'wait','cond':cond,'edge':'none',**kw}
def read(var,source): return {'op':'read','var':var,'src':source}
def branch(cond,then,otherwise=None):
 x={'op':'if','cond':cond,'then':then}
 if otherwise is not None:x['else']=otherwise
 return x
def cycle(body,**kw): return {'op':'cycle','until':None,'period':'0 MSEC','body':body,**kw}
def put(n,body,label='complete under agent-fixed interpretation',reason='Standard event/state sequencing; no delegated temporal policy.'):
 ATTEMPTS[f'E1-{n:03d}']={'label':label,'label_reason':reason,'automations':[{'name':'main','ir':{'timeline':[{'op':'start_at','anchor':'now'},*body]}}]}
def oncond(n,cond,actions,initial=False):
 put(n,([branch(cond,actions)] if initial else [])+[cycle([wait(f'not ({cond})'),wait(cond),*actions])])
def edge(n,field,actions,guard=None):
 x=src(n,field)
 put(n,[read('previous',x),cycle([wait(f'{x} != $previous'),branch(f'{x} == true'+(f' and ({guard})' if guard else ''),actions),read('previous',x)])])
for n,field,value,seconds,method in [(13,'PotPresent',False,301,'Off'),(14,'DoorOpen',True,301,'Alarm'),(29,'Closed',True,10,'Lock'),(30,'Idle',True,3600,'Off'),(35,'Occupied',False,601,'Off')]:
 cond=f'{src(n,field)} == {str(value).lower()}'
 put(n,[cycle([wait(cond,**{'for':f'{seconds} SEC'}),call(n,method),wait(f'not ({cond})')])])
edge(16,'LowPower',[call(16,'ReturnToCharge')]);edge(19,'OtherHotWaterDemand',[call(19,'Pause')])
n=20;wr=src(n,'WasherRequest');dr=src(n,'DishRequest')
put(n,[read('wprev',wr),read('dprev',dr),cycle([wait(f'{wr} != $wprev or {dr} != $dprev'),branch(f'{wr} == true and $wprev == false and {src(n,"DishRunning")} == false',[call(n,'StartWasher')],[branch(f'{dr} == true and $dprev == false and {src(n,"WasherRunning")} == false',[call(n,'StartDish')])]),read('wprev',wr),read('dprev',dr)])],label='complete for observed-state admission; acknowledgement-race qualification',reason='Matches fixed author admission policy and agent washer tie priority; delayed acknowledgements beyond tested histories remain outside mutual-exclusion guarantee.')
for n,hours,method,weekly in [(21,[8],'Mow',True),(22,[6,18],'Feed',False),(40,[19],'On',False),(46,[18],'On',False),(50,[18],'On',False)]:
 cond='('+' or '.join(f'Clock.Hour == {h}' for h in hours)+') and Clock.Minute == 0'
 if weekly:cond+=' and Clock.Weekday == "monday"'
 oncond(n,cond,[call(n,method)],initial=True)
n=23;r=src(n,'Rain');q=src(n,'Request')
put(n,[read('rain_prev',r),read('request_prev',q),cycle([wait(f'{r} != $rain_prev or {q} != $request_prev'),branch(f'{r} == false and $rain_prev == true',[read('last_wet','Clock.Timestamp')]),branch(f'{q} == true and $request_prev == false and {r} == false and ($last_wet == null or Clock.Timestamp - $last_wet >= 86400)',[call(n,'On')]),read('rain_prev',r),read('request_prev',q)])])
n=24
put(n,[cycle([wait(f'{src(n,"Request")} == true',edge='rising') if False else {'op':'wait','cond':f'{src(n,"Request")} == true','edge':'rising'},read('started','Clock.Timestamp'),read('requested',src(n,'DurationSeconds')),call(n,'On'),wait('Clock.Timestamp - $started >= $requested or Clock.Timestamp - $started >= 600'),call(n,'Off'),wait('Clock.Timestamp - $started >= 172800')])],label='partial: conservative one-session cooldown',reason='Caps any one session at ten minutes and waits 48 h before another; cannot admit legal split sessions or account for rolling cumulative runtime. Frozen split-session and quota-cap histories expose this loss. No general accumulator is delegated to fixture.')
edge(25,'Request',[call(25,'Test')],guard='Clock.Hour < 22')
n=26;a=src(n,'AutoRequest');m=src(n,'ManualRequest')
put(n,[read('aprev',a),read('mprev',m),cycle([wait(f'{a} != $aprev or {m} != $mprev'),branch(f'({m} == true and $mprev == false) or ({a} == true and $aprev == false and {src(n,"Lux")} < 100)',[call(n,'On')]),read('aprev',a),read('mprev',m)])])
n=31;b=src(n,'BrushUse');q=src(n,'Request');end='Clock.Timestamp >= $day_timestamp - $day_hour * 3600 - $day_minute * 60 + 86400'
check=branch(end,[{'op':'break'}])
phase=[]
for _ in range(2):
 phase += [wait(f'{b} == true or ({end})'),check,wait(f'{b} == false or ({end})'),check]
phase += [cycle([wait(f'{q} == true or ({end})'),check,call(n,'On'),wait(f'{q} == false or ({end})'),check]),{'op':'break'}]
put(n,[cycle([read('day_timestamp','Clock.Timestamp'),read('day_hour','Clock.Hour'),read('day_minute','Clock.Minute'),cycle(phase)])],label='complete on frozen fixed-two raw-event histories; same-instant qualification',reason='Two explicit use phases followed by request phase, restarted at midnight. Corpus author also allows delegated count, but this stronger fixture does not delegate counting. Candidate waits for second-use pulse end, so request at exactly the second-use onset can be delayed/missed; retained as a qualification, not universal completeness.')
edge(32,'Request',[call(32,'Open')],guard=f'{src(32,"ACOn")} == false')
n=33;window='Clock.Hour == 17 and Clock.Weekday != "saturday" and Clock.Weekday != "sunday"';closed=src(n,'Closed')
put(n,[read('closed_prev',closed),read('hour_prev','Clock.Hour'),cycle([wait(f'{closed} != $closed_prev or Clock.Hour != $hour_prev'),branch(f'({window}) and ((Clock.Hour != $hour_prev) or ({closed} == true and $closed_prev == false))',[call(n,'Open')]),branch('Clock.Hour == 18 and $hour_prev == 17 and Clock.Weekday != "saturday" and Clock.Weekday != "sunday"',[call(n,'Close')]),read('closed_prev',closed),read('hour_prev','Clock.Hour')])])
edge(38,'Received',[call(38,'Blink')],guard=f'{src(38,"Sender")} == "JohnDoe@gmail.com"')
oncond(39,f'{src(39,"Daylight")} == false',[call(39,'On')])
edge(41,'AtFrontDoor',[call(41,'Blink')])
n=42;x=src(n,'Present')
put(n,[branch(f'{x} == true',[call(n,'On')],[call(n,'Off')]),read('previous',x),cycle([wait(f'{x} != $previous'),branch(f'{x} == true',[call(n,'On')],[call(n,'Off')]),read('previous',x)])])
edge(43,'Rain',[call(43,'SetColor',{'Color':'blue'})])
edge(44,'Closed',[call(44,'Lock'),call(44,'LightOff')])
n=45;x=src(n,'Asleep')
put(n,[cycle([wait(f'{x} == false'),wait(f'{x} == true'),read('sleep_start','Clock.Timestamp'),wait(f'{x} == false'),branch('Clock.Timestamp - $sleep_start < 18000',[call(n,'Brew')])])])
edge(47,'Person',[call(47,'Email')],guard='Clock.Hour >= 9 and Clock.Hour < 17')
n=48;x=src(n,'TemperatureF')
put(n,[cycle([branch(f'{x} < 40',[call(n,'Set',{'Temperature':72}),wait(f'{x} >= 40')],[call(n,'Off'),wait(f'{x} < 40')])])])
for n,lo in [(49,0),(53,7)]:oncond(n,f'{src(n,"TemperatureF")} < 40 and Clock.Hour >= {lo} and Clock.Hour < 10',[call(n,'Brew')],True)
edge(51,'Home',[call(51,'On')],guard='Clock.Hour >= 18 and Clock.Hour < 23')
oncond(52,f'{src(52,"Snow")} == true',[call(52,'Set',{'Temperature':75})],True)
assert len(ATTEMPTS)==33
# v2: fixes following separately frozen sensitivity cases; original candidate retained.
n=20;wr=src(n,'WasherRequest');dr=src(n,'DishRequest')
put(n,[read('wprev',wr),read('dprev',dr),cycle([wait(f'{wr} != $wprev or {dr} != $dprev'),branch(f'{wr} == true and $wprev == false and {src(n,"DishRunning")} == false',[call(n,'StartWasher'),wait(f'{src(n,"WasherRunning")} == true'),wait(f'{src(n,"WasherRunning")} == false')],[branch(f'{dr} == true and $dprev == false and {src(n,"WasherRunning")} == false',[call(n,'StartDish'),wait(f'{src(n,"DishRunning")} == true'),wait(f'{src(n,"DishRunning")} == false')])]),read('wprev',wr),read('dprev',dr)])],label='complete for serialized request admission with acknowledged lifecycle',reason='Admitted start reserves the single flow until the selected device is observed running then stopped; later requests during reservation are discarded. This handles the delayed-acknowledgement sensitivity. Assumes starts go through this controller, acknowledged run/stop transitions are sampled, and no already-conflicting external start. Does not claim plant-level mutual exclusion for arbitrary external starts.')
n=31;b=src(n,'BrushUse');q=src(n,'Request');end='Clock.Timestamp >= $day_timestamp - $day_hour * 3600 - $day_minute * 60 + 86400';check=branch(end,[{'op':'break'}])
phase=[wait(f'{b} == false or ({end})'),check,wait(f'{b} == true or ({end})'),check,wait(f'{b} == false or ({end})'),check,wait(f'{b} == true or ({end})'),check,
       cycle([wait(f'{q} == true or ({end})'),check,call(n,'On'),wait(f'{q} == false or ({end})'),check]),{'op':'break'}]
put(n,[cycle([read('day_timestamp','Clock.Timestamp'),read('day_hour','Clock.Hour'),read('day_minute','Clock.Minute'),cycle(phase)])],label='complete for fixed-two raw-event interpretation',reason='Two observed rising use events enable requests immediately at the second onset; initial held use is not an event. Day deadline resets the phases at midnight, before requests at that boundary. This is bounded phase state, not arbitrary counting; the corpus author additionally permits an external daily-count guard.')
ATTEMPTS['E1-024']['joi_fallback']='Separate executed mutable-accumulator prefix fallback in joi_fallback.py; only covers these sub-48-hour histories, not general rolling expiry. See runs/joi_024.json.'
ATTEMPTS['E1-024']['outcome_category']='language-candidate limitation under agent request-serving rolling-budget interpretation; no impossibility proof'
