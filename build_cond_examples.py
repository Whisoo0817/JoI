# -*- coding: utf-8 -*-
"""조건 예문 만들기 — 조각 경로가 값 서비스를 고를 때 쓸 예문.

매핑은 두 갈래로 돈다.
  ① 절 단위 순위 — 절 전체를 서비스 문서·예문과 견준다 (예문을 쓴다)
  ② 조각 단위 값 검색 — 조건절을 잘게 쪼개 **값 서비스**하고만 견준다 (예문을 안 썼다)
`?` 가 남는 자리가 ②다. 어느 기기인지는 골라도 어느 값을 견줄지를 못 정한다.
여기에 5k 의 조건·시간절을 예문으로 먹인다. 기본은 전부, --train-only 면 학습 몫만.

    ~/temp/bin/python build_cond_examples.py
"""
import json, os, re, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.join(HERE, "joi_slm", "assets", "cond_examples.json")


def main():
    tr = (set(json.load(open(os.path.join(HERE, "bench", "split_5k.json"),
                             encoding="utf-8"))["학습"])
          if "--train-only" in sys.argv else None)
    import csv
    ir = {r["id"]: r["ir_gt"] for r in
          csv.DictReader(open(os.path.join(HERE, "bench", "dataset_5k.csv"), encoding="utf-8"))}
    L = json.load(open(os.path.join(HERE, "bench", "labels_5k.json"), encoding="utf-8"))
    from joi_slm.catalog import SERVICES
    VAL = {s["svc"] for s in SERVICES if s["role"] == "read"}

    ex, skip = [], collections.Counter()
    for i, o in enumerate(L):
        if (tr is not None and o["id"] not in tr) or not ir.get(o["id"]):
            skip["학습 몫 아님" if tr is not None else "정답 IR 없음"] += 1
            continue
        conds = re.findall(r'"(?:cond|until)": "([^"]*)"', ir[o["id"]])
        svcs = {m for c in conds for m in
                re.findall(r"\b([A-Z][A-Za-z]+\.[A-Za-z0-9]+)", c)} & VAL
        cl = [c for c in o["절"] if c["종류"] in ("COND", "TRIG")]
        if len(svcs) == 1 and len(cl) == 1:
            ex.append({"i": i, "text": cl[0]["글"], "svc": next(iter(svcs))})
        elif len(cl) > 1 and len(svcs) == len(cl):
            skip["절과 서비스가 여럿 — 짝짓기 애매"] += 1
        else:
            skip["짝이 안 맞음"] += 1

    json.dump(ex, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"{OUT} — 조건 예문 {len(ex)}개 / 서비스 {len({e['svc'] for e in ex})}종")
    print(" 건너뜀:", dict(skip.most_common(3)))
    print(" 많이 나온 서비스:", collections.Counter(e["svc"] for e in ex).most_common(5))
    return 0


if __name__ == "__main__":
    sys.exit(main())
