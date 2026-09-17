"""Static-only generator. Run with ~/temp/bin/python; never imports evaluators."""
import copy, hashlib, json, re, sys
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent
E2=HERE.parent.parent
ROOT=E2.parents[2]
SRC=E2/'pairs/e1_pairs.json'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(name,obj): (HERE/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def normalize(s):
    # Preserve quoted string tokens; remove insignificant inter-token whitespace.
    return tuple(re.findall(r'"(?:\\.|[^"\\])*"|\w+|[^\w\s]',s))
sys.path.insert(0,str(ROOT/'lowering/parser/generated'))
from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener
from JOILangLexer import JOILangLexer
from JOILangParser import JOILangParser
class Errors(ErrorListener):
    def __init__(self): self.errors=[]
    def syntaxError(self,recognizer,symbol,line,column,msg,e): self.errors.append(f'{line}:{column} {msg}')
def parse(s):
    listener=Errors(); lexer=JOILangLexer(InputStream(s)); parser=JOILangParser(CommonTokenStream(lexer))
    for x in [lexer,parser]: x.removeErrorListeners(); x.addErrorListener(listener)
    parser.scenario();return listener.errors

def main():
    source=json.loads(SRC.read_text()); all_old=source['pairs']
    bases=sorted([p for p in all_old if p['kind']=='correct'],key=lambda p:p['pair_id'])
    allocation=json.loads((HERE/'allocation.json').read_text())
    assert len(bases)==21
    seen={normalize(p['joi']['script']) for p in all_old}
    pairs=[];provenance=[]
    for rank,b in enumerate(bases):
        key=b['pair_id'].split('/')[0]; edits=allocation[key]
        assert len(edits)==(3 if rank<6 else 2),(key,len(edits))
        for index,m in enumerate(edits,1):
            original=b['joi']['script']; assert original.count(m['old'])==m['count'],(key,index,original.count(m['old']),m['count'])
            script=original.replace(m['old'],m['new']);assert script!=original
            errors=parse(script);assert not errors,(key,index,errors)
            norm=normalize(script);assert norm not in seen,('duplicate',key,index);seen.add(norm)
            p=copy.deepcopy(b);p.update(pair_id=f'{key}/ext60-fault{index}',kind='fault',family=m['family'],description=m['rationale'],change={k:m[k] for k in ['old','new','count']});p['joi']['script']=script
            old_catalog=p['catalog']; p['catalog']=old_catalog.replace('PerCom/6_Evaluation/','PerCom/08_Evaluation/')
            assert (ROOT/p['catalog']).is_file(),p['catalog']
            if old_catalog!=p['catalog']:
                assert sha(ROOT/p['catalog'])==source['inputs_sha256'][old_catalog], 'Relocated catalog differs from frozen source'
            pairs.append(p)
            provenance.append(dict(pair_id=p['pair_id'],base_pair_id=b['pair_id'],base_case=b['base_case'],automation=b['automation'],allocation_rank=rank+1,mutation=m,catalog_relocation=dict(original=old_catalog,current=p['catalog'],sha256=sha(ROOT/p['catalog']),content_equal_to_frozen_input=True),original_joi=copy.deepcopy(b['joi']),mutated_joi=copy.deepcopy(p['joi']),original_script=original,mutated_script=script,base_pair_sha256=hashlib.sha256(json.dumps(b,sort_keys=True).encode()).hexdigest(),ground_truth='not assigned; author-intended mutation only'))
    assert len(pairs)==48
    inputs=[SRC,E2/'pairs/e1_pairs_src.py',HERE/'allocation.json',HERE/'generate.py',HERE/'declare.py',HERE/'PROTOCOL.md']
    input_hashes={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    dump('pairs.json',dict(inputs_sha256=input_hashes,n_pairs=48,n_correct=0,n_fault=48,families=sorted({p['family'] for p in pairs}),pairs=pairs))
    dump('provenance.json',dict(selection='Sorted 21 correct base pairs; 2 faults each plus third for first six; no outcomes used.',inputs_sha256=input_hashes,pairs=provenance))
    dump('STATIC_CHECKS.json',dict(n_pairs=48,n_base_pairs=21,n_requests=20,allocation={k:len(v) for k,v in sorted(allocation.items())},families=dict(sorted(Counter(p['family'] for p in pairs).items())),grammar_errors=0,duplicates_against_original102=0,duplicates_within_extension=0,semantic_equivalence_checked=False,reference_executed=False,explorer_executed=False))
    frozen=['PROTOCOL.md','declare.py','allocation.json','generate.py','pairs.json','provenance.json','STATIC_CHECKS.json']
    dump('FREEZE_MANIFEST.json',dict(status='frozen-before-evaluator-execution',files={f:sha(HERE/f) for f in frozen},source_sha256=sha(SRC)))
    print('Frozen 48 variants; grammar and script duplicate checks passed.')
if __name__=='__main__':main()
