#!/usr/bin/env python3
"""dataset_5k.csv 가 어디에 몰려 있는지 본다 — 4단계 진단.

쿼터가 아니다. 축마다 분포를 보고, 비어 있는 칸을 3단계로 돌아가 채우는 데 쓴다.
"""
import collections
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AXES = [("tier", "난이도"), ("d", "시간·로직"), ("ref", "기기 지목"), ("tone", "말투"), ("b1", "서비스 쓰임"),
        ("b3", "기기 종류 수"), ("expect", "판정"), ("context", "바깥 정보"),
        ("mode", "덩어리"), ("kind", "공간 종류"), ("trig", "트리거"), ("act", "동작")]
T_NAME = {"T0": "즉시 실행", "T1": "TAP 그대로", "T2": "조건·지연",
          "T3": "반복·제한시간 (TAP 불가)", "T4": "변수·비교·누적 (TAP 불가)"}
D_NAME = {"D1": "지금 한 번", "D2": "순서+지연", "D3": "조건 지금", "D4": "트리거 기다림",
          "D5": "지속 조건", "D6": "정해진 시각", "D7": "주기 반복",
          "D8": "기간·횟수 제한 반복", "D9": "트리거 후 반복", "D10": "제한시간 대기",
          "D11": "두 번 읽고 비교", "D12": "누적·상태 보존", "D13": "복합 중첩"}


def bar(v, tot, w=28):
    return "█" * max(1, round(w * v / tot)) if v else ""


def main():
    R = list(csv.DictReader(open(os.path.join(HERE, "dataset_5k.csv"), encoding="utf-8")))
    n = len(R)
    print(f"dataset_5k.csv {n}문장\n")
    for key, name in AXES:
        c = collections.Counter(x[key] for x in R)
        items = c.most_common(14) if key in ("trig", "act") else sorted(
            c.items(), key=lambda x: (len(x[0]), x[0]) if key in ("d", "tier")
            else (-x[1],))
        print(f"── {name} ({key}) — {len(c)}종")
        for k, v in items:
            lbl = f"{k} {D_NAME.get(k) or T_NAME.get(k, '')}".strip()
            print(f"   {lbl:26}{v:5d} {v/n:5.1%} {bar(v, n)}")
        if key in ("trig", "act") and len(c) > 14:
            print(f"   … 나머지 {len(c)-14}종")
        print()

    # 비어 있는 칸 찾기 — 축을 둘씩 겹쳐 본다
    print("── 비어 있는 칸 (교차)")
    for a, b in (("d", "expect"), ("d", "ref"), ("expect", "kind"), ("b1", "mode"),
                 ("context", "expect"), ("tier", "expect"), ("tier", "ref")):
        va = sorted({x[a] for x in R})
        vb = sorted({x[b] for x in R})
        have = {(x[a], x[b]) for x in R}
        gap = [(p, q) for p in va for q in vb if (p, q) not in have]
        print(f"   {a}×{b}: {len(va)*len(vb)}칸 중 빈 칸 {len(gap)}", gap[:6])

    thin = [(k, v) for k, v in collections.Counter(x["space_id"] for x in R).items()
            if v < 40]
    print(f"\n── 문장 40개 미만인 공간: {thin or '없음 ✅'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
