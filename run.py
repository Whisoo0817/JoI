"""Minimal E2E runner for generate_joi_code (paper pipeline).

Runs every command in COMMANDS through the full IR -> JoI pipeline and prints
ONLY the final JoI code. No verifier, no IR/selector rendering.

    python3 run.py
"""
# 바이스 타겟 목록: AirConditioner, AirPurifier, AirQualitySensor,
# Button, Camera, ContactSensor, Humidifier, HumiditySensor,
# Light, LightSensor, MotionSensor, Plug, PresenceSensor, 
# SmokeDetector, Speaker, Switch, TemperatureSensor, Clock,
# ToastPublisher, EmailProvider
import os

# E2E + verifier OFF. These constants are read at import time / per call, so
# clear any shell overrides BEFORE importing the pipeline to guarantee:
#   - no verifier / self-correction loop (JOI_VERIFY)
#   - no IR-only short-circuit (JOI_IR_ONLY)
#   - no ground-truth IR injection (JOI_GT_IR_PATH)
for _k in ("JOI_VERIFY", "JOI_IR_ONLY", "JOI_GT_IR_PATH", "JOI_SKIP_TRANSLATION"):
    os.environ.pop(_k, None)

from paper.run_local_ir import generate_joi_code

# 실제 연결 디바이스. 원본 category가 비어 있어 닉네임/기기종류로 직접 채웠고
# (actuator엔 Switch 기본 포함, 전등 스위치는 Switch만), location은 tags 끝에 추가했다.
# nickname은 참고용 (파이프라인은 category/tags만 읽음).
CONNECTED_DEVICES = {
    #d1
    "tc0_Speaker_88A29E5F0D65": {"nickname": "JOI 스피커", "category": ["Switch", "Speaker"], "tags": ["Switch", "StudentRoom", "Office"]},
    "tc0_Aqara_Door_and_Window_Sensor_P2__2__ep1": {"nickname": "Aqara P2 문열림 센서1", "category": ["ContactSensor"], "tags": ["Matter", "Entrance", "Window", "Office"]},
    "tc0_Smart_Wi-Fi_Plug__5__ep1": {"nickname": "타포 스마트 플러그1", "category": ["Switch", "Plug"], "tags": ["Matter", "StudentRoom", "runA", "plug", "NoneNecessary", "Office"]},
    "tc0_Smart_Wi-Fi_Plug__8": {"nickname": "타포 스마트 플러그4", "category": ["Switch", "Plug"], "tags": ["Matter", "NoneNecessary", "MeetingRoom"]},
    "tc0_Smart_Wi-Fi_Plug__9": {"nickname": "타포 스마트 플러그5", "category": ["Switch", "Plug"], "tags": ["Matter", "NoneNecessary", "MeetingRoom"]},
    "tc0_eb3868818a4c9bbe5659zn": {"nickname": "투야 문열림 센서1", "category": ["ContactSensor"], "tags": ["Tuya", "Entrance", "Window", "Office"]},
    "tc0_eb86508b2d8d4f2472gpbx": {"nickname": "투야 유선 재실 센서", "category": ["PresenceSensor"], "tags": ["Tuya", "MeetingRoom"]},
    "tc0_eb3b9aaeedbf3ad037eh0y": {"nickname": "투야 미니 재신 센서2", "category": ["PresenceSensor"], "tags": ["Tuya", "StudentRoom", "Office"]},
    "tc0_eb61f16a24808ba09cdmyv": {"nickname": "투야 모션&조도 센서1", "category": ["PresenceSensor", "LightSensor"], "tags": ["Tuya", "StudentRoom", "runA", "MotionSensor", "MeetingRoom"]},
    #d10
    "tc0_ebf9bbe6130bf4d66dmitl": {"nickname": "투야 모션&조도 센서2", "category": ["PresenceSensor", "LightSensor"], "tags": ["Tuya", "StudentRoom", "MeetingRoom"]},
    "tc0_ebb1abce1f52d16352hugy": {"nickname": "투야 통합공기질 센서", "category": ["AirQualitySensor"], "tags": ["Tuya", "AirDetector", "MeetingRoom"]},
    "tc0_ebda0261399e3ab43cuhgx": {"nickname": "투야 미니 재신 센서1", "category": ["PresenceSensor"], "tags": ["Tuya", "StudentRoom", "Office"]},
    "tc0_eb41731d070c6357e2fnv2": {"nickname": "투야 화재 감지기", "category": ["SmokeDetector"], "tags": ["Tuya", "StudentRoom", "MeetingRoom"]},
    "tc0_Smart_Wi-Fi_Plug__5__ep2": {"nickname": "타포 스마트 플러그1", "category": ["Switch", "Plug"], "tags": ["Matter", "NoneNecessary", "StudentRoom", "Office"]},
    "tc0_Smart_Wi-Fi_Plug__6": {"nickname": "타포 스마트 플러그2", "category": ["Switch", "Plug"], "tags": ["Matter", "NoneNecessary", "plug", "StudentRoom", "Office"]},
    "tc0_Smart_Wi-Fi_Plug__7": {"nickname": "타포 스마트 플러그3", "category": ["Switch", "Plug"], "tags": ["Matter", "NoneNecessary", "StudentRoom", "Office"]},
    #d17
    "tc0_Smart_Wi-Fi_Plug__10": {"nickname": "타포 스마트 플러그6", "category": ["Switch", "Plug"], "tags": ["Matter", "NoneNecessary", "MeetingRoom"]},
    "tc0_Smart_Multicolor_Bulb__11": {"nickname": "타포 스마트 전구1", "category": ["Switch", "Light"], "tags": ["Matter", "MeetingRoom", "NoneNecessary", "Office"]},
    "tc0_eb3cbd47e9745ebd25d4ws__ep1": {"nickname": "투야 전등 스위치1구", "category": ["Switch"], "tags": ["Tuya", "test", "NoneNecessary", "MeetingRoom"]},
    "tc0_eb3cbd47e9745ebd25d4ws__ep2": {"nickname": "투야 전등 스위치2구", "category": ["Switch"], "tags": ["Tuya", "NoneNecessary", "MeetingRoom"]},
    "tc0_eb3cbd47e9745ebd25d4ws__ep3": {"nickname": "투야 전등 스위치3구", "category": ["Switch"], "tags": ["Tuya", "NoneNecessary", "MeetingRoom"]},
    "tc0_Aqara_Motion_and_Light_Sensor_P2__14__ep1": {"nickname": "Aqara P2 모션&조도 센서1", "category": ["PresenceSensor"], "tags": ["Matter", "Office"]},
    #d23
    "tc0_Aqara_Motion_and_Light_Sensor_P2__14__ep2": {"nickname": "Aqara P2 모션&조도 센서1", "category": ["LightSensor"], "tags": ["Matter", "Office"]},
    "tc0_eb1854bcd3fd5d266ao7bn": {"nickname": "투야 IR 에어컨", "category": ["Switch", "AirConditioner"], "tags": ["Tuya", "Switch", "MeetingRoom"]},
    "tc0_builtin_clock": {"nickname": "시계", "category": ["Clock"], "tags": ["Office"]},
    "tc0_builtin_toast_publisher": {"nickname": "토스트 퍼블리셔", "category": ["ToastPublisher"], "tags": ["Office"]},
    "tc0_eb2f8a1c7d4b9e6035hqtz": {"nickname": "투야 온도 센서1", "category": ["TemperatureSensor"], "tags": ["Tuya", "StudentRoom", "Office"]},
    "tc0_builtin_email_provider": {"nickname": "이메일", "category": ["EmailProvider"], "tags": ["Office"]},
    "tc0_eb974c3e6b27dd6380u67u": {"nickname": "투야 보안 카메라1", "category": ["Switch", "Camera"], "tags": ["Tuya", "Office"]},
    #d30
    "tc0_ebfdecd85f8b6f00fcmxur": {"nickname": "투야 보안 카메라2", "category": ["Switch", "Camera"], "tags": ["Tuya", "MeetingRoom"]},
    "tc0_eb889aece396abc05dzl6u": {"nickname": "출퇴근 버튼", "category": ["Button"], "tags": ["Tuya", "ModeToggle", "Office"]},
    "tc0_eb5d9c2a7f3b1e8046apfr": {"nickname": "투야 공기청정기1", "category": ["Switch", "AirPurifier"], "tags": ["Tuya", "MeetingRoom"]},
    "tc0_eb8a4f1d6c2e9b7035hmdf": {"nickname": "투야 가습기1", "category": ["Switch", "Humidifier"], "tags": ["Tuya", "Office"]},
    "tc0_eb1c7e3a9d5f2b8064hmds": {"nickname": "투야 습도 센서1", "category": ["HumiditySensor"], "tags": ["Tuya", "StudentRoom", "Office"]},
    "tc0_eb3f9a1c8d4b2e7056mtsn": {"nickname": "투야 모션 센서1", "category": ["MotionSensor"], "tags": ["Tuya", "StudentRoom", "MeetingRoom"]},
}

# 실행할 명령어 목록 — 여기에 추가하면 모두 순서대로 수행된다.
COMMANDS = [
    # "출퇴근 버튼을 누를 때마다 모든 조명과 플러그를 켜줘",
    # "온도가 25도 이상이되면 에어컨을 냉방모드로 켜줘."
    "투야 기기 모두 꺼줘",
    # "오전 11시 8분에 모든 조명을 켜줘",
    # "10분 이상 사람이 있으면 환기하라고 스피커로 알려줘",
    # "문이 5분 이상 열려있으면 스피커로 문 열렸다고 알려줘",
    # "매일 오후 6시 18분에 모든 조명을 꺼줘",
    # "창문이 열리면 커튼을 닫아줘"    
]


def run(command: str) -> None:
    print(f"\n================ {command} ================")
    try:
        result = generate_joi_code(command, CONNECTED_DEVICES, {})
    except Exception as e:
        print(f"Error: {e}")
        logs = getattr(e, "logs", "")
        if logs:
            print(f"\n----- reasoning log -----\n{logs}")
        return
    log = result.get("log", {})
    # 단계별 추론 트레이스 (translation / extractor / mapping / lowering ...)
    print(f"----- reasoning log -----\n{log.get('logs', '')}")
    print(f"\n----- code -----\n{result.get('code', '')}")
    print(f"\nresponse_time : {log.get('response_time', '')}")


if __name__ == "__main__":
    for command in COMMANDS:
        run(command)
