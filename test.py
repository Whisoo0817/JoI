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
from run_local import run_llm_inference

# [MODE: target | pre] 테스트할 타겟 지정 (python3 test.py target | pre)
# Keys are category_v2 (e.g., "C01"..."C18"). Values: list of indices, or None for all rows in that category.
test_targets = {
    "C09": [13],
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
    if result.get('ir_readable'):
        print(f"\n[IR Readable]\n{result['ir_readable']}")
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
                result = generate_joi_code(kor, row['connected_devices'], {})
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
            print(f"\n({idx}) 🛑 {kor}")
            t0 = time.perf_counter()
            try:
                sentence = kor
                logs = []
                if re.search("[가-힣]", sentence):
                    sentence, log_line = infer("translation", sentence)
                    logs.append(log_line)
                print(f"     ENG: {sentence}")
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


def run_custom_test(modification=None):
    print("\n🛠️ Running Custom Test...")
    print(f"Command: {CUSTOM_COMMAND}")
    print(f"[connected_devices]\n{CUSTOM_DEVICES}")
    try:
        result = generate_joi_code(CUSTOM_COMMAND, CUSTOM_DEVICES, {}, modification=modification)
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
