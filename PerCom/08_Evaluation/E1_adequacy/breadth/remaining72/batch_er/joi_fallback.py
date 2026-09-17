"""Executed JoI fallback: cumulative-runtime prefix with no session yet 48 h old.
This is deliberately NOT a full rolling-expiry implementation. It tests whether mutable
local state suffices for the two failed sub-48-hour histories, without a backend aggregate.
"""
from pathlib import Path
import sys,json,runpy
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import run_batch as B
SCRIPT='''used := 0
active := false
previous := false
started := 0
stop_at := 0
now = (#Clock).Timestamp
request = (#ER24).Request
if (active and now >= stop_at) {
    (#ER24).Off()
    used = used + now - started
    active = false
}
if (request and not previous and not active and used < 600) {
    duration = (#ER24).DurationSeconds
    remaining = 600 - used
    if (duration > remaining) {
        duration = remaining
    }
    started = now
    stop_at = now + duration
    active = true
    (#ER24).On()
}
previous = request
'''
def main():
 cases=runpy.run_path(str(HERE/'cases.py'))['CASE_BY_ID'];attempt=runpy.run_path(str(HERE/'attempts.py'))['ATTEMPTS']['E1-024'];case=cases['E1-024']
 ir,binding=B.R.lower(attempt['automations'][0]['ir']);catalog=str(HERE/'runs/catalog.json')
 def factory():return [B.R.compile_pair(ir,binding,case['devices'],catalog,script=SCRIPT,period=1000)[0].code_runner]
 try:
  rows,match,exact=B.R.run_histories(case,factory)
  result={'case_id':'E1-024','scope':'sub-48-hour prefix only; no session expiry implemented; NOT complete JoI coverage of rolling48h','script':SCRIPT,'histories':rows,'match':match,'exact':exact}
 except Exception as e:result={'case_id':'E1-024','error':repr(e),'scope':'prefix-only fallback attempt'}
 (HERE/'runs/joi_024.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
