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
import re
import json

# E2E + verifier OFF. These constants are read at import time / per call, so
# clear any shell overrides BEFORE importing the pipeline to guarantee:
#   - no verifier / self-correction loop (JOI_VERIFY)
#   - no IR-only short-circuit (JOI_IR_ONLY)
#   - no ground-truth IR injection (JOI_GT_IR_PATH)
for _k in ("JOI_VERIFY", "JOI_IR_ONLY", "JOI_GT_IR_PATH", "JOI_SKIP_TRANSLATION"):
    os.environ.pop(_k, None)

from paper.run_local_ir import generate_joi_code

# 실제 연결 디바이스 — last_connected_devices.json(실서버 페이로드) 그대로.
# 클라이언트가 보내는 그대로 category/tags를 유지하고, UI 카드에 보이는 nickname을
# 추가로 매핑해 두었다(닉네임 지명 명령 테스트용). GlobalVariable은 제외.
# 파이프라인은 현재 category/tags만 읽음 — nickname은 향후 그라운딩용 참고 필드.
CONNECTED_DEVICES = {
    "tc0_AirQualitySensor_D83ADDD14F2A": {"nickname": "공기질 센서", "category": ["AirQualitySensor"], "tags": ["AirQualityManagement", "tc0_AirQualitySensor_D83ADDD14F2A", "AirQualitySensor", "tc0_local"]},
    "tc0_Speaker_D83ADDD14F4B": {"nickname": "JOI 스피커", "category": ["Speaker"], "tags": ["tc0_Speaker_D83ADDD14F4B", "Speaker", "tc0_local"]},
    "tc0_5452b6c5-0dee-4cca-ba6f-15582b358305": {"nickname": "Hue color lamp 3", "category": ["Light", "Switch"], "tags": ["PhilipsHue", "NoneNecessary", "tc0_5452b6c5-0dee-4cca-ba6f-15582b358305", "Light", "tc0_philipshue", "Switch"]},
    "tc0_7def1d9d-721c-4e35-b217-51fb8b46ba59": {"nickname": "Hue go 1", "category": ["Light", "Switch"], "tags": ["PhilipsHue", "NoneNecessary", "tc0_7def1d9d-721c-4e35-b217-51fb8b46ba59", "Light", "tc0_philipshue", "Switch"]},
    "tc0_081181c1-3210-4ad2-8af1-f262fdc0fc76": {"nickname": "Hue lindy lamp 3", "category": ["Light", "Switch"], "tags": ["PhilipsHue", "NoneNecessary", "tc0_081181c1-3210-4ad2-8af1-f262fdc0fc76", "Light", "tc0_philipshue", "Switch"]},
    "tc0_livingroom_light_01": {"nickname": "거실 조명", "category": ["Light", "Switch"], "tags": ["LivingRoom", "tc0_livingroom_light_01", "Light", "Switch", "tc0_local"]},
    "tc0_livingroom_light_02": {"nickname": "거실 조명", "category": ["Light", "Switch"], "tags": ["LivingRoom", "tc0_livingroom_light_02", "Light", "Switch", "tc0_local"]},
    "tc0_550713ef-d27f-43f3-9dcf-7b16101c618a": {"nickname": "Hue motion sensor 2", "category": ["MotionSensor", "LightSensor", "TemperatureSensor"], "tags": ["PhilipsHue", "tc0_550713ef-d27f-43f3-9dcf-7b16101c618a", "MotionSensor", "tc0_philipshue", "LightSensor", "TemperatureSensor"]},
    "tc0_01df2e24-81ac-2056-2edd-c6582bab5d52": {"nickname": "삼성 공기청정기 작은거", "category": ["AirPurifier", "Switch"], "tags": ["Smartthings", "tc0_01df2e24-81ac-2056-2edd-c6582bab5d52", "AirPurifier", "tc0_smartthings", "Switch"]},
    "tc0_3c7a4839-c2a6-4731-98f9-03eda6b31608": {"nickname": "미로 가습기", "category": ["Humidifier", "Switch"], "tags": ["Smartthings", "tc0_3c7a4839-c2a6-4731-98f9-03eda6b31608", "Humidifier", "tc0_smartthings", "Switch"]},
    "tc0_481471e8-2319-cbfd-9eb3-714df64ada77": {"nickname": "삼성 로봇청소기", "category": ["RobotVacuumCleaner", "Switch"], "tags": ["Smartthings", "tc0_481471e8-2319-cbfd-9eb3-714df64ada77", "RobotVacuumCleaner", "tc0_smartthings", "Switch"]},
    "tc0_efb00b25-259e-1660-fb7b-9ca9b396b694": {"nickname": "삼성 공기청정기 큰거", "category": ["AirPurifier", "Switch"], "tags": ["Smartthings", "tc0_efb00b25-259e-1660-fb7b-9ca9b396b694", "AirPurifier", "tc0_smartthings", "Switch"]},
    "tc0_s8e7a31295af78fb09mmpp": {"nickname": "헤이홈 IR 에어컨", "category": ["AirConditioner", "Switch", "TemperatureSensor"], "tags": ["Hejhome", "tc0_s8e7a31295af78fb09mmpp", "AirConditioner", "tc0_hejhome", "Switch", "TemperatureSensor"]},
    "tc0_LG_Smart_Button_2_Button__28__ep1": {"nickname": "LG 스마트 버튼 2구 1", "category": ["Button"], "tags": ["Matter", "tc0_LG_Smart_Button_2_Button__28__ep1", "Button", "tc0_matter"]},
    "tc0_LG_Smart_Button_2_Button__28__ep2": {"nickname": "LG 스마트 버튼 2구 2", "category": ["Button"], "tags": ["Matter", "tc0_LG_Smart_Button_2_Button__28__ep2", "Button", "tc0_matter"]},
    "tc0_LG_Smart_Button_1_Button__29": {"nickname": "LG 스마트 버튼 1구", "category": ["Button"], "tags": ["Matter", "tc0_LG_Smart_Button_1_Button__29", "Button", "tc0_matter"]},
    "tc0_LG_Temp_and_Humidity_Sensor__30__ep1": {"nickname": "LG 온습도 센서 (온도)", "category": ["TemperatureSensor"], "tags": ["Matter", "tc0_LG_Temp_and_Humidity_Sensor__30__ep1", "TemperatureSensor", "tc0_matter"]},
    "tc0_LG_Temp_and_Humidity_Sensor__30__ep2": {"nickname": "LG 온습도 센서 (습도)", "category": ["HumiditySensor"], "tags": ["Matter", "tc0_LG_Temp_and_Humidity_Sensor__30__ep2", "HumiditySensor", "tc0_matter"]},
    "tc0_LG_Door_and_Window_Sensor__31": {"nickname": "LG 문열림 센서", "category": ["ContactSensor"], "tags": ["Matter", "Window", "tc0_LG_Door_and_Window_Sensor__31", "ContactSensor", "tc0_matter"]},
    "tc0_LG_Air_Quality_Sensor__32": {"nickname": "LG 공기질 센서", "category": ["AirQualitySensor"], "tags": ["Matter", "tc0_LG_Air_Quality_Sensor__32", "AirQualitySensor", "tc0_matter"]},
    "tc0_Aqara_Motion_and_Light_Sensor_P2__33__ep1": {"nickname": "Aqara P2 모션&조도 센서 1 (재실)", "category": ["PresenceSensor"], "tags": ["Matter", "tc0_Aqara_Motion_and_Light_Sensor_P2__33__ep1", "PresenceSensor", "tc0_matter"]},
    "tc0_Aqara_Motion_and_Light_Sensor_P2__33__ep2": {"nickname": "Aqara P2 모션&조도 센서 1 (조도)", "category": ["LightSensor"], "tags": ["Matter", "tc0_Aqara_Motion_and_Light_Sensor_P2__33__ep2", "LightSensor", "tc0_matter"]},
    "tc0_Aqara_Motion_and_Light_Sensor_P2__36__ep1": {"nickname": "Aqara P2 모션&조도 센서 2 (재실)", "category": ["PresenceSensor"], "tags": ["Matter", "tc0_Aqara_Motion_and_Light_Sensor_P2__36__ep1", "PresenceSensor", "tc0_matter"]},
    "tc0_Aqara_Motion_and_Light_Sensor_P2__36__ep2": {"nickname": "Aqara P2 모션&조도 센서 2 (조도)", "category": ["LightSensor"], "tags": ["Matter", "tc0_Aqara_Motion_and_Light_Sensor_P2__36__ep2", "LightSensor", "tc0_matter"]},
    "tc0_Aqara_Door_and_Window_Sensor_P2__25__ep1": {"nickname": "Aqara P2 문열림 센서 1", "category": ["ContactSensor"], "tags": ["Matter", "Entrance", "Door", "tc0_Aqara_Door_and_Window_Sensor_P2__25__ep1", "ContactSensor", "tc0_matter"]},    
    "tc0_Aqara_Door_and_Window_Sensor_P2__25__ep2": {"nickname": "Aqara P2 문열림 센서 1 (배터리)", "category": ["Battery"], "tags": ["Matter", "tc0_Aqara_Door_and_Window_Sensor_P2__25__ep2", "Battery", "tc0_matter"]},
    "tc0_Aqara_Motion_and_Light_Sensor_P2__33__ep3": {"nickname": "Aqara P2 모션&조도 센서 1 (배터리)", "category": ["Battery"], "tags": ["Matter", "tc0_Aqara_Motion_and_Light_Sensor_P2__33__ep3", "Battery", "tc0_matter"]},
    "tc0_Aqara_Motion_and_Light_Sensor_P2__36__ep3": {"nickname": "Aqara P2 모션&조도 센서 2 (배터리)", "category": ["Battery"], "tags": ["Matter", "tc0_Aqara_Motion_and_Light_Sensor_P2__36__ep3", "Battery", "tc0_matter"]},
    "tc0_Aqara_Door_and_Window_Sensor_P2__37__ep1": {"nickname": "Aqara P2 문열림 센서 2", "category": ["ContactSensor"], "tags": ["Matter", "Window", "tc0_Aqara_Door_and_Window_Sensor_P2__37__ep1", "ContactSensor", "tc0_matter"]},
    "tc0_Aqara_Door_and_Window_Sensor_P2__37__ep2": {"nickname": "Aqara P2 문열림 센서 2 (배터리)", "category": ["Battery"], "tags": ["Matter", "tc0_Aqara_Door_and_Window_Sensor_P2__37__ep2", "Battery", "tc0_matter"]},
    "tc0_Presence_Multi-Sensor_FP300__41__ep1": {"nickname": "Aqara FP300 재실 센서 (재실)", "category": ["PresenceSensor"], "tags": ["Matter", "tc0_Presence_Multi-Sensor_FP300__41__ep1", "PresenceSensor", "tc0_matter"]},
    "tc0_Presence_Multi-Sensor_FP300__41__ep2": {"nickname": "Aqara FP300 재실 센서 (조도)", "category": ["LightSensor"], "tags": ["Matter", "tc0_Presence_Multi-Sensor_FP300__41__ep2", "LightSensor", "tc0_matter"]},
    "tc0_Presence_Multi-Sensor_FP300__41__ep3": {"nickname": "Aqara FP300 재실 센서 (온도)", "category": ["TemperatureSensor"], "tags": ["Matter", "tc0_Presence_Multi-Sensor_FP300__41__ep3", "TemperatureSensor", "tc0_matter"]},
    "tc0_Presence_Multi-Sensor_FP300__41__ep4": {"nickname": "Aqara FP300 재실 센서 (습도)", "category": ["HumiditySensor"], "tags": ["Matter", "tc0_Presence_Multi-Sensor_FP300__41__ep4", "HumiditySensor", "tc0_matter"]},
    "tc0_Presence_Multi-Sensor_FP300__41__ep5": {"nickname": "Aqara FP300 재실 센서 (배터리)", "category": ["Battery"], "tags": ["Matter", "tc0_Presence_Multi-Sensor_FP300__41__ep5", "Battery", "tc0_matter"]},
    "tc0_6dbb914e-01ee-4f38-a977-6b700af2ba96": {"nickname": "Hue dimmer switch 1", "category": ["MultiButton"], "tags": ["PhilipsHue", "tc0_6dbb914e-01ee-4f38-a977-6b700af2ba96", "MultiButton", "tc0_philipshue"]},
    "tc0_163a3cde-6bca-4b70-b93f-839d57b6f6ff": {"nickname": "Hue dimmer switch 2", "category": ["MultiButton"], "tags": ["PhilipsHue", "tc0_163a3cde-6bca-4b70-b93f-839d57b6f6ff", "MultiButton", "tc0_philipshue"]},
    "tc0_4fab94c3-a3ce-4814-8d03-e84c6775d1f4": {"nickname": "Hue tap dial switch 1", "category": ["RotaryControl", "MultiButton"], "tags": ["PhilipsHue", "tc0_4fab94c3-a3ce-4814-8d03-e84c6775d1f4", "RotaryControl", "tc0_philipshue", "MultiButton"]},
    "tc0_ebe47e098219089fc7frjx__ep1": {"nickname": "스마트빌 전등 스위치 6구 1", "category": ["Switch"], "tags": ["Tuya", "NoneNecessary", "tc0_ebe47e098219089fc7frjx__ep1", "LightSwitch", "Switch", "tc0_tuya"]},
    "tc0_ebe47e098219089fc7frjx__ep2": {"nickname": "스마트빌 전등 스위치 6구 2", "category": ["Switch"], "tags": ["Tuya", "NoneNecessary", "tc0_ebe47e098219089fc7frjx__ep2", "LightSwitch", "Switch", "tc0_tuya"]},
    "tc0_ebe47e098219089fc7frjx__ep3": {"nickname": "스마트빌 전등 스위치 6구 3", "category": ["Switch"], "tags": ["Tuya", "NoneNecessary", "tc0_ebe47e098219089fc7frjx__ep3", "LightSwitch", "Switch", "tc0_tuya"]},
    "tc0_ebe47e098219089fc7frjx__ep4": {"nickname": "스마트빌 전등 스위치 6구 4", "category": ["Switch"], "tags": ["Tuya", "NoneNecessary", "tc0_ebe47e098219089fc7frjx__ep4", "LightSwitch", "Switch", "tc0_tuya"]},
    "tc0_ebe47e098219089fc7frjx__ep5": {"nickname": "스마트빌 전등 스위치 6구 5", "category": ["Switch"], "tags": ["Tuya", "NoneNecessary", "tc0_ebe47e098219089fc7frjx__ep5", "LightSwitch", "Switch", "tc0_tuya"]},
    "tc0_ebe47e098219089fc7frjx__ep6": {"nickname": "스마트빌 전등 스위치 6구 6", "category": ["Switch"], "tags": ["Tuya", "NoneNecessary", "tc0_ebe47e098219089fc7frjx__ep6", "LightSwitch", "Switch", "tc0_tuya"]},
    "tc0_ebfce1cbd88459d75bnymz": {"nickname": "투야 스마트 IR&온습도 센서", "category": ["TemperatureSensor", "HumiditySensor"], "tags": ["Tuya", "tc0_ebfce1cbd88459d75bnymz", "TemperatureSensor", "tc0_tuya", "HumiditySensor"]},
    "tc0_ebfb522a028ef8add497wu": {"nickname": "스카이라이트 CCT", "category": ["Light", "Switch"], "tags": ["Tuya", "NoneNecessary", "tc0_ebfb522a028ef8add497wu", "Light", "tc0_tuya", "Switch"]},
    "tc0_eb8c9cf310d709af51rs9c": {"nickname": "스카이라이트 YUER", "category": ["Light", "Switch"], "tags": ["Tuya", "NoneNecessary", "tc0_eb8c9cf310d709af51rs9c", "Light", "tc0_tuya", "Switch"]},
    "tc0_ebd62449e3a700125du284": {"nickname": "투야 푸시 버튼 1", "category": ["Button", "Battery"], "tags": ["Tuya", "ModeToggle", "tc0_ebd62449e3a700125du284", "Button", "tc0_tuya", "Battery"]},
    "tc0_eb70b2f140ec4acb9ebpwt": {"nickname": "투야 모션 센서 1", "category": ["PresenceSensor"], "tags": ["Tuya", "tc0_eb70b2f140ec4acb9ebpwt", "PresenceSensor", "tc0_tuya"]},
    "tc0_ebc3c76ceb8d4a5a4907wk": {"nickname": "투야 미니 재실 센서 1", "category": ["PresenceSensor"], "tags": ["Tuya", "tc0_ebc3c76ceb8d4a5a4907wk", "PresenceSensor", "tc0_tuya"]},
    "tc0_ebe62c3d24c9220549quqn": {"nickname": "투야 화재 감지 센서", "category": ["SmokeDetector", "Battery"], "tags": ["Tuya", "tc0_ebe62c3d24c9220549quqn", "SmokeDetector", "tc0_tuya", "Battery"]},
    "tc0_ebec1cd10fda5a0f355eq9": {"nickname": "투야 미니 재실 센서 2", "category": ["PresenceSensor"], "tags": ["Tuya", "tc0_ebec1cd10fda5a0f355eq9", "PresenceSensor", "tc0_tuya"]},
    "tc0_ebfee34916a45f1de9sllx": {"nickname": "투야 유선 재실 센서", "category": ["PresenceSensor"], "tags": ["Tuya", "tc0_ebfee34916a45f1de9sllx", "PresenceSensor", "tc0_tuya"]},
    "tc0_builtin_clock": {"nickname": "시계", "category": ["Clock"], "tags": ["tc0_builtin_clock", "Clock", "tc0_local"]},
    "tc0_builtin_toast_publisher": {"nickname": "토스트 퍼블리셔", "category": ["ToastPublisher"], "tags": ["tc0_builtin_toast_publisher", "ToastPublisher", "tc0_local"]},
    "tc0_builtin_weather_provider": {"nickname": "날씨", "category": ["WeatherProvider"], "tags": ["tc0_builtin_weather_provider", "WeatherProvider", "tc0_local"]},
    "tc0_builtin_email_provider": {"nickname": "이메일", "category": ["EmailProvider"], "tags": ["tc0_builtin_email_provider", "EmailProvider", "tc0_local"]},
    "tc0_ebbcbc45bf05318db9w0ew": {"nickname": "투야 보안 카메라", "category": ["Camera"], "tags": ["Tuya", "tc0_ebbcbc45bf05318db9w0ew", "Camera", "tc0_tuya"]},
    "tc0_Smart_Wi-Fi_Plug__43": {"nickname": "스마트 Wi-Fi 플러그 1", "category": ["Plug", "Switch", "PowerMeter", "EnergyMeter"], "tags": ["Matter", "NoneNecessary", "tc0_Smart_Wi-Fi_Plug__43", "Plug", "tc0_matter", "Switch", "PowerMeter", "EnergyMeter"]},
    "tc0_Smart_Wi-Fi_Plug__44": {"nickname": "스마트 Wi-Fi 플러그 2", "category": ["Plug", "Switch", "PowerMeter", "EnergyMeter"], "tags": ["Matter", "NoneNecessary", "tc0_Smart_Wi-Fi_Plug__44", "Plug", "tc0_matter", "Switch", "PowerMeter", "EnergyMeter"]},
    "tc0_Wi-Fi_Plug__46": {"nickname": "스마트 Wi-Fi 플러그 3", "category": ["Plug", "Switch"], "tags": ["Matter", "NoneNecessary", "tc0_Wi-Fi_Plug__46", "Plug", "tc0_matter", "Switch"]},
    "tc0_Smart_Presence_Sensor__47__ep1": {"nickname": "Smart Presence Sensor 47 ep1", "category": ["PresenceSensor"], "tags": ["Matter", "tc0_Smart_Presence_Sensor__47__ep1", "PresenceSensor", "tc0_matter"]},
    "tc0_Smart_Presence_Sensor__47__ep2": {"nickname": "Smart Presence Sensor 47 ep2", "category": ["LightSensor"], "tags": ["Matter", "tc0_Smart_Presence_Sensor__47__ep2", "LightSensor", "tc0_matter"]},
}

# 실행할 명령어 목록 — 여기에 추가하면 모두 순서대로 수행된다.
# ── QA 시트 (qa.pdf) 명령어 — 3개 그룹으로 분할 ──────────────
# 한 번에 다 돌리기엔 많아서 나눠둠. 아래 ACTIVE 에서 돌릴 그룹만 고르면 됨.

COMMANDS_1 = [
    # 단순 동작 + 조건 기반
    "조명 밝기 20 퍼센트로 설정해줘",
    "문이 5분 이상 열려 있으면 문 열렸다고 알려줘",
    "문이 5분 이상 열려있으면 스피커로 문 열렸다고 알려줘",
    "10분 이상 사람이 있으면 환기 알림을 보내줘",
    "10분 이상 사람이 있으면 환기하라고 스피커로 알려줘",
    "미세먼지 좋음이면 창문 닫으라고 알려줘",
    "이산화탄소 농도가 1000ppm 이상이면 스피커로 환기해줘라고 말해줘",
    "사람이 감지되면 토스트 알림으로 \"재실 감지\"라고 보여줘",
    # 디바이스 없음
    "창문이 열리면 커튼을 닫아줘",
    "커튼 닫아줘",
    "도어락을 잠가줘",
]

COMMANDS_2 = [
    # 스케줄
    "매일 오후 4시 30분에 스피커로 환기 안내를 한 번 해줘.",
    "매일 오후 4시 35분에 회의 시작 5분 전이라고 스피커로 안내해줘.",
    "매일 오후 4시 39분에 환기히라고 스피커로 알려주고 알림도 띄워줘.",
    "매일 오후 6시 18분에 모든 조명을 꺼줘.",
    "오후 6시 20분에 모든 조명을 꺼줘",
    "매시간 정각마다 스피커로 시간을 알려줘",
    "매일 오후 4시 46분에 모든 조명을 꺼줘.",
    "매일 오후 4시 49분에 에어컨을 꺼줘",
    # 시간 + 조건 혼합
    "오후 5시에 사람이 감지되면 조명을 20 퍼센트만 켜줘",
    "오후 5시에 사람이 감지되면 에어컨을 켜줘",
]

COMMANDS_3 = [
    # nickname 지칭
    "오후 3시에 삼성 공기청정기 큰거를 토글해줘",
    "투야 장치들 다 꺼줘",
    "헤이홈 IR 에어컨 꺼줘",
    # 다중 디바이스
    "퇴근 후 사람이 감지되면 조명을 켜고 카메라 녹화 시작하고 메일 보내줘",
    "오후 6시 27분에 카메라 녹화 시작하고 'lindy@mysmax.kr'로 메일 보내줘",
    "오후 6시 30분에 조명을 끄고 카메라 녹화 시작하고 메일 보내줘",
    "문이 열리면 카메라로 촬영하고 'lindy@mysmax.kr' 이메일로 보내줘",
    # 지연 조건 테스트
    "CO₂가 1분 이상 1000ppm 이상이면 환기하라고 알려줘",
    "CO₂가 1분 이상 1000ppm 이상이면 스피커로 환기하라고 알려줘",
    "문이 1분 이상 열려 있으면 스피커로 문 닫으라고 알려줘",
    # ANY/ALL 테스트
    "모든 문이 닫혀 있으면 스피커로 문이 모두 닫혔다고 알려줘",
    "문 하나라도 닫혀있으면 스피커로 알려줘",
    "사람이 한 명이라도 감지되면 스피커로 사람이 있다고 알려줘",
    "모든 재실 센서가 사람 없음이면 조명을 꺼줘",
    "창문 중 하나라도 닫혀 있으면 창문 열라고 알려줘",
    # 기타
    "창문이 열려 있는데 에어컨이 켜져 있으면 에어컨을 꺼줘",
]

# 돌릴 그룹만 여기서 선택 (COMMANDS_1 / COMMANDS_2 / COMMANDS_3)
# qwen ↔ Ornith 결과가 갈렸거나 이슈가 있던 명령들 (직접 돌려 비교용)
COMMANDS = [
    "조명 다 꺼줘",
    "오후 5시에 사람이 감지되면 불 꺼줘"
]

def _reindent(script: str, unit: str = "    ") -> str:
    """Re-indent a JoI script by { } nesting depth so blocks are readable."""
    out, depth = [], 0
    for raw in script.split("\n"):
        ln = raw.strip()
        if not ln:
            continue
        lead_close = len(ln) - len(ln.lstrip("}"))
        depth = max(0, depth - lead_close)
        out.append(unit * depth + ln)
        rest = ln[lead_close:]
        depth = max(0, depth + rest.count("{") - rest.count("}"))
    return "\n".join(out)


def _format_code(code) -> str:
    """Pretty-print the pipeline `code` (JSON-ish string) with an indented script."""
    if not code:
        return "(no code)"
    code_str = code if isinstance(code, str) else json.dumps(code, ensure_ascii=False)

    def _field(name):
        m = re.search(rf'"{name}"\s*:\s*"?(.*?)"?\s*[,\n}}]', code_str)
        return m.group(1) if m else ""

    m = re.search(r'"script"\s*:\s*"(.*)"\s*}', code_str, re.DOTALL)
    script = m.group(1) if m else code_str
    script = script.replace("\\n", "\n").replace('\\"', '"')
    head = f"name={_field('name')}  cron={_field('cron')!r}  period={_field('period')}"
    return head + "\n" + _reindent(script)


def run(command: str) -> None:
    print(f"\n✳️✳️✳️✳️✳️✳️✳️✳️✳️✳️ {command} ✳️✳️✳️✳️✳️✳️✳️✳️✳️✳️")
    try:
        result = generate_joi_code(command, CONNECTED_DEVICES, {})
    except Exception as e:
        print(f"Error: {e}  [error_code={getattr(e, 'error_code', '')}]")
        logs = getattr(e, "logs", "")
        if logs:
            print(f"\n----- reasoning log -----\n{logs}")
        return
    log = result.get("log", {})
    # 단계별 추론 트레이스 (translation / extractor / mapping / lowering ...)
    print(f"----- reasoning log -----\n{log.get('logs', '')}")
    print(f"\n----- code -----\n{_format_code(result.get('code', ''))}")
    print(f"\nresponse_time : {log.get('response_time', '')}")


if __name__ == "__main__":
    for command in COMMANDS:
        run(command)
