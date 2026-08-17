# -*- coding: utf-8 -*-
"""2단계 준비: gold 절마다 어미 규칙으로 타입 초안을 붙인다 (사람 검토용 초안일 뿐).

타입(주 분류 1개):
  ACT   기능 호출 (call)                     "조명을 켜줘", "닫고"
  COND  상태 조건 — 지금 상태가 …이면 (레벨)   "온도가 28도 이상이면", "켜져 있으면"
  TRIG  사건 — …가 일어나면 (엣지)            "버튼이 눌리면", "감지되면", "열리면", "눌릴 때마다"
  TIME  시간 구동 — 시각/주기/기간             "매일 아침 7시에", "10분마다 확인해서", "1시부터 3시까지 5분마다"
  DELAY 기다리기 — 시간 경과                  "3분 뒤에", "10초 후"
  READ  값 읽기 — 값을 확인해서/읽어서 넘김    "현재 온도를 확인해서"
  ELSE  아니면 분기                           "아니면", "그렇지 않으면"
  REPEAT 반복 지시 — 횟수/조건 반복           "3번만.", "닫힐 때까지 반복해줘"
  BREAK 반복 종료                             "멈춰줘"(반복 안에서)
출력: draft.json (segments.json + 절별 draft 타입) 과 review.txt (눈검토용)
"""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
S = json.load(open(os.path.join(HERE, "segments.json")))

def draft(seg):
    s = seg.strip().rstrip(".,")
    w = s.split()
    last = w[-1]
    if re.search(r"(아니면|그렇지 않으면|않다면|아니라면)$", s) and len(w) <= 3:
        return "ELSE"
    if re.search(r"(그만|멈춰|중단)", last) and re.search(r"반복|까지", s):
        return "BREAK"
    if re.search(r"(반복해|반복하고|번만|번 반복|회 반복|번씩|반복해줘)", s) and not re.search(r"(면|고|서)$", last):
        return "REPEAT"
    if re.search(r"(때마다|마다)$", last):
        if re.search(r"(눌릴|감지될|열릴|닫힐|될|올|울릴|바뀔|켜질|꺼질) 때마다$", s):
            return "TRIG"
        return "TIME"
    if re.search(r"마다$", last) or re.search(r"(마다 확인해서|마다 체크해서|마다 확인하고|마다 체크하고)$", s):
        return "TIME"
    if re.search(r"(뒤에|후에|지나면|지난 후|지나고|후|있다가|다가|동안 기다렸다가|기다렸다가|기다린 후)$", last) or re.search(r"(초|분|시간) (뒤에|후에|후|있다가|지나면|지나고)$", s):
        return "DELAY"
    if re.search(r"(확인해서|체크해서|확인하고|체크하고|읽어서|측정해서|확인한 뒤|확인 후|알아내서|조회해서)$", s):
        if re.search(r"(마다|시에|시간마다|분마다)", s):
            return "TIME"
        return "READ"
    if re.search(r"(면|거나|면,|든|든지)$", last.rstrip(",")):
        if re.search(r"(감지되면|눌리면|눌러지면|열리면|닫히면|잠기면|풀리면|커지면|작아지면|낮아지면|높아지면|넘으면|떨어지면|올라가면|내려가면|바뀌면|변하면|시작되면|끝나면|끝나면|도착하면|나가면|들어오면|울리면|켜지면|꺼지면|되면|오면|받으면|발생하면|생기면|잠기면|열면|닫으면|누르면|어두워지면|밝아지면|졌으면|왔으면|눌렸으면)$", last.rstrip(",")):
            return "TRIG"
        return "COND"
    if re.search(r"(시에|시부터|시까지|아침에|저녁에|밤에|주말에|평일에|요일에|정각에|자정에|시 정각에)$", last) and len(w) <= 4:
        return "TIME"
    return "ACT"

out = []
lines = []
for o in S:
    types = [draft(s) for s in o["gold_segs"]]
    o2 = dict(o); o2["draft_types"] = types
    out.append(o2)
    lines.append("#%d %s" % (o["i"], o["cat"]))
    for s, t in zip(o["gold_segs"], types):
        lines.append("   %-6s %s" % (t, s))
json.dump(out, open(os.path.join(HERE, "draft.json"), "w"), ensure_ascii=False, indent=1)
open(os.path.join(HERE, "review.txt"), "w").write("\n".join(lines))
import collections
print(collections.Counter(t for o in out for t in o["draft_types"]))
