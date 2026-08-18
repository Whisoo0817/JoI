# -*- coding: utf-8 -*-
"""슬롯 값 규칙 — 절 텍스트에서 시간·수량·조건식·인자 값을 원문 복사+정규화로 뽑는다 (모델 없음).
  duration(text)  "10분 뒤에/1시간 반/30초간"        → "10 MIN" / "90 MIN" / "30 SEC"
  period(text)    "5분마다/1시간 간격으로"            → "5 MIN"
  count(text)     "총 3번/최대 5번/4번만"             → 3
  cron(text)      "매일 오후 3시/평일 8시/월요일과 수요일 6시/정오/자정/새해" → "0 15 * * *" …
  until(text)     "오후 3시까지/밤 11시까지"          → "clock.time >= 1500"
  comparator(text) 이상/이하/미만/초과/넘으면/떨어지면/보다 크면 … → (">=", N) …
  bool_state(text) 감지되면/없으면/열리면/눌리면/잠기면/켜져 있으면 … → 값 (BOOL·ENUM 멤버)
  enum_arg(text, members)  냉방→cool, 응급→emergency …  (사전 + 부분 문자열)
"""
import re

KNUM = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10, "스무": 20, "서른": 30, "삼십": 30, "십": 10, "이십": 20, "사십": 40, "오십": 50, "육십": 60}
UNIT = {"초": "SEC", "분": "MIN", "시간": "HOUR", "일": "DAY", "밀리초": "MSEC"}
_num = r"(\d+(?:\.\d+)?|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|스무|서른|삼십|십|이십|사십|오십|육십)"
def _n(s):
    return float(s) if re.match(r"^\d", s) else float(KNUM[s])
def _fmt(n, unit):
    n = int(n) if float(n).is_integer() else n
    return f"{n} {unit}"

def duration(text):
    """'N시간 M분' / 'N시간 반' / 'N분' → 단일 단위 문자열(gold 관례: 정수+단위)."""
    t = text
    m = re.search(_num + r"\s*(초|분|시간)간(?![가-힣])", t)          # "5초간" 지속이 주기("1분마다")보다 우선
    if m: return _fmt(_n(m.group(1)), UNIT[m.group(2)])
    m = re.search(_num + r"\s*시간\s*반", t)
    if m: return _fmt(_n(m.group(1)) * 60 + 30, "MIN")
    m = re.search(_num + r"\s*시간\s*" + _num + r"\s*분", t)
    if m: return _fmt(_n(m.group(1)) * 60 + _n(m.group(2)), "MIN")
    m = re.search(_num + r"\s*(밀리초|초|분|시간|일)(?![가-힣]*(이상|미만|이하))", t)
    if m: return _fmt(_n(m.group(1)), UNIT[m.group(2)])
    m = re.search(r"반\s*시간", t)
    if m: return "30 MIN"
    return None

def period(text):
    m = re.search(_num + r"\s*(밀리초|초|분|시간|일)\s*(마다|간격|주기)", text)
    if m: return _fmt(_n(m.group(1)), UNIT[m.group(2)])
    m = re.search(_num + r"\s*시간\s*반\s*마다", text)
    if m: return _fmt(_n(m.group(1)) * 60 + 30, "MIN")
    return None

def count(text):
    m = re.search(r"(총|최대|딱)?\s*" + _num + r"\s*(번|회|차례)(?!도)", text)     # "한번도"는 횟수 아님
    if m and not re.search(_num + r"\s*번\s*(으로|채널)", text):
        return int(_n(m.group(2)))
    return None

DOW = {"월요일": 1, "화요일": 2, "수요일": 3, "목요일": 4, "금요일": 5, "토요일": 6, "일요일": 7}
def _dow(text):
    if "평일" in text: return "1-5"
    if "주말" in text: return "6,7"
    ds = sorted({v for k, v in DOW.items() if k in text})
    if ds: return ",".join(str(d) for d in ds)
    return "*"
def _hour(text):
    """'오후 3시', '밤 10시', '아침 7시', '새벽 2시', '정오', '자정', '12시 30분' → (H, M)"""
    if "정오" in text: return 12, 0
    if "자정" in text or "밤 12시" in text: return 0, 0
    m = re.search(r"(오전|오후|아침|저녁|밤|새벽|낮)?\s*(\d{1,2})\s*시(?!간)\s*(?:(\d{1,2})\s*분|반)?", text)
    if not m: return None
    h = int(m.group(2)); mi = int(m.group(3)) if m.group(3) else (30 if "반" in m.group(0) else 0)
    amb = m.group(1)
    if amb in ("오후", "저녁", "밤", "낮") and h < 12: h += 12
    if amb == "밤" and h == 12: h = 0
    return h, mi
def cron(text):
    if "부터" in text: text = text.split("부터")[0] + "부터"      # 시작 시각만 ("밤10시부터 자정까지")
    if "새해" in text or "1월 1일" in text: return "0 0 1 1 *"
    day = any(k in text for k in ("매일", "평일", "주말")) or any(k in text for k in DOW)
    pm = re.search(_num + r"\s*시간\s*(마다|간격)", text)                     # 날짜/요일 범위 + N시간마다 = cron 시(step) ("주말에 2시간마다"→"0 */2 * * 6,7")
    if "크리스마스" in text:
        return f"0 {'*' if pm and _n(pm.group(1)) == 1 else ('*/' + str(int(_n(pm.group(1)))) if pm else '0')} 25 12 *"
    hm = _hour(text)
    if hm is None:
        if day and pm: return f"0 {'*' if _n(pm.group(1)) == 1 else '*/' + str(int(_n(pm.group(1))))} * * {_dow(text)}"
        if day and re.search(r"오후에|오후 ", text): return f"0 12 * * {_dow(text)}"       # "주말 오후에" = 정오 시작
        if day and re.search(r"오전에|아침에", text): return f"0 6 * * {_dow(text)}"
        # 시각 없이 요일/매일만: 자정 기준
        if day: return f"0 0 * * {_dow(text)}"
        return None
    h, mi = hm
    return f"{mi} {h} * * {_dow(text)}"

def until(text):
    """'…부터 N시까지' — 마지막 '시까지' 앞의 시각."""
    m = re.search(r"(오전|오후|아침|저녁|밤|새벽|낮)?\s*(\d{1,2})\s*시\s*(?:(\d{1,2})\s*분)?\s*까지", text)
    if "자정까지" in text: return "clock.time >= 2400"
    if not m:
        if re.search(r"오후에|오후 (?!\d)", text): return "clock.time >= 1800"    # "주말 오후에 30분마다" = 오후 창(12~18시)
        if re.search(r"오전에|아침에", text): return "clock.time >= 1200"
        return None
    h = int(m.group(2)); mi = int(m.group(3)) if m.group(3) else 0; amb = m.group(1)
    if amb is None:                                  # 앞쪽 시각의 오전/오후를 상속 ("오후 1시부터 3시까지")
        pm = re.search(r"(오전|오후|아침|저녁|밤|새벽)", text[: m.start()])
        amb = pm.group(1) if pm else None
        if amb in ("오후", "저녁", "밤") and h < 12: h += 12
        elif amb is None and h < 8: h += 12
    elif amb in ("오후", "저녁", "밤", "낮") and h < 12: h += 12
    return f"clock.time >= {h:02d}{mi:02d}"

def number(text):
    """비교값: 단위/비교어 앞의 숫자 우선("구역1의 온도가 36.5도 이상" → 36.5), 없으면 마지막 숫자."""
    ms = list(re.finditer(r"(-?\d+(?:\.\d+)?)\s*(도|℃|%|퍼센트|W|와트|lux|럭스|dB|데시벨|ppm|V|볼트|kWh|개|명|미터|m)?", text))
    if not ms: return None
    for m in ms:
        tail = text[m.end():m.end() + 6]
        if m.group(2) or re.match(r"\s*(이상|이하|미만|초과|보다|을|를|가|이|로|으로|넘|아래|위)", tail): return float(m.group(1))
    return float(ms[-1].group(1))

CMP = [  # (정규식, 연산자)  — 값 뒤에 붙는 표현
    (r"이상", ">="), (r"이하", "<="), (r"미만|아래로|밑이면|보다 (낮|작|떨어)", "<"), (r"초과|넘|보다 (높|커|크|많)|위로|올랐", ">"),
    (r"떨어졌|떨어지|내려가|낮아|밑으로", "<"), (r"올라가|높아", ">"),
]
def comparator(text):
    """숫자 비교 조건 → (op, value). 값은 문장의 첫 숫자(단위 제거)."""
    t = re.sub(r"\d+\s*(분|초|시간)\s*(이상|동안|간|넘게)", "", text)     # "10분 이상 감지되지 않으면"의 10은 for
    v = number(t)
    if v is None: return None
    for pat, op in CMP:
        if re.search(pat, t): return op, v
    if re.search(r"(이|가) 되면|되면", t): return ">=", v         # "35도가 되면" 관례
    return "==", v

NEG = r"(않으면|없으면|안 ?오면|안 ?하면|아니면|없을 때|않을 때|없고|않고|되지 않)"
def bool_state(text, vtype, members):
    """상태/사건 조건 → 값. BOOL: true/false. ENUM: 사전 → 멤버."""
    neg = re.search(NEG, text) is not None
    if vtype == "BOOL": return "false" if neg else "true"
    if vtype == "ENUM":
        lex = {"open": ["열리", "열려", "열림", "개방"], "closed": ["닫히", "닫혀", "닫힘"], "locked": ["잠기", "잠겨", "잠김", "잠금"], "unlocked": ["풀리", "해제", "열리", "열려"],
               "pushed": ["눌", "누르", "누름"], "on": ["켜지", "켜져", "켜짐", "켜면"], "off": ["꺼지", "꺼져", "꺼짐"], "rain": ["비가 오", "비 오", "비가 내"],
               "fullyCharged": ["완료", "충전이 끝", "다 되", "완충"], "playing": ["재생 중", "재생중", "틀어져"], "paused": ["일시정지"], "stopped": ["멈춰", "멈춘", "정지"], "sleep": ["수면", "취침"], "keepWarm": ["보온"], "lownoise": ["저소음"], "quick": ["퀵", "빠른"], "grill": ["그릴"], "cooking": ["조리", "취사"], "charging": ["충전 중", "충전중"], "normal": ["노말", "일반"], "maximum": ["맥시멈", "최대"], "cool": ["냉방", "쿨"], "heat": ["난방", "히트"], "auto": ["자동", "오토"],
               "idle": ["멈춰", "정지", "유휴"], "cleaning": ["청소 중"], "docked": ["도킹", "충전기에"], "running": ["작동 중", "돌아가", "동작 중"], "stopped": ["멈춰", "정지"],
               "sunny": ["맑"], "cloudy": ["흐리"], "snow": ["눈이 오", "눈 오"], "clear": ["맑"], "monday": ["월요일"], "weekend": ["주말"]}
        best = None
        for m_ in members:
            key = m_.split(" - ")[0].strip()
            for w in lex.get(key, []) + [key.lower()]:
                if w and w in text.lower():
                    if best is None or len(w) > best[1]: best = (key, len(w))
        if best: return f'"{best[0]}"'
        return None
    return None

ENUM_KO = {"dehumidifying": ["제습"], "drying": ["건조"], "AIDrying": ["AI건조", "AI 건조", "에이아이 건조"], "freezeProtection": ["동결 방지", "동결방지", "결빙 방지"], "refreshing": ["리프레쉬", "리프레시", "환기"], "stop": ["멈춰", "멈추", "정지", "중지"], "start": ["시작"], "pause": ["일시정지"],
           "cool": ["냉방", "쿨", "시원"], "heat": ["난방", "히터", "따뜻"], "auto": ["자동", "오토", "AI"], "dry": ["제습", "건조", "드라이"], "fan": ["송풍", "팬"], "sleep": ["수면", "취침"],
           "emergency": ["응급", "긴급", "비상"], "fire": ["화재", "불"], "police": ["경찰"], "ambulance": ["구급", "앰뷸런스"], "high": ["강풍", "강하게", "세게", "강"], "low": ["약풍", "약하게", "약"], "medium": ["중간", "보통"],
           "quiet": ["조용", "저소음"], "turbo": ["터보"], "normal": ["노말", "일반", "보통", "표준"], "maximum": ["맥시멈", "최대"], "minimum": ["미니멈", "최소"], "eco": ["에코", "절전"], "wash": ["세척", "세탁"],
           "cooking": ["조리", "취사"], "warm": ["보온"], "bake": ["굽", "베이크"], "grill": ["그릴"], "roast": ["로스트"], "spot": ["스팟", "집중"], "repeat": ["반복"], "edge": ["엣지", "가장자리"], "map": ["맵"], "silent": ["무음"],
           "manual": ["수동"], "night": ["야간", "밤"], "day": ["주간"], "off": ["끄", "꺼", "off"], "on": ["켜", "on"], "cold": ["찬", "냉"], "hot": ["뜨거", "온"], "black": ["검"], "white": ["흰", "하양"], "red": ["빨"], "purple": ["보라"], "blue": ["파"], "green": ["초록", "녹"], "yellow": ["노랑", "노란"], "pink": ["분홍"], "orange": ["주황"]}
def enum_arg(text, members):
    best = None
    for m_ in members:
        key = m_.split(" - ")[0].strip()
        for w in ENUM_KO.get(key, []) + [key.lower()]:
            if w and w.lower() in text.lower() and (best is None or len(w) > best[1]): best = (key, len(w))
    return best[0] if best else None

def quoted(text):
    m = re.search(r"[\"'“‘]([^\"'”’]+)[\"'”’]", text)
    if m: return m.group(1)
    m = re.search(r"(.+?)(?:라고|다고|이라고)\s", text)
    return m.group(1).strip() if m else None
