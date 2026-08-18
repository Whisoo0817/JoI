# -*- coding: utf-8 -*-
"""조건 절 재질의 — COND/TRIG 절을 값 표현 단위(접속어미 분할)로 나눠 부분마다 값 서비스(role read/read_action)를 검색.
연결 기기 카테고리 조인 필터 유지. 문서 = svc_doc(effects.json). 질의 = 부분 텍스트(+ 조건 지시문). 출력 cond_parts.json:
  {cmd: {j: [{"part": text, "ranked": top5}]}}
"""
import json, os, re, sys, collections
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from embed import embed
ROOT = os.path.join(HERE, "..", "..", "..")
E = json.load(open(os.path.join(ROOT, "mapping_v2", "effects.json")))["services"]
AL = json.load(open(os.path.join(ROOT, "mapping_v2", "category_aliases.json")))["aliases"]
R = json.load(open(os.path.join(HERE, "ranked.json")))
P = pd.read_csv(os.path.join(HERE, "dataset_paper.csv")); prow = {r.command_kor: r for r in P.itertuples()}
def svc_doc(s):
    cat = s["svc"].split(".")[0]; al = " ".join(AL.get(cat, [])[:4])
    return f"{al} | {s['svc']} | " + " / ".join(s.get("ko_triggers", [])) + " | " + "; ".join(s.get("effects", []))
VAL = [s for s in E if s["role"] == "read"]                       # 조건은 값 서비스만
D = embed([svc_doc(s) for s in VAL]); SV = [s["svc"] for s in VAL]
# 접속어미 분할: '고'는 용언 어간 뒤에서만 ("차고/창고" 같은 명사 보호), 진행형 "고 있" 제외
CONJ_SPLIT = re.compile(r"(?<=[가-힣])((?<=[있없되하이않크작높낮많적리히지오가주시밝덥춥])고|거나|이거나|며|이며|는데|은데)[,\s]+(?!있|않|없)")
TOK = {"고", "거나", "이고", "이거나", "며", "이며", "는데", "은데"}
INSTRUCT = "이 한국어 조건 표현이 가리키는 IoT 센서 값 또는 기기 상태 값을 찾아라"
def parts_of(text):
    ps = [p for p in CONJ_SPLIT.split(text) if p and p not in TOK]
    return [p + ("이면" if not re.search(r"(면|때|경우)[,.]?$", p) else "") for p in ps] if len(ps) >= 2 else [text]
def _bigrams(t):
    t = re.sub(r"[\s.,]", "", t); return {t[i:i + 2] for i in range(len(t) - 1)}
LEXW = float(os.environ.get("LEXW", "0.02")); ALW = float(os.environ.get("ALW", "0.08"))
def lex(part, s):
    cat = s["svc"].split(".")[0]
    doc = " ".join(AL.get(cat, []) + s.get("ko_triggers", []) + [cat])
    return len(_bigrams(part) & _bigrams(doc))
def alias_hit(part, s):
    """카테고리 별칭/트리거 중 부분에 그대로 들어 있는 가장 긴 것 (길수록 강한 증거: 초미세먼지 > 미세먼지)"""
    cat = s["svc"].split(".")[0]; best = 0
    for w in AL.get(cat, []) + [t for t in s.get("ko_triggers", [])]:
        w = w.strip()
        if len(w) >= 2 and w in part: best = max(best, len(w))
    return best

queries, meta = [], []
for r in R:
    row = prow.get(r["cmd"])
    conn = {c for d in json.loads(row.connected_devices).values() for c in d["category"] if not c.endswith("Control")} if row is not None else None   # *Control 제외
    for s in r["segs"]:
        if s["type"] not in ("COND", "TRIG"): continue
        for p in parts_of(s["text"]):
            queries.append(p); meta.append((r["cmd"], s["j"], p, conn))
Q = embed(queries, instruct=INSTRUCT); S = Q @ D.T
out = collections.defaultdict(lambda: collections.defaultdict(list))
for q, (cmd, j, p, conn) in enumerate(meta):
    sc = S[q].copy()
    for k, s in enumerate(VAL):
        if conn is not None and s["svc"].split(".")[0] not in conn: sc[k] = -9
        sc[k] += LEXW * lex(p, s) + ALW * alias_hit(p, s)
    order = np.argsort(-sc)[:5]
    out[cmd][str(j)].append({"part": p, "ranked": [SV[k] for k in order]})
json.dump(out, open(os.path.join(HERE, "cond_parts.json"), "w"), ensure_ascii=False, indent=1)
print("조건 절 부분 질의", len(queries), "명령", len(out))
