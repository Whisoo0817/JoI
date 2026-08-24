# -*- coding: utf-8 -*-
"""bench_run.py — 5k 한국어 데이터셋으로 파이프라인을 돌려 본다.

공간마다 기기 목록이 정해져 있고(spaces.json), 명령문은 그 공간에 붙어 있다.
행 하나 = 공간 하나의 기기 목록 + 한국어 명령문.

    ~/temp/bin/python bench_run.py -n 40             # 앞에서 골고루 40행
    ~/temp/bin/python bench_run.py -n 40 --seed 7    # 다른 40행
    ~/temp/bin/python bench_run.py --ids G00014 G00019
    ~/temp/bin/python bench_run.py -n 20 --show      # 행마다 자세히

채점하는 것 (whisoo 결정 2026-08-24)
  판정   실행 / 되묻기 / 거절.  되묻기는 **중복정답** — 되물어도 맞고 다 해도 맞다.
         그래서 점수에는 안 들어가고 "얼마나 되물었나" 만 따로 센다.
  대상   기기 집합(targets)과 서비스(target_svc). 순서는 안 본다.
  로직   정답 IR 과 견준다 (joi_slm/compare.py 기준).
  효과   지금은 안 잰다. 보조 진단으로 나중에 붙인다.

전부 다 돌리지 않는다 — 표본으로만 본다.
"""
import argparse
import csv
import json
import os
import random
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

ENGINE_URL = "http://localhost:49998"      # 엔진 서버(engine_server.py). 안 떠 있으면 이 프로세스에 모델을 올린다


def use_engine_server(url=None):
    """엔진 서버가 살아 있으면 거기에 붙는다. 안 붙으면 모델을 또 올리다 GPU 가 모자란다."""
    import urllib.request
    url = url or os.environ.get("JOI_ENGINE_URL") or ENGINE_URL
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=1.5) as r:
            if r.status != 200:
                return False
    except Exception:                                    # noqa: BLE001
        return False
    os.environ["JOI_ENGINE_URL"] = url
    return True


DATA = os.path.join(HERE, "bench", "dataset_ko.csv")
SPACES = os.path.join(HERE, "bench", "spaces.json")
HUB = os.path.join(HERE, "files", "hub_config.json")


# ── 입력 어댑터 ────────────────────────────────────────────────────────
def load_spaces():
    """공간 40개. 기기 형식이 옛 dataset.csv 의 connected_devices 와 같아 그대로 쓴다."""
    return json.load(open(SPACES, encoding="utf-8"))["spaces"]


def devices_of(spaces, space_id):
    """그 공간의 고정 기기 목록 → 파이프라인이 받는 connected_devices."""
    return spaces[space_id]["devices"]


def hub_config():
    """허브 설정 — 기준값·장면·알림 순서·보폭·재실 주체 순서."""
    return json.load(open(HUB, encoding="utf-8"))


def occupancy_source(devices, hub):
    """재실을 무엇으로 판단하나. 목록을 위에서부터 훑어 처음 되는 것.
    다 없으면 None — 판단할 방법이 없다는 뜻이라 거절이다."""
    cats = {c for d in devices.values() for c in (d.get("category") or [])}
    has_human = any("Human" in (d.get("variables") or {}) for d in devices.values())
    for step in hub["재실주체_순서"]:
        need = step["있어야 하는 것"]
        if need.startswith("GlobalVariable"):
            if has_human:
                return step["쓸 것"]
        elif need in cats:
            return step["쓸 것"]
    return None


# ── 채점기 ─────────────────────────────────────────────────────────────
def score_targets(got, want):
    """기기 집합 비교 — 순서는 안 본다."""
    g, w = set(got or []), set(want or [])
    if not w:
        return None                 # 정답에 대상이 없다 (알림·조회 등) — 이 축은 건너뛴다
    return g == w


def bucket(msg):
    """막힌 이유를 종류로 묶는다 — 무엇을 먼저 고칠지 보려고."""
    m = msg or ""
    if "여러 대 자리" in m:     return "값 자리에 기기 여럿"
    if "cond tokenize" in m:   return "조건이 비었음"
    if "cond trailing" in m:   return "조건에 딴 글자가 섞임"
    if "DIVERGE" in m:         return "게이트 갈라짐"
    if "REFUSED" in m:         return "게이트 기타"
    if "CantLower" in m or "규칙 밖" in m: return "규칙이 못 옮김"
    if "No connected" in m or "기기" in m: return "기기 없음"
    return "그 밖"


def judge_ok(got, want):
    """판정 채점. 되묻기는 중복정답 — 되물어도, 다 해도 맞다."""
    if want == "ask":
        return got in ("ask", "execute")
    return got == want


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=40, help="몇 행을 볼까 (기본 40)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--ids", nargs="*", default=None)
    ap.add_argument("--show", action="store_true", help="행마다 자세히")
    ap.add_argument("--test", action="store_true",
                    help="시험 몫에서만 뽑는다 (split_5k.json). 학습에 쓴 행은 안 본다")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(DATA, encoding="utf-8")))
    # 정답 IR 은 영어판에만 있다 (한국어판은 문장·라벨만 든다)
    ir_gt = {r["id"]: r["ir_gt"] for r in
             csv.DictReader(open(os.path.join(HERE, "bench", "dataset_5k.csv"),
                                 encoding="utf-8"))}
    for r in rows:
        r["ir_gt"] = ir_gt.get(r["id"], "")
    spaces, hub = load_spaces(), hub_config()

    if args.test:
        import json as _j
        keep = set(_j.load(open(os.path.join(HERE, "bench", "split_5k.json"),
                                encoding="utf-8"))["시험"])
        rows = [r for r in rows if r["id"] in keep]
        print(f"시험 몫에서만 본다 — {len(rows)}행 중에서 뽑음")
    if args.ids:
        pick = [r for r in rows if r["id"] in args.ids]
    else:
        rng = random.Random(args.seed)
        pick = rng.sample(rows, min(args.n, len(rows)))

    print("엔진 서버에 붙음" if use_engine_server() else "엔진 서버 없음 — 이 프로세스에 모델을 올린다")
    from joi.generate import generate_joi_code_ir
    from pipeline_helpers import JoiGenerationError
    from joi_slm import compare

    stat = Counter()
    t0 = time.perf_counter()
    for i, r in enumerate(pick, 1):
        devs = devices_of(spaces, r["space_id"])
        want_judge = r["expect"]
        want_targets = (r["targets"] or "").split()
        got_judge, got_targets, err, got_ir = "execute", [], "", None
        try:
            res = generate_joi_code_ir(r["command_ko"], devs, {})
            got_ir = res.get("ir")
            got_targets = sorted({d for s in (res.get("resolved") or {}).values()
                                  for d in (s.get("devices") or [])})
        except JoiGenerationError as e:
            got_judge, err = "refuse", (e.args[0] if e.args else "")
            got_ir = getattr(e, "ir", None)      # 게이트에 막혀도 IR 은 만들어졌다
            res = None
            stat["막힌이유/" + bucket(err)] += 1
        except Exception as e:                       # noqa: BLE001
            got_judge, err = "error", f"{type(e).__name__}: {e}"
            res = None

        # 정답 IR 과 견준다 — 게이트에 막혀도 Stage 1 이 맞았는지는 따로 봐야 한다
        if r["ir_gt"] and res is not None or (r["ir_gt"] and got_ir is not None):
            pass
        if r["ir_gt"] and got_ir is not None:
            v = compare.verdict(got_ir, json.loads(r["ir_gt"]))
            stat["IR잼"] += 1
            stat["IR뜻같음"] += bool(v.get("same"))
            stat["IR서비스같음"] += bool(v.get("svc"))
        ok_j = judge_ok(got_judge, want_judge)
        ok_t = score_targets(got_targets, want_targets)
        stat["행"] += 1
        stat["판정맞음"] += bool(ok_j)
        if ok_t is not None:
            stat["대상잼"] += 1
            stat["대상맞음"] += bool(ok_t)
        stat[f"정답={want_judge}"] += 1
        stat[f"낸것={got_judge}"] += 1

        if args.show or not ok_j:
            print(f"[{i:3d}] {r['id']} {r['space_id']:8s} 정답={want_judge:7s} 낸것={got_judge:7s} "
                  f"{'○' if ok_j else '✗'}")
            print(f"      {r['command_ko'][:70]}")
            if err:
                print(f"      막힌 이유: {err[:90]}")

    dt = time.perf_counter() - t0
    print("\n" + "─" * 60)
    print(f"본 행 {stat['행']}  ({dt:.0f}초, 한 행 {dt/max(1,stat['행']):.1f}초)")
    print(f"판정  {stat['판정맞음']}/{stat['행']}   (되묻기는 중복정답 — 되물어도 다 해도 맞음)")
    if stat["대상잼"]:
        print(f"대상  {stat['대상맞음']}/{stat['대상잼']}")
    if stat["IR잼"]:
        print(f"IR    {stat['IR뜻같음']}/{stat['IR잼']} 뜻이 같음  "
              f"(서비스만 같음 {stat['IR서비스같음']}/{stat['IR잼']})")
    stuck = {k.split("/", 1)[1]: v for k, v in stat.items() if k.startswith("막힌이유/")}
    if stuck:
        print("막힌 이유:", dict(sorted(stuck.items(), key=lambda x: -x[1])))
    print("정답 분포:", {k[3:]: v for k, v in stat.items() if k.startswith("정답=")})
    print("낸 것    :", {k[3:]: v for k, v in stat.items() if k.startswith("낸것=")})


if __name__ == "__main__":
    sys.exit(main() or 0)
