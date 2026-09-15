"""E3 하네스 — 확인된 IR × LLM lowering 후보를 게이트로 판정 (382행).

두 단계로 나뉜다 (생성은 몇 시간, 판정은 몇 분):

  python -m explorer.eval.e3 gen  [--limit N] [--cat C01,C02] [--workers K]
      dataset.csv 각 행에 대해 확인된 IR(ir_gt)과 binding(binding_gt)을 주입하고
      자연어 매핑을 생략한 채 lowering만 LLM으로 돌려 후보 JoI를 만든다.
      결과는 explorer/candidates/<모델태그>/<행키>.json — 이미 있으면
      건너뛰므로 중단 후 재실행해도 이어진다.

  python -m explorer.eval.e3 gate [--tag 모델태그]
      후보 전부를 explorer.verification.gate.gate_pair로 판정(EQUIV/DIVERGE(재생 확인)/
      REFUSED) → 분포 + explorer/runs/e3.md.

측정 구도(§6 E3): 확인된 IR과 binding을 직접 주입하고 lowering만 LLM으로
수행한다. service prefix는 확인된 IR–selector 대응으로 결정한다.
모델 원문과 최종 코드를 trace에 보존한다. 네이밍은 JOI_SKIP_NAME=1로 끈다.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CAND_BASE = os.path.join(ROOT, "explorer", "candidates")
E3_EXPECTED_CASES = 382
E3_SELECTION_RULE = "confirmed IR/binding rows excluding any IR containing timeout or on_timeout"


def has_timeout(value) -> bool:
    """Exclude the entire timeout feature, independently of candidate outcomes."""
    if isinstance(value, dict):
        return ('timeout' in value or 'on_timeout' in value
                or any(has_timeout(v) for v in value.values()))
    if isinstance(value, list):
        return any(has_timeout(v) for v in value)
    return False

# 행별 작업 프로세스: env 격리 + 파이프라인 크래시 격리.
WORKER = r"""
import os, sys, json, re
sys.path.insert(0, os.environ['JOI_ROOT'])
from lowering.run_local_ir import generate_joi_code, JoiGenerationError
cmd, devs, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    r = generate_joi_code(cmd, devs, {})
    code = r.get('code') or ''
    try:
        # script 필드의 진짜 개행만 \n으로 되감아 dict로 파싱. 따옴표·역슬래시는
        # pretty 단계에서 escape가 안 풀렸으므로 그대로 둔다. escape 쌍(\\.)을
        # 원자로 매칭해 \" 앞에서 일찍 끊기지 않게 한다.
        packed = re.sub(
            r'("script"\s*:\s*")((?:[^"\\]|\\.)*)(")',
            lambda m: m.group(1) + m.group(2).replace('\n', '\\n') + m.group(3),
            code, count=1, flags=re.DOTALL,
        )
        joi_block = json.loads(packed)
    except Exception:
        joi_block = None
    out = {'status': 'ok', 'joi_block': joi_block, 'code': code,
           'precision': r.get('precision'),
           'precision_reasoning': r.get('precision_reasoning'),
           'trace_path': r.get('trace_path')}
except JoiGenerationError as e:
    out = {'status': 'error', 'error_code': getattr(e, 'error_code', 'unknown'),
           'error_msg': str(e)[:600]}
except Exception as e:
    out = {'status': 'error', 'error_code': 'exception',
           'error_msg': f'{type(e).__name__}: {str(e)[:600]}'}
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
"""


def load_rows() -> list[dict]:
    rows = []
    with open(os.path.join(ROOT, "dataset.csv"), encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cat = (r.get("category_v2") or "").strip()
            if not cat or not (r.get("ir_gt") or "").strip():
                continue
            if has_timeout(json.loads(r['ir_gt'])):
                continue
            rows.append(r)
    return rows


def key_of(r: dict) -> str:
    return f'{r["category_v2"]}_{int(float(r["index"])):03d}'


def row_payload(r: dict) -> dict:
    return {
        "command_kor": r["command_kor"],
        "command_eng": r["command_eng"],
        "connected_devices": json.loads(r["connected_devices"]),
        "ir": json.loads(r["ir_gt"]),
        "binding": json.loads(r.get("binding_gt") or "{}"),
    }


def payload_sha256(payload: dict) -> str:
    packed = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(packed).hexdigest()


def candidate_matches_row(candidate: dict, row: dict) -> bool:
    payload = row_payload(row)
    return (candidate.get("input_payload_sha256") == payload_sha256(payload)
            and candidate.get("ir") == payload["ir"]
            and candidate.get("binding") == payload["binding"]
            and candidate.get("connected_devices") == payload["connected_devices"]
            and candidate.get("command_kor") == payload["command_kor"]
            and candidate.get("command_eng") == payload["command_eng"])


def parse_generated_code(code: str) -> dict | None:
    """Parse pipeline pretty JSON whose script contains literal newlines."""
    try:
        packed = __import__("re").sub(
            r'("script"\s*:\s*")((?:[^"\\]|\\.)*)(")',
            lambda m: m.group(1) + m.group(2).replace("\n", "\\n") + m.group(3),
            code, count=1, flags=__import__("re").DOTALL)
        value = json.loads(packed)
        return value if isinstance(value, dict) else None
    except Exception:
        return None


def model_tag() -> str:
    from timeline_ir.config import get_client, get_model_id
    mid = get_model_id(get_client())
    return mid.rsplit("/", 1)[-1].lower().replace(".", "_")


def active_model_id() -> str:
    """Exact server model ID; unlike ``--tag``, this is provenance."""
    from timeline_ir.config import get_client, get_model_id
    return get_model_id(get_client())


def candidate_manifest(tag: str, output: str) -> None:
    """Seal one terminal generation artifact per current E3 row."""
    rows = sorted(load_rows(), key=key_of)
    base = os.path.join(CAND_BASE, tag)
    records, errors = [], []
    for row in rows:
        key = key_of(row)
        path = os.path.join(base, key + ".json")
        record = {"id": key, "path": path}
        if not os.path.exists(path):
            record.update(status="MISSING")
            errors.append(key + ": missing")
        else:
            raw = open(path, "rb").read()
            record["sha256"] = hashlib.sha256(raw).hexdigest()
            try:
                candidate = json.loads(raw)
                record["status"] = ("GENERATED" if candidate.get("status") == "ok"
                                    and isinstance(candidate.get("joi_block"), dict)
                                    else "GENERATION_ERROR")
                record["error_code"] = candidate.get("error_code")
                record["model"] = candidate.get("model")
                record["input_payload_sha256"] = candidate.get("input_payload_sha256")
                if not candidate_matches_row(candidate, row):
                    errors.append(key + ": payload mismatch")
            except Exception as exc:
                record.update(status="UNREADABLE", error=f"{type(exc).__name__}: {exc}")
                errors.append(key + ": unreadable")
        records.append(record)
    manifest = {
        "schema": "e3-candidate-manifest-v1", "candidate_tag": tag,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "expected": E3_EXPECTED_CASES, "records": records, "errors": errors,
        "selection_rule": E3_SELECTION_RULE,
        "complete": len(records) == E3_EXPECTED_CASES and not errors,
    }
    with open(output, "x", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"records": len(records), "errors": len(errors),
                      "complete": manifest["complete"]}, ensure_ascii=False))
    if not manifest["complete"]:
        raise SystemExit(1)


def gen(args) -> None:
    model_id = active_model_id()
    tag = args.tag or model_id.rsplit("/", 1)[-1].lower().replace(".", "_")
    out_dir = os.path.join(CAND_BASE, tag)
    os.makedirs(out_dir, exist_ok=True)
    gt_dir = os.path.join(out_dir, "_gt_ir")
    os.makedirs(gt_dir, exist_ok=True)
    binding_dir = os.path.join(out_dir, "_gt_binding")
    os.makedirs(binding_dir, exist_ok=True)

    rows = load_rows()
    if args.cat:
        want = {c.strip() for c in args.cat.split(",")}
        rows = [r for r in rows if r["category_v2"] in want]
    if args.limit:
        rows = rows[: args.limit]
    todo = []
    mismatches = []
    for r in rows:
        path = os.path.join(out_dir, key_of(r) + ".json")
        if not os.path.exists(path):
            todo.append(r)
            continue
        try:
            existing = json.load(open(path, encoding="utf-8"))
        except Exception:
            mismatches.append(key_of(r) + ": unreadable candidate")
            continue
        if not candidate_matches_row(existing, r):
            mismatches.append(key_of(r) + ": current row payload differs")
    if mismatches:
        raise RuntimeError(
            "candidate reuse rejected; choose a fresh tag or restore matching inputs: "
            + "; ".join(mismatches[:20])
        )
    print(f"[e3 gen] 모델 {model_id} | tag={tag} | 대상 {len(rows)}행, "
          f"남은 {len(todo)}행, workers={args.workers}")

    def one(r):
        key = key_of(r)
        gt_path = os.path.join(gt_dir, key + ".json")
        with open(gt_path, "w", encoding="utf-8") as f:
            json.dump(json.loads(r["ir_gt"]), f, ensure_ascii=False)
        binding_path = os.path.join(binding_dir, key + ".json")
        with open(binding_path, "w", encoding="utf-8") as f:
            json.dump(json.loads(r.get("binding_gt") or "{}"), f, ensure_ascii=False)
        out_path = os.path.join(out_dir, key + ".json")
        env = os.environ.copy()
        env.update(JOI_ROOT=ROOT, JOI_SKIP_NAME="1", JOI_TRACE="1",
                   JOI_GT_IR_PATH=gt_path, JOI_GT_BINDING_PATH=binding_path)
        env.pop("JOI_IR_ONLY", None)
        t0 = time.perf_counter()
        try:
            # 입력은 한국어 원문 — 매핑(제약 추출)은 한국어 명령 전제이고,
            # 영어 번역은 파이프라인 안에서 IR/lowering 단계용으로 일어난다
            # (허브 제품 흐름과 동일).
            p = subprocess.run(
                [sys.executable, "-c", WORKER,
                 r["command_kor"], r["connected_devices"], out_path],
                env=env, capture_output=True, text=True, cwd=ROOT,
                timeout=args.timeout)
            err = "" if os.path.exists(out_path) else (p.stderr or "")[-300:]
        except subprocess.TimeoutExpired:
            err = f"timeout {args.timeout}s"
        el = time.perf_counter() - t0
        if os.path.exists(out_path):
            d = json.load(open(out_path, encoding="utf-8"))
            payload = row_payload(r)
            d.update(**payload, input_payload_sha256=payload_sha256(payload), model=model_id,
                     candidate_tag=tag,
                     elapsed_sec=round(el, 1))
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        return key, el, err

    t0 = time.perf_counter()
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(one, r): r for r in todo}
        for fut in as_completed(futs):
            key, el, err = fut.result()
            done += 1
            line = f"  [{done}/{len(todo)}] {key} ({el:.0f}s)"
            if err:
                line += f"  ⚠️ {err[:100]}"
            print(line, flush=True)
    print(f"[e3 gen] 완료 — {time.perf_counter() - t0:.0f}s")


def gate(args) -> None:
    import glob
    from collections import Counter

    from explorer.verification.gate import GateResult, gate_pair
    from explorer.diagnostics.e3_classify import classify

    tag = args.tag or model_tag()
    out_dir = os.path.join(CAND_BASE, tag)
    rows = {key_of(r): r for r in load_rows()}
    res, gen_err = Counter(), Counter()
    diverged, unconfirmed, refused = [], [], Counter()
    refused_kind = Counter()
    classes = Counter()
    lines = []
    files = sorted(glob.glob(os.path.join(out_dir, "*.json")))
    for f in files:
        key = os.path.basename(f)[:-5]
        r = rows.get(key)
        if r is None:
            continue
        d = json.load(open(f, encoding="utf-8"))
        if d.get("status") != "ok" or not isinstance(d.get("joi_block"), dict):
            code = d.get("error_code", "no_joi_block")
            gen_err[code] += 1
            res["GEN_ERROR"] += 1
            lines.append((key, "GEN_ERROR", code))
            continue
        try:
            g = gate_pair(json.loads(r["ir_gt"]),
                          json.loads(r.get("binding_gt") or "{}"),
                          json.loads(r["connected_devices"]), d["joi_block"])
        except Exception as e:
            # 후보가 JoI 문법/접지 단계에서 아예 해석 불가 — 조각 밖과 같은
            # fail-closed. 예외 내용을 비고로 남겨 따로 센다.
            g = GateResult("REFUSED", notes=[
                f"후보 해석 불가: {type(e).__name__}: {str(e)[:120]}"])
        res[g.verdict] += 1
        note = ""
        if g.verdict == "DIVERGE":
            diverged.append(key)
            cls, why = classify(json.loads(r["ir_gt"]),
                                json.loads(r.get("binding_gt") or "{}"),
                                json.loads(r["connected_devices"]),
                                d["joi_block"], key=key)
            classes[cls] += 1
            note = f"[{cls}] {why}"
            if not g.confirmed:
                unconfirmed.append(key)
                note += " (재생 미확인!)"
        if g.verdict == "REFUSED":
            note = (g.notes[-1] if g.notes else "")[:80]
            refused[note[:60]] += 1
            # 내부 4-way 구분(§9.16 fold_verdict): 정적 미지원(조각 밖)과
            # 내부 UNKNOWN(탐색 미완·재생 미확인)은 배포 행동은 같아도
            # 논문 집계에선 다른 종류다.
            joined = " ".join(g.notes)
            if "재생 미확인" in joined:
                refused_kind["내부 UNKNOWN(재생 미확인)"] += 1
            elif "내부 UNKNOWN" in joined:
                refused_kind["내부 UNKNOWN(탐색 미완)"] += 1
            else:
                refused_kind["정적 미지원(조각 밖)"] += 1
        lines.append((key, g.verdict, note))

    n = sum(res.values())
    print(f"[e3 gate] 모델 {tag} | {n}행: {dict(res)}")
    if diverged:
        print(f"DIVERGE {len(diverged)}: {diverged[:30]}")
        print(f"  그중 재생 미확인: {unconfirmed[:10] or '없음'}")
        print("  DIVERGE 분류:", dict(classes.most_common()))
    for k, v in gen_err.most_common():
        print(f"  [생성실패 {v}] {k}")
    if refused_kind:
        print("  REFUSED 내역:", dict(refused_kind.most_common()))
    for k, v in refused.most_common(10):
        print(f"  [{v}] {k}")

    os.makedirs(os.path.join(ROOT, "explorer", "runs"), exist_ok=True)
    md = os.path.join(ROOT, "explorer", "runs", "e3.md")
    with open(md, "w", encoding="utf-8") as f:
        f.write("# E3 — 게이트 분류 (확인된 IR × LLM lowering 후보)\n\n")
        f.write("판독 방침(whisoo 08-14): 수량 정책은 보류 — `집합/수량(정책)`은 "
                "통과 취급, 지금 보는 것은 로직·서비스·디바이스 매핑.\n\n")
        f.write(f"생성: `python -m explorer.eval.e3` | 모델 `{tag}` | {n}행\n\n")
        f.write("| 판정 | 행 수 |\n|---|---|\n")
        for k in ("EQUIV", "DIVERGE", "REFUSED", "GEN_ERROR"):
            if res.get(k):
                f.write(f"| {k} | {res[k]} |\n")
        if refused_kind:
            f.write("\n## REFUSED 내역 (내부 4-way, §9.16 fold_verdict)\n\n"
                    "| 종류 | 행 수 |\n|---|---|\n")
            for k, v in refused_kind.most_common():
                f.write(f"| {k} | {v} |\n")
        if classes:
            f.write("\n## DIVERGE 분류 (수량 정책은 보류 — whisoo 결정 08-14)\n\n"
                    "| 분류 | 행 수 |\n|---|---|\n")
            for k, v in classes.most_common():
                f.write(f"| {k} | {v} |\n")
        f.write("\n## 행별 판정\n\n| 행 | 판정 | 비고 |\n|---|---|---|\n")
        for key, v, note in lines:
            f.write(f"| {key} | {v} | {note} |\n")
    print(f"{md} 기록 완료")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen")
    g.add_argument("--limit", type=int, default=0)
    g.add_argument("--cat", default="")
    g.add_argument("--workers", type=int, default=2)
    g.add_argument("--timeout", type=int, default=300)
    g.add_argument("--tag", default="")
    t = sub.add_parser("gate")
    t.add_argument("--tag", default="")
    m = sub.add_parser("manifest")
    m.add_argument("--tag", required=True)
    m.add_argument("--output", required=True)
    args = ap.parse_args()
    if args.cmd == "gen":
        gen(args)
    elif args.cmd == "gate":
        gate(args)
    else:
        candidate_manifest(args.tag, args.output)


if __name__ == "__main__":
    main()
