# -*- coding: utf-8 -*-
"""서비스 매핑 — 절 임베딩 검색(문서 유사도 + 코퍼스 예문 유사도) + 역할·연결 기기 카테고리 조인 → 절별 top-5;
조건 절은 값 표현 단위(접속어미 분할)로 재질의(값 서비스만, 어휘·별칭 보너스). 결과는 builder.Mapping."""
import json, os, re
import numpy as np
from .catalog import SERVICES, EFF, ROLE, AL, svc_doc, svc_info, conn_categories, switch_categories
from .builder import Mapping

ASSET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "examples.json")
COND_ASSET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "cond_examples.json")
INSTRUCT = "주어진 스마트홈 명령의 절에 해당하는 IoT 서비스(기기 기능 또는 센서 값)를 찾아라"
CINSTRUCT = "이 한국어 조건 표현이 가리키는 IoT 센서 값 또는 기기 상태 값을 찾아라"
OK = {"ACT": {"action", "read_action"}, "COND": {"read", "read_action"}, "TRIG": {"read", "read_action"}, "READ": {"read", "read_action"}}
SVCS = [s["svc"] for s in SERVICES]; VAL = [s["svc"] for s in SERVICES if s["role"] == "read"]
CONJ_SPLIT = re.compile(r"(?<=[가-힣])((?<=[있없되하이않크작높낮많적리히지오가주시밝덥춥])고|거나|이거나|며|이며|는데|은데)[,\s]+(?!있|않|없)")
TOK = {"고", "거나", "이고", "이거나", "며", "이며", "는데", "은데"}
NOUN_PAIR = re.compile(r"(\S+?)(?:와|과)\s*(\S+)(?:이|가|은|는|도)\s*(?:모두|둘 다|다)?\s*([^,]*(?:면|때|경우))")
def _noun_pair(text):
    """"금고와 도어락이 모두 잠겨있으면" 처럼 기기 두 개를 한 번에 부른 조건 → 둘로 나눈다.
    두 낱말이 서로 다른 기기 종류를 가리킬 때만 나눈다(그냥 나열이면 그대로 둔다)."""
    m = NOUN_PAIR.search(text.strip())
    if not m: return None
    def cat_of(w):
        return {c for c, al in AL.items() if any(len(a) >= 2 and a in w for a in al)}
    a, b_ = cat_of(m.group(1)), cat_of(m.group(2))
    if not a or not b_ or a == b_: return None
    def josa(w): return "이" if (ord(w[-1]) - 0xAC00) % 28 else "가"          # 받침 있으면 "이", 없으면 "가"
    return [f"{m.group(1)}{josa(m.group(1))} {m.group(3)}", f"{m.group(2)}{josa(m.group(2))} {m.group(3)}"]

def parts_of(text):
    ps = [p for p in CONJ_SPLIT.split(text) if p and p not in TOK]
    if len(ps) >= 2:
        return [p + ("이면" if not re.search(r"(면|때|경우)[,.]?$", p) else "") for p in ps]
    return _noun_pair(text) or [text]
def _bg(t): t = re.sub(r"[\s.,]", "", t); return {t[i:i + 2] for i in range(len(t) - 1)}
def _lex(part, s):
    cat = s["svc"].split(".")[0]; return len(_bg(part) & _bg(" ".join(AL.get(cat, []) + s.get("ko_triggers", []) + [cat])))
def _alias(part, s):
    cat = s["svc"].split(".")[0]
    return max([len(w.strip()) for w in AL.get(cat, []) + s.get("ko_triggers", []) if len(w.strip()) >= 2 and w.strip() in part] or [0])

class Retriever:
    def __init__(self, embedder, examples=ASSET):
        """examples: [{i, text, svc}] 코퍼스 예문(절 텍스트→gold 서비스, 없으면 문서 유사도만)."""
        self.emb = embedder
        self.D = embedder([svc_doc(s) for s in SERVICES])
        self.DV = np.array([[self.D[k] for k, s in enumerate(SERVICES) if s["svc"] == v][0] for v in VAL])
        ex = json.load(open(examples)) if examples and os.path.exists(examples) else []
        self.ex_i = np.array([e["i"] for e in ex]); self.ex_col = np.array([SVCS.index(e["svc"]) for e in ex], int)
        self.EX = embedder([e["text"] for e in ex], instruct=INSTRUCT) if ex else None
        # 조각 경로(조건절→값 서비스)용 예문. 절 단위 예문과 지시문이 다르다.
        cx = json.load(open(COND_ASSET)) if os.path.exists(COND_ASSET) else []
        cx = [e for e in cx if e["svc"] in VAL]
        self.cx_i = np.array([e["i"] for e in cx]); self.cx_col = np.array([VAL.index(e["svc"]) for e in cx], int)
        self.CX = embedder([e["text"] for e in cx], instruct=CINSTRUCT) if cx else None
    def __call__(self, segs, connected_devices=None, exclude=()):
        """segs: [{j, text, type}] → Mapping. exclude: 예문에서 뺄 원본 명령 i(held-out 평가용)."""
        conn = conn_categories(connected_devices); sw = switch_categories(connected_devices)
        q = [(s["j"], s["text"], s["type"]) for s in segs if s["type"] in OK]
        ranked = {}
        if q:
            Q = self.emb([t for _, t, _ in q], instruct=INSTRUCT); S = Q @ self.D.T
            if self.EX is not None:                                     # 예문 확장: 서비스 점수 = max(문서 유사도, 예문 유사도)
                E = Q @ self.EX.T
                for k in np.where(~np.isin(self.ex_i, list(exclude)))[0]:
                    c = self.ex_col[k]; S[:, c] = np.maximum(S[:, c], E[:, k])
            for r, (j, t, ty) in enumerate(q):
                order = np.argsort(-S[r])
                ranked[j] = [SVCS[k] for k in order if ROLE[SVCS[k]] in OK[ty] and (conn is None or SVCS[k].split(".")[0] in conn)][:5]
        parts = {}
        pq = [(s["j"], p) for s in segs if s["type"] in ("COND", "TRIG") for p in parts_of(s["text"])]
        if pq:
            Q2 = self.emb([p for _, p in pq], instruct=CINSTRUCT)
            S2 = Q2 @ self.DV.T
            if self.CX is not None:                                  # 조건 예문: 값 점수 = max(문서, 예문)
                E2 = Q2 @ self.CX.T
                for k in np.where(~np.isin(self.cx_i, list(exclude)))[0]:
                    c = self.cx_col[k]; S2[:, c] = np.maximum(S2[:, c], E2[:, k])
            for r, (j, p) in enumerate(pq):
                sc = S2[r].copy()
                for k, v in enumerate(VAL):
                    if conn is not None and v.split(".")[0] not in conn: sc[k] = -9
                    else: sc[k] += 0.02 * _lex(p, EFF[v]) + 0.08 * _alias(p, EFF[v])
                parts.setdefault(j, []).append({"part": p, "ranked": [VAL[k] for k in np.argsort(-sc)[:5]]})
        return Mapping(ranked, parts, {s["j"]: s["text"] for s in segs}, conn, sw)

def build_examples(labels, gold_of, embedder, out=ASSET):
    """코퍼스 예문: 명령의 gold 서비스마다 역할이 맞는 절 중 문서 유사도 최고인 절을 예문으로. labels: type_labels 항목들, gold_of(o)→IR."""
    D = embedder([svc_doc(s) for s in SERVICES]); ex = []
    for o in labels:
        g = gold_of(o)
        if not g: continue
        gold = set(re.findall(r"\b([A-Z][A-Za-z]+\.[A-Za-z0-9]+)", json.dumps(g))) & set(SVCS)
        segs = [s for s in o["segments"] if s["type"] in OK]
        if not gold or not segs: continue
        Q = embedder([s["text"] for s in segs], instruct=INSTRUCT); S = Q @ D.T
        for v in gold:
            c = SVCS.index(v); best = max((k for k, s in enumerate(segs) if ROLE[v] in OK[s["type"]]), key=lambda k: S[k, c], default=None)
            if best is not None: ex.append({"i": o["i"], "text": segs[best]["text"], "svc": v})
    json.dump(ex, open(out, "w"), ensure_ascii=False, indent=0); return ex
