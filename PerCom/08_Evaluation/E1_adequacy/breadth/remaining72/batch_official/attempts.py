"""ASTRA encodings written after final pre-encoding freeze. No expected-trace reads.
Previous-state snapshots follow original20 E-PREV. Timing and policy stay in IR.
"""
ATTEMPTS={}
def inp(d,f):return f'OfficialInput[{d}].{f}'
def read(v,s):return {'op':'read','var':v,'src':s}
def call(m,d='a_light',**args):return {'op':'call','target':f'OfficialAction[{d}].{m}','args':args}
def iff(c,b):return {'op':'if','cond':c,'then':b}
def wait(c):return {'op':'wait','cond':c,'edge':'none'}
def delay(s):return {'op':'delay','duration':f'{s} SEC'}
def cyc(b,period='100 MSEC',**kw):return {'op':'cycle','until':None,'period':period,'body':b,**kw}
def install(n,steps,label='complete under frozen interpretation',reason='Previous-state snapshots identify events; guards and command arguments implement frozen source-derived semantics.'):
 ATTEMPTS[f'E1-{n:03d}']={'label':label,'label_reason':reason,'source':'ASTRA agent encoding after FREEZE_MANIFEST.json; not author approval','automations':[{'name':'main','ir':{'timeline':[{'op':'start_at','anchor':'now'}]+steps}}]}
def poll(n,fields,body,**kw):
 init=[read(v,s) for v,s in fields];install(n,init+[cyc(body+init)],**kw)
def rise(n,field,condition,actions,device='i_sensor',guard=None,**kw):
 s=inp(device,field); condition=condition.replace('@',s).replace('PREV','$prev')
 if guard:actions=[iff(guard,actions)]
 poll(n,[('prev',s)],[iff(condition,actions)],**kw)
rise(54,'State','@ == true and PREV == false',[call('On')])
rise(56,'Home','@ == true and PREV == false',[call('Off','a_camera')])
rise(64,'PoorAir','@ == true and PREV == false',[call('On','a_purifier'),call('Speed','a_purifier',Level='speed_high')])
rise(69,'Home','@ == false and PREV == true',[call('On','a_camera')])
rise(73,'Delivered','@ == true and PREV == false',[call('Notify','a_phone',Message='A package is delivered')])
rise(76,'Zone','@ != "Work" and PREV == "Work"',[call('Notify','a_phone',Message='Person has left Work')])
rise(59,'Temperature','@ < 18 and PREV >= 18',[call('Open','a_blind',Percent=100),call('On','a_fan'),call('SetTemperature','a_thermostat',Celsius=21)])
rise(60,'Temperature','@ > 25 and PREV <= 25',[call('Open','a_blind1',Percent=0),call('Open','a_blind2',Percent=0),call('On','a_fan'),call('SetTemperature','a_thermostat',Celsius=22)])
rise(77,'Elevation','@ < -4 and PREV >= -4',[call('On')])
s=inp('i_sensor','Home');poll(57,[('prev',s)],[iff(f'{s} != $prev',[iff(f'{s} == false',[call('Start','a_vacuum')]),iff(f'{s} == true',[call('Stop','a_vacuum')])])])
rise(58,'State','@ == true and PREV == false',[call('Brightness',Percent=5),call('Open','a_blind',Percent=0)],guard=inp('i_sun','Daylight')+' == false')
rise(65,'Locked','@ == false and PREV == true',[call('Brightness',Percent=100)],guard=inp('i_sun','Daylight')+' == false')
poll(55,[('hour','Clock.Hour')],[iff('Clock.Hour == 22 and $hour != 22',[call('Brightness',Percent=50),call('Open','a_blind',Percent=0)])])
poll(61,[('hour','Clock.Hour'),('sun',inp('i_sun','Daylight'))],[iff(inp('i_sun','Daylight')+' == false and $sun == true',[call('Brightness',Percent=100)]),iff('Clock.Hour == 22 and $hour != 22',[call('Brightness',Percent=50)]),iff('Clock.Hour == 0 and $hour != 0',[call('Off')])],reason='Three source schedules expressed as independent guards in one continuously polling flow; no waits block another schedule.')
rise(63,'Smoke','@ == true and PREV == false',[call('Color',Name='red'),delay(5),call('Off'),delay(5),call('Color',Name='blue'),delay(5),call('Off'),delay(5),call('Color',Name='red')],label='complete under qualified single-flight interpretation',reason='Exact finite source color sequence; concurrent/restart policy not specified by source and frozen as ignore while busy.')
for n,field in [(67,'Motion'),(68,'Occupied')]:
 s=inp('i_sensor',field)
 poll(n,[('prev',s)],[iff(f'{s} == true and $prev == false',[call('On')]),iff(f'{s} == false and $prev == true',[read('absent_at','Clock.Timestamp')]),iff(f'{s} == false and $absent_at != null and Clock.Timestamp - $absent_at >= 300 and ($off_at == null or $off_at < $absent_at)',[call('Off'),read('off_at','Clock.Timestamp')])],label='complete under source-YAML absence interpretation' if n==68 else 'complete under frozen interpretation',reason='Controller timestamp tracks last absence onset; input is inspected before deadline action so coincident renewed presence cancels Off. E1-068 YAML selected over abbreviated prose.' if n==68 else 'Timestamp timer resets at every true->false transition; no repeated Off or startup timer.')
# Fixed finite pulse is intentionally unrolled, avoiding a timed device fixture.
for n,field,ds in [(66,'CO',['a_light1','a_light2']),(70,'Pressed',['a_light'])]:
 pulse=[]
 for k in range(300):pulse += [call('On' if k%2==0 else 'Off',d) for d in ds]+[delay(1)]
 rise(n,field,'@ == true and PREV == false',pulse,guard=inp('i_room','Occupied')+' == true' if n==70 else None,label='qualified complete for frozen pulse waveform',reason='Controller emits 150 square-wave On/Off pairs over five minutes. Waveform and ignore-while-busy policy are agent choices; native LightEffectPulse equivalence is not established.')
rise(71,'Query','@ == "Movie Night" and PREV != "Movie Night"',[call('Off'),call('Open','a_blind',Percent=0),call('Pause','a_washer')],device='i_assistant')
s=inp('i_sensor','Motion');poll(74,[('prev',s)],[iff(f'{s} == true and $prev == false and Clock.Hour >= 5 and Clock.Hour < 12 and ($opened_at == null or Clock.Timestamp - $opened_at >= 72000)',[call('Open','a_blind1',Percent=100),call('Open','a_blind2',Percent=100),read('opened_at','Clock.Timestamp')])],label='qualified complete for success-based suppression',reason='Twenty-hour cooldown maintained by timestamp after action, inclusive expiry. Suppression before condition evaluation is an untested alternative source interpretation.')
weekday='(Clock.Weekday == "monday" or Clock.Weekday == "tuesday" or Clock.Weekday == "wednesday" or Clock.Weekday == "thursday" or Clock.Weekday == "friday")'
fields=[(f'prev{k}',inp(f'i_motion{k}','Motion')) for k in range(1,4)]
poll(75,fields,[iff(f'{s} == true and ${v} == false and Clock.Hour >= 9 and Clock.Hour < 18 and {weekday}',[call('Notify','a_phone1',Message='Motion at home'),call('Notify','a_phone2',Message='Motion at home')]) for v,s in fields],reason='All three raw motion events inspected independently; two recipients per event; actual runtime weekday strings. Frozen transcription MON is a metadata shorthand, runtime uses monday.')
assert len(ATTEMPTS)==22
