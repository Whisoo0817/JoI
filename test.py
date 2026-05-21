"""Local test entry point for generate_joi_code.

Modes:
    python3 test.py target   # run full pipeline on test_targets indices
    python3 test.py pre      # run translation + pre_analysis ONLY on test_targets
    python3 test.py custom   # run a single CUSTOM_COMMAND interactively

When run with `target` or `pre`, all stdout is mirrored to a timestamped log file in /tmp.
The path is printed at start and end so the caller can grep / tail it.
"""

import os
import re
import sys
import time
import pandas as pd

from config import get_client, get_model_id
from loader import PROMPTS
from paper.run_local_ir import generate_joi_code
from pipeline_helpers import run_llm_inference

# [MODE: target | pre] 테스트할 타겟 지정 (python3 test.py target | pre)
# Keys are category_v2 (e.g., "C01"..."C18"). Values: list of indices, or None for all rows in that category.
test_targets = {
    # IR-only batch failures (350-row run, 2026-05-21 evening). 22 cases.
    # See /tmp/joi_ir_grade.json for full bug-type breakdown.
    "C01": [9, 10, 14],          # 3× pipeline-error: timeline[0]!=start_at
    "C03": [30],                  # 1× C03 "if" got cycle
    "C06": [1, 5],                # 2× pipeline-error: service_not_in_devices
    "C07": [15, 18, 24],          # 3× "when" NL got cycle / edge=rising
    "C15": [15],                  # 1× pipeline-error: multi-cron rejected
    "C16": [5],                   # 1× pipeline-error: multi-cron rejected
    "C17": [2, 3, 8, 9],          # 4× "every <period>" got noncycle
    "C18": [5],                   # 1× C18 missing cycle
    "C19": [1, 2, 3, 6],          # 4× hysteresis collapsed to one-shot
    "C21": [1, 3],                # 2× "either/or" / "both/and" lost in cond
}


class _Tee:
    """Write to multiple streams (e.g. real stdout + log file) at once."""
    def __init__(self, *streams):
        self._streams = streams
    def write(self, data):
        for s in self._streams:
            try:
                s.write(data)
                s.flush()
            except Exception:
                pass
    def flush(self):
        for s in self._streams:
            try:
                s.flush()
            except Exception:
                pass

# [MODE: custom] 직접 입력 테스트 데이터 (python3 test.py custom)
# Sector2에 WindowCovering(Window+Blind) + Door 함께 두고 "everything in Sector2" 시 답이 어떻게 갈리는지 검증
CUSTOM_COMMAND = "거실 조명 색깔을 보라색으로 바꿔줘."

CUSTOM_DEVICES = {
    "LR_Light": {"category": ["Light"], "tags": ["LivingRoom", "Light"]},
}

csv_file_path = 'dataset_migration/local_dataset2.csv'


def print_result(result):
    log = result.get('log', {})
    if log.get('logs'):
        print(f"{log.get('logs', '')}")
    print("\n⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️\n")
    precision = result.get('precision')
    if precision:
        print("\n[Selectors]")
        for svc, sel_list in precision.items():
            print(f"  {svc}: {sel_list}")
    # if result.get('ir_readable'):
    #     print(f"\n[IR Readable]\n{result['ir_readable']}")
    print(f"\ncode           :\n{result.get('code', '')}")
    print(f"response_time  : {log.get('response_time', '')}")


def run_targeted_test(df):
    print("\n🎯 Running Targeted Tests...")
    for category, indices in test_targets.items():
        print(f"--- Category {category} ---")
        sub = df[df['category_v2'] == category]
        if indices is None:
            indices = sorted(sub['index'].tolist())
        for idx in indices:
            match = sub[sub['index'] == idx]
            if match.empty:
                print(f"(Idx {idx}) - Not Found")
                continue
            row = match.iloc[0]
            kor = row['command_kor']
            eng = row['command_eng']
            print(f"({idx}) 🛑 {kor}\n 🛑 {eng}")
            print(f"[connected_devices]\n{row['connected_devices']}")
            try:
                result = generate_joi_code(eng, row['connected_devices'], {})
                print_result(result)
            except Exception as e:
                print(f"Error at Idx {idx}: {e}")
                logs = getattr(e, 'logs', '')
                if logs:
                    print(f"[logs]\n{logs}")


def run_pre_analysis_only(df):
    """Translation + pre_analysis only. No service_plan, no precision, no IR."""
    print("\n🔍 Running Pre-Analysis Only...")
    client = get_client()
    model = get_model_id(client)

    def infer(key, user_input):
        sys_content = PROMPTS.get(key, "")
        content, log_line = run_llm_inference(model, client, key, [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": user_input},
        ])
        return content, log_line

    for category, indices in test_targets.items():
        print(f"--- Category {category} ---")
        sub = df[df['category_v2'] == category]
        if indices is None:
            indices = sorted(sub['index'].tolist())
        for idx in indices:
            match = sub[sub['index'] == idx]
            if match.empty:
                print(f"(Idx {idx}) - Not Found")
                continue
            row = match.iloc[0]
            kor = row['command_kor']
            eng = row['command_eng']
            print(f"\n({idx}) 🛑 {kor}")
            print(f"     ENG: {eng}")
            t0 = time.perf_counter()
            try:
                sentence = eng
                logs = []
                pre, log_line = infer("pre_analysis", f"[Command]\n{sentence}")
                logs.append(log_line)
                elapsed = time.perf_counter() - t0
                print(f"\n[pre_analysis]\n{pre}")
                print(f"\n[stage timings]")
                for line in logs:
                    head = line.split("\n", 1)[0]
                    print(f"  {head}")
                print(f"[total: {elapsed:.2f}s]")
            except Exception as e:
                elapsed = time.perf_counter() - t0
                print(f"Error at Idx {idx} after {elapsed:.2f}s: {e}")


def run_custom_test():
    print("\n🛠️ Running Custom Test...")
    print(f"Command: {CUSTOM_COMMAND}")
    print(f"[connected_devices]\n{CUSTOM_DEVICES}")
    try:
        result = generate_joi_code(CUSTOM_COMMAND, CUSTOM_DEVICES, {})
        print_result(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")
        logs = getattr(e, 'logs', '')
        if logs:
            print(f"[logs]\n{logs}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "custom"

    if mode in ("target", "pre"):
        log_path = f"/tmp/joi_{mode}_{time.strftime('%Y%m%d_%H%M%S')}.log"
        log_fh = open(log_path, "w", encoding="utf-8")
        original_stdout = sys.stdout
        sys.stdout = _Tee(original_stdout, log_fh)
        try:
            print(f"📁 Log file: {log_path}")
            df = pd.read_csv(csv_file_path, encoding='utf-8-sig')
            if mode == "target":
                run_targeted_test(df)
            else:
                run_pre_analysis_only(df)
            print(f"\n📁 Log file: {log_path}")
        except Exception as e:
            print(f"CSV Load Error: {e}")
        finally:
            sys.stdout = original_stdout
            log_fh.close()
            print(f"\n✅ Done. Log saved to: {log_path}")
    elif mode == "custom":
        run_custom_test()
    else:
        print("Usage: python3 test.py [target | pre | custom]")
