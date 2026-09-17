from pathlib import Path
import sys,importlib.util,json,hashlib
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent));import run_batch as B
import run_depth as R
from timeline_ir.catalog import load_catalog
from timeline_ir.timeline_ir import validate_ir,validate_ir_against_catalog
s=B.load('sensitivity_cases',HERE/'sensitivity_cases.py')
record=json.loads((HERE/'SENSITIVITY_FREEZE.json').read_text());assert hashlib.sha256((HERE/'sensitivity_cases.py').read_bytes()).hexdigest()==record['sha256']
a=B.load('sensitivity_attempts',Path(sys.argv[1]) if len(sys.argv)>1 else HERE/'attempts.py')
cp=HERE/'runs'/'catalog.json';cat=load_catalog(str(cp));rows=[]
for c in s.CASES:
 pairs=[]
 for auto in a.ATTEMPTS[c['id']]['automations']:
  ir,b=R.lower(auto['ir']);validate_ir(ir);validate_ir_against_catalog(ir,cat);pairs.append((ir,b))
 hs,m,x=R.run_histories(c,lambda:[R.compile_pair(ir,b,c['devices'],str(cp))[0].ir_runner for ir,b in pairs]);rows.append({'id':c['id'],'histories':hs,'match':m,'exact':x});print(c['id'],m,x)
name=sys.argv[2] if len(sys.argv)>2 else 'sensitivity_results.json'
(HERE/'runs'/name).write_text(json.dumps(rows,indent=1))
