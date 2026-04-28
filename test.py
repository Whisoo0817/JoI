"""Local test entry point for generate_joi_code.

Modes:
    python3 test.py target   # run targeted indices from local_dataset.csv
    python3 test.py custom   # run a single CUSTOM_COMMAND interactively

When run with `target`, all stdout is mirrored to a timestamped log file in /tmp.
The path is printed at start and end so the caller can grep / tail it.
"""

import os
import sys
import time
import pandas as pd

from paper.run_local_ir import generate_joi_code

# [MODE: target] 테스트할 타겟 지정 (python3 test.py target)
# Keys are category_v2 (e.g., "C01"..."C18"). Values: list of indices, or None for all rows in that category.
test_targets = {
    "C07": [24],
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
CUSTOM_COMMAND = "사이렌을 켜줘"

# format_connected_devices_for_joi_llm 결과 형식
# key: device name, category: skills 기반, tags: tags + predefined_tags + category_labels 머지
CUSTOM_DEVICES = {
    "tc0_af37207d-f2f2-447f-8006-f1e030755e65": {
        "category": ["MultiButton"],
        "tags": ["PhilipsHue", "tc0_af37207d-f2f2-447f-8006-f1e030755e65", "DimmerSwitch", "MultiButton", "tc0_philipshue"],
    },
    "tc0_5452b6c5-0dee-4cca-ba6f-15582b358305": {
        "category": ["Switch", "Light"],
        "tags": ["PhilipsHue", "tc0_5452b6c5-0dee-4cca-ba6f-15582b358305", "Light", "Switch", "tc0_philipshue"],
    },
    "tc0_9fe5d8b9-9ebc-4203-9963-497546c9740d": {
        "category": ["Switch", "Light"],
        "tags": ["PhilipsHue", "tc0_9fe5d8b9-9ebc-4203-9963-497546c9740d", "Light", "Switch", "tc0_philipshue"],
    },
    "tc0_7def1d9d-721c-4e35-b217-51fb8b46ba59": {
        "category": ["Switch", "Light"],
        "tags": ["PhilipsHue", "tc0_7def1d9d-721c-4e35-b217-51fb8b46ba59", "Light", "Switch", "tc0_philipshue"],
    },
    "tc0_a2e7594e-aced-4e03-a25e-841aa7315614": {
        "category": ["Switch", "Light"],
        "tags": ["PhilipsHue", "tc0_a2e7594e-aced-4e03-a25e-841aa7315614", "Light", "Switch", "tc0_philipshue"],
    },
    "tc0_ebf02f5cfcd67e4ce4bexu": {
        "category": ["Switch", "AirConditioner", "TemperatureSensor"],
        "tags": ["Hejhome", "tc0_ebf02f5cfcd67e4ce4bexu", "AirConditioner", "Switch", "TemperatureSensor", "tc0_local"],
    },
    "tc0_eba69f1846b797f9a72gis": {
        "category": ["Switch"],
        "tags": ["Hejhome", "tc0_eba69f1846b797f9a72gis", "Siren", "Switch", "tc0_local"],
    },
    "tc0_ebd382239e6a6e4a29lccz": {
        "category": ["Switch"],
        "tags": ["Hejhome", "tc0_ebd382239e6a6e4a29lccz", "Switch", "tc0_local"],
    },
}

csv_file_path = 'dataset_migration/local_dataset2.csv'


def print_result(result):
    log = result.get('log', {})
    if log.get('logs'):
        print(f"{log.get('logs', '')}")
    print("\n⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️\n")
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

    if mode == "target":
        log_path = f"/tmp/joi_test_{time.strftime('%Y%m%d_%H%M%S')}.log"
        log_fh = open(log_path, "w", encoding="utf-8")
        original_stdout = sys.stdout
        sys.stdout = _Tee(original_stdout, log_fh)
        try:
            print(f"📁 Log file: {log_path}")
            df = pd.read_csv(csv_file_path, encoding='utf-8-sig')
            run_targeted_test(df)
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
        print("Usage: python3 test.py [target | custom]")
