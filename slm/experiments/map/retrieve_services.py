# -*- coding: utf-8 -*-
"""RAG 매핑 실험 1 — 절(segment) 임베딩으로 서비스/카테고리 검색.

데이터: slm 절 라벨(type_labels.json)의 gold 절 × paper 브랜치 dataset(카탈로그 정합 ir_gt, binding_gt).
  두 데이터에 같은 문장으로 있는 353행만 사용.
문서: joi_slm/assets/effects.json 서비스 247개 — "카테고리 한글별칭 | svc | ko_triggers | effects".
질의: 절 텍스트 (ACT/COND/TRIG/READ만; TIME/DELAY/STOP/ELSE는 서비스 없음).
역할 필터: ACT → role∈{action, read_action} / COND·TRIG·READ → role∈{read, read_action}.
지표:
  절 hit@k     — 절의 top-k에 이 명령 gold 서비스 중 하나가 있는가
  명령 recall@k — 명령 gold 서비스 집합이 절들의 top-k 합집합에 얼마나 들어오나
  + 조인 후(연결 기기 카테고리로 필터) 같은 지표
"""
import json, os, re, collections, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from embed import embed
ROOT = os.path.join(HERE, "..", "..", "..")

E = [s for s in json.load(open(os.path.join(ROOT, "joi_slm", "assets", "effects.json")))["services"]
     if not s["svc"].split(".")[0].endswith("Control")]   # *Control 계열 제외(사용자 결정)
AL = json.load(open(os.path.join(ROOT, "joi_slm", "assets", "category_aliases.json")))["aliases"]
T = json.load(open(os.path.join(HERE, "..", "type", "type_labels.json")))
if os.environ.get("EXTRA", "1") == "1":   # paper 재작성 명령 29개(기기 교체분, 직접 라벨) 포함
    T = T + json.load(open(os.path.join(HERE, "..", "type", "type_labels_extra.json")))
P = pd.read_csv(os.path.join(HERE, "dataset_paper.csv"))
prow = {r.command_kor: r for r in P.itertuples()}

def svc_doc(s):
    cat = s["svc"].split(".")[0]
    al = " ".join(AL.get(cat, [])[:4])
    return f"{al} | {s['svc']} | " + " / ".join(s.get("ko_triggers", [])) + " | " + "; ".join(s.get("effects", []))
DOCS = [svc_doc(s) for s in E]
SVCS = [s["svc"] for s in E]
ROLE = {s["svc"]: s["role"] for s in E}
OK = {"ACT": {"action", "read_action"}, "COND": {"read", "read_action"}, "TRIG": {"read", "read_action"}, "READ": {"read", "read_action"}}

items = []
for o in T:
    r = prow.get(o["cmd"])
    if r is None:
        continue
    gold = set(re.findall(r"\b([A-Z][A-Za-z]+\.[A-Za-z0-9]+)", r.ir_gt)) & set(SVCS)
    devs = json.loads(r.connected_devices)
    conn = {c for d in devs.values() for c in d["category"] if not c.endswith("Control")}   # *Control 계열 제외(사용자 결정)
    segs = [s for s in o["segments"] if s["type"] in OK]
    items.append(dict(cmd=o["cmd"], gold=gold, conn=conn, segs=segs, cat=o["cat"]))
print("명령", len(items), "질의 절", sum(len(i["segs"]) for i in items))

INSTRUCT = "주어진 스마트홈 명령의 절에 해당하는 IoT 서비스(기기 기능 또는 센서 값)를 찾아라"
D = embed(DOCS)
Q = embed([s["text"] for i in items for s in i["segs"]], instruct=INSTRUCT)
S = Q @ D.T
qi = 0
KS = (1, 3, 5, 10)
def run(join):
    hit = {k: [0, 0] for k in KS}; rec = {k: [] for k in KS}; miss = collections.Counter()
    q = 0
    for it in items:
        union = {k: set() for k in KS}
        for s in it["segs"]:
            sc = S[q]; q += 1
            order = np.argsort(-sc)
            ranked = [SVCS[j] for j in order if ROLE[SVCS[j]] in OK[s["type"]]
                      and (not join or SVCS[j].split(".")[0] in it["conn"])]
            for k in KS:
                top = set(ranked[:k]); union[k] |= top
                hit[k][1] += 1
                if top & it["gold"]:
                    hit[k][0] += 1
                elif k == 5:
                    miss[(s["type"], s["text"], tuple(sorted(it["gold"]))[:3], tuple(ranked[:3]))] += 1
        for k in KS:
            if it["gold"]:
                rec[k].append(len(it["gold"] & union[k]) / len(it["gold"]))
    tag = "조인 후" if join else "조인 전"
    print(f"[{tag}] 절 hit@k: " + "  ".join(f"@{k} {hit[k][0]/hit[k][1]:.3f}" for k in KS) +
          " | 명령 recall@k: " + "  ".join(f"@{k} {np.mean(rec[k]):.3f}" for k in KS))
    return miss
run(False)
miss = run(True)
print("\n조인 후 hit@5 실패 예 (타입 | 절 | gold | top3):")
for (t, txt, g, top), _ in list(miss.items())[:40]:
    print(f"  {t:4s} | {txt} | {g} | {top}")
np.save(os.path.join(HERE, "svc_docs.npy"), D)

# ── 2. 코퍼스 예문 확장 (5조각 교차검증, 다른 조각의 명령에서만 수집) ─────
print("\n== 코퍼스 예문 확장 (fold 밖 명령의 절을 서비스별 예문으로, max-sim) ==")
from sklearn.model_selection import GroupKFold
EXPEN = float(os.environ.get("EXPEN", "0")); LEXB = float(os.environ.get("LEXB", "0"))
def lex_words(s):
    cat = s["svc"].split(".")[0]
    ws = set()
    for tr in AL.get(cat, []) + s.get("ko_triggers", []):
        for w in re.split(r"[\s,./]+", tr):
            w = re.sub(r"(을|를|이|가|은|는|의|로|으로|에|도)$", "", w)
            if len(w) >= 2 and not re.fullmatch(r"[\d.]+", w): ws.add(w)
    return ws
LEXW = [lex_words(s) for s in E]
LEXQ = np.stack([np.array([min(2, sum(1 for w in ws if w in re.sub(r"\s", "", s["text"]))) for ws in LEXW], dtype=np.float32)
                 for it in items for s in it["segs"]]) * LEXB
seg_rows = [(ci, si) for ci, it in enumerate(items) for si in range(len(it["segs"]))]
groups = np.array([ci for ci, _ in seg_rows])
svc_idx = {s: j for j, s in enumerate(SVCS)}
row_of = {p: q for q, p in enumerate(seg_rows)}

def align(train_cmds):
    """명령의 gold 서비스마다 역할이 맞는 절 중 문서 유사도 최고인 절을 예문으로."""
    ex = collections.defaultdict(list)
    for ci in train_cmds:
        it = items[ci]
        for g in it["gold"]:
            best, bs = None, -1
            for si, s in enumerate(it["segs"]):
                if ROLE[g] not in OK[s["type"]]:
                    continue
                sc = S[row_of[(ci, si)], svc_idx[g]]
                if sc > bs:
                    bs, best = sc, si
            if best is not None:
                ex[g].append(row_of[(ci, best)])
    return ex

RANKED = {}
def run_multi(join, KS=(1, 3, 5, 10)):
    hit = {k: [0, 0] for k in KS}; rec = {k: [] for k in KS}
    fails = []
    for tr, te in GroupKFold(5).split(seg_rows, groups=groups):
        train_cmds = sorted(set(groups[tr]))
        ex = align(train_cmds)
        # 서비스별 점수 = max(문서 유사도, 예문 유사도들)
        for ci in sorted(set(groups[te])):
            it = items[ci]
            union = {k: set() for k in KS}
            for si, s in enumerate(it["segs"]):
                q = row_of[(ci, si)]
                sc = S[q] + LEXQ[q]
                for g, rows in ex.items():
                    if rows:
                        sc[svc_idx[g]] = max(sc[svc_idx[g]], float((Q[rows] @ Q[q]).max()) - EXPEN)
                order = np.argsort(-sc)
                ranked = [SVCS[j] for j in order if ROLE[SVCS[j]] in OK[s["type"]]
                          and (not join or SVCS[j].split(".")[0] in it["conn"])]
                if join:
                    RANKED[(ci, si)] = ranked[:5]
                for k in KS:
                    top = set(ranked[:k]); union[k] |= top
                    hit[k][1] += 1
                    if top & it["gold"]:
                        hit[k][0] += 1
                    elif k == 3 and join:
                        fails.append((s["type"], s["text"], tuple(sorted(it["gold"]))[:3], tuple(ranked[:3])))
            for k in KS:
                if it["gold"]:
                    rec[k].append(len(it["gold"] & union[k]) / len(it["gold"]))
    tag = "조인 후" if join else "조인 전"
    print(f"[{tag}] 절 hit@k: " + "  ".join(f"@{k} {hit[k][0]/hit[k][1]:.3f}" for k in KS) +
          " | 명령 recall@k: " + "  ".join(f"@{k} {np.mean(rec[k]):.3f}" for k in KS))
    return fails
run_multi(False)
fails = run_multi(True)
print("\n확장+조인 후 hit@3 실패 예:")
for f in fails[:40]:
    print("  %s | %s | %s | %s" % f)

json.dump([{"cmd": it["cmd"], "cat": it["cat"], "gold": sorted(it["gold"]),
            "segs": [{"j": s["j"], "text": s["text"], "type": s["type"], "mods": s["mods"],
                      "ranked": RANKED.get((ci, si), [])} for si, s in enumerate(it["segs"])]}
           for ci, it in enumerate(items)],
          open(os.path.join(HERE, "ranked.json"), "w"), ensure_ascii=False, indent=1)
print("저장 ranked.json")
