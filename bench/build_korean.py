#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""한국어판 검토표 — 영어와 나란히 놓고 문제를 표시한다.

  python bench/build_dataset.py      # 먼저 돌린다 (command_ko 가 여기서 생긴다)
  python bench/build_korean.py       # dataset_ko.csv + 문제 보고

N=0 이면 전부, 숫자를 주면 축이 골고루 들어가게 층을 나눠 그만큼만 뽑는다.

한국어 문장은 `korean.py` 가 영어와 **같은 틀 자리**에 한국어를 끼워 만든다.
영어 문장을 다시 읽어 옮기는 것이 아니다 — 관사·복수가 이미 녹아 있어서 틀린다.

뽑는 법: 축이 골고루 들어가게 층을 나눠 뽑는다 (공간 종류 × 난이도 × 판정).
같은 층 안에서는 앞에서부터 순서대로 — 무작위가 아니라 다시 돌려도 같게.
"""
import collections
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
csv.field_size_limit(10 ** 7)

SRC = os.path.join(HERE, "dataset_5k.csv")
DST = os.path.join(HERE, "dataset_ko.csv")
N = 0        # 0 이면 전부

COLS = ["id", "space_id", "command", "command_ko", "expect", "why",
        "act", "ref", "d", "tier", "targets"]


def load():
    rows = list(csv.DictReader(open(SRC, encoding="utf-8")))
    if not rows or "command_ko" not in rows[0]:
        sys.exit("dataset_5k.csv 에 command_ko 가 없다 — build_dataset.py 를 먼저 돌려라")
    n_u = sum(1 for r in rows if not r["command_ko"])
    if n_u:
        print(f"※ 한국어가 아직 없는 행 {n_u}개(U행)는 뽑기에서 뺀다 — "
              f"손으로 쓴 문장이라 틀이 없다\n")
    return [r for r in rows if r["command_ko"]]


def sample(rows, n):
    """공간 종류 × 난이도 × 판정 으로 층을 나눠 비율대로 뽑는다."""
    S = json.load(open(os.path.join(HERE, "spaces.json"), encoding="utf-8"))["spaces"]
    key = lambda r: (S[r["space_id"]]["kind"], r["tier"], r["expect"])   # noqa: E731
    buckets = collections.OrderedDict()
    for r in rows:
        buckets.setdefault(key(r), []).append(r)
    total = len(rows)
    out, left = [], n
    order = sorted(buckets, key=lambda k: -len(buckets[k]))
    for i, k in enumerate(order):
        want = max(1, round(n * len(buckets[k]) / total)) if i < len(order) - 1 else left
        want = min(want, len(buckets[k]), left)
        out += buckets[k][:want]
        left -= want
        if left <= 0:
            break
    return sorted(out, key=lambda r: r["id"])


# ── 한국어 문장에서 걸러낼 것 ──────────────────────────────────────────
LATIN = re.compile(r"[A-Za-z]{2,}")
# 한국어 문장에 남아도 되는 로마자 — 제품명·약어. 뒤에 한글 조사가 붙으므로
# \b 를 쓰면 경계가 안 잡힌다(한글도 낱말 문자다). 그래서 경계를 안 쓴다.
# 긴 것을 앞에 둔다 — "TVOC" 가 "TV" 로 먼저 잘리면 "OC" 가 남는다
ALLOW = re.compile(r"(TVOC|RFID|CO2|SmartThings|TV|EV|LG|Aqara|Tuya|Wi-?Fi|Philips|Hue|SmartThings|"
                   r"Skylight|YUER|JOI|IR|barrier|tc0|Smart|Plug|Sensor|Speaker|"
                   r"Button|Motion|Light|Door|Window|Presence|Multi|Gang|Zigbee|"
                   r"Hub|Bulb|Switch|P2|ep\d|pH|Ph|CO)", re.I)


def flags(r):
    """이 행의 한국어가 미심쩍은 이유. 없으면 빈 목록."""
    f = []
    ko = r["command_ko"]
    if not ko:
        f.append("한국어없음")
        return f
    left = ALLOW.sub("", ko)
    if LATIN.search(left):
        f.append("영어남음:" + ",".join(sorted(set(LATIN.findall(left)))[:3]))
    if "  " in ko or " ." in ko:
        f.append("띄어쓰기")
    # 단수로 부른 자리. 영어는 "the light" 로 티가 나지만 한국어는 그냥 "조명" 이다.
    # 복수 쪽에 "다" 를 붙여 판정이 겹치지는 않게 했고(충돌 0), 후보가 여럿인
    # 행은 한국어로도 애매해서 되묻기가 맞다 — 결함이 아니라 성격 표시다.
    if r["ref"] == "onedup":
        f.append("단수지목")
    # 거절 행은 지목이 실패한 자리라 ref 가 '시도한 방식' 을 남긴다 — 검사에서 뺀다
    if (r["expect"] != "refuse" and r["ref"] == "all"
            and not re.search(r"전부|전체|모든|모두| 다 ", ko)):
        f.append("전부표시없음")
    if len(ko) > 90:
        f.append("너무김")
    # 시간절과 조건절이 둘 다 "~면" 으로 끝나 겹친다 (말투 어미는 뺀다)
    if len(re.findall(r"(?<!으)면[ ,]", ko.replace("줬으면 해", ""))) >= 2:
        f.append("면겹침")
    return f


def main():
    rows = load()
    picked = sample(rows, N) if N else rows

    # 표시(flags)는 아래 보고로만 낸다 — 표에 열로 싣지 않는다
    marks = {r["id"]: flags(r) for r in picked}
    out = [{k: r[k] for k in COLS} for r in picked]

    with open(DST, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(out)

    # ── 보고 ──
    S = json.load(open(os.path.join(HERE, "spaces.json"), encoding="utf-8"))["spaces"]
    print(f"{os.path.basename(DST)} — {len(out)}행\n")
    print("공간 종류:", dict(collections.Counter(
        S[r["space_id"]]["kind"] for r in picked)))
    print("판정:", dict(collections.Counter(r["expect"] for r in picked)))
    print("난이도:", dict(sorted(collections.Counter(r["tier"] for r in picked).items())))
    print("기기 지목:", dict(collections.Counter(r["ref"] for r in picked)))

    fl = collections.Counter()
    for f in marks.values():
        for x in f:
            fl[x.split(":")[0]] += 1
    print(f"\n── 표시된 것 {sum(1 for f in marks.values() if f)}행 ──")
    for k, v in fl.most_common():
        print(f"   {k:14}{v:5}")

    # 한국어가 있는 행 전체에서도 같은 것을 센다 — 1,000 이 대표하는지 보려고
    allf = collections.Counter()
    for r in rows:
        for x in flags(r):
            allf[x.split(":")[0]] += 1
    print(f"\n── 전체 {len(rows)}행 기준 ──")
    for k, v in allf.most_common():
        print(f"   {k:14}{v:5} ({v / len(rows):.1%})")

    print("\n── 표본 ──")
    for r in out[::max(1, len(out) // 12)][:12]:
        print(f"  [{r['expect']:7}] {r['command'][:60]}")
        print(f"            → {r['command_ko']}")


if __name__ == "__main__":
    main()
