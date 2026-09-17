"""Generate standard Timeline IR: 600 reusable timestamp slots, no new operator.
Each slot records the start of one actual commanded ON second. Control-flow position
is the circular-buffer cursor. Reading an expired slot overwrites it only on use.
"""
from pathlib import Path
import json
WINDOW=172800
BUDGET=600
REQUEST='ER24[D24].Request'
DURATION='ER24[D24].DurationSeconds'
NOW='Clock.Timestamp'
ACTIVE='$started_at != null and ($finished_at == null or $started_at >= $finished_at)'

def read(var,src=NOW): return dict(op='read',var=var,src=src)
def call(method): return dict(op='call',target='ER24[D24].'+method,args={})
def wait(cond): return dict(op='wait',cond=cond,edge='none')
def branch(cond,body): return dict(op='if',cond=cond,then=body)
def cycle(body,until=None): return dict(op='cycle',period='0 MSEC',until=until,body=body)

def slot(i):
    stamp=f'used_{i}'
    available=f'${stamp} == null or {NOW} - ${stamp} >= {WINDOW}'
    return [
        branch(f'({ACTIVE}) and ({NOW} - $started_at >= $requested_seconds or not ({available}))',
               [call('Off'),read('finished_at')]),
        cycle([
            wait(f'{REQUEST} != $previous_request'),
            branch(f'{REQUEST} == true and $previous_request == false and {DURATION} > 0 and ({available})',
                   [read('requested_seconds',DURATION),read('started_at'),call('On')]),
            read('previous_request',REQUEST),
        ],until=ACTIVE),
        read(stamp),
        read('previous_request',REQUEST),
        dict(op='delay',duration='1 SEC'),
    ]

def build():
    return {'timeline':[dict(op='start_at',anchor='now'),read('previous_request',REQUEST),
                        cycle([s for i in range(BUDGET) for s in slot(i)])]}

if __name__=='__main__':
    target=Path(__file__).with_name('timeline_ir.json')
    target.write_text(json.dumps(build(),indent=2)+'\n')
    print(target, target.stat().st_size)
