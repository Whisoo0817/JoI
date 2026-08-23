#!/usr/bin/env python3
"""corpus.csv 를 시나리오 단위로 묶어 5,000개 배분표를 만든다 — 2단계.

두 덩어리로 나눈다.
  trigger  무엇이 생기면 무엇을 한다   (ifttt · ha)  — 점수는 설치수 · 조회수
  now      지금 이것을 해라            (acon · massive) — 점수는 등장 횟수

점수를 합치는 방식:
  IFTTT 설치수와 HA 조회수는 단위가 달라서 각각 제 전체합으로 나눈 뒤 반반 더한다.
  두 곳의 순위가 꽤 다르기 때문이다 — IFTTT 는 손으로 켜는 애플릿(voice/button)이,
  HA 블루프린트는 집에 걸어두는 자동화(motion/threshold)가 크다. 한쪽만 쓰면 쏠린다.

  그냥 더하면 안 된다. HA 는 글이 360개뿐이라 조회수 21만짜리 글 하나가 5,000개 중
  145개를 가져간다. 그래서 원천마다 두 가지를 반반 섞는다.
    얼마나 쓰이나  규칙별 점수를 log1p 로 누른 뒤 시나리오별로 더한 값
    얼마나 흔한가  그 시나리오를 쓴 서로 다른 규칙의 수
  뒤엣것이 "그럴듯함" 이다 — 서로 모르는 사람 193명이 각자 만든 시나리오는,
  한 사람이 만들어 대박 난 시나리오보다 확실히 흔한 요구다.

세 덩어리로 나눈다:
  now      1,750 (35%)  지금 이것을 해라 — acon·massive·IFTTT 음성
  trigger  2,500 (50%)  집·오피스 자동화 — 원천 빈도가 정한다
  domain     750 (15%)  연구실·농장·공장 — 원천에 아예 없어서 우리가 적는다

원천(IFTTT·HA)은 가정집 이야기뿐이다. 그런데 우리 공간 40개 중 14개가 연구실·농장·공장이다.
빈도만 따르면 그 14개 공간에 명령어가 하나도 안 생긴다. 그래서 그쪽은 따로 몫을 떼고,
그 공간에 실제로 놓인 기기에서 시나리오를 뽑았다. 여기엔 설치수 근거가 없다 — 우리 판단이다.

배분:
  빈도로 8할, 다양성으로 2할. (사용자 우선순위: 1순위 많이 쓰임·그럴듯함, 2순위 다양성)
  한 시나리오가 전체의 3% (150개) 를 넘지 못하게 자른다.
  조명은 실제로 스마트홈의 절반이지만 그대로 두면 42% 가 조명이 된다 —
  기기 무리마다 상한을 걸어 남는 몫을 아래로 내린다.
"""
import collections
import csv
import math
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SPACES = os.path.join(HERE, "spaces.json")
csv.field_size_limit(10 ** 7)

TOTAL = 5000
NOW_SHARE = 0.35        # 즉시 실행 1,750
DOMAIN_SHARE = 0.15     # 연구실·농장·공장 750 (나머지 2,500 이 집·오피스 자동화)
HEAD = 0.80             # 빈도로 8할, 나머지는 고루 뿌린다
CAP = 150               # 한 시나리오 상한 (전체의 3%)
FAMILY_CAP = {"light": 0.30}   # 기기 무리별 상한 (전체 대비)
DROP_TRIG = {"message"}  # 이메일·SNS·문자 트리거 — 우리 밖
NOW_TRIG = {"voice", "now", ""}   # 음성·무조건은 트리거가 아니라 즉시 실행이다
MIN_TAIL = 3            # 살아남은 시나리오는 최소 이만큼


# ── 연구실·농장·공장 시나리오 ───────────────────────────────────────
# 원천에 없다. 각 공간에 실제로 놓인 기기에서 뽑았고, 무게는 우리가 매겼다 (1~3).
# (kind, 트리거, 액션, 트리거 기기, 액션 기기, 무게)
DOMAIN = [
    # 연구실 ────────────────────────────────────────────────────────
    ("lab", "threshold", "chamber",   "TemperatureSensor", "Chamber", 3),
    ("lab", "threshold", "notify",    "TemperatureSensor", "NotificationProvider", 3),
    ("lab", "gas",       "siren",     "GasSensor",         "Siren", 3),
    ("lab", "gas",       "ventilator", "GasSensor",        "Ventilator", 2),
    ("lab", "leak",      "valve",     "LeakSensor",        "Valve", 2),
    ("lab", "time",      "chamber",   "Clock",             "Chamber", 2),
    ("lab", "power",     "notify",    "PowerMeter",        "NotificationProvider", 2),
    ("lab", "contact",   "notify",    "ContactSensor",     "NotificationProvider", 2),
    ("lab", "motion",    "light.on",  "MotionSensor",      "Light", 2),
    ("lab", "finished",  "notify",    "ProductionMachine", "NotificationProvider", 2),
    ("lab", "threshold", "ventilator", "AirQualitySensor", "Ventilator", 2),
    ("lab", "device",    "armrobot",  "Switch",            "ArmRobot", 1),
    ("lab", "timer",     "notify",    "Clock",             "NotificationProvider", 1),
    ("lab", "threshold", "pump",      "PressureSensor",    "Pump", 1),
    # 농장 ──────────────────────────────────────────────────────────
    ("farm", "threshold", "sprinkler", "SoilMoistureSensor", "Sprinkler", 3),
    ("farm", "time",      "growlight", "Clock",             "GrowLight", 3),
    ("farm", "threshold", "ventilator", "TemperatureSensor", "Ventilator", 3),
    ("farm", "time",      "feeder",    "Clock",             "FeedDispenser", 3),
    ("farm", "threshold", "pump",      "WaterLevelSensor",  "Pump", 2),
    ("farm", "weather",   "sprinkler", "WeatherProvider",   "Sprinkler", 2),
    ("farm", "threshold", "notify",    "WaterQualitySensor", "NotificationProvider", 2),
    ("farm", "threshold", "valve",     "FlowSensor",        "Valve", 2),
    ("farm", "wind",      "cover",     "WindSensor",        "WindowCovering", 2),
    ("farm", "sun",       "growlight", "SunProvider",       "GrowLight", 2),
    ("farm", "threshold", "humidity",  "HumiditySensor",    "Humidifier", 1),
    ("farm", "contact",   "notify",    "ContactSensor",     "NotificationProvider", 1),
    # 공장 ──────────────────────────────────────────────────────────
    ("factory", "emergency", "conveyor", "EmergencyStop",   "ConveyorBelt", 3),
    ("factory", "barrier",   "conveyor", "SafetyBarrier",   "ConveyorBelt", 3),
    ("factory", "vibration", "notify",   "VibrationSensor", "NotificationProvider", 3),
    ("factory", "power",     "notify",   "PowerMeter",      "NotificationProvider", 3),
    ("factory", "threshold", "compressor", "PressureSensor", "AirCompressor", 2),
    ("factory", "time",      "conveyor", "Clock",           "ConveyorBelt", 2),
    ("factory", "finished",  "statuslight", "ProductionMachine", "StatusLight", 2),
    ("factory", "proximity", "conveyor", "ProximitySensor", "ConveyorBelt", 2),
    ("factory", "threshold", "notify",   "WeightSensor",    "NotificationProvider", 2),
    ("factory", "leak",      "valve",    "LeakSensor",      "Valve", 2),
    ("factory", "threshold", "ventilator", "GasSensor",     "Ventilator", 2),
    ("factory", "contact",   "siren",    "ContactSensor",   "Siren", 1),
    ("factory", "tilt",      "notify",   "TiltSensor",      "NotificationProvider", 1),
    ("factory", "threshold", "pump",     "WaterLevelSensor", "Pump", 1),
]


def load():
    rows = list(csv.DictReader(open(os.path.join(HERE, "corpus.csv"), encoding="utf-8")))
    for r in rows:
        r["score"] = int(r["score"] or 0)
        r["n_act"] = int(r["n_act"] or 0)
    return rows


def eligible(have, dt, da, kinds=None):
    """이 시나리오를 쓸 수 있는 공간 목록."""
    return [sid for sid, (cats, kind) in have.items()
            if (not kinds or kind in kinds)
            and (not dt or dt in cats) and (not da or da in cats)]


def space_pairs():
    """40 공간 중 어디에 (트리거 기기, 액션 기기) 가 함께 있는지."""
    S = json.load(open(SPACES, encoding="utf-8"))["spaces"]
    have = {}
    for sid, sp in S.items():
        cats = set()
        for d in sp["devices"].values():
            cats.update(d["category"])
        have[sid] = (cats, sp["kind"])
    return have


FAMILY = {"light.on": "light", "light.off": "light", "light.dim": "light",
          "light.color": "light", "light.scene": "light"}


def cap_family(q, keyfn, total):
    """기기 무리가 전체의 상한을 넘으면 잘라 나머지에게 비례로 돌린다."""
    for fam, share in FAMILY_CAP.items():
        limit = total * share
        mine = {k: v for k, v in q.items() if FAMILY.get(keyfn(k)) == fam}
        cur = sum(mine.values())
        if cur <= limit:
            continue
        scale = limit / cur
        spill = cur - limit
        for k in mine:
            q[k] *= scale
        rest = {k: v for k, v in q.items() if k not in mine}
        rtot = sum(rest.values()) or 1.0
        for k in rest:
            q[k] += spill * rest[k] / rtot
    return q


def allocate(items, budget):
    """items = [(key, weight)]. 빈도 8할 + 고루 2할, 상한 CAP."""
    tot = sum(w for _, w in items) or 1.0
    head_budget = budget * HEAD
    tail_budget = budget - head_budget
    q = {k: head_budget * w / tot for k, w in items}
    # 상한을 넘는 것을 잘라 남는 몫을 나머지에게 비례로 돌린다
    for _ in range(8):
        over = {k: v for k, v in q.items() if v > CAP}
        if not over:
            break
        spill = sum(v - CAP for v in over.values())
        for k in over:
            q[k] = CAP
        rest = {k: v for k, v in q.items() if k not in over}
        rtot = sum(rest.values()) or 1.0
        for k in rest:
            q[k] += spill * rest[k] / rtot
    # 다양성 몫은 고루
    per = tail_budget / len(items) if items else 0
    for k in q:
        q[k] += per
    # 정수로 내리고 남는 것을 큰 순서로 하나씩
    out = {k: max(MIN_TAIL, int(v)) for k, v in q.items()}
    diff = budget - sum(out.values())
    order = [k for k, _ in sorted(items, key=lambda x: -x[1])]
    i = 0
    while diff != 0 and order:
        k = order[i % len(order)]
        if diff > 0:
            if out[k] < CAP:
                out[k] += 1
                diff -= 1
        else:
            if out[k] > MIN_TAIL:
                out[k] -= 1
                diff += 1
        i += 1
        if i > 200000:
            break
    return out


def main():
    rows = load()
    have = space_pairs()

    # ── 트리거 자동화 ──────────────────────────────────────────────────
    ift = collections.Counter()
    ha = collections.Counter()
    ift_raw = collections.Counter()
    ha_raw = collections.Counter()
    meta = {}
    n_src = collections.Counter()
    for r in rows:
        if r["src"] not in ("ifttt", "ifttt_pop", "ha"):
            continue
        if not r["trig"] or not r["act"] or r["trig"] in DROP_TRIG:
            continue
        if r["trig"] in NOW_TRIG:      # 즉시 실행 쪽에서 센다
            continue
        key = (r["trig"], r["act"])
        meta.setdefault(key, (r["dev_trig"], r["dev_act"]))
        n_src[key] += 1
        if r["src"] == "ha":
            ha[key] += math.log1p(r["score"])
            ha_raw[key] += r["score"]
        else:
            ift[key] += math.log1p(r["score"])
            ift_raw[key] += r["score"]

    n_ift = collections.Counter()
    n_ha = collections.Counter()
    for r in rows:
        if r["src"] not in ("ifttt", "ifttt_pop", "ha"):
            continue
        if not r["trig"] or not r["act"] or r["trig"] in DROP_TRIG or r["trig"] in NOW_TRIG:
            continue
        (n_ha if r["src"] == "ha" else n_ift)[(r["trig"], r["act"])] += 1

    def blend(score, count):
        ts = sum(score.values()) or 1.0
        tc = sum(count.values()) or 1.0
        return {k: 0.5 * score[k] / ts + 0.5 * count[k] / tc for k in set(score) | set(count)}

    w_ift, w_ha = blend(ift, n_ift), blend(ha, n_ha)
    trig_w = {k: 0.5 * w_ift.get(k, 0) + 0.5 * w_ha.get(k, 0)
              for k in set(w_ift) | set(w_ha)}

    # 우리 공간에서 실제로 쓸 수 있는 짝만 남긴다
    live, dead = [], []
    for k, w in trig_w.items():
        dt, da = meta[k]
        ok = bool(eligible(have, dt, da))
        (live if ok and w > 0 else dead).append((k, w))
    live.sort(key=lambda x: -x[1])

    q_trig = allocate(live, round(TOTAL * (1 - NOW_SHARE - DOMAIN_SHARE)))

    # ── 연구실·농장·공장 ───────────────────────────────────────────────
    dom_items = [((k[0], k[1], k[2]), float(k[5])) for k in DOMAIN]
    q_dom = allocate(dom_items, round(TOTAL * DOMAIN_SHARE))
    dom_meta = {(k[0], k[1], k[2]): (k[3], k[4]) for k in DOMAIN}

    # ── 즉시 실행 ──────────────────────────────────────────────────────
    now = collections.Counter()
    now_meta = {}
    for r in rows:
        voice_rule = (r["src"].startswith("ifttt") and r["trig"] == "voice")
        if not r["act"]:
            continue
        if not (r["src"] in ("acon", "massive") or voice_rule):
            continue
        combo = tuple(sorted(set(r["acts"].split("|")))) if r["acts"] else (r["act"],)
        combo = combo[:3]           # 4개 이상 섞인 문장은 앞 3개까지만 본다
        # 음성 애플릿은 설치수가 있으니 로그로 눌러서 몇 표 몫으로 친다
        now[combo] += int(math.log1p(r["score"])) + 1 if voice_rule else 1
        now_meta.setdefault(combo, r["dev_act"])
    now_items = [(k, v) for k, v in now.items() if v >= 3]
    now_items.sort(key=lambda x: -x[1])
    q_now = allocate(now_items, round(TOTAL * NOW_SHARE))

    # 조명이 전체의 30% 를 넘지 않게 세 몫을 한꺼번에 본다
    allq = {("T",) + k: v for k, v in q_trig.items()}
    allq.update({("N",) + (kk,): v for kk, v in
                 ((("+".join(k)), v) for k, v in q_now.items())})
    allq.update({("D",) + k: v for k, v in q_dom.items()})
    before = sum(v for k, v in allq.items()
                 if FAMILY.get(k[-1] if k[0] != "N" else k[1].split("+")[0]))
    allq = cap_family(allq, lambda k: (k[-1] if k[0] != "N" else k[1].split("+")[0]), TOTAL)
    after = sum(v for k, v in allq.items()
                if FAMILY.get(k[-1] if k[0] != "N" else k[1].split("+")[0]))
    for k, v in allq.items():
        v = max(MIN_TAIL, int(round(v)))
        if k[0] == "T":
            q_trig[(k[1], k[2])] = v
        elif k[0] == "D":
            q_dom[(k[1], k[2], k[3])] = v
        else:
            q_now[tuple(k[1].split("+"))] = v
    print(f"조명 몫 {before:.0f} → {after:.0f} (상한 {TOTAL*0.30:.0f})")

    # 반올림하며 흘린 몇 개를 정확히 5,000 에 맞춘다 (조명 아닌 쪽부터)
    def bump(diff):
        pool = ([k for k in q_trig if not FAMILY.get(k[1])] +
                [k for k in q_dom] +
                [k for k in q_now if not FAMILY.get(k[0])])
        pool.sort(key=lambda k: -(q_trig.get(k) or q_dom.get(k) or q_now.get(k) or 0))
        i = 0
        while diff and pool:
            k = pool[i % len(pool)]
            for d in (q_trig, q_dom, q_now):
                if k in d:
                    if diff > 0 and d[k] < CAP:
                        d[k] += 1
                        diff -= 1
                    elif diff < 0 and d[k] > MIN_TAIL:
                        d[k] -= 1
                        diff += 1
                    break
            i += 1
            if i > 100000:
                break
    bump(TOTAL - sum(q_trig.values()) - sum(q_now.values()) - sum(q_dom.values()))

    # ── 쓰기 ───────────────────────────────────────────────────────────
    dst = os.path.join(HERE, "scenarios.csv")
    with open(dst, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mode", "trig", "act", "dev_trig", "dev_act",
                    "installs", "views", "weight", "n_rules", "quota", "spaces"])
        for k, wt in live:
            dt, da = meta[k]
            w.writerow(["trigger", k[0], k[1], dt, da,
                        ift_raw[k], ha_raw[k], f"{wt:.6f}", n_src[k], q_trig[k],
                        " ".join(eligible(have, dt, da))])
        for k, (dt, da) in sorted(dom_meta.items()):
            w.writerow(["domain", k[1], k[2], dt, da, "", "", "", k[0], q_dom[k],
                        " ".join(eligible(have, dt, da, {k[0]}))])
        for k, c in now_items:
            da = now_meta[k]
            w.writerow(["now", "now", "+".join(k), "", da,
                        "", "", f"{c/sum(now.values()):.6f}", c, q_now[k],
                        " ".join(eligible(have, "", da))])

    # ── 진단 ───────────────────────────────────────────────────────────
    tt, tn, td = sum(q_trig.values()), sum(q_now.values()), sum(q_dom.values())
    print(f"scenarios.csv: 트리거 {len(live)} + 즉시 {len(now_items)} + 도메인 "
          f"{len(dom_items)} = {len(live)+len(now_items)+len(dom_items)} 시나리오")
    print(f"배분 합계: 트리거 {tt} + 즉시 {tn} + 도메인 {td} = {tt+tn+td}")
    if dead:
        print(f"\n우리 공간에 짝이 없어 버린 시나리오 {len(dead)}개:",
              ", ".join(f"{a}→{b}" for (a, b), _ in sorted(dead, key=lambda x: -x[1])[:10]))

    print("\n── 트리거 자동화 상위 25 ──")
    print(f"  {'트리거':<10}{'액션':<13}{'설치수':>9}{'조회수':>9}"
          f"{'규칙수':>6}{'비중':>7}{'배분':>6}")
    for k, wt in live[:25]:
        print(f"  {k[0]:<10}{k[1]:<13}{ift_raw[k]:>9,}{ha_raw[k]:>9,}"
              f"{n_src[k]:>6}{wt:>6.1%}{q_trig[k]:>6}")

    print("\n── 즉시 실행 상위 20 ──")
    for k, c in now_items[:20]:
        print(f"  {'+'.join(k):<28}{c:>6}{q_now[k]:>6}")

    bt = collections.Counter()
    for k, _ in live:
        bt[k[0]] += q_trig[k]
    print(f"\n── 트리거 자동화 {tt} 을 트리거별로 ──")
    for k, v in bt.most_common():
        print(f"  {k:<10}{v:>5}  {v/sum(bt.values()):>6.1%}")

    ba = collections.Counter()
    for k, _ in live:
        ba[k[1]] += q_trig[k]
    for k, _ in now_items:
        for a in k:
            ba[a] += q_now[k] / len(k)
    for k in q_dom:
        ba[k[2]] += q_dom[k]
    reach = collections.Counter()
    for k, _ in live:
        for sid in eligible(have, *meta[k]):
            reach[sid] += q_trig[k]
    for k in q_dom:
        for sid in eligible(have, *dom_meta[k], {k[0]}):
            reach[sid] += q_dom[k]
    empty = [sid for sid in have if sid not in reach]
    print(f"\n── 자동화를 하나도 못 받는 공간: {empty or '없음 ✅'}")
    lo = sorted(reach.items(), key=lambda x: x[1])[:6]
    print("   후보가 가장 적은 공간:", ", ".join(f"{k}({v})" for k, v in lo))

    print("\n── 5,000 을 액션별로 ──")
    for k, v in ba.most_common(18):
        print(f"  {k:<13}{v:>7.0f}  {v/sum(ba.values()):>6.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
