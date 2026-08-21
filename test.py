# -*- coding: utf-8 -*-
"""test.py — 데이터셋 카테고리를 골라 파이프라인 단계별 결과를 본다.

2B 한 대(engine.py)로 절 나누기 → 그래프 정리 → 서비스 후보 → Timeline IR 을 만들고,
이어서 기기 고르기·수량·셀렉터(바인딩)까지 보여준다. 정답(ir_gt, binding_gt)이 있으면 나란히 댄다.

채점은 joi_slm/compare.py 기준 — "뜻이 같다"(변수 이름·괄호·말 문구 표기는 눈감음)를 본 점수로 쓰고,
"말 문구까지"·"글자까지 같다"를 괄호 안에 함께 적는다.

    ~/temp/bin/python test.py                 # 카테고리 목록
    ~/temp/bin/python test.py C01             # C01 전부
    ~/temp/bin/python test.py C01 -n 5        # 앞 5개만
    ~/temp/bin/python test.py C01 -i 3 7      # 그 카테고리의 index 3, 7 만
    ~/temp/bin/python test.py C01 --code      # 코드 생성(lowering·이름)까지
    ~/temp/bin/python test.py C01 --no-gates  # 객관식 게이트 끄고 head 만

엔진 서버(engine_server.py)가 떠 있으면 알아서 붙는다(모델 적재 38초가 사라진다). 아무것도 안 적어도 된다.
서버가 없으면 이 프로세스에 모델을 올린다. 다른 곳에 띄웠으면 아래 ENGINE_URL 만 고치거나
JOI_ENGINE_URL 을 주면 되고, 서버를 쓰기 싫으면 --no-server.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from joi_slm import compare

ENGINE_URL = "http://localhost:49998"      # 엔진 서버(engine_server.py) 주소. 안 떠 있으면 그냥 무시된다


def use_engine_server(url=None):
    """엔진 서버가 살아 있으면 거기에 붙는다 → True. 없으면 이 프로세스에 모델을 올린다 → False."""
    import urllib.request
    url = url or os.environ.get("JOI_ENGINE_URL") or ENGINE_URL
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=1.5) as r:
            if r.status != 200: return False
    except Exception:
        return False
    os.environ["JOI_ENGINE_URL"] = url
    return True


DATASET = os.path.join(HERE, "dataset.csv")
BINDING_CSV = os.path.join(HERE, "slm", "experiments", "map", "dataset_paper.csv")

BAR = "═" * 78
SUB = "─" * 78


# ── 데이터 읽기 ────────────────────────────────────────────────────────────
def load_rows():
    """dataset.csv + (명령이 같을 때만) dataset_paper.csv 의 binding_gt 를 붙인다."""
    rows = list(csv.DictReader(open(DATASET, encoding="utf-8")))
    binding = {}
    if os.path.exists(BINDING_CSV):
        for r in csv.DictReader(open(BINDING_CSV, encoding="utf-8")):
            binding[(r["category_v2"], r["index"], r["command_kor"].strip())] = r.get("binding_gt", "")
    for r in rows:
        r["binding_gt"] = binding.get(
            (r["category_v2"], r["index"], r["command_kor"].strip()), "")
    return rows


def show_categories(rows):
    cnt = Counter(r["category_v2"] for r in rows)
    print(f"■ dataset.csv {len(rows)}행 / 카테고리 {len(cnt)}종\n")
    for cat in sorted(cnt):
        sample = next(r["command_kor"] for r in rows if r["category_v2"] == cat)
        print(f"  {cat}  {cnt[cat]:>3}행   예: {sample[:52]}")
    print("\n  사용법: ~/temp/bin/python test.py C01 [-n 5] [-i 3 7] [--code]")


def jload(s, default=None):
    try:
        return json.loads(s) if s else (default if default is not None else {})
    except Exception:
        return default if default is not None else {}


# ── 보기 좋게 찍기 ─────────────────────────────────────────────────────────
def show_devices(devs):
    print(f"연결 기기 {len(devs)}대")
    for did, info in devs.items():
        cats = "/".join(info.get("category", []))
        tags = [t for t in info.get("tags", []) if t != did and t not in info.get("category", [])]
        nick = info.get("nickname", "")
        nick = f' "{nick}"' if nick else ""
        print(f"   · {did}{nick}  [{cats}]" + (f"  태그 {tags}" if tags else ""))


def show_segments(segs, title):
    print(f"\n{title}")
    for s in segs:
        mods = s.get("mods")
        mods = f"  mods={mods}" if mods else ""
        p = s.get("p")
        p = f"  p={p:.2f}" if isinstance(p, float) else ""
        print(f"   {s['j']}. [{s['type']:<5}] {s['text']}{mods}{p}")


def show_graph(gd, final_segs, raw_segs):
    print("\n[2단계] 그래프 정리 (필러 탈락·참조 이동·후치 절 앞으로)")
    order_before = [s["j"] for s in raw_segs]
    order_after = [s["j"] for s in final_segs]
    if gd:
        role, prob = gd.get("role") or [], gd.get("p") or []
        if role:
            print("   절 역할: " + "  ".join(
                f"{j}={r}" + (f"({prob[j]:.2f})" if j < len(prob) else "")
                for j, r in enumerate(role)))
        parent = gd.get("parent") or []
        deps = [f"{i}←{pj}" for i, pj in enumerate(parent) if pj not in (-1, None)]
        if deps:
            print("   딸린 절: " + "  ".join(deps))
        if gd.get("anchors"):
            print(f"   참조 절: {gd['anchors']}")
        if gd.get("drop"):
            print(f"   버린 절: {sorted(gd['drop'])}")
        if gd.get("moved"):
            print(f"   옮긴 절: {gd['moved']}")
    if order_before != order_after:
        print(f"   절 순서: {order_before} → {order_after}")
    elif not (gd and (gd.get("drop") or gd.get("moved"))):
        print("   (순서·구성 그대로)")


def show_mapping(M, segs_by_j):
    print("\n[3단계] 서비스 후보 (임베딩 매핑, 연결 카테고리로 거름)")
    if not M.r and not M.p:
        print("   (후보 없음)")
    for j in sorted(M.r):
        cands = M.r[j]
        text = segs_by_j.get(j, "")
        top = cands[0] if cands else "(없음)"
        rest = ", ".join(cands[1:5])
        print(f"   절{j} \"{text}\"")
        print(f"       → {top}" + (f"   (다음 후보: {rest})" if rest else ""))
    for j in sorted(M.p):
        for item in M.p[j]:
            top = item["ranked"][0] if item["ranked"] else "(없음)"
            rest = ", ".join(item["ranked"][1:4])
            print(f"   절{j} 조건조각 \"{item['part']}\"")
            print(f"       → {top}" + (f"   (다음 후보: {rest})" if rest else ""))


def services_of(ir):
    return sorted(set(re.findall(r"\b([A-Z][A-Za-z]+\.[A-Za-z0-9]+)", json.dumps(ir, ensure_ascii=False))))


def show_ir(ir, title="[4단계] Timeline IR"):
    print(f"\n{title}")
    for line in json.dumps(ir, ensure_ascii=False, indent=2).split("\n"):
        print("   " + line)


def gt_devices(binding, cat, used):
    """binding_gt 에서 cat(또는 cat#2 …) 자리를 순서대로 하나 꺼낸다 → (기기집합, 수량어)."""
    for k in [cat] + [f"{cat}#{n}" for n in range(2, 6)]:
        if k in binding and k not in used:
            used.add(k)
            v = binding[k]
            if isinstance(v, dict):
                q = "any" if "any" in v else ("all" if "all" in v else "")
                return set(v.get("any") or v.get("all") or []), q
            return set(v), ""
    return None, ""


def show_binding(selection, binding_gt):
    print("\n[5단계] 기기 고르기 + 수량 + 셀렉터  (joi/devices.py)")
    if selection["swaps"]:
        print("   능력 검사 교체: " + ", ".join(f"{a} → {b}" for a, b in selection["swaps"]))
    resolved = selection["resolved"]
    if not resolved:
        print("   (기기가 붙는 서비스 없음)")
    used, hit, tot = set(), 0, 0
    def gt_line(info):
        nonlocal hit, tot
        if not binding_gt: return
        gt, gq = gt_devices(binding_gt, svc.split(".", 1)[0], used)
        if gt is None: return
        tot += 1
        ok = gt == set(info["devices"])
        hit += ok
        extra = f"   수량 정답={gq} {'✅' if gq == info['q'] else '❌'}" if gq else ""
        print(f"       정답    : {'✅' if ok else '❌'} {sorted(gt)}{extra}")
    for svc, info in resolved.items():
        sel = " / ".join(selection["selectors"].get(svc, []))
        print(f"   {svc}")
        if info.get("slots"):                       # 같은 서비스가 조건에 여러 번 → 자리마다 따로
            print(f"       자리 {len(info['slots'])}개 (같은 서비스가 여러 번 나옴 — 자리마다 따로 고름)")
            for k, si in enumerate(info["slots"], 1):
                print(f"     #{k} 근거 조각: \"{si['text']}\"")
                print(f"       수량    : {si['q']}   기기: {si['devices']}   셀렉터: {si['selector']}")
                gt_line(si)
            continue
        print(f"       근거 절 : \"{info['text']}\"")
        print(f"       수량    : {info['q']}")
        print(f"       기기    : {info['devices']}")
        print(f"       태그    : {info['tags']}")
        print(f"       셀렉터  : {sel}")
        gt_line(info)
    return hit, tot


def show_gt(ir, ir_gt):
    print("\n[정답 대조] ir_gt")
    if not ir_gt:
        print("   (정답 없음)")
        return {}
    v = compare.verdict(ir, ir_gt)
    got, want = services_of(ir), services_of(ir_gt)
    print(f"   뜻이 같다     : {'✅' if v['same'] else '❌'}   (변수 이름·괄호·말 문구 표기는 눈감고 본 것)")
    print(f"   말 문구까지   : {'✅' if v['text'] else '❌'}")
    print(f"   글자까지 같다 : {'✅' if v['strict'] else '❌'}")
    print(f"   서비스 일치   : {'✅' if v['svc'] else '❌'}  예측={got}  정답={want}")
    if not v["same"]:
        for line in json.dumps(ir_gt, ensure_ascii=False, indent=2).split("\n"):
            print("   │ " + line)
    return v


# ── 한 줄(시나리오) 돌리기 ─────────────────────────────────────────────────
def run_row(row, pipe, build, build_selectors, MissingDevices, want_code):
    devs = jload(row["connected_devices"], {})
    cmd = row["command_kor"]
    print(f"\n{BAR}\n▶ {row['category_v2']} #{row['index']}   {cmd}\n{BAR}")
    show_devices(devs)
    if row.get("notes"):
        print(f"메모: {row['notes']}")
    print(SUB)

    stat = {"same": None, "text": None, "strict": None, "svc": None, "dev_hit": 0, "dev_tot": 0, "error": None}

    # ── 1~4단계: 명령 → Timeline IR (2B 단어상태 + head, LLM 생성 없음)
    t0 = time.perf_counter()
    try:
        segs = pipe.seg(cmd.strip())
    except Exception as e:
        print(f"⛔ 절 나누기 실패: {type(e).__name__}: {e}")
        stat["error"] = "seg"
        return stat
    t_seg = time.perf_counter() - t0
    raw_segs = [{k: v for k, v in s.items() if k != "h6"} for s in segs]
    show_segments(raw_segs, f"[1단계] 절 나누기 ({t_seg:.2f}s)")

    t0 = time.perf_counter()
    M = pipe.map(segs, devs)
    t_map = time.perf_counter() - t0

    t0 = time.perf_counter()
    ir = build(segs, M)
    t_build = time.perf_counter() - t0
    final_segs = [{k: v for k, v in s.items() if k != "h6"} for s in build.last["segments"]]

    show_graph(build.last.get("graph"), final_segs, raw_segs)
    if [s["j"] for s in final_segs] != [s["j"] for s in raw_segs]:
        show_segments(final_segs, "   정리 후 절 순서")
    print(f"\n   (매핑 {t_map:.2f}s, 조립 {t_build:.2f}s)")
    show_mapping(M, {s["j"]: s["text"] for s in raw_segs})
    show_ir(ir)

    slm_out = {"ir": ir, "segments": final_segs,
               "mapping": {"ranked": M.r, "parts": M.p}, "graph": build.last.get("graph")}

    # ── 5단계: 기기 고르기 + 수량 + 셀렉터
    binding_gt = jload(row.get("binding_gt", ""), {})
    try:
        selection = build_selectors(ir, devs, slm_out)
    except MissingDevices as e:
        print(f"\n[5단계] ⛔ 붙일 기기가 없음: {e}")
        selection = None
        stat["error"] = "no_device"
    if selection:
        ir = selection["ir"]
        hit, tot = show_binding(selection, binding_gt)
        stat["dev_hit"], stat["dev_tot"] = hit, tot
        if binding_gt and not tot:
            print("   (정답 자리와 서비스가 안 맞아 기기 대조 못 함)")
    elif binding_gt:
        print(f"   바인딩 정답: {json.dumps(binding_gt, ensure_ascii=False)}")

    stat.update(show_gt(ir, jload(row.get("ir_gt", ""), None)))

    # ── 6단계(선택): 코드 생성
    if want_code:
        print("\n[6단계] JoI 코드 (lowering)")
        from joi import generate_joi_code
        try:
            t0 = time.perf_counter()
            result = generate_joi_code(cmd, devs, {})
            code = result.get("code", "")
            code = code if isinstance(code, str) else json.dumps(code, ensure_ascii=False)
            for line in code.replace("\\n", "\n").split("\n"):
                print("   " + line)
            g = result.get("gate") or {}
            if g.get("verdict"):
                print(f"   🚧 게이트: {g['verdict']}  {g.get('note', '')}".rstrip()
                      + f"  (lowering={result.get('lowering', '?')})")
            print(f"   ({time.perf_counter() - t0:.2f}s)")
            stat["gate"] = g.get("verdict", "")
        except Exception as e:
            jj = getattr(e, "joi_json", None)
            if jj:  # 게이트가 거절했어도 만든 코드는 보여준다
                for line in json.dumps(jj, indent=2, ensure_ascii=False).replace("\\n", "\n").split("\n"):
                    print("   " + line)
                g = getattr(e, "gate", {}) or {}
                print(f"   🚧 게이트: {g.get('verdict', '?')}  {g.get('note', '')}".rstrip() + "  → 거절")
            else:
                print(f"   ⛔ {type(e).__name__}: {e}")
            stat["gate"] = getattr(e, "error_code", "") or type(e).__name__
        if row.get("joi_code"):
            print("\n   ── 정답 코드 ──")
            for line in row["joi_code"].replace("\\n", "\n").split("\n"):
                print("   │ " + line)
    return stat


def run_row_quiet(row, pipe, build, build_selectors, MissingDevices):
    """행마다 한 줄만 — 대량 측정용. run_row 와 같은 통계를 돌려준다."""
    devs = jload(row["connected_devices"], {})
    stat = {"same": None, "text": None, "strict": None, "svc": None, "dev_hit": 0, "dev_tot": 0, "error": None}
    tag = f"{row['category_v2']} #{row['index']:>3}"
    try:
        segs = pipe.seg(row["command_kor"].strip())
        M = pipe.map(segs, devs)
        ir = build(segs, M)
    except Exception as e:
        print(f"{tag}  ⛔ {type(e).__name__}: {e}")
        stat["error"] = "ir"
        return stat
    slm_out = {"ir": ir,
               "segments": [{k: v for k, v in s.items() if k != "h6"} for s in build.last["segments"]],
               "mapping": {"ranked": M.r, "parts": M.p}, "graph": build.last.get("graph")}
    binding_gt = jload(row.get("binding_gt", ""), {})
    note = ""
    try:
        sel = build_selectors(ir, devs, slm_out)
        ir = sel["ir"]
        used = set()
        for svc, info in sel["resolved"].items():
            for one in (info.get("slots") or [info]):          # 자리별로 골랐으면 자리마다 대조
                gt, gq = gt_devices(binding_gt, svc.split(".", 1)[0], used) if binding_gt else (None, "")
                if gt is not None:
                    stat["dev_tot"] += 1
                    stat["dev_hit"] += gt == set(one["devices"])
    except MissingDevices as e:
        stat["error"] = "no_device"
        note = f"  기기없음({e})"
    ir_gt = jload(row.get("ir_gt", ""), None)
    stat.update(compare.verdict(ir, ir_gt))
    mark = ("✅" if stat["same"] else ("△" if stat["svc"] else "❌")) if ir_gt else "·"
    dev = f"  기기 {stat['dev_hit']}/{stat['dev_tot']}" if stat["dev_tot"] else ""
    print(f"{tag}  {mark}{dev}  {row['command_kor'][:44]}{note}")
    return stat


def main():
    ap = argparse.ArgumentParser(description="카테고리별 시나리오 단계별 실행")
    ap.add_argument("category", nargs="*", help="카테고리 (예: C01 C07). all 이면 전부. 빼면 목록만 본다")
    ap.add_argument("-n", "--num", type=int, default=0, help="앞에서 N개만")
    ap.add_argument("-i", "--index", nargs="+", default=None, help="그 카테고리 안의 index 만")
    ap.add_argument("--code", action="store_true", help="코드 생성(lowering·이름)까지")
    ap.add_argument("--no-gates", action="store_true", help="객관식 게이트 끄고 head 만")
    ap.add_argument("-v", "--verbose", action="store_true", help="vLLM 적재 로그까지 보기")
    ap.add_argument("--no-server", action="store_true", help="엔진 서버를 쓰지 않고 이 프로세스에 모델을 올린다")
    ap.add_argument("-q", "--quiet", action="store_true", help="행마다 한 줄 + 요약만")
    args = ap.parse_args()

    rows = load_rows()
    if not args.category:
        show_categories(rows)
        return

    cats = [c.upper() for c in args.category]
    if "ALL" in cats:
        cat, picked = "전체", list(rows)
    else:
        cat = " ".join(cats)
        picked = [r for r in rows if r["category_v2"] in cats]
    if not picked:
        print(f"카테고리 {cat} 없음.\n")
        show_categories(rows)
        return
    if args.index:
        want = set(args.index)
        picked = [r for r in picked if r["index"] in want]
    if args.num:
        picked = picked[:args.num]
    if not picked:
        print("고른 조건에 맞는 행이 없음.")
        return

    if args.no_server:
        os.environ.pop("JOI_ENGINE_URL", None)
        print(f"■ {cat} {len(picked)}행 — 이 프로세스에 모델 올리는 중 …")
    elif use_engine_server():
        print(f"■ {cat} {len(picked)}행 — 엔진 서버({os.environ['JOI_ENGINE_URL']}) 에 붙음")
    else:
        print(f"■ {cat} {len(picked)}행 — 엔진 서버가 없어 이 프로세스에 모델 올리는 중 …")
    if not args.verbose:
        os.environ.setdefault("VLLM_LOGGING_LEVEL", "WARNING")
    if args.no_gates:
        os.environ["JOI_SLM_GATES"] = "0"
    from joi.generate import _slm_pipe
    from joi_slm.builder import build
    from joi.devices import build_selectors, MissingDevices
    t0 = time.perf_counter()
    pipe = _slm_pipe()
    print(f"■ 준비 완료 ({time.perf_counter() - t0:.1f}s)")

    stats = []
    for row in picked:
        if args.quiet:
            stats.append(run_row_quiet(row, pipe, build, build_selectors, MissingDevices))
        else:
            stats.append(run_row(row, pipe, build, build_selectors, MissingDevices, args.code))

    ir_n = sum(1 for s in stats if s["same"] is not None)
    same_ok = sum(1 for s in stats if s["same"])
    text_ok = sum(1 for s in stats if s["text"])
    strict_ok = sum(1 for s in stats if s["strict"])
    svc_ok = sum(1 for s in stats if s["svc"])
    dev_hit = sum(s["dev_hit"] for s in stats)
    dev_tot = sum(s["dev_tot"] for s in stats)
    err = Counter(s["error"] for s in stats if s["error"])
    print(f"\n{BAR}\n■ {cat} 요약 — {len(stats)}행")
    if ir_n:
        print(f"   뜻이 같다   {same_ok}/{ir_n}   (말 문구까지 {text_ok}, 글자까지 {strict_ok})")
        print(f"   서비스 일치 {svc_ok}/{ir_n}")
    if dev_tot:
        print(f"   기기 일치   {dev_hit}/{dev_tot} 자리 (binding 정답 있는 것만)")
    if err:
        print(f"   실패        {dict(err)}")
    gates = Counter(s.get("gate") for s in stats if s.get("gate"))
    if gates:
        print(f"   코드 게이트 {dict(gates)}")
    print(BAR)


if __name__ == "__main__":
    main()
