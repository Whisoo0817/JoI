#!/usr/bin/env python3
"""학습·시험 나누기 — **문장이 아니라 틀 종류로** 가른다.

왜 틀로 가르나
  한 틀에서 나온 문장이 학습과 시험 양쪽에 걸리면, 모델이 그 틀의 겉모습을
  외워 버려 시험이 무의미해진다. 그래서 틀을 통째로 한쪽에만 둔다.

어떻게
  자리마다(시간절·동작절·로직·조건) 틀의 일부를 시험 몫으로 떼어 둔다.
  한 문장이라도 시험 몫 틀을 쓰면 그 문장은 시험행이다.
  네 자리 모두 학습 몫 틀만 쓴 문장이 학습행이다.

  U행 578개는 손으로 쓴 문장이라 틀이 없다 — 통째로 시험 몫이다.
  씨앗이 실제 사용 사례라, 처음 보는 말투를 재는 칸이 된다.

  python bench/build_split.py            # 기본(자리마다 10%, 조건은 2종)
  python bench/build_split.py --rate 0.2
"""
import argparse
import collections
import csv
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.join(HERE, "parts_5k.json")
DATA = os.path.join(HERE, "dataset_5k.csv")
OUT = os.path.join(HERE, "split_5k.json")

SLOTS = ("trig", "act", "frame", "cond")


def sole_frames(parts, rows):
    """제 난이도(D코드)를 혼자 짊어진 문형. 이걸 떼면 그 난이도가 학습에서 통째로
    사라진다 (D10 문형 둘 중 하나를 지웠을 때 실제로 그렇게 됐다)."""
    by_d = collections.defaultdict(set)
    for p in parts:
        r = rows.get(p["id"])
        if p.get("frame") and r:
            by_d[r["d"]].add(p["frame"])
    return {next(iter(v)) for v in by_d.values() if len(v) == 1}


def hold_out(parts, rate, seed, cond_min, keep=()):
    """자리마다 틀의 일부를 시험 몫으로 뗀다. 종류가 적은 자리는 최소 개수를 지킨다.
    keep 에 든 문형은 안 뗀다 — 그 난이도의 학습 몫이 0 이 되기 때문이다."""
    rng = random.Random(seed)
    out = {}
    for slot in SLOTS:
        kinds = sorted({p[slot] for p in parts if p[slot]})
        if slot == "frame":
            kinds = [k for k in kinds if k not in keep]
        n = max(cond_min if slot in ("frame", "cond") else 1, round(len(kinds) * rate))
        out[slot] = sorted(rng.sample(kinds, min(n, len(kinds))))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", type=float, default=0.10, help="자리마다 뗄 비율 (기본 0.10)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--cond-min", type=int, default=2, help="로직·조건은 최소 몇 종을 뗄까")
    args = ap.parse_args()

    parts = json.load(open(PARTS, encoding="utf-8"))
    rows = {r["id"]: r for r in csv.DictReader(open(DATA, encoding="utf-8"))}
    held = hold_out(parts, args.rate, args.seed, args.cond_min,
                    keep=sole_frames(parts, rows))

    train, test, why = [], [], collections.Counter()
    for p in parts:
        hit = [s for s in SLOTS if p[s] and p[s] in held[s]]
        if hit:
            test.append(p["id"])
            why["+".join(hit)] += 1
        else:
            train.append(p["id"])
    # U행은 틀이 없다 — 통째로 시험 몫
    useen = [i for i in rows if i.startswith("U")]
    test += sorted(useen)
    why["U행(손으로 쓴 문장)"] = len(useen)

    split = {"$설명": "틀 종류로 가른 학습·시험 몫. 한 틀은 한쪽에만 있다.",
             "뗀 틀": held, "학습": sorted(train), "시험": sorted(test)}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(split, f, ensure_ascii=False, indent=1)
        f.write("\n")

    tot = len(train) + len(test)
    print(f"{OUT}")
    print(f"  학습 {len(train)} ({len(train)/tot:.0%}) · 시험 {len(test)} ({len(test)/tot:.0%})")
    print("  뗀 틀:", {s: len(v) for s, v in held.items()},
          "/ 전체:", {s: len({p[s] for p in parts if p[s]}) for s in SLOTS})
    print("  시험행이 된 까닭:", dict(why.most_common(6)))

    # 시험 몫이 한쪽으로 쏠리지 않았는지 본다
    print("\n  ── 쏠림 검사 (학습 대비 시험 비율)")
    ts = set(test)
    for axis in ("expect", "tier", "d", "ref"):
        a = collections.Counter(rows[i][axis] for i in train if i in rows)
        b = collections.Counter(rows[i][axis] for i in test if i in rows)
        line = {k: f"{b[k]}/{a[k]+b[k]}" for k in sorted(set(a) | set(b))}
        print(f"   {axis:7s}", line)
    miss = [k for k in set(rows[i]["expect"] for i in test if i in rows)] 
    return 0


if __name__ == "__main__":
    sys.exit(main())
