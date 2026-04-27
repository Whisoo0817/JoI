"""Local test entry point for generate_joi_code.

Modes:
    python3 test.py target   # run targeted indices from local_dataset.csv
    python3 test.py custom   # run a single CUSTOM_COMMAND interactively
"""

import sys
import pandas as pd

from paper.run_local_ir import generate_joi_code

# [MODE: target] 테스트할 타겟 지정 (python3 test.py target)
test_targets = {
    8: list(range(1, 51)),
}

# [MODE: custom] 직접 입력 테스트 데이터 (python3 test.py custom)
CUSTOM_COMMAND = "오후 3시마다 조명을 켜줘"

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

csv_file_path = 'local_dataset.csv'


def print_result(result):
    print("\n[Final Result]")
    log = result.get('log', {})
    if log.get('logs'):
        print(f"[logs]\n{log.get('logs', '')}")
    print("\n⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️\n")
    if result.get('ir_readable'):
        print(f"\n[IR Readable]\n{result['ir_readable']}")
    print(f"\ncode           :\n{result.get('code', '')}")
    print(f"response_time  : {log.get('response_time', '')}")


def run_targeted_test(df):
    print("\n🎯 Running Targeted Tests...")
    for category, indices in test_targets.items():
        print(f"--- Category {category} ---")
        for idx in indices:
            match = df[(df['category'] == category) & (df['index'] == idx)]
            if match.empty:
                print(f"(Idx {idx}) - Not Found")
                continue
            row = match.iloc[0]
            kor = row['command_kor']
            eng = row['command_eng']
            print(f"({idx}) 🛑 {kor}\n 🛑 {eng}")
            try:
                result = generate_joi_code(kor, row['connected_devices'], {})
                print_result(result)
            except Exception as e:
                print(f"Error at Idx {idx}: {e}")


def run_custom_test(modification=None):
    print("\n🛠️ Running Custom Test...")
    print(f"Command: {CUSTOM_COMMAND}")
    try:
        result = generate_joi_code(CUSTOM_COMMAND, CUSTOM_DEVICES, {}, modification=modification)
        print_result(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "custom"

    if mode == "target":
        try:
            df = pd.read_csv(csv_file_path, encoding='utf-8-sig')
            run_targeted_test(df)
        except Exception as e:
            print(f"CSV Load Error: {e}")
    elif mode == "custom":
        run_custom_test()
    else:
        print("Usage: python3 test.py [target | custom]")
