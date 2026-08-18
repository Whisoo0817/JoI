# -*- coding: utf-8 -*-
"""RAG 매핑 실험 2 — 절 → 기기 선택 (연결 기기 조인 + 태그/닉네임 한정 + 수량 정책).

입력: ranked.json (절별 서비스 top-5, 조인 후) + dataset_paper.csv (connected_devices, binding_gt)
절차(절마다):
  1. 서비스 = top-1. 후보 = 그 서비스의 카테고리를 가진 연결 기기 전부.
  2. 한정어 매칭: 절의 단어(조사 제거)를 (a) 태그 어휘(tag_lexicon 트리거, substring)
     (b) 태그 이름·닉네임 임베딩(단어 ↔ 태그 문서 cos ≥ τ) 로 대조 → 매칭 태그 집합.
     후보 중 매칭 태그를 하나라도 가진 기기 집합이 비지 않고 진부분집합이면 그것으로 좁힘.
     ("홀수"→Odd, "안방"→Bedroom, "섹터 비"→SectorB, "삼성"→닉네임)
  3. 수량: 좁혀진 집합 전부 (액션 무표지=전체 정책, 조건 센서=집합, 스칼라 읽기=Main→첫 기기).
평가: 절의 top-1 서비스가 binding_gt 자리에 있을 때, 예측 기기 집합 == binding_gt 집합.
"""
import json, os, re, sys, collections
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from embed import embed
ROOT = os.path.join(HERE, "..", "..", "..")
TAGLEX = json.load(open(os.path.join(ROOT, "joi_slm", "assets", "tag_lexicon.json")))["tags"]
TAGKO = json.load(open(os.path.join(HERE, "tag_ko.json")))          # 컴파일된 태그 한국어 어휘 (9B, 1회)
TAGKO.setdefault("Bedroom", []).append("안방")
TAGKO.setdefault("Shade", []).extend(["쉐이드", "셰이드"])
# 컴파일 어휘 수기 보정 (LLM 잡음 제거 + 누락 보충) — 소량, 목록으로 관리
for _t, _rm in {"Garage": ["주차장"], "Farm": ["가든"], "Terrace": ["마당"]}.items():
    TAGKO[_t] = [x for x in TAGKO.get(_t, []) if x not in _rm]
for _t, _add in {"Lab": ["연구실"], "SectorA": ["섹터 에이", "에이 섹터"], "SectorB": ["섹터 비", "비 섹터"],
                 "SectorC": ["섹터 씨"], "Inside": ["실내", "내부"], "Outside": ["실외", "외부", "바깥"],
                 "FrontDoor": ["현관문", "현관"], "Safe": ["금고"], "Vault": ["금고실"]}.items():
    TAGKO.setdefault(_t, []).extend(_add)
for _t, _v in list(TAGKO.items()):                 # "1 구역" ↔ "구역1" 양방향
    for _tr in list(_v):
        m = re.match(r"^(\d+)\s*(\S+)$", _tr)
        if m: _v.append(m.group(2) + m.group(1))
        m = re.match(r"^(\S+?)\s*(\d+)$", _tr)
        if m: _v.append(m.group(2) + m.group(1))
USE_EMB = os.environ.get("EMB", "0") == "1"
AL = json.load(open(os.path.join(ROOT, "joi_slm", "assets", "category_aliases.json")))["aliases"]
R = json.load(open(os.path.join(HERE, "ranked.json")))
P = pd.read_csv(os.path.join(HERE, "dataset_paper.csv"))
prow = {r.command_kor: r for r in P.itertuples()}
TAU = float(os.environ.get("TAU", "0.62"))

PARTICLE = re.compile(r"(에서는|에서|으로|로|은|는|이|가|을|를|의|에|과|와|도|만|들|이라도|라도|든|이든|들을|들의|들이|들은|들도)$")
def words(text):
    out = []
    for w in re.split(r"[\s,.\"'()]+", text):
        w = w.strip()
        if not w:
            continue
        out.append(w)
        w2 = PARTICLE.sub("", w)
        if w2 and w2 != w:
            out.append(w2)
    return list(dict.fromkeys(out))

def split_camel(t):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Za-z])(?=[0-9])", " ", t).replace("_", " ")

# 태그 문서: 이름 + camelCase 분해 + lexicon 트리거
def tag_doc(t):
    trig = TAGLEX.get(t, {}).get("triggers", [])
    return f"{t} ({split_camel(t)}) " + " ".join(trig)

def norm(x):
    return re.sub(r"[\s_\-]", "", x.lower())
def lex_hits_text(text, tag):
    """트리거를 절 전체(정규화)에 대조: 2자 이상은 substring, 1자는 조사 제거 단어와 완전 일치."""
    tn_text = norm(text)
    ws = {norm(w) for w in words(text)}
    for tr in TAGKO.get(tag, []) + [tag, split_camel(tag)]:
        tn = norm(tr)
        if not tn:
            continue
        if len(tn) >= 2 and tn in tn_text:
            return True
        if len(tn) == 1 and tn in ws:
            return True
    return False

# 카테고리 이름·별칭은 한정어가 아니라 기기 종류이므로 태그 매칭에서 제외
CAT_TAGS = set(AL.keys()) | {"Switch", "Light"}
GENERIC = {"Main"}   # 규약용 태그: 사용자가 말하지 않으면 매칭 금지 (임베딩 오탐 방지)

# 전체 태그·단어 임베딩 캐시
all_tags = sorted({t for r in R for d in json.loads(prow[r["cmd"]].connected_devices).values() for t in d["tags"]} - CAT_TAGS)
TV = embed([tag_doc(t) for t in all_tags]); tag_i = {t: i for i, t in enumerate(all_tags)}
all_words = sorted({w for r in R for s in r["segs"] for w in words(s["text"])})
WV = embed(all_words, instruct="이 한국어 단어가 가리키는 장소·구역·태그 이름을 찾아라"); word_i = {w: i for i, w in enumerate(all_words)}
SIM = WV @ TV.T
STOP_W = {"모두", "모든", "다", "전부", "하나라도", "켜줘", "꺼줘", "있으면", "이상이면", "이하이면", "감지되면"}

def match_tags(text, cand_tags):
    hits = {}
    for t in cand_tags:
        if t in GENERIC:
            continue
        if lex_hits_text(text, t):
            hits[t] = 1.0; continue
        if USE_EMB:
            for w in words(text):
                if w in STOP_W or len(w) < 2:
                    continue
                sc = float(SIM[word_i[w], tag_i[t]])
                if sc >= TAU:
                    hits[t] = max(hits.get(t, 0), sc)
    return hits

def gt_devices(binding, svc, used):
    """binding_gt에서 svc(또는 svc#2…) 자리를 순서대로 소비."""
    for k in [svc] + [f"{svc}#{n}" for n in range(2, 6)]:
        if k in binding and k not in used:
            used.add(k)
            v = binding[k]
            if isinstance(v, dict):
                v = v.get("any") or v.get("all") or []
            return set(v)
    return None

tot = ok = need_narrow = ok_narrow = 0
JOINT = os.environ.get("JOINT", "0") == "1"; svc_tot = [0, 0]
fails = []
for r in R:
    row = prow[r["cmd"]]
    devs = json.loads(row.connected_devices)
    binding = json.loads(row.binding_gt) if isinstance(row.binding_gt, str) else {}
    used = set()
    for s in r["segs"]:
        if not s["ranked"]:
            continue
        # 공동 선택: top-3 중 절 안의 한정어(태그)가 붙는 첫 서비스, 없으면 top-1
        svc = s["ranked"][0]
        if JOINT:
            for cand_svc in s["ranked"][:3]:
                c0 = cand_svc.split(".")[0]
                cs = {d for d, v in devs.items() if c0 in v["category"]}
                ct = {t for d in cs for t in devs[d]["tags"]} - CAT_TAGS
                h = match_tags(s["text"], ct)
                if h and {d for d in cs if set(devs[d]["tags"]) & set(h)} < cs:
                    svc = cand_svc; break
        svc_tot[0] += 1; svc_tot[1] += svc in set(json.loads(row.ir_gt) and re.findall(r"\b([A-Z][A-Za-z]+\.[A-Za-z0-9]+)", row.ir_gt))
        cat = svc.split(".")[0]
        gt = gt_devices(binding, cat, used)
        if gt is None:
            continue                     # top-1 서비스 자리가 정답에 없음 (서비스 오류는 1단계 지표)
        cands = {d for d, v in devs.items() if cat in v["category"]}
        _extra = []
        for k in [f"{cat}#{n}" for n in range(2, 6)]:
            if k in binding and k not in used:
                v = binding[k]; v = (v.get("any") or v.get("all") or []) if isinstance(v, dict) else v
                _extra.append((k, set(v)))
        cand_tags = {t for d in cands for t in devs[d]["tags"]} - CAT_TAGS
        hits = match_tags(s["text"], cand_tags)
        via = "seg"
        if not hits:
            hits = match_tags(" ".join(x["text"] for x in r["segs"]), cand_tags); via = "cmd"
        narrowed = {d for d in cands if set(devs[d]["tags"]) & set(hits)} if hits else set()
        # 여러 태그가 맞으면 교집합 우선("섹터 비의 홀수 금고"), 서로소면 합집합("거실과 침실")
        if len(hits) >= 2:
            inter = {d for d in cands if set(hits) <= set(devs[d]["tags"])}
            if inter:
                narrowed = inter
        pred = narrowed if narrowed and narrowed < cands else cands
        for k, v in _extra:                # 병합 조건 절: 같은 서비스 다음 자리가 예측 안에 있으면 함께 소비
            if v and v <= pred and not (v <= gt):
                gt = gt | v; used.add(k)
        # 스칼라 읽기 규약: 값 하나만 필요한 자리(READ 절 등)는 Main → 첫 기기
        if s["type"] == "READ" and len(pred) > 1:
            main = [d for d in sorted(pred) if "Main" in devs[d]["tags"]]
            pred = {main[0]} if main else {sorted(pred)[0]}
        tot += 1
        # 판별 태그 = gt 전부가 공유하되 후보 전부는 공유하지 않는 태그
        common_gt = set.intersection(*[set(devs[d]["tags"]) for d in gt]) if gt else set()
        common_all = set.intersection(*[set(devs[d]["tags"]) for d in cands])
        disc = common_gt - common_all - CAT_TAGS
        cmd_text = " ".join(x["text"] for x in r["segs"])
        # 한정어 자리 = 판별 태그 중 하나라도 명령 어딘가에서 발화됨 (아니면 규약 자리)
        qualifier_slot = any(lex_hits_text(cmd_text, t) for t in disc - GENERIC)
        needed = qualifier_slot
        need_narrow += needed
        if pred == gt:
            ok += 1; ok_narrow += needed
        elif not needed and gt <= pred:
            ok += 1                       # 규약 자리(수량만 다름) — 보류 정책상 통과
        else:
            fails.append((s["type"], s["text"], svc, sorted(gt), sorted(pred), dict(hits), sorted(disc), via))
print(f"JOINT={JOINT} 서비스 top-1 정답 포함률 {svc_tot[1]}/{svc_tot[0]} = {svc_tot[1]/svc_tot[0]:.3f}")
print(f"EMB={USE_EMB} τ={TAU}  평가 자리 {tot}: 통과 {ok} ({ok/tot:.3f}) | 한정어 자리 {need_narrow} 중 정확 {ok_narrow} ({ok_narrow/max(need_narrow,1):.3f})")
kinds = collections.Counter()
for f in fails:
    kinds["과대(못 좁힘)" if set(f[3]) < set(f[4]) else "과소/엇갈림"] += 1
print(kinds)
print("\n실패 예 (타입 | 절 | svc | gt | pred | 태그 매칭 | 판별태그 | 출처):")
for f in fails[:70]:
    print("  %s | %s | %s | %s | %s | %s | %s | %s" % f)
