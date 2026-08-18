"""Minimal E2E runner for generate_joi_code.

Runs every command in COMMANDS through the full pipeline (joi_slm IR → selectors →
lowering → naming) and prints the reasoning log and the final JoI code.

    python3 run.py
"""
# 바이스 타겟 목록: AirConditioner, AirPurifier, AirQualitySensor,
# Button, Camera, ContactSensor, Humidifier, HumiditySensor,
# Light, LightSensor, MotionSensor, Plug, PresenceSensor, 
# SmokeDetector, Speaker, Switch, TemperatureSensor, Clock,
# ToastPublisher, EmailProvider
import json
import os
import re
import sys

from joi import generate_joi_code

# 실제 연결 디바이스 — generate_joi_code API 요청의 connected_devices 페이로드 그대로
# (last_connected_devices.json 덤프). 파이프라인은 category/tags 를 읽고, nickname 은
# 지명 명령 테스트용 참고 필드다.
# ⚠️ 끝의 3개(ChatProvider/NewsProvider/MessageSender)는 허브에 아직 미연결이라
#    builtin 규칙(tc0_builtin_*, tc0_local)에 맞춰 합성해 둔 항목이다 (COMMANDS_4 테스트용).
CONNECTED_DEVICES = {
    "tc0_AirQualitySensor_D83ADDD14F2A": {"nickname": "공기질 센서", "category": ["AirQualitySensor"], "tags": ["AirQualityManagement", "tc0_AirQualitySensor_D83ADDD14F2A", "AirQualitySensor", "tc0_local"]},
    "tc0_Speaker_D83ADDD14F4B": {"nickname": "JOI 스피커", "category": ["Speaker"], "tags": ["tc0_Speaker_D83ADDD14F4B", "Speaker", "tc0_local"]},
    "tc0_5452b6c5-0dee-4cca-ba6f-15582b358305": {"nickname": "재실 상태 인디케이터 (구역 5)", "category": ["Light", "Switch"], "tags": ["PhilipsHue", "NoneNecessary", "Section5", "tc0_5452b6c5-0dee-4cca-ba6f-15582b358305", "Light", "tc0_philipshue", "Switch"]},
    "tc0_7def1d9d-721c-4e35-b217-51fb8b46ba59": {"nickname": "CO2 농도 인디케이터", "category": ["Light", "Switch"], "tags": ["PhilipsHue", "NoneNecessary", "CO2_Indicator", "tc0_7def1d9d-721c-4e35-b217-51fb8b46ba59", "Light", "tc0_philipshue", "Switch"]},
    "tc0_081181c1-3210-4ad2-8af1-f262fdc0fc76": {"nickname": "Hue lindy lamp 3", "category": ["Light", "Switch"], "tags": ["PhilipsHue", "tc0_081181c1-3210-4ad2-8af1-f262fdc0fc76", "Light", "tc0_philipshue", "Switch"]},
    "tc0_550713ef-d27f-43f3-9dcf-7b16101c618a": {"nickname": "사무실 입구 모션 센서", "category": ["MotionSensor", "LightSensor", "TemperatureSensor"], "tags": ["PhilipsHue", "Entrance", "Door", "Section_E", "tc0_550713ef-d27f-43f3-9dcf-7b16101c618a", "MotionSensor", "tc0_philipshue", "LightSensor", "TemperatureSensor"]},
    "tc0_01df2e24-81ac-2056-2edd-c6582bab5d52": {"nickname": "삼성 공기청정기 큰거", "category": ["AirPurifier", "Switch"], "tags": ["Smartthings", "tc0_01df2e24-81ac-2056-2edd-c6582bab5d52", "AirPurifier", "tc0_smartthings", "Switch"]},
    "tc0_3c7a4839-c2a6-4731-98f9-03eda6b31608": {"nickname": "미로 가습기", "category": ["Humidifier", "Switch"], "tags": ["가습기", "tc0_3c7a4839-c2a6-4731-98f9-03eda6b31608", "Humidifier", "tc0_smartthings", "Switch"]},
    "tc0_481471e8-2319-cbfd-9eb3-714df64ada77": {"nickname": "삼성 로봇청소기", "category": ["RobotVacuumCleaner"], "tags": ["Smartthings", "tc0_481471e8-2319-cbfd-9eb3-714df64ada77", "RobotVacuumCleaner", "tc0_smartthings"]},
    "tc0_efb00b25-259e-1660-fb7b-9ca9b396b694": {"nickname": "삼성 공기청정기 작은거", "category": ["AirPurifier", "Switch"], "tags": ["Smartthings", "lindytest", "tc0_efb00b25-259e-1660-fb7b-9ca9b396b694", "AirPurifier", "tc0_smartthings", "Switch"]},
    "tc0_efb00b25-259e-1660-fb7b-9ca9b396b6": {"nickname": "KT 공기청정기", "category": ["AirPurifier", "Switch"], "tags": ["Smartthings", "lindytest", "tc0_efb00b25-259e-1660-fb7b-9ca9b396b6", "AirPurifier", "tc0_smartthings", "Switch"]},
    "tc0_s8e7a31295af78fb09mmpp": {"nickname": "헤이홈 IR 에이컨", "category": ["AirConditioner", "Switch", "TemperatureSensor"], "tags": ["Hejhome", "tc0_s8e7a31295af78fb09mmpp", "AirConditioner", "tc0_hejhome", "Switch", "TemperatureSensor"]},
    "tc0_LG_Temp_and_Humidity_Sensor__30__ep1": {"nickname": "LG 온습도 센서 (온도)", "category": ["TemperatureSensor"], "tags": ["Matter", "tc0_LG_Temp_and_Humidity_Sensor__30__ep1", "TemperatureSensor", "tc0_matter"]},
    "tc0_LG_Temp_and_Humidity_Sensor__30__ep2": {"nickname": "LG 온습도 센서 (습도)", "category": ["HumiditySensor"], "tags": ["Matter", "tc0_LG_Temp_and_Humidity_Sensor__30__ep2", "HumiditySensor", "tc0_matter"]},
    "tc0_LG_Door_and_Window_Sensor__31": {"nickname": "좌측 창문 열림 센서", "category": ["ContactSensor"], "tags": ["Matter", "Window", "tc0_LG_Door_and_Window_Sensor__31", "ContactSensor", "tc0_matter"]},
    "tc0_LG_Air_Quality_Sensor__32": {"nickname": "LG 공기질 센서", "category": ["AirQualitySensor"], "tags": ["Matter", "tc0_LG_Air_Quality_Sensor__32", "AirQualitySensor", "tc0_matter"]},
    "tc0_Aqara_Motion_and_Light_Sensor_P2__33__ep2": {"nickname": "Aqara P2 모션&조도 센서 1 (조도)", "category": ["LightSensor"], "tags": ["Matter", "tc0_Aqara_Motion_and_Light_Sensor_P2__33__ep2", "LightSensor", "tc0_matter"]},
    "tc0_Aqara_Door_and_Window_Sensor_P2__25__ep1": {"nickname": "사무실 문열림 센서", "category": ["ContactSensor"], "tags": ["Matter", "Entrance", "Door", "Section_E", "tc0_Aqara_Door_and_Window_Sensor_P2__25__ep1", "ContactSensor", "tc0_matter"]},
    "tc0_Aqara_Motion_and_Light_Sensor_P2__33__ep3": {"nickname": "Aqara P2 모션&조도 센서 1 (배터리)", "category": ["Battery"], "tags": ["Matter", "tc0_Aqara_Motion_and_Light_Sensor_P2__33__ep3", "Battery", "tc0_matter"]},
    "tc0_Aqara_Door_and_Window_Sensor_P2__37__ep1": {"nickname": "우측 창문 열림 센서", "category": ["ContactSensor"], "tags": ["Matter", "Window", "tc0_Aqara_Door_and_Window_Sensor_P2__37__ep1", "ContactSensor", "tc0_matter"]},
    "tc0_6dbb914e-01ee-4f38-a977-6b700af2ba96": {"nickname": "Hue dimmer switch 1", "category": ["MultiButton"], "tags": ["PhilipsHue", "tc0_6dbb914e-01ee-4f38-a977-6b700af2ba96", "MultiButton", "tc0_philipshue"]},
    "tc0_163a3cde-6bca-4b70-b93f-839d57b6f6ff": {"nickname": "Hue dimmer switch 2", "category": ["MultiButton"], "tags": ["PhilipsHue", "tc0_163a3cde-6bca-4b70-b93f-839d57b6f6ff", "MultiButton", "tc0_philipshue"]},
    "tc0_4fab94c3-a3ce-4814-8d03-e84c6775d1f4": {"nickname": "Hue tap dial switch 1", "category": ["RotaryControl", "MultiButton"], "tags": ["PhilipsHue", "tc0_4fab94c3-a3ce-4814-8d03-e84c6775d1f4", "RotaryControl", "tc0_philipshue", "MultiButton"]},
    "tc0_ebe47e098219089fc7frjx__ep1": {"nickname": "스마트빌 전등 스위치 6구 1", "category": ["Switch"], "tags": ["Tuya", "NoneNecessary", "LightSwitch", "tc0_ebe47e098219089fc7frjx__ep1", "Switch", "tc0_tuya"]},
    "tc0_ebe47e098219089fc7frjx__ep2": {"nickname": "스마트빌 전등 스위치 6구 2", "category": ["Switch"], "tags": ["Tuya", "NoneNecessary", "LightSwitch", "tc0_ebe47e098219089fc7frjx__ep2", "Switch", "tc0_tuya"]},
    "tc0_ebe47e098219089fc7frjx__ep3": {"nickname": "스마트빌 전등 스위치 6구 3", "category": ["Switch"], "tags": ["Tuya", "NoneNecessary", "LightSwitch", "tc0_ebe47e098219089fc7frjx__ep3", "Switch", "tc0_tuya"]},
    "tc0_ebe47e098219089fc7frjx__ep4": {"nickname": "스마트빌 전등 스위치 6구 4", "category": ["Switch"], "tags": ["Tuya", "NoneNecessary", "LightSwitch", "tc0_ebe47e098219089fc7frjx__ep4", "Switch", "tc0_tuya"]},
    "tc0_ebe47e098219089fc7frjx__ep5": {"nickname": "스마트빌 전등 스위치 6구 5", "category": ["Switch"], "tags": ["Tuya", "NoneNecessary", "LightSwitch", "tc0_ebe47e098219089fc7frjx__ep5", "Switch", "tc0_tuya"]},
    "tc0_ebe47e098219089fc7frjx__ep6": {"nickname": "스마트빌 전등 스위치 6구 6", "category": ["Switch"], "tags": ["Tuya", "NoneNecessary", "LightSwitch", "tc0_ebe47e098219089fc7frjx__ep6", "Switch", "tc0_tuya"]},
    "tc0_ebfb522a028ef8add497wu": {"nickname": "스카이라이트 CCT", "category": ["Light", "Switch"], "tags": ["Tuya", "NoneNecessary", "SharedLight", "tc0_ebfb522a028ef8add497wu", "Light", "tc0_tuya", "Switch"]},
    "tc0_eb8c9cf310d709af51rs9c": {"nickname": "스카이라이트 YUER", "category": ["Light", "Switch"], "tags": ["Tuya", "NoneNecessary", "SharedLight", "tc0_eb8c9cf310d709af51rs9c", "Light", "tc0_tuya", "Switch"]},
    "tc0_ebd62449e3a700125du284": {"nickname": "투야 푸시 버튼 1", "category": ["Button", "Battery"], "tags": ["Tuya", "ModeToggle", "tc0_ebd62449e3a700125du284", "Button", "tc0_tuya", "Battery"]},
    "tc0_ebe62c3d24c9220549quqn": {"nickname": "투야 화재 감지 센서", "category": ["SmokeDetector", "Battery"], "tags": ["Tuya", "tc0_ebe62c3d24c9220549quqn", "SmokeDetector", "tc0_tuya", "Battery"]},
    "tc0_builtin_toast_publisher": {"nickname": "토스트 퍼블리셔", "category": ["ToastPublisher"], "tags": ["tc0_builtin_toast_publisher", "ToastPublisher", "tc0_local"]},
    "tc0_builtin_weather_provider": {"nickname": "날씨", "category": ["WeatherProvider"], "tags": ["tc0_builtin_weather_provider", "WeatherProvider", "tc0_local"]},
    "tc0_builtin_email_provider": {"nickname": "이메일", "category": ["EmailProvider"], "tags": ["tc0_builtin_email_provider", "EmailProvider", "tc0_local"]},
    "tc0_ebbcbc45bf05318db9w0ew": {"nickname": "투야 보안 카메라", "category": ["Camera"], "tags": ["Tuya", "tc0_ebbcbc45bf05318db9w0ew", "Camera", "tc0_tuya"]},
    "tc0_Smart_Wi-Fi_Plug__43": {"nickname": "스마트 Wi-Fi 플러그 1", "category": ["Plug", "Switch", "PowerMeter", "EnergyMeter"], "tags": ["Matter", "NoneNecessary", "tc0_Smart_Wi-Fi_Plug__43", "Plug", "tc0_matter", "Switch", "PowerMeter", "EnergyMeter"]},
    "tc0_Smart_Wi-Fi_Plug__44": {"nickname": "스마트 Wi-Fi 플러그 2", "category": ["Plug", "Switch", "PowerMeter", "EnergyMeter"], "tags": ["Matter", "NoneNecessary", "tc0_Smart_Wi-Fi_Plug__44", "Plug", "tc0_matter", "Switch", "PowerMeter", "EnergyMeter"]},
    "tc0_Wi-Fi_Plug__46": {"nickname": "스마트 Wi-Fi 플러그 3", "category": ["Plug", "Switch"], "tags": ["Matter", "NoneNecessary", "tc0_Wi-Fi_Plug__46", "Plug", "tc0_matter", "Switch"]},
    "tc0_builtin_printer": {"nickname": "사무실 프린터", "category": ["Printer"], "tags": ["Builtin", "tc0_builtin_printer", "Printer", "tc0_local"]},
    "Clock_IoT_Core": {"nickname": "시계", "category": ["Clock"], "tags": ["Clock_IoT_Core", "Clock"]},
    "tc0_Smart_Presence_Sensor__52__ep2": {"nickname": "재실 감지 센서 (구역 1)", "category": ["PresenceSensor"], "tags": ["Matter", "Section1", "tc0_Smart_Presence_Sensor__52__ep2", "PresenceSensor", "tc0_matter"]},
    "GlobalVariable_IoT_Core": {"nickname": "전역 변수", "category": ["GlobalVariable"], "tags": ["GlobalVariable_IoT_Core", "GlobalVariable"]},
    "tc0_57b081e4-f567-4a84-9121-4f0ed61ae733": {"nickname": "재실 상태 인디케이터 (구역 3)", "category": ["Light", "Switch"], "tags": ["PhilipsHue", "NoneNecessary", "Section3", "tc0_57b081e4-f567-4a84-9121-4f0ed61ae733", "Light", "tc0_philipshue", "Switch"]},
    "tc0_d1b5e845-cbe2-42b4-9606-8ad71cb14901": {"nickname": "재실 상태 인디케이터 (구역 1)", "category": ["Light", "Switch"], "tags": ["PhilipsHue", "NoneNecessary", "Section1", "tc0_d1b5e845-cbe2-42b4-9606-8ad71cb14901", "Light", "tc0_philipshue", "Switch"]},
    "tc0_4e13891d-054f-494a-9517-c56b38632fef": {"nickname": "재실 상태 인디케이터 (구역 2)", "category": ["Light", "Switch"], "tags": ["PhilipsHue", "NoneNecessary", "Section2", "tc0_4e13891d-054f-494a-9517-c56b38632fef", "Light", "tc0_philipshue", "Switch"]},
    "tc0_05b24023-a435-4e1a-bf7d-680c5a0174ba": {"nickname": "재실 상태 인디케이터 (구역 6)", "category": ["Light", "Switch"], "tags": ["PhilipsHue", "NoneNecessary", "Section6", "tc0_05b24023-a435-4e1a-bf7d-680c5a0174ba", "Light", "tc0_philipshue", "Switch"]},
    "tc0_ba52d76e-e6dc-41ff-8207-64c7d9d88b3b": {"nickname": "재실 상태 인디케이터 (구역 4)", "category": ["Light", "Switch"], "tags": ["PhilipsHue", "NoneNecessary", "Section4", "tc0_ba52d76e-e6dc-41ff-8207-64c7d9d88b3b", "Light", "tc0_philipshue", "Switch"]},
    "tc0_Smart_Presence_Sensor__60__ep2": {"nickname": "재실 감지 센서 (구역 2)", "category": ["PresenceSensor"], "tags": ["Matter", "Section2", "tc0_Smart_Presence_Sensor__60__ep2", "PresenceSensor", "tc0_matter"]},
    "tc0_Smart_Presence_Sensor__61__ep2": {"nickname": "재실 감지 센서 (구역 3)", "category": ["PresenceSensor"], "tags": ["Matter", "Section3", "tc0_Smart_Presence_Sensor__61__ep2", "PresenceSensor", "tc0_matter"]},
    "tc0_Smart_Presence_Sensor__62__ep2": {"nickname": "재실 감지 센서 (구역 4)", "category": ["PresenceSensor"], "tags": ["Matter", "Section4", "tc0_Smart_Presence_Sensor__62__ep2", "PresenceSensor", "tc0_matter"]},
    "tc0_Smart_Presence_Sensor__63__ep2": {"nickname": "재실 감지 센서 (구역 5)", "category": ["PresenceSensor"], "tags": ["Matter", "Section5", "tc0_Smart_Presence_Sensor__63__ep2", "PresenceSensor", "tc0_matter"]},
    "tc0_Smart_Presence_Sensor__64__ep2": {"nickname": "재실 감지 센서 (구역 6)", "category": ["PresenceSensor"], "tags": ["Matter", "Section6", "tc0_Smart_Presence_Sensor__64__ep2", "PresenceSensor", "tc0_matter"]},
    "tc0_Aqara_Door_and_Window_Sensor_P2__65__ep1": {"nickname": "Aqara Door and Window Sensor P2 65 ep1", "category": ["ContactSensor"], "tags": ["Matter", "tc0_Aqara_Door_and_Window_Sensor_P2__65__ep1", "ContactSensor", "tc0_matter"]},
    "tc0_builtin_chat_provider": {"nickname": "AI 챗봇", "category": ["ChatProvider"], "tags": ["tc0_builtin_chat_provider", "ChatProvider", "tc0_local"]},
    "tc0_builtin_news_provider": {"nickname": "뉴스", "category": ["NewsProvider"], "tags": ["tc0_builtin_news_provider", "NewsProvider", "tc0_local"]},
    "tc0_builtin_message_sender": {"nickname": "문자 발송", "category": ["MessageSender"], "tags": ["tc0_builtin_message_sender", "MessageSender", "tc0_local"]},
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

# service_list_ver2.0.7 신규 스킬 실험 중 오류가 관측된 명령만 남김 (세부 로그 분석용).
# 각 줄 끝 주석 = 관측된 증상.
COMMANDS_4 = [
    # ── ChatProvider ──
    "챗봇에게 대한민국의 수도가 어디인지 물어봐줘",                # speaker_speak가 #ChatProvider 태그에 붙음(4/4 재현)
    "챗봇에게 삼행시 지어달라고 하고 토스트로 보여줘",             # Message 미분리(명령 전체 verbatim) + 토스트 고정문구→답변 유실
    # ── NewsProvider ──
    "최신 뉴스 요약해서 스피커로 읽어줘",                        # Topic/Count 과다주입(테크/3, 명령엔 없음)
    "AI 뉴스 3개만 토스트로 보여줘",                            # Topic "AI" 누락(→"") + 토스트 고정문구→뉴스 유실
    "경제 뉴스 알려줘",                                       # 요청 안 한 토스트(고정문구) 덤으로 추가
    # ── MessageSender ──
    "문이 열리면 '문이 열렸습니다'라고 010-1234-5678로 문자 보내줘",  # SMS 본문이 영어("The door is open")로 번역 유출
]

# 돌릴 그룹만 여기서 선택 (COMMANDS_1 / COMMANDS_2 / COMMANDS_3 / COMMANDS_4)
COMMANDS = COMMANDS_3

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
    # 단계별 추론 트레이스 (segments / IR / selectors / lowering / naming)
    print(f"----- reasoning log -----\n{log.get('logs', '')}")
    print(f"\n----- code -----\n{_format_code(result.get('code', ''))}")
    print(f"\nresponse_time : {log.get('response_time', '')}")


if __name__ == "__main__":
    print(f"■ {len(COMMANDS)} commands")
    for command in COMMANDS:
        run(command)
