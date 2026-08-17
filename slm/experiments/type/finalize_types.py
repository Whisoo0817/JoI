# -*- coding: utf-8 -*-
"""2단계: gold 절 타입 정답 라벨 확정 (초안 + 눈검토 정정 + 체계 규칙).

타입 8종(주 분류):
  ACT   기능 호출                       "조명을 켜줘", "닫고", "아니면 꺼줘"(mods:else)
  COND  상태 조건(레벨) — 지금/그때 …이면  "온도가 28도 이상이면", "켜져 있으면", "30초 이상 감지되면"(mods:sustain)
  TRIG  사건(엣지) — …가 일어나면          "버튼이 눌리면", "감지되면", "열리면", "이상이 되면", "눌릴 때마다"(mods:every)
  TIME  시간 구동 — 시각/주기/기간 자체가 절 "매일 7시에"(단독), "10분마다 확인해서", "1시부터 3시까지 5분마다", "자정이 되면"
  DELAY 기다리기 — 시간 경과               "3분 뒤에", "10초 후에"
  READ  값 읽기 — 값을 확인해서 넘김        "지금 온도를 확인하고", "다시 체크해서"
  ELSE  아니면 분기(단독)                  "그렇지 않으면"
  STOP  반복 종료 지시(횟수/조건/단독)      "6번 후 멈춰줘", "멈춰.", "그만해."
부수 표지(mods, 복수 가능):
  time    절 안에 시각/요일/주기/기간 표현이 얹힘 ("오후 6시에 …켜줘", "1초마다 …이면", "N분마다 …해줘")
  every   "때마다" — 사건마다 반복
  sustain "N초/분 이상 …이면/유지되면" — 지속 조건
  count   "N번(만)/총 N번/최대 N번"
  else    "아니면 …/그렇지 않고 …/그 외에는 …" 가 절 안에 포함
  repeat  "반복해줘/번갈아/전환/열었다 닫았다" — 토글·반복 행동
  read    값을 읽어 전달·비교 ("온도를 스피커로 알려줘", TIME 절의 "…를 체크해서")
  delay   READ 절에 "N분 뒤 다시" 경과가 얹힘
  mixed   gold 분할이 두 역할을 한 절에 묶은 경우 (예: "등을 100%로, 500lux 이상이면")
"""
import json, os, re, collections
HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "draft.json")))

# ── 눈검토 정정 (명령 i, 절 j) → 타입 ─────────────────────────────
FIX = {
    (109, 0): "TRIG", (114, 0): "TRIG", (330, 0): "TRIG",          # 눌리고/감지되거나 — 사건 연쇄
    (160, 0): "COND", (165, 0): "COND", (173, 0): "COND",          # 비가 오고 (상태 연쇄)
    (166, 0): "COND", (168, 0): "COND",                            # …는데 (상태 연쇄)
    (132, 4): "COND", (183, 1): "COND", (219, 1): "COND", (222, 1): "COND",  # 확인 뒤 상태 판정
    (306, 2): "COND", (331, 2): "COND", (332, 2): "COND", (334, 2): "COND",  # 두 값 차 비교
    (188, 0): "TIME", (201, 0): "TIME", (244, 0): "TIME",          # 새해가/크리스마스가/자정이 되면
    (219, 0): "TIME",                                              # 10시부터 11시까지 30초마다 비를 감지해서
    (257, 1): "ACT", (258, 1): "ACT", (273, 1): "ACT",             # 켰다가/유지하다가 = 행동
    (305, 1): "COND", (327, 1): "COND",                            # "…100% 밝기로, 500lux 이상이면" (mixed)
    (305, 2): "ACT", (327, 2): "ACT",                              # "30%로, 그 외에는 60%로 설정해줘"
    (301, 0): "COND",                                              # 열려있고 오후 10시가 되면 (cron+상태)
    (234, 1): "ACT",                                               # 높여줘. 최대 밝기가 되면 (mixed)
    (234, 2): "STOP", (348, 1): "STOP", (350, 1): "STOP", (353, 1): "STOP",  # 그만해/멈춰/종료/끝
    (96, 2): "ACT",                                                # 끄는 것을 반복해줘 (행동+반복)
    (324, 0): "TRIG", (296, 0): "TRIG",                            # 감지되면/초과하면 — 사건(표면 유지)                                              # 감지되면 (…아니면 꺼줘) 표면 유지
}
for i in range(377, 382):
    FIX[(i, 4)] = "STOP"                                           # N번 후 멈춰줘
MIXED = {(305, 1), (327, 1), (234, 1)}

TIME_RE = re.compile(r"(매일|매주|매달|평일|주말|월요일|화요일|수요일|목요일|금요일|토요일|일요일|오전|오후|아침|저녁|"
                     r"밤 ?\d|밤에|밤 1|자정|정오|\d+시에|\d+시부터|\d+시까지|\d+시 ?\d+분|새해|크리스마스|"
                     r"(초|분|시간)마다|(초|분|시간) ?간격|지금부터|이후에 \d|이후로 \d|뒤로 \d|후부터)")
COUNT_RE = re.compile(r"((\d+|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*번(만|\s*반복|\s*후|\s*알려|\s*찍|\s*눌리|씩|\.|,|$)|총 \d+|최대 \d+\s*번|\d+회)")
ELSE_RE = re.compile(r"(아니면|그렇지 않고|그렇지 않으면|그 외에는|그외에는)")
REPEAT_RE = re.compile(r"(반복(?! 모드)|번갈아|사이에서 전환|열었다 닫았다|올렸다 내렸다|울렸다 꺼|toggle)")
SUSTAIN_RE = re.compile(r"((초|분|시간) 이상 .*(면|되면)|이상 유지되|동안 .*(면)$)")
READ_ACT_RE = re.compile(r"(온도|습도|날씨|농도|전력소모량|전력|메뉴|정보|수치|조도)(를|을) .*(알려|출력|말해|안내)")
READ_TIME_RE = re.compile(r"(체크해서|확인해서|측정해서|감지해서|확인해서,)")

def label(i, j, seg, draft):
    s = seg.strip()
    core = s.rstrip(".,")
    t = FIX.get((i, j), draft)
    # 체계 규칙: 사건 때마다 → TRIG(every)
    if re.search(r"때마다,?$", core) or re.search(r"될때마다|눌릴때마다|잠길때마다|올때마다", core):
        if not re.search(r"^(정오|자정)", core):
            t = "TRIG"
    if t == "REPEAT":
        t = "ACT"
    if t == "BREAK":
        t = "STOP"
    if t == "ELSE" and len(core.split()) > 2:
        t = "ACT"
    mods = []
    if t not in ("DELAY",) and TIME_RE.search(core):
        mods.append("time")
    if re.search(r"때마다", core):
        mods.append("every")
    if SUSTAIN_RE.search(core) and t == "COND" or (t == "TRIG" and SUSTAIN_RE.search(core)):
        t = "COND"; mods.append("sustain")
    if COUNT_RE.search(core) and t in ("ACT", "STOP", "TRIG"):
        mods.append("count")
    if ELSE_RE.search(core) and t != "ELSE":
        mods.append("else")
    if REPEAT_RE.search(core) and t == "ACT":
        mods.append("repeat")
    if (t == "ACT" and READ_ACT_RE.search(core)) or (t == "TIME" and READ_TIME_RE.search(core)) or t == "READ":
        mods.append("read")
    if t == "READ" and re.search(r"(뒤|후) ", core):
        mods.append("delay")
    if (i, j) in MIXED:
        mods.append("mixed")
    return t, sorted(set(mods))

out = []
for o in D:
    segs = []
    for j, (seg, dr) in enumerate(zip(o["gold_segs"], o["draft_types"])):
        t, mods = label(o["i"], j, seg, dr)
        segs.append({"j": j, "text": seg, "type": t, "mods": mods})
    out.append({"i": o["i"], "index": o["index"], "cat": o["cat"], "cmd": o["cmd"],
                "words": o["words"], "gold_labels": o["gold_labels"], "pred_labels": o["pred_labels"],
                "pred_segs": o["pred_segs"], "seg_match": o["match"],
                "segments": segs, "ir_gt": o["ir_gt"]})
json.dump(out, open(os.path.join(HERE, "type_labels.json"), "w"), ensure_ascii=False, indent=1)

tc = collections.Counter(s["type"] for o in out for s in o["segments"])
mc = collections.Counter(m for o in out for s in o["segments"] for m in s["mods"])
print("타입:", dict(tc.most_common()))
print("mods:", dict(mc.most_common()))
lines = []
for o in out:
    lines.append("#%d %s" % (o["i"], o["cat"]))
    for s in o["segments"]:
        lines.append("   %-5s %-22s %s" % (s["type"], ",".join(s["mods"]), s["text"]))
open(os.path.join(HERE, "review_final.txt"), "w").write("\n".join(lines))
print("저장: type_labels.json / review_final.txt")
