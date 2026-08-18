# -*- coding: utf-8 -*-
"""상자(스택) 규칙 조립기 — gold 타입·mods 열 (+ gold 슬롯 플래그) → 뼈대. README §15 검증.

입력 절: (type, mods). 슬롯 플래그(cron 유무, cycle의 p/u/c 조합)는 gold IR에서 가져와 순서대로 소비
(슬롯 추출은 별도 단계 — 여기선 '슬롯이 맞게 추출됐다면 구조가 맞게 조립되는가'만 검증).

규칙(스트리밍, 1절 lookahead 허용 지점 표시 ★):
  TIME/ACT/COND/TRIG의 time 표지 → cron이면 SA:cron, period 있으면 가장 안쪽 상자에 CYC 열기
  TRIG                 → 다음 절이 COND/TRIG(접속 -고)면 조건 병합해 IF 열기; 아니면 WAIT:none 잎
                          ★ 그 TRIG의 행동들 뒤에 else가 오면 IF (wait엔 else가 없음)
  TRIG/every           → CYC 열고 그 안에 WAIT:rising 잎
  COND                 → IF 열기 (연속 COND/TRIG는 하나의 IF로 병합)
                          직전 상자가 내용 있는 IF이고 사이에 DELAY 없음 → 그 IF의 else 안에 IF (else-if)
  COND/sustain         → WAIT:none:for 잎
  COND/else            → 직전 IF의 else 안에 IF ;  ELSE / ACT/else → 직전 IF의 else 칸으로 전환
  ACT                  → CALL 잎(가장 안쪽 상자)  ACT/read → READ CALL  ACT/repeat → CALL 잎(내부 실현은 매핑 몫)
  READ(/read)          → ★ 다음 절이 COND면 조건의 값 읽기라 생략, 아니면 READ 잎
  DELAY                → ★ 다음 절이 COND/TRIG(새 상자)면 현재 IF를 닫고 부모에 DELAY, 아니면 안쪽에 DELAY
  STOP                 → count 표지면 cycle 플래그(이미 gold 플래그) / cond 있는 STOP → IF[BREAK]
"""
import json, os, sys, collections, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skeleton import skeleton

class Leaf(str):
    """잎(CALL/READ/DELAY/WAIT…) — 소유 절 추적을 위해 개별 객체""" 
_CUR = [None]                      # 조립 중인 절 번호 (후보 생성·렌더링용 소유 정보)
class Box:
    def __init__(self, kind, flags=""):
        self.kind = kind          # ROOT / IF / ELSE / CYC
        self.flags = flags
        self.items = []           # 문자열 잎 또는 Box
        self.else_items = None    # IF일 때 else 목록(활성화 시 list)
        self.in_else = False
        self.seg = _CUR[0]        # 이 상자를 연 절
        self.owner = {}           # id(item) → 절 번호
    def add(self, x):
        if isinstance(x, str) and not isinstance(x, Leaf): x = Leaf(x)
        (self.else_items if self.in_else else self.items).append(x)
        self.owner[id(x)] = _CUR[0]
    def render(self):
        inner = " ".join(x.render() if isinstance(x, Box) else x for x in self.items)
        if self.kind == "ROOT": return inner
        if self.kind == "IF":
            e = "{" + " ".join(x.render() if isinstance(x, Box) else x for x in self.else_items) + "}" if self.else_items else ""
            return "IF[" + inner + "]" + e
        if self.kind == "CYC": return "CYC:" + self.flags + "[" + inner + "]"
        return inner

def gold_flags(ir):
    """gold IR에서 cron 유무 + cycle 플래그 열(선순위)."""
    cron = bool(ir["timeline"][0].get("cron")) if ir["timeline"] and ir["timeline"][0]["op"] == "start_at" else False
    cyc = []
    def walk(nodes):
        for n in nodes:
            if n["op"] == "cycle":
                cyc.append(("p" if n.get("period") else "") + ("u" if n.get("until") else "") + ("c" if n.get("count") else ""))
                walk(n.get("body") or [])
            elif n["op"] == "if":
                walk(n.get("then") or []); walk(n.get("else") or [])
    walk(ir["timeline"]); return cron, cyc

CONJ_RE = re.compile(r"(고|거나|이거나|며|이며|는데|은데|면서|또는|이나|그리고),?\.?$")          # 접속어미(조건 병합)
PERIOD_RE = re.compile(r"(?:\d+|한|두|세|네|다섯|여섯|열|삼십|십|이십)\s*(초|분|시간)\s*(마다|간격|주기)")   # 시각+마다(정오마다)는 cron, 기간+마다는 period               # 반복 주기 → CYC
UNTIL_RE = re.compile(r"(\d+\s*시|정오|자정|밤|아침|저녁|오후|오전|새벽)\S*(까지|사이에)")   # 시각까지 = 시간창 → CYC(until) ("최대 100까지"는 값 상한)
TOGGLE_RE = re.compile(r"(였다 .*?[았었]다|번갈아|사이에서 전환|켜고 끄는|켰다 껐다|올렸다 내렸다|열었다 닫았다|열었다 잠갔다|잠갔다 열었다|내렸다 올렸다|닫았다 열었다|열고 닫기|올리고 내리기|켜고 끄기|열었다가 닫)")
FILLER_ONLY_RE = re.compile(r"^(그리고|그리|그렇지 않고|그렇지 않으면|아니면|아니면서|그게 아니고|그 외에는|그리고 나서|또는|그때부터|그 이후로|그 뒤로|이후|그 후|그런 다음)[,.]?$")
ELSE_SPLIT = re.compile(r".+[,\s](그 외에는|그 외에|아니면|그렇지 않으면) ")   # 한 절 안의 else 분기
MODE_TEMP_RE = re.compile(r"모드로 \d+\s*도로|\d+\s*도로 \S*모드로")
DELAY_LEAD_RE = re.compile(r"^(그리고 |그 뒤에? |이후 |그 이후로 )?(?:\d+|한|두|세|네|다섯|열|삼십)\s*(초|분|시간)\s*(뒤|후|이후|지나면|지나서|있다가)(에|에는|로|엔|서)?\s")   # ACT 안에 앞선 지연("5분 뒤 조명을 꺼줘")
MODE_ON_RE = re.compile(r"모드로 (켜|켜서|켠)")                     # A4: "냉방 모드로 켜고" = Switch.On + SetMode 두 호출
PULSE_RE = re.compile(r"(\d+\s*(초|분|시간)(간|씩) |유지하다가)")   # "5초간 울려줘/울렸다 꺼줘" = 켜기·지연·끄기
SLOT_DRIVEN = os.environ.get("SLOT", "1") == "1"   # 기본: 어휘 표지로 CYC 열기(mods 의존 안 함)
STOPCOND_RE = re.compile(r"(되면|이면|하면) ?(그만|멈춰|중단)")

def assemble(segs, cron, cyc_flags):
    cyc_flags = list(cyc_flags)
    texts = [x[2] if len(x) > 2 else "" for x in segs]
    segs = [(x[0], x[1]) for x in segs]
    _CUR[0] = None; root = Box("ROOT"); stack = [root]
    out_prefix = "SA:cron" if cron else "SA"
    n = len(segs)
    def cur(): return stack[-1]
    def open_box(b):
        cur().add(b); stack.append(b)
    def innermost_if():
        for b in reversed(stack):
            if b.kind == "IF": return b
        return None
    def open_cyc():
        fl = cyc_flags.pop(0) if cyc_flags else "p"
        open_box(Box("CYC", fl))
    def has_else_later(i):
        # i(조건 절) 뒤로 ACT들 다음에 else 표지 절이 오는가 (사이에 새 조건 없이)
        for j in range(i + 1, n):
            t, m = segs[j]
            if t in ("ELSE",) or "else" in m: return True
            if t in ("COND", "TRIG", "TIME", "STOP", "DELAY", "READ"): return False
        return False
    i = 0
    pending_cond = None   # 병합 중인 조건 상자 종류: "IF" 열림 대기
    pend_else = False
    while i < n:
        _CUR[0] = i
        t, m = segs[i]
        nxt = segs[i + 1] if i + 1 < n else (None, [])
        if SLOT_DRIVEN and t in ("COND", "TRIG", "TIME") and FILLER_ONLY_RE.match(texts[i].strip()):
            # 접속·지시 부분만 있는 절("아니면서", "그때부터"): 조건이 아님. else 표지면 다음 조건 절에 else를 넘기고, 다음이 행동이면 ELSE로
            if re.match(r"^(아니면서|그게 아니고|그렇지 않고|아니면|그렇지 않으면)", texts[i].strip()):
                if nxt[0] in ("COND", "TRIG"): pend_else = True; i += 1; continue
                t = "ELSE"
            else:
                i += 1; continue
        if pend_else and t in ("COND", "TRIG"):
            m = list(m) + ["else"]; pend_else = False
        # 시간 표지: period가 있으면(=gold cycle 플래그가 남아 있고 그 다음 cycle이 every용이 아님) CYC 열기
        opened_cyc = False
        # 주기/시간창 표지는 어휘적(슬롯 추출이 어차피 잡음) → SLOT_DRIVEN이면 mods 없이도 CYC 열기
        if t != "STOP" and ("time" in m or SLOT_DRIVEN) and (PERIOD_RE.search(texts[i]) or UNTIL_RE.search(texts[i])):
            open_cyc(); opened_cyc = True
        if t == "TIME":
            i += 1; continue
        if t == "TRIG" and "every" in m:
            open_cyc(); cur().add("WAIT:rising"); i += 1; continue
        if t in ("TRIG", "COND") and "sustain" in m:
            cur().add("WAIT:none:for"); i += 1; continue
        if t in ("TRIG", "COND"):
            merged_next = bool(CONJ_RE.search(texts[i]))   # 현재 절 어미만으로 결정(lookahead 없음)
            if "else" in m or "mixed" in m:       # COND/else = else-if; COND/mixed("등을 100%로, 500lux 이상이면") = 앞 조건의 행동 + else-if
                if "mixed" in m: cur().add("CALL")
                b = innermost_if()
                if b is not None:
                    while stack[-1] is not b: stack.pop()
                    b.in_else = True; b.else_items = b.else_items or []
                nb = Box("IF"); open_box(nb)
                i += 1; continue
            if pending_cond is None:
                # 조건 상자 열기: 직전 상자가 내용 있는 IF(닫히지 않음)이면 else-if
                # 시각(cron)이나 시간창(cycle) 아래의 TRIG는 '그 시점에 점검' = IF, 아니면 WAIT
                if t == "TRIG" and not merged_next and not has_else_later(i) and not opened_cyc and "time" not in m:
                    cur().add("WAIT:none"); i += 1; continue
                b = innermost_if()
                if b is not None and b is stack[-1] and b.items and not b.in_else:
                    b.in_else = True; b.else_items = []
                nb = Box("IF"); open_box(nb)
                pending_cond = nb
            if not merged_next:
                pending_cond = None
            i += 1; continue
        if t == "ELSE" or (t == "ACT" and "else" in m):
            if t == "ACT" and ELSE_SPLIT.search(texts[i]): cur().add("CALL")     # "30%로, 그 외에는 60%로" = 앞 조건의 행동 + else 행동
            b = innermost_if()
            if b is not None:
                while stack[-1] is not b: stack.pop()
                b.in_else = True; b.else_items = b.else_items or []
            if t == "ELSE": i += 1; continue
        if t == "ACT":
            if "read" in m: cur().add("READ")
            if SLOT_DRIVEN and DELAY_LEAD_RE.search(texts[i]) and not PERIOD_RE.search(texts[i]): cur().add("DELAY")   # 절 안 지연 → DELAY + CALL
            if "mixed" in m and nxt[0] == "STOP":       # ACT/mixed("10씩 높여줘. 최대 밝기가 되면") + STOP = CALL + IF[BREAK]
                cur().add("CALL"); b = Box("IF"); b.add("BREAK"); cur().add(b); i += 2; continue
            if MODE_TEMP_RE.search(texts[i]):           # "냉방 모드로 18도로 설정" = SetMode + SetTargetTemperature
                cur().add("CALL"); cur().add("CALL"); i += 1; continue
            if TOGGLE_RE.search(texts[i]):
                b = Box("IF"); b.add("CALL"); b.in_else = True; b.else_items = []; b.add("CALL"); b.in_else = False; cur().add(b)
            elif "유지하다가" in texts[i]:               # "…로 10초 유지하다가" = 켜기·지연 (끄기는 다음 절)
                cur().add("CALL"); cur().add("DELAY")
            elif PULSE_RE.search(texts[i]):
                cur().add("CALL"); cur().add("DELAY"); cur().add("CALL")
            elif MODE_ON_RE.search(texts[i]):
                cur().add("CALL"); cur().add("CALL")
            else:
                cur().add("CALL")
            i += 1; continue
        if t == "READ":
            if "delay" in m: cur().add("DELAY")
            elif nxt[0] != "COND": cur().add("READ")
            i += 1; continue
        if t == "DELAY":
            if nxt[0] in ("COND", "TRIG"):
                # 새 상자가 이어짐 → 현재 IF를 닫고 부모에 DELAY
                if stack[-1].kind == "IF": stack.pop()
            cur().add("DELAY"); i += 1; continue
        if t == "STOP":
            if "count" not in m and STOPCOND_RE.search(texts[i]):
                b = Box("IF"); b.add("BREAK"); cur().add(b)
            i += 1; continue
        i += 1
    root.prefix = out_prefix
    return out_prefix + (" " + root.render() if root.render() else "")

def assemble_tree(segs, cron, cyc_flags):
    """뼈대 문자열 대신 Box 트리(절 소유 정보 포함) 반환."""
    holder = {}
    _orig = Box.__init__
    def _init(self, kind, flags=""):
        _orig(self, kind, flags)
        if kind == "ROOT": holder["root"] = self
    Box.__init__ = _init
    try:
        assemble(segs, cron, cyc_flags)
    finally:
        Box.__init__ = _orig
    return holder["root"]

def lenient(sk):
    """관대 동치: (1) CALL/READ 잎 연속 → A  (2) 최상위 WAIT:none X ≡ IF[X] (gold 혼용)  """
    s = re.sub(r"\b(CALL|READ)(\s+(CALL|READ))*\b", "A", sk)
    s = re.sub(r"\bA(\s+A)+\b", "A", s)
    m = re.match(r"^(SA(?::cron)?) WAIT:none (.+)$", s)
    if m and "IF[" not in m.group(2) and "CYC" not in m.group(2):
        s = f"{m.group(1)} IF[{m.group(2)}]"
    return s

if __name__ == "__main__":
    HERE = os.path.dirname(os.path.abspath(__file__))
    T = json.load(open(os.path.join(HERE, "..", "type", "type_labels.json")))
    tot = ok = okl = 0; fails = []
    for o in T:
        if not o["ir_gt"]: continue
        segs = [(s["type"], s["mods"], s["text"]) for s in o["segments"]]
        cron, cyc = gold_flags(o["ir_gt"])
        pred = assemble(segs, cron, cyc); gold = skeleton(o["ir_gt"])
        tot += 1
        if pred == gold: ok += 1; okl += 1
        elif lenient(pred) == lenient(gold): okl += 1
        else: fails.append((o["i"], " ".join(t + ("/" + ",".join(m) if m else "") for t, m, _ in segs), gold, pred, o["cmd"]))
    print(f"명령 {tot}: 뼈대 완전일치 {ok} ({ok/tot:.3f}) | 관대 일치 {okl} ({okl/tot:.3f})")
    for f in fails:
        print(f"\n#{f[0]} {f[1]}\n  gold {f[2]}\n  pred {f[3]}\n  {f[4]}")
