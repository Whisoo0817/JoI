"""Phase 1 gate: does the compiled effect index reproduce the hand-written
routing knowledge (device_retrieve.md rules + baseline command set)?

Deliberately uses NAIVE substring matching (no embeddings, no morphology) —
this is the floor. The production matcher will be an embedding lookup; if the
floor already passes, the lexicon content is sound.

Two knobs proven necessary during gating (2026-07-20):
  1. connected-device filter (the join): without it hit@1 64% → with it recall@5 100%.
     Unconnected categories (DoorLock, Valve, ArmRobot...) were most of the noise.
  2. STOP verbs: generic verbs (알려줘/켜줘/보여줘...) contribute nothing in
     partial matching — they belong to the notify-channel policy, not to any
     category's lexicon.

Usage: /home/ikess/joi-llm/venv/bin/python gate_check.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)

SVCS = json.load(open(os.path.join(HERE, "effects.json")))["services"]

STOP = {"알려줘", "알려", "말해줘", "해줘", "해서", "보여줘", "보내줘",
        "켜줘", "꺼줘", "시작", "설정", "확인해줘", "줘"}


def norm(s):
    return re.sub(r"[^\w가-힣]", "", s.lower())


def score_cmd(cmd, universe):
    """Rank categories for a command: full-trigger substring > token overlap.

    `universe` = the categories actually connected. Passing it in (rather than
    reading a fixed payload) keeps this module independent of any test harness.
    """
    scores, cn = {}, norm(cmd)
    stop_n = {norm(x) for x in STOP}
    for s in SVCS:
        cat = s["svc"].split(".")[0]
        if cat not in universe:
            continue
        best = 0
        for trig in s.get("ko_triggers", []):
            tn = norm(trig)
            if not tn:
                continue
            if tn in cn:
                best = max(best, len(tn) * 2)
            else:
                toks = [t for t in re.split(r"\s+", trig)
                        if len(norm(t)) >= 2 and norm(t) not in stop_n]
                best = max(best, sum(len(norm(t)) for t in toks if norm(t) in cn))
        if best > 0 and best > scores.get(cat, (0, ""))[0]:
            scores[cat] = (best, s["svc"])
    return sorted(scores.items(), key=lambda kv: -kv[1][0])


# (command, expected categories) — routing rules from device_retrieve.md:42-47
# plus representative baseline commands. Expected = every category the command
# needs (condition sensors AND action devices).
CASES = [
    ("'lindy@mysmax.kr'로 메일 보내줘", {"EmailProvider"}),
    ("문이 열리면 '문이 열렸습니다'라고 010-1234-5678로 문자 보내줘", {"MessageSender", "ContactSensor"}),
    ("챗봇에게 대한민국의 수도가 어디인지 물어봐줘", {"ChatProvider"}),
    ("최신 뉴스 요약해서 스피커로 읽어줘", {"NewsProvider", "Speaker"}),
    ("경제 뉴스 알려줘", {"NewsProvider"}),
    ("AI 뉴스 3개만 토스트로 보여줘", {"NewsProvider", "ToastPublisher"}),
    ("매시간 정각마다 스피커로 시간을 알려줘", {"Clock", "Speaker"}),
    ("사람이 감지되면 토스트 알림으로 재실 감지라고 보여줘", {"PresenceSensor", "ToastPublisher"}),
    ("조명 밝기 20 퍼센트로 설정해줘", {"Light"}),
    ("문이 5분 이상 열려 있으면 문 열렸다고 알려줘", {"ContactSensor"}),
    ("10분 이상 사람이 있으면 환기 알림을 보내줘", {"PresenceSensor"}),
    ("미세먼지 좋음이면 창문 닫으라고 알려줘", {"AirQualitySensor"}),
    ("이산화탄소 농도가 1000ppm 이상이면 스피커로 환기해줘라고 말해줘", {"AirQualitySensor", "Speaker"}),
    ("에어컨을 꺼줘", {"AirConditioner"}),
    ("카메라 녹화 시작해줘", {"Camera"}),
    ("문이 열리면 카메라로 촬영하고 이메일로 보내줘", {"Camera", "EmailProvider", "ContactSensor"}),
    ("창문이 열려 있는데 에어컨이 켜져 있으면 에어컨을 꺼줘", {"ContactSensor", "AirConditioner"}),
    ("모든 재실 센서가 사람 없음이면 조명을 꺼줘", {"PresenceSensor", "Light"}),
    ("불 켜줘", {"Light"}),
    ("온도 몇 도야", {"TemperatureSensor"}),
]

if __name__ == "__main__":
    import run as R  # 게이트 측정용 디바이스 페이로드 (하네스에서만 읽는다)
    CONNECTED = {c for d in R.CONNECTED_DEVICES.values() for c in d["category"]}
    K = 5
    tot = found = full = 0
    for cmd, exp in CASES:
        ranked = score_cmd(cmd, CONNECTED)
        topk = {c for c, _ in ranked[:K]}
        tot += len(exp)
        found += len(exp & topk)
        ok = exp <= topk
        full += ok
        if not ok:
            print(f"❌ {cmd}\n   놓친 것: {sorted(exp - topk)}\n   상위: {ranked[:4]}")
    print(f"recall@{K}: {found}/{tot} ({found/tot:.0%}) | 완전충족: {full}/{len(CASES)}")
