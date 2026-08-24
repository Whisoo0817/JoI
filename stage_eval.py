# -*- coding: utf-8 -*-
"""단계별 정확도 — 절 나누기 · 절 타입 · 서비스 고르기 · IR 을 따로 잰다.

왜 따로 재나
  전체 IR 점수만 보면 어느 단계가 무너졌는지 모른다. 앞 단계가 틀리면 뒤는
  자동으로 틀리므로, 뒤 단계 점수는 앞이 맞은 행에서만 봐야 뜻이 있다.

재는 것 (정답은 bench/labels_5k.json 과 ir_gt)
  절 나누기  단어마다 "여기서 절이 갈리나" — 문장 통째로 맞아야 1점
  절 타입    절마다 TRIG/TIME/COND/ACT… — 절 나누기가 맞은 행에서만 잰다
  서비스     정답 IR 이 부르는 서비스 집합을 골랐나 (순위 1등 기준)
  IR         뜻이 같은가 (joi_slm/compare.py)

    ~/temp/bin/python stage_eval.py --tier T0 T1 -n 150
"""
import argparse, collections, csv, json, os, random, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ENGINE_URL = "http://localhost:49998"


def use_engine_server(url=None):
    import urllib.request
    url = url or os.environ.get("JOI_ENGINE_URL") or ENGINE_URL
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=1.5) as r:
            if r.status != 200:
                return False
    except Exception:                                   # noqa: BLE001
        return False
    os.environ["JOI_ENGINE_URL"] = url
    return True


def gold_services(ir_gt):
    import re
    return set(re.findall(r'"target": "([^"]+)"', ir_gt)) | \
           set(re.findall(r'"src": "([A-Za-z]+\.[A-Za-z0-9]+)', ir_gt))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", nargs="*", default=["T0", "T1"])
    ap.add_argument("-n", type=int, default=150)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--all", action="store_true", help="시험 몫 말고 전부에서 뽑는다")
    args = ap.parse_args()

    lab = {o["id"]: o for o in json.load(open(os.path.join(HERE, "bench", "labels_5k.json"),
                                              encoding="utf-8"))}
    data = {r["id"]: r for r in csv.DictReader(
        open(os.path.join(HERE, "bench", "dataset_5k.csv"), encoding="utf-8"))}
    ko = {r["id"]: r for r in csv.DictReader(
        open(os.path.join(HERE, "bench", "dataset_ko.csv"), encoding="utf-8"))}
    test = set(json.load(open(os.path.join(HERE, "bench", "split_5k.json"),
                              encoding="utf-8"))["시험"])

    pool = [i for i, r in data.items()
            if r["tier"] in args.tier and r["ir_gt"] and i in lab
            and (args.all or i in test)]
    pick = random.Random(args.seed).sample(pool, min(args.n, len(pool)))
    print(f"{'전체' if args.all else '시험 몫'}에서 {args.tier} · 정답 IR 이 있는 행 {len(pool)} 중 {len(pick)}개")

    if not use_engine_server():
        print("엔진 서버가 없다"); return 1
    import bench_run as B
    from joi.generate import generate_joi_code_ir
    from pipeline_helpers import JoiGenerationError
    from joi_slm import compare
    sp = B.load_spaces()

    c = collections.Counter()
    t0 = time.perf_counter()
    for i in pick:
        r, g = ko[i], lab[i]
        try:
            res = generate_joi_code_ir(r["command_ko"], B.devices_of(sp, r["space_id"]), {})
            ir, segs, mp = res["ir"], res["segments"], res["mapping"]
        except JoiGenerationError as e:
            ir = getattr(e, "ir", None)
            segs = getattr(e, "segments", None) or []
            mp = {}
        except Exception:                                # noqa: BLE001
            c["터짐"] += 1; continue

        c["행"] += 1
        # ① 절 나누기 — 절 글이 정답과 그대로 같아야 1점
        got_txt = [s["text"] for s in segs]
        want_txt = [x["글"] for x in g["절"]]
        seg_ok = got_txt == want_txt
        c["절나누기"] += seg_ok
        # ② 절 타입 — 절 나누기가 맞은 행에서만
        if seg_ok:
            c["타입잼"] += 1
            c["타입"] += [s["type"] for s in segs] == [x["종류"] for x in g["절"]]
        # ③ 서비스 — 정답이 부르는 서비스를 다 골랐나 (순위 1등)
        want_svc = gold_services(data[i]["ir_gt"])
        top = {v[0] for v in (mp.get("ranked") or {}).values() if v}
        if want_svc:
            c["서비스잼"] += 1
            c["서비스"] += want_svc <= top
        # ④ IR
        if ir is not None:
            v = compare.verdict(ir, json.loads(data[i]["ir_gt"]))
            c["IR잼"] += 1
            c["IR뜻"] += bool(v.get("same"))
            c["IR서비스"] += bool(v.get("svc"))

    def line(name, a, b):
        n, d = c[a], c[b]
        return f"  {name:12s} {n:4d}/{d:<4d} {n/d*100:5.1f}%" if d else f"  {name:12s}   -"
    print(f"\n본 행 {c['행']}  ({time.perf_counter()-t0:.0f}초)")
    print(line("① 절 나누기", "절나누기", "행"))
    print(line("② 절 타입", "타입", "타입잼") + "   (절 나누기가 맞은 행에서만)")
    print(line("③ 서비스", "서비스", "서비스잼"))
    print(line("④ IR 뜻", "IR뜻", "IR잼"))
    print(line("   IR 서비스", "IR서비스", "IR잼"))
    if c["터짐"]:
        print(f"  (예외로 빠진 행 {c['터짐']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
