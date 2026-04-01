import sys
import pandas as pd
from run_local import generate_joi_code, agent_chat

# [MODE: target] 테스트할 타겟 지정 (python3 test.py target)
test_targets = {
    # 1: [1]
    # 1: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30],
    # 2: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30],    
    # 3: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30],    
    # 4: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30],    
    # 5: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30],    
    # 6: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30],    
    # 7: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50],
    8: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50],     
}

# [MODE: custom] 직접 입력 테스트 데이터 (python3 test.py custom)
CUSTOM_COMMAND = "월요일부터 금요일까지 오전 9시에 모든 공간 불을 미리 켜줘."
CUSTOM_COMMAND = "평일 오후 6시마다 문이 닫혀 있으면 모든 공간 불을 꺼줘."
CUSTOM_COMMAND = "문이 닫히면 조명을 빨간색으로 바꾸고 회의 중이라고 안내해줘"
CUSTOM_COMMAND = "스위치 두번째 버튼을 누르면 사무실 불 토글해줘."
CUSTOM_COMMAND = "스위치 세번째 버튼을 누르면 모든 불 토글해줘."
CUSTOM_COMMAND = "스위치 첫번째 버튼을 길게 누르면 회의를 시작합니다라고 안내해줘"
CUSTOM_COMMAND = "문이 열리면 로봇이 인사하고 조명을 초록색으로 바꿔줘"
CUSTOM_COMMAND = "매일 낮 12시에 점심시간이라고 알려주는 알림을 설정해줘"
CUSTOM_COMMAND = "조광 스위치 네번째 버튼을 누르면 사무실 불이 켜져 있는 경우 회의실 불도 켜줘"
CUSTOM_COMMAND = "문이 닫히면 조명을 빨간색으로 바꾸고 회의 중이라고 안내해줘"
CUSTOM_COMMAND = "스위치 첫번째 버튼을 누르면 회의실 불 토글해줘."
CUSTOM_COMMAND = "8시마다 불을 켜줘"
CUSTOM_DEVICES = """
{'tc0_Speaker_88A29E1B0557': {'category': 'Speaker', 'tags': ['Switch']},
 'tc0_ArmRobot_88A29E1B0557': {'category': 'ArmRobot', 'tags': []},
 'tc0_Matter__8': {'category': 'ContactSensor', 'tags': ['Matter']},
 'tc0_Matter__21': {'category': 'TemperatureHumiditySensor', 'tags': ['Matter', 'TemperatureHumiditySensor']},
 'tc0_605c48ef-eb66-45eb-acbc-4e4ef25e28d5': {'category': 'Light', 'tags': ['PhilipsHue']},
 'tc0_c66b7261-bdc0-4559-99ac-c2fc35b13451': {'category': 'DimmerSwitch', 'tags': ['PhilipsHue']},
 'tc0_df9b47b3-a479-40db-a228-30810e163b32': {'category': 'Light', 'tags': ['PhilipsHue']}}
"""
CUSTOM_OPTIONS = {}

csv_file_path = 'local_dataset.csv'

def run_full_batch(df, debug=False):
    print("\n🚀 Starting Full Batch Processing...")
    total_rows = len(df)
    current_cat = None
    log_file = None
    original_stdout = sys.stdout
    
    for i, (idx, row) in enumerate(df.iterrows()):
        cat = int(row['category'])
        if cat != current_cat:
            if log_file:
                log_file.flush()
                log_file.close()
                sys.stdout = original_stdout
            current_cat = cat
            print(f"Starting Category {cat}... logging to category{cat}.log")
            log_file = open(f"category{cat}.log", "w", encoding="utf-8")
            sys.stdout = log_file

        cmd_input = row['command_eng']
        print(f"[{i+1}/{total_rows}] Category {cat}, Index {int(row['index'])}: {cmd_input}")
        try:
            result = generate_joi_code(cmd_input, row['connected_devices'], {}, debug=debug)
            print_result(result)
        except Exception as e:
            print(f"Error at row {i}: {e}")

    if log_file:
        log_file.flush()
        log_file.close()
    sys.stdout = original_stdout
    print(f"\n✨ Full Batch Processing Completed.")

def print_result(result):
    print("\n[Final Result]")
    # print(f"merged_command : {result.get('merged_command', '')}")
    print(f"code           :\n{result.get('code', '')}")
    log = result.get('log', {})
    print(f"translated     : {log.get('translated_sentence', '')}")
    # print(f"mapped_devices : {log.get('mapped_devices', [])}")
    print(f"response_time  : {log.get('response_time', '')}")

def run_targeted_test(df, debug=False):
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
                # Use ENG from CSV as base for targeted testing consistency or KOR to test translation
                result = generate_joi_code(kor, row['connected_devices'], {}, debug=debug)
                if not debug: print_result(result)
            except Exception as e:
                print(f"Error at Idx {idx}: {e}")

def run_custom_test(debug=False):
    print("\n🛠️ Running Custom Test...")
    print(f"Command: {CUSTOM_COMMAND}")
    print(f"Devices: {CUSTOM_DEVICES}")
    try:
        result = generate_joi_code(CUSTOM_COMMAND, CUSTOM_DEVICES, {}, debug=debug)
        print("\n[Final Result]")
        print(f"merged_command : {result.get('merged_command', '')}")
        print(f"code           :\n{result.get('code', '')}")
        log = result.get('log', {})
        print(f"translated     : {log.get('translated_sentence', '')}")
        print(f"mapped_devices : {log.get('mapped_devices', [])}")
        print(f"response_time  : {log.get('response_time', '')}")
    except Exception as e:
        print(f"Error: {e}")
        return

    while True:
        modification = input("\n수정사항 입력 (엔터 시 종료) >>> ").strip()
        if not modification:
            print("종료합니다.")
            break
        try:
            result = generate_joi_code(CUSTOM_COMMAND, CUSTOM_DEVICES, {}, modification=modification, debug=debug)
            print_result(result)
        except Exception as e:
            print(f"Error: {e}")

def run_agent_chat(debug=False):
    print("\n💬 Agent Chat Mode (종료: 'quit' 또는 'q')")
    print(f"Devices: {CUSTOM_DEVICES}\n")

    while True:
        user_input = input("You >>> ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "q", "exit"):
            print("종료합니다.")
            break

        try:
            result = agent_chat(
                user_message=user_input,
                connected_devices=CUSTOM_DEVICES,
                debug=debug,
            )
            print(f"\nAgent >>> {result['response']}")
            lr = result.get("last_result")
            if lr and lr.get("code"):
                print(f"\n  [code]\n{lr['code']}")
                print(f"  [translated] {lr.get('log', {}).get('translated_sentence', '')}")
                print(f"  [time] {lr.get('log', {}).get('response_time', '')}")
            print()
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "target"
    debug_mode = "debug" in sys.argv
    
    if mode == "all":
        try:
            df = pd.read_csv(csv_file_path, encoding='utf-8-sig')
            run_full_batch(df, debug=debug_mode)
        except Exception as e:
            print(f"CSV Load Error: {e}")
            
    elif mode == "target":
        try:
            df = pd.read_csv(csv_file_path, encoding='utf-8-sig')
            run_targeted_test(df, debug=debug_mode)
        except Exception as e:
            print(f"CSV Load Error: {e}")
            
    elif mode == "custom":
        run_custom_test(debug=debug_mode)
    elif mode == "agent":
        run_agent_chat(debug=debug_mode)
    else:
        print("Usage: python3 test.py [all | target | custom | agent] [debug]")