# -*- coding: utf-8 -*-
"""RAG 매핑 실험 3 — 실제 허브 페이로드(run.py CONNECTED_DEVICES, 닉네임·브랜드 태그 있음)에서
닉네임/태그 기반 명령이 풀리는지. 절 → 서비스(문서+코퍼스 예문 max-sim, 조인) → 기기(태그 어휘 + 닉네임 매칭).
"""
import json, os, re, sys, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "..", ".."))
from embed import embed
import run as R
DEV = R.CONNECTED_DEVICES
ROOT = os.path.join(HERE, "..", "..", "..")
E = json.load(open(os.path.join(ROOT, "joi_slm", "assets", "effects.json")))["services"]
AL = json.load(open(os.path.join(ROOT, "joi_slm", "assets", "category_aliases.json")))["aliases"]
TAGKO = json.load(open(os.path.join(HERE, "tag_ko.json")))
TAGKO.setdefault("Tuya", []).extend(["투야", "tuya"]); TAGKO.setdefault("Section3", []).extend(["구역 3", "구역3"])
RK = json.load(open(os.path.join(HERE, "ranked.json")))     # 코퍼스 예문 (절 텍스트 + gold)

def svc_doc(s):
    cat = s["svc"].split(".")[0]
    return f"{' '.join(AL.get(cat, [])[:4])} | {s['svc']} | " + " / ".join(s.get("ko_triggers", [])) + " | " + "; ".join(s.get("effects", []))
SVCS = [s["svc"] for s in E]; ROLE = {s["svc"]: s["role"] for s in E}
OK = {"ACT": {"action", "read_action"}, "COND": {"read", "read_action"}, "TRIG": {"read", "read_action"}, "READ": {"read", "read_action"}}
INSTRUCT = "주어진 스마트홈 명령의 절에 해당하는 IoT 서비스(기기 기능 또는 센서 값)를 찾아라"
D = embed([svc_doc(s) for s in E])
# 코퍼스 예문: 절 → (역할 맞는) gold 서비스 중 문서 유사도 최고인 것에 배정
ex_text, ex_svc = [], []
for r in RK:
    for s in r["segs"]:
        if s["type"] not in OK: continue
        ex_text.append(s["text"]); ex_svc.append((s["type"], r["gold"]))
EX = embed(ex_text, instruct=INSTRUCT)
svc_i = {s: i for i, s in enumerate(SVCS)}
ex_of = collections.defaultdict(list)
for q, (t, gold) in enumerate(ex_svc):
    best, bs = None, -1
    for g in gold:
        if g in svc_i and ROLE[g] in OK[t]:
            sc = float(EX[q] @ D[svc_i[g]])
            if sc > bs: bs, best = sc, g
    if best: ex_of[best].append(q)

_NUM = {"일": "1", "이": "2", "삼": "3", "사": "4", "오": "5", "육": "6", "칠": "7", "팔": "8", "구": "9"}
_ORD = {"첫": "1", "첫번째": "1", "두번째": "2", "둘째": "2", "세번째": "3", "셋째": "3", "네번째": "4", "넷째": "4",
        "다섯번째": "5", "여섯번째": "6"}
_ENKO = {"lamp": "램프", "switch": "스위치", "plug": "플러그", "sensor": "센서", "dial": "다이얼", "tap": "탭", "dimmer": "디머",
         "light": "라이트", "wifi": "와이파이", "kt": "케이티", "lg": "엘지"}
def norm(x):
    x = x.lower()
    for k, v in _ORD.items(): x = x.replace(k, v)
    x = re.sub(r"(?<=구역)\s*([일이삼사오육칠팔구])", lambda m: _NUM[m.group(1)], x)
    x = re.sub(r"([일이삼사오육칠팔구])(?=\s*(번|층|호|구))", lambda m: _NUM[m.group(1)], x)
    x = re.sub(r"[\s_\-()]", "", x)
    for k, v in _ENKO.items(): x = re.sub(rf"(?<![a-z]){k}(?![a-z])", v, x)
    return x
def split_camel(t): return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Za-z])(?=[0-9])", " ", t).replace("_", " ")
def hit_text(text, triggers):
    tn = norm(text)
    return any(len(norm(tr)) >= 2 and norm(tr) in tn for tr in triggers)
CAT_TAGS = set(AL.keys()) | {"Switch", "Light"}
TAGLEX = json.load(open(os.path.join(ROOT, "joi_slm", "assets", "tag_lexicon.json")))["tags"]
GENERIC = {"NoneNecessary", "Main"} | {t for t, v in TAGLEX.items() if v.get("kind") == "affordance"}   # 능력 태그는 한정어 아님
BRAND_TAGS = {t for t, v in TAGLEX.items() if v.get("kind") == "brand"}
BRAND_KO = {"삼성": ["삼성", "samsung"], "kt": ["kt", "케이티"], "lg": ["lg", "엘지"], "미로": ["미로"], "hue": ["휴", "hue", "필립스"],
            "aqara": ["아카라", "aqara"], "스카이라이트": ["스카이라이트"], "스마트빌": ["스마트빌"], "헤이홈": ["헤이홈", "hejhome"]}

def nick_hits(text, did, skip_brand=False, allow_fuzzy=True):
    """닉네임 어절이 절에 나오면 매칭. 표기 변형(SAMSUNG↔삼성, 에이컨↔에어컨)은 소사전 + 정규화로.
    숫자 어절은 다른 어절이 차지한 자리를 지운 뒤 독립 숫자로만 대조 ("6구 3" vs "6구 6")."""
    nick = DEV[did].get("nickname", "")
    if not nick: return 0
    tn = norm(text).replace("에이컨", "에어컨")
    toks = [t for t in re.split(r"[\s()]+", nick) if t]
    for t in list(toks):                       # "큰거/작은거" → "큰/작은" 변형도 어절로
        m = re.match(r"^(.+?)(거|것)$", t)
        if m and len(m.group(1)) >= 1: toks.append(m.group(1))
    score, rest = 0, tn
    for t in toks:
        t2 = norm(t)
        if t2.isdigit(): continue
        brand = any(t2 == k or t2 in vs for k, vs in BRAND_KO.items())
        if (len(t2) >= 2 and t2 in tn) or (len(t2) == 1 and not t2.isdigit() and t2 in {norm(w) for w in re.split(r"\s+", text)}):
            if not (brand and skip_brand): score += max(len(t2), 2) if len(t2) == 1 else len(t2)
            rest = rest.replace(t2, "#")
        elif brand and not skip_brand:
            for k, vs in BRAND_KO.items():
                if (t2 == k or t2 in vs) and any(norm(v) in tn for v in vs): score += len(t2)
    for t in toks:
        t2 = norm(t)
        if t2.isdigit() and re.search(rf"(?<!\d){t2}(?!\d)", rest): score += 1
    if score == 0 and USE_FUZZ and allow_fuzzy:            # 퍼지: 닉네임 어절(3자 이상)이 절 어절과 유사
        for t in toks:
            t2 = norm(t)
            if len(t2) >= 3 and not (skip_brand and any(t2 == k or t2 in vs for k, vs in BRAND_KO.items())) \
                    and fuzzy_hit(text, [t2]):
                score += len(t2) - 1
    return score

# ── 퍼지 매칭: 자모 분해 편집거리(한글) / 문자 편집거리(로마자) ─────────────
import unicodedata, difflib
CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"; JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
JONG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"
def jamo(s):
    out = []
    for ch in s:
        c = ord(ch)
        if 0xAC00 <= c <= 0xD7A3:
            c -= 0xAC00; out += [CHO[c // 588], JUNG[(c % 588) // 28]] + ([JONG[c % 28]] if c % 28 else [])
        else: out.append(ch)
    return "".join(out)
def fuzzy(a, b):
    """0~1 유사도. 둘 다 정규화된 문자열. 한글은 자모열로 비교."""
    a, b = jamo(a), jamo(b)
    return difflib.SequenceMatcher(None, a, b).ratio()
FUZZ = float(os.environ.get("FUZZ", "0.84"))
def fuzzy_hit(text, triggers):
    """트리거가 절의 어떤 어절(또는 인접 2어절)과 퍼지 유사 ≥ FUZZ면 매칭. 3자 미만 트리거는 정확 일치만."""
    ws = [norm(w) for w in re.split(r"[\s,.]+", text) if w]
    ws2 = ws + [ws[i] + ws[i + 1] for i in range(len(ws) - 1)]
    for tr in triggers:
        tn = norm(tr)
        if len(tn) < 3: continue
        for w in ws2:
            w2 = re.sub(r"(에서|으로|로|은|는|이|가|을|를|의|에|과|와|도|만|들)$", "", w)
            for cand in (w, w2):
                if len(cand) < 3 or abs(len(cand) - len(tn)) > 2: continue
                if re.findall(r"\d", cand) != re.findall(r"\d", tn): continue      # 숫자는 정확히
                if bool(re.search(r"[a-z]", cand)) != bool(re.search(r"[a-z]", tn)): continue  # 문자 체계 같을 때만
                if fuzzy(cand, tn) >= FUZZ:
                    return True
    return False

# ── 기기 문서 임베딩 fallback: "닉네임 | 태그(분해+한글) | 카테고리 별칭" vs 절 ──
def dev_doc(did):
    d = DEV[did]
    tags = [t for t in d["tags"] if not t.startswith("tc0_") and t not in CAT_TAGS]
    tag_ko = " ".join(x for t in tags for x in [split_camel(t)] + TAGKO.get(t, [])[:2])
    cats = " ".join(x for c in d["category"] for x in AL.get(c, [])[:2])
    return f"{d.get('nickname','')} | {tag_ko} | {cats}"
DEV_IDS = list(DEV); DV = embed([dev_doc(d) for d in DEV_IDS]); dev_i = {d: i for i, d in enumerate(DEV_IDS)}
EMB_MARGIN = float(os.environ.get("MARGIN", "0.03")); EMB_MIN = float(os.environ.get("EMBMIN", "0.55"))
TOPK = int(os.environ.get("TOPK", "3")); EXPEN = float(os.environ.get("EXPEN", "0"))
USE_FUZZ = os.environ.get("NOFUZZ") is None; USE_DEVEMB = os.environ.get("NODEVEMB") is None

LEXB = float(os.environ.get("LEXB", "0"))
def lex_words(s):
    cat = s["svc"].split(".")[0]
    ws = set()
    for tr in AL.get(cat, []) + s.get("ko_triggers", []):
        for w in re.split(r"[\s,./]+", tr):
            w = re.sub(r"(을|를|이|가|은|는|의|로|으로|에|도)$", "", w)
            if len(w) >= 2 and not re.fullmatch(r"[\d.]+", w): ws.add(w)
    return ws
LEXW = [lex_words(s) for s in E]
def lex_bonus(text):
    tn = re.sub(r"\s", "", text)
    return np.array([min(2, sum(1 for w in ws if w in tn)) * LEXB for ws in LEXW], dtype=np.float32)
def resolve(seg_text, seg_type):
    q = embed([seg_text], instruct=INSTRUCT)[0]
    q_dev = embed([seg_text], instruct="이 명령이 가리키는 스마트홈 기기를 찾아라")[0]
    sc = D @ q + lex_bonus(seg_text)
    for g, rows in ex_of.items():
        sc[svc_i[g]] = max(sc[svc_i[g]], float((EX[rows] @ q).max()) - EXPEN)
    conn = {c for d in DEV.values() for c in d["category"]}
    ranked = [SVCS[j] for j in np.argsort(-sc) if ROLE[SVCS[j]] in OK[seg_type] and SVCS[j].split(".")[0] in conn]
    # 서비스: 전원 의도는 Switch-first 규칙(매핑 규칙과 동일); 그 외 top-3 중 "한정어(태그/닉네임)가 붙는 서비스" 우선, 없으면 top-1
    if seg_type == "ACT" and re.search(r"(켜|꺼|끄|토글|반전)", seg_text) and not re.search(r"(밝기|퍼센트|%|색)", seg_text):
        pw = "Switch.Toggle" if re.search(r"토글|반전", seg_text) else ("Switch.On" if re.search(r"켜", seg_text) else "Switch.Off")
        order = [pw]
    else:
        order = ranked[:TOPK]
    choice = None
    for svc in order:
        cat = svc.split(".")[0]
        cands = {d for d, v in DEV.items() if cat in v["category"]}
        cand_tags = {t for d in cands for t in DEV[d]["tags"] if not t.startswith("tc0_")} - CAT_TAGS - GENERIC
        thits = {t for t in cand_tags if hit_text(seg_text, TAGKO.get(t, []) + [t, split_camel(t)])
                 or (USE_FUZZ and fuzzy_hit(seg_text, TAGKO.get(t, []) + [t]))}
        by_tag = {d for d in cands if set(DEV[d]["tags"]) & thits}
        if len(thits) >= 2:
            inter = {d for d in cands if thits <= set(DEV[d]["tags"])}
            if inter: by_tag = inter
        skip_brand = bool(thits & BRAND_TAGS)          # 브랜드는 태그가 잡았으면 닉네임에서 중복 계산 안 함
        ns = {d: nick_hits(seg_text, d, skip_brand, allow_fuzzy=False) for d in cands}
        if max(ns.values(), default=0) == 0:               # 정확 매칭이 하나도 없을 때만 퍼지
            ns = {d: nick_hits(seg_text, d, skip_brand, allow_fuzzy=True) for d in cands}
        top = max(ns.values()) if ns else 0
        by_nick = {d for d, v in ns.items() if v == top and v > 0}
        pred, narrowed = cands, False
        if by_tag and by_nick and by_tag & by_nick: pred, narrowed = by_tag & by_nick, True
        elif by_nick and top >= 2: pred, narrowed = by_nick, True
        elif by_tag: pred, narrowed = by_tag, True
        if not narrowed and USE_DEVEMB and len(cands) > 1:
            # 임베딩 fallback: 기기 문서 vs 절, 1위가 2위보다 마진 이상 앞서면 채택
            ids = sorted(cands); scs = DV[[dev_i[d] for d in ids]] @ q_dev
            o = np.argsort(-scs)
            if scs[o[0]] >= EMB_MIN and (len(o) == 1 or scs[o[0]] - scs[o[1]] >= EMB_MARGIN):
                pred, narrowed = {ids[o[0]]}, True
                thits = thits | {"emb:%s(%.2f)" % (DEV[ids[o[0]]]["nickname"], scs[o[0]])}
        if choice is None: choice = (svc, pred, thits)
        if narrowed:
            choice = (svc, pred, thits); break
    svc, pred, thits = choice
    return svc, ranked[:3], sorted(DEV[d]["nickname"] for d in pred), sorted(thits)

CASES = [
    ("삼성 공기청정기 큰거를 토글해줘", "ACT", "Switch.Toggle", ["삼성 공기청정기 큰거"]),
    ("tuya 기기 모두 켜줘", "ACT", "Switch.On", [d["nickname"] for d in DEV.values() if "Tuya" in d["tags"] and "Switch" in d["category"]]),
    ("KT 공기청정기만 꺼줘", "ACT", "Switch.Off", ["KT 공기청정기"]),
    ("삼성 공기청정기 다 꺼줘", "ACT", "Switch.Off", ["삼성 공기청정기 작은거", "삼성 공기청정기 큰거"]),
    ("헤이홈 에어컨 켜줘", "ACT", "Switch.On", ["헤이홈 IR 에이컨"]),
    ("구역 3 재실 인디케이터 켜줘", "ACT", "Switch.On", ["재실 상태 인디케이터 (구역 3)"]),
    ("스카이라이트 다 꺼줘", "ACT", "Switch.Off", ["스카이라이트 CCT", "스카이라이트 YUER"]),
    ("전등 스위치 6구 3번 켜줘", "ACT", "Switch.On", ["스마트빌 전등 스위치 6구 3"]),
    ("매터 플러그 전부 꺼줘", "ACT", "Switch.Off", ["스마트 Wi-Fi 플러그 1", "스마트 Wi-Fi 플러그 2", "스마트 Wi-Fi 플러그 3"]),
    ("좌측 창문 열림 센서가 열리면", "TRIG", "ContactSensor.Contact", ["좌측 창문 열림 센서"]),
    ("스피커로 알려줘", "ACT", "Speaker.Speak", ["JOI 스피커"]),
    ("구역 1에 사람이 감지되면", "TRIG", "PresenceSensor.Presence", ["재실 감지 센서 (구역 1)"]),
    ("구역 1 인디케이터를 켜줘", "ACT", "Switch.On", ["재실 상태 인디케이터 (구역 1)"]),
    ("미로 가습기 켜줘", "ACT", "Switch.On", ["미로 가습기"]),
    ("LG 온도 센서가 28도 넘으면", "TRIG", "TemperatureSensor.Temperature", ["LG 온습도 센서 (온도)"]),
    ("사무실 입구 모션 센서에 움직임이 감지되면", "TRIG", "MotionSensor.Motion", ["사무실 입구 모션 센서"]),
    ("투야 보안 카메라로 사진 찍어줘", "ACT", "Camera.CaptureImage", ["투야 보안 카메라"]),
    ("휴 램프 3 밝기 50으로 해줘", "ACT", "Light.MoveToBrightness", ["Hue lindy lamp 3"]),
    ("필립스 휴 조명 다 꺼줘", "ACT", "Switch.Off", sorted(d["nickname"] for d in DEV.values() if "PhilipsHue" in d["tags"] and "Light" in d["category"])),
    ("공용 조명 켜줘", "ACT", "Switch.On", ["스카이라이트 CCT", "스카이라이트 YUER"]),
    ("투야 푸시 버튼이 눌리면", "TRIG", "Button.Button", ["투야 푸시 버튼 1"]),
    ("스마트 Wi-Fi 플러그 1 켜줘", "ACT", "Switch.On", ["스마트 Wi-Fi 플러그 1"]),
    ("삼성 로봇청소기 청소 시작해줘", "ACT", "RobotVacuumCleaner.SetRobotVacuumCleanerCleaningMode", ["삼성 로봇청소기"]),
    ("CO2 인디케이터를 빨간색으로 바꿔줘", "ACT", "Light.MoveToColor", ["CO2 농도 인디케이터"]),
    ("공기청정기 다 꺼줘", "ACT", "Switch.Off", ["KT 공기청정기", "삼성 공기청정기 작은거", "삼성 공기청정기 큰거"]),
    # ── 오타·구어 (2026-08-18 추가) ──
    ("toya 기기 모두 켜줘", "ACT", "Switch.On", [d["nickname"] for d in DEV.values() if "Tuya" in d["tags"] and "Switch" in d["category"]]),
    ("삼성 공기청정 젤 큰거 토글해줘", "ACT", "Switch.Toggle", ["삼성 공기청정기 큰거"]),
    ("삼송 공기청정기 작은거 꺼줘", "ACT", "Switch.Off", ["삼성 공기청정기 작은거"]),
    ("케이티 공기청정기 꺼줘", "ACT", "Switch.Off", ["KT 공기청정기"]),
    ("헤이홈 에어콘 켜줘", "ACT", "Switch.On", ["헤이홈 IR 에이컨"]),
    ("hejhome 에어컨 꺼줘", "ACT", "Switch.Off", ["헤이홈 IR 에이컨"]),
    ("필립스 램프 3 밝기 30으로", "ACT", "Light.MoveToBrightness", ["Hue lindy lamp 3"]),
    ("구역삼 인디케이터 켜줘", "ACT", "Switch.On", ["재실 상태 인디케이터 (구역 3)"]),
    ("스카이 라이트 다 켜줘", "ACT", "Switch.On", ["스카이라이트 CCT", "스카이라이트 YUER"]),
    ("와이파이 플러그 2 꺼줘", "ACT", "Switch.Off", ["스마트 Wi-Fi 플러그 2"]),
    ("제일 큰 삼성 공기청정기 꺼줘", "ACT", "Switch.Off", ["삼성 공기청정기 큰거"]),
    ("매터플러그 다 켜줘", "ACT", "Switch.On", ["스마트 Wi-Fi 플러그 1", "스마트 Wi-Fi 플러그 2", "스마트 Wi-Fi 플러그 3"]),
    ("LG 습도센서가 70 넘으면", "TRIG", "HumiditySensor.Humidity", ["LG 온습도 센서 (습도)"]),
    ("투야 화재감지기가 감지되면", "TRIG", "SmokeDetector.Smoke", ["투야 화재 감지 센서"]),
    ("사무실 문 열림센서가 열리면", "TRIG", "ContactSensor.Contact", ["사무실 문열림 센서"]),
    ("휴 다이얼 스위치 돌리면", "TRIG", "RotaryControl.Rotation", ["Hue tap dial switch 1"]),
    ("공기 질 센서 CO2가 1000 넘으면", "TRIG", "AirQualitySensor.CarbonDioxide", ["LG 공기질 센서", "공기질 센서"]),
    ("삼성 청소기 돌려줘", "ACT", "RobotVacuumCleaner.SetRobotVacuumCleanerCleaningMode", ["삼성 로봇청소기"]),
    ("스마트빌 스위치 첫번째 켜줘", "ACT", "Switch.On", ["스마트빌 전등 스위치 6구 1"]),
    ("젤 작은 삼성 청정기 켜줘", "ACT", "Switch.On", ["삼성 공기청정기 작은거"]),
]
ok_s = ok_d = 0
for text, typ, esvc, edev in CASES:
    svc, top3, pred, thits = resolve(text, typ)
    s_ok = svc == esvc; d_ok = sorted(pred) == sorted(edev)
    ok_s += s_ok; ok_d += d_ok
    print(f"{'✅' if s_ok and d_ok else '❌'} {text}\n     svc {svc} {'' if s_ok else '(기대 '+esvc+')'} top3={top3}\n     dev {pred} {'' if d_ok else '(기대 '+str(sorted(edev))+')'}  tags={thits}")
print(f"\n서비스 {ok_s}/{len(CASES)}  기기 {ok_d}/{len(CASES)}")
