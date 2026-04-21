import sys
import pandas as pd
from run_local import generate_joi_code
from agent import agent_chat_stream

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
CUSTOM_COMMAND = "스위치 세번째 버튼을 누르면 모든 불 토글해줘."
CUSTOM_COMMAND = "스위치 첫번째 버튼을 길게 누르면 회의를 시작합니다라고 안내해줘"
CUSTOM_COMMAND = "문이 열리면 로봇이 인사하고 조명을 초록색으로 바꿔줘"
CUSTOM_COMMAND = "필립스 휴 모두 꺼줘"
CUSTOM_COMMAND = "매일 낮 12시에 점심시간이라고 알려주는 알림을 설정해줘"
CUSTOM_COMMAND = "스위치 네번째 버튼을 누르면 사무실 불이 켜져 있는 경우 회의실 불도 켜줘"
CUSTOM_COMMAND = "문이 닫히면 조명을 빨간색으로 바꾸고 회의 중이라고 안내해줘"
CUSTOM_COMMAND = "버튼을 누를때마다 모든 조명을 빨간색과 파란색을 번갈아 설정해줘"
CUSTOM_COMMAND = "30도 이상이고 접촉 센서가 감지되고 있으면 스피커를 켜고 조명을 켜줘"
CUSTOM_COMMAND = "조명이 하나라도 켜져있으면 3초 뒤에 하나를 꺼줘"
CUSTOM_COMMAND = "습도와 온도가 각각 어때 지금?"
CUSTOM_COMMAND = "30분마다 조명을 토글해줘"
CUSTOM_COMMAND = "3분마다 조명 하나를 3초간 켰다가 꺼줘"
CUSTOM_COMMAND = "조명을 모두 켜줘"
# Connected Devices
CUSTOM_DEVICES = """
{'tc0_Speaker_88A29E1B0557': {'category': ['Switch', 'Speaker'], 'tags': ['Switch', 'Speaker']},
 'tc0_ArmRobot_88A29E1B0557': {'category': ['ArmRobot'], 'tags': ['ArmRobot']},
 'tc0_Matter__8': {'category': ['ContactSensor'], 'tags': ['Matter', 'Entrance', 'ContactSensor']},
 'tc0_Matter__21': {'category': ['TemperatureSensor', 'HumiditySensor'], 'tags': ['Matter', 'TemperatureHumiditySensor', 'TemperatureSensor', 'HumiditySensor']},
 'tc0_605c48ef-eb66-45eb-acbc-4e4ef25e28d5': {'category': ['Switch', 'Light'], 'tags': ['PhilipsHue', 'Office', 'Light', 'Switch']},
 'tc0_c66b7261-bdc0-4559-99ac-c2fc35b13451': {'category': ['MultiButton'], 'tags': ['PhilipsHue', 'DimmerSwitch', 'MultiButton']},
 'tc0_df9b47b3-a479-40db-a228-30810e163b32': {'category': ['Switch', 'Light'], 'tags': ['PhilipsHue', 'MeetingRoom', 'Light', 'Switch']}}"""
CUSTOM_DEVICES = {
    "tc0_af37207d-f2f2-447f-8006-f1e030755e65": {"category": ["DimmerSwitch"], "tags": ["PhilipsHue"], "nickname": "Hue dimmer switch 1"},
    "tc0_5452b6c5-0dee-4cca-ba6f-15582b358305": {"category": ["Light"], "tags": ["PhilipsHue"], "nickname": "Hue color lamp 3"},
    "tc0_9fe5d8b9-9ebc-4203-9963-497546c9740d": {"category": ["Light"], "tags": ["PhilipsHue"], "nickname": "Hue color lamp 4"},
    "tc0_7def1d9d-721c-4e35-b217-51fb8b46ba59": {"category": ["Light"], "tags": ["PhilipsHue"], "nickname": "Hue go 1"},
    "tc0_a2e7594e-aced-4e03-a25e-841aa7315614": {"category": ["Light"], "tags": ["PhilipsHue"], "nickname": "Hue lightstrip plus 1"},
    "tc0_081181c1-3210-4ad2-8af1-f262fdc0fc76": {"category": ["Light"], "tags": ["PhilipsHue"], "nickname": "Hue lindy lamp 3"},
    "tc0_550713ef-d27f-43f3-9dcf-7b16101c618a": {"category": ["MotionSensor"], "tags": ["PhilipsHue"], "nickname": "Hue motion sensor 2"},
    "tc0_4fab94c3-a3ce-4814-8d03-e84c6775d1f4": {"category": ["TapDialSwitch"], "tags": ["PhilipsHue"], "nickname": "Hue tap dial switch 1"},
    "tc0_b990fd42-fe20-4be7-8969-e5b00d605324": {"category": ["TapDialSwitch"], "tags": ["PhilipsHue"], "nickname": "Hue tap dial switch 3"},
    "tc0_s8e7a31295af78fb09mmpp": {"category": ["AirConditioner"], "tags": ["Hejhome"], "nickname": "에어컨 (office)"},
    "tc0_eb62d33c2d328d97cdbltl": {"category": ["AirConditioner"], "tags": ["Hejhome"], "nickname": "airconditioner__gulliver"},
    "tc0_ebf02f5cfcd67e4ce4bexu": {"category": ["AirConditioner"], "tags": ["Hejhome"], "nickname": "Air Conditioner (cafe)"},
    "tc0_eb3377e5ffd045b5f3qdur": {"category": ["Switch"], "tags": ["Hejhome"], "nickname": "SmartPlug (냉장고)"},
    "tc0_ebcbfbd4976307a137qq1c": {"category": ["Switch"], "tags": ["Hejhome"], "nickname": "plug__3d_printer__gulliver"},
    "tc0_ebfce1cbd88459d75bnymz": {"category": ["Etc"], "tags": ["Tuya"], "nickname": "Smart IR with T&H Sensor"},
    "tc0_eb4dc043204490364bfota": {"category": ["Etc"], "tags": ["Tuya"], "nickname": "Multimode gateway(mini)"},
    "tc0_ebe47e098219089fc7frjx": {"category": ["Switch"], "tags": ["Tuya"], "nickname": "SMARTvill"},
    "tc0_ebfb522a028ef8add497wu": {"category": ["Light"], "tags": ["Tuya"], "nickname": "CCT"},
    "tc0_ebb1abce1f52d16352hugy": {"category": ["Etc"], "tags": ["Tuya"], "nickname": "AIR_DETECTOR"},
    "tc0_eb8c9cf310d709af51rs9c": {"category": ["Light"], "tags": ["Tuya"], "nickname": "YUER"},
    "tc0_ebd62449e3a700125du284": {"category": ["Button"], "tags": ["Tuya"], "nickname": "Wireless scene switch"},
    "tc0_eb70b2f140ec4acb9ebpwt": {"category": ["Etc"], "tags": ["Tuya"], "nickname": "MINI Occupancy Sensor"},
    "tc0_ebc3c76ceb8d4a5a4907wk": {"category": ["Etc"], "tags": ["Tuya"], "nickname": "Motion Sensor&TH"},
}
csv_file_path = 'local_dataset.csv'

def run_full_batch(df):
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
            result = generate_joi_code(cmd_input, row['connected_devices'], {})
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
    log = result.get('log', {})
    if log.get('logs'):
        print(f"[logs]\n{log.get('logs', '')}")
    print(f"code           :\n{result.get('code', '')}")
    print(f"translated     : {log.get('translated_sentence', '')}")
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
                # Use ENG from CSV as base for targeted testing consistency or KOR to test translation
                result = generate_joi_code(kor, row['connected_devices'], {})
                print_result(result)
            except Exception as e:
                print(f"Error at Idx {idx}: {e}")

def run_custom_test():
    print("\n🛠️ Running Custom Test...")
    print(f"Command: {CUSTOM_COMMAND}")
    try:
        result = generate_joi_code(CUSTOM_COMMAND, CUSTOM_DEVICES, {})
        print_result(result)
    except Exception as e:
        print(f"Error: {e}")
        return

    while True:
        modification = input("\n수정사항 입력 (엔터 시 종료) >>> ").strip()
        if not modification:
            print("종료합니다.")
            break
        try:
            result = generate_joi_code(CUSTOM_COMMAND, CUSTOM_DEVICES, {}, modification=modification)
            print_result(result)
        except Exception as e:
            print(f"Error: {e}")

def run_agent_chat():
    import uuid, json as _json, os
    from datetime import datetime
    from zoneinfo import ZoneInfo
    _KST = ZoneInfo("Asia/Seoul")

    os.environ.setdefault("MCP_SERVER_URL", "http://192.168.0.163:48012/mcp")

    LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "logs")
    os.makedirs(LOG_DIR, exist_ok=True)

    print("\n💬 Agent Chat Mode (종료: 'quit' 또는 'q')")
    session_id = f"test_{uuid.uuid4().hex[:4]}"
    log_path = os.path.join(LOG_DIR, f"{session_id}.log")
    print(f"Session ID: {session_id}")
    print(f"MCP     : {os.environ['MCP_SERVER_URL']}")
    print(f"Log     : {log_path}\n")

    def write_log(content):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(content)

    def on_tool_call(name, args, result):
        ts = datetime.now(_KST).strftime("%Y-%m-%d %H:%M:%S")
        stage_logs = ''
        if isinstance(result, dict):
            stage_logs = result.get('logs', '') or (result.get('log') or {}).get('logs', '')
            result_clean = {}
            for k, v in result.items():
                if k == 'logs':
                    continue
                if k == 'log' and isinstance(v, dict):
                    result_clean[k] = {ik: iv for ik, iv in v.items() if ik != 'logs'}
                elif k == 'code' and isinstance(v, str):
                    try:
                        result_clean[k] = _json.loads(v)
                    except Exception:
                        result_clean[k] = v
                else:
                    result_clean[k] = v
        else:
            result_clean = result
        write_log(
            f"[{ts}] TOOL CALL: {name}\n"
            f"  args   : {_json.dumps(args, ensure_ascii=False, indent=2)}\n"
            f"  result : {_json.dumps(result_clean, ensure_ascii=False, indent=2)}\n"
            + (f"  logs   :\n{stage_logs}\n" if stage_logs else "")
        )

    def on_complete(message, last_result):
        ts = datetime.now(_KST).strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{ts}] RESPONSE (stream complete)\n  message    : {message}\n"
        if last_result:
            lr = last_result
            entry += (
                f"  translated : {lr.get('log', {}).get('translated_sentence', '')}\n"
                f"  code       : {_json.dumps(_json.loads(lr['code']), ensure_ascii=False, indent=2) if isinstance(lr.get('code'), str) else _json.dumps(lr.get('code', ''), ensure_ascii=False, indent=2)}\n"
                f"  status     : {lr.get('status', '')}\n"
            )
        write_log(entry)

    prev_lr_code = None

    while True:
        try:
            user_input = input("You >>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break
        if not user_input:
            continue
        if user_input.lower() in ("quit", "q", "exit"):
            print("종료합니다.")
            break

        ts = datetime.now(_KST).strftime("%Y-%m-%d %H:%M:%S")
        write_log(f"\n{'='*60}\n[{ts}] REQUEST\n  sentence : {user_input}\n")

        try:
            response_text = ""
            last_result = None

            print("Agent >>> ", end="", flush=True)
            for event in agent_chat_stream(
                user_message=user_input,
                session_id=session_id,
                connected_devices=CUSTOM_DEVICES,
                on_tool_call=on_tool_call,
                on_complete=on_complete,
            ):
                if not event.startswith("data: "):
                    continue
                payload = event[len("data: "):].strip()
                if payload.startswith("[DONE]"):
                    done_data = _json.loads(payload[len("[DONE] "):])
                    last_result = done_data.get("last_result")
                else:
                    char = _json.loads(payload)
                    print(char, end="", flush=True)
                    response_text += char
            print()

            lr = last_result
            current_code = lr.get("code") if lr else None
            if lr and current_code and current_code != prev_lr_code:
                if lr.get("status") in ("confirmation_needed", "approved", "registered_locally"):
                    print(f"\n  [code]\n{current_code}")
                    print(f"  [translated] {lr.get('log', {}).get('translated_sentence', '')}")
                    print(f"  [time] {lr.get('log', {}).get('response_time', '')}")
                    prev_lr_code = current_code
            elif not lr:
                prev_lr_code = None

            print()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error: {e}")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "agent"

    if mode == "all":
        try:
            df = pd.read_csv(csv_file_path, encoding='utf-8-sig')
            run_full_batch(df)
        except Exception as e:
            print(f"CSV Load Error: {e}")

    elif mode == "target":
        try:
            df = pd.read_csv(csv_file_path, encoding='utf-8-sig')
            run_targeted_test(df)
        except Exception as e:
            print(f"CSV Load Error: {e}")

    elif mode == "custom":
        run_custom_test()
    elif mode == "agent":
        run_agent_chat()
    else:
        print("Usage: python3 test.py [all | target | custom | agent]")