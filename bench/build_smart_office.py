# -*- coding: utf-8 -*-
"""run.py 의 QA 명령어 37개(COMMANDS_1~3) → 영어 + 벤치마크 라벨 → bench/smart_office.csv.

이 37개는 실제 연구실 허브(스마트 오피스)에 대고 QA 시트에서 나온 문장이다.
벤치마크에서 유일한 '현장' 데이터라 한국어 원문을 함께 보존한다.
COMMANDS_4(챗봇/뉴스/문자)는 whisoo 결정으로 제외.

5,000개(dataset_5k.csv)와 **따로** 두는 묶음이다. 겹치는 문장은 1개뿐이다.

`connected_devices` 열에는 run.py 의 CONNECTED_DEVICES 58대를 그대로 싣는다 —
줄마다 같은 값이다. 기존 dataset.csv 가 쓰는 방식이라 그대로 읽힌다
(`json.loads(row["connected_devices"])`). run.py 를 고치면 여기도 따라 바뀐다.

딱 한 군데만 손댄다: 카테고리 이름 `ToastPublisher` → `NotificationProvider`.
3.0.0 에서 이름이 바뀐 같은 것이다 (build_spaces.py 의 LAB01 도 똑같이 한다).
기기 목록·id·별명·나머지 태그는 실물 그대로다.

라벨 뜻은 bench/README.md 참조. E: 1=실행 2=기본값으로 실행 3=되묻기 4=거절.
"""
import ast
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RUNPY = os.path.join(os.path.dirname(HERE), "run.py")


def connected_devices():
    """run.py 의 CONNECTED_DEVICES 를 그대로 가져온다.
    import 하면 joi 전체가 딸려 오므로 소스만 읽어 값을 꺼낸다."""
    tree = ast.parse(open(RUNPY, encoding="utf-8").read())
    devs = None
    for n in tree.body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "CONNECTED_DEVICES":
            devs = ast.literal_eval(n.value)
    if devs is None:
        raise SystemExit("run.py 에서 CONNECTED_DEVICES 를 못 찾음")
    remap = {"ToastPublisher": "NotificationProvider"}   # 3.0.0 에서 바뀐 이름
    for v in devs.values():
        v["category"] = [remap.get(c, c) for c in v["category"]]
        v["tags"] = [remap.get(t, t) for t in v["tags"]]
    return devs

# (그룹, 한국어 원문, 영어, D, A1, A2, B2, B3, C, E, 메모)
R = [
# ── COMMANDS_1: 단순 동작 + 조건 ───────────────────────────────────────────
("C1", "조명 밝기 20 퍼센트로 설정해줘",
 "Set the light brightness to 20 percent.",
 "D1", "type", "unmarked", "explicit", 1, "plain", 1,
 "장소를 안 말했는데 조명이 10대 — 무지정 단수 규약 대상"),
("C1", "문이 5분 이상 열려 있으면 문 열렸다고 알려줘",
 "If the door stays open for more than 5 minutes, let me know the door is open.",
 "D5", "type", "unmarked", "explicit", 1, "plain", 2,
 "알릴 채널 미지정(스피커/토스트) → 기본값 선택"),
("C1", "문이 5분 이상 열려있으면 스피커로 문 열렸다고 알려줘",
 "If the door stays open for more than 5 minutes, announce through the speaker that the door is open.",
 "D5", "type", "unmarked", "explicit", 1, "plain", 1, "위 문장의 채널 명시판 — 짝 비교용"),
("C1", "10분 이상 사람이 있으면 환기 알림을 보내줘",
 "If someone is present for more than 10 minutes, send a ventilation alert.",
 "D5", "type", "unmarked", "explicit", 1, "plain", 2, "채널 미지정"),
("C1", "10분 이상 사람이 있으면 환기하라고 스피커로 알려줘",
 "If someone is present for more than 10 minutes, announce through the speaker to ventilate.",
 "D5", "type", "unmarked", "explicit", 1, "plain", 1, "채널 명시판"),
("C1", "미세먼지 좋음이면 창문 닫으라고 알려줘",
 "If the fine dust level is good, tell me to close the window.",
 "D3", "type", "unmarked", "grade", 1, "plain", 2,
 "의도가 뒤집힌 듯한 명령(좋은데 왜 닫나) + 등급어 '좋음'의 수치 경계 + 채널 미지정"),
("C1", "이산화탄소 농도가 1000ppm 이상이면 스피커로 환기해줘라고 말해줘",
 "If the CO2 level is 1000 ppm or higher, say 'please ventilate' through the speaker.",
 "D3", "type", "unmarked", "explicit", 1, "plain", 1, ""),
("C1", "사람이 감지되면 토스트 알림으로 \"재실 감지\"라고 보여줘",
 "When presence is detected, show 'occupancy detected' as a toast notification.",
 "D4", "type", "unmarked", "explicit", 1, "plain", 1, "NotificationProvider 사용"),
("C1", "창문이 열리면 커튼을 닫아줘",
 "When the window opens, close the curtain.",
 "D4", "absent_kind", "unmarked", "explicit", 1, "plain", 4, "LAB01 에 커튼 없음 → 거절"),
("C1", "커튼 닫아줘", "Close the curtain.",
 "D1", "absent_kind", "unmarked", "explicit", 1, "terse", 4, "LAB01 에 커튼 없음 → 거절"),
("C1", "도어락을 잠가줘", "Lock the door lock.",
 "D1", "absent_kind", "unmarked", "explicit", 1, "plain", 4, "LAB01 에 도어락 없음 → 거절"),
# ── COMMANDS_2: 스케줄 / 시간+조건 ─────────────────────────────────────────
("C2", "매일 오후 4시 30분에 스피커로 환기 안내를 한 번 해줘.",
 "Every day at 4:30 PM, announce the ventilation notice once through the speaker.",
 "D6", "type", "unmarked", "explicit", 1, "plain", 1, ""),
("C2", "매일 오후 4시 35분에 회의 시작 5분 전이라고 스피커로 안내해줘.",
 "Every day at 4:35 PM, announce through the speaker that the meeting starts in 5 minutes.",
 "D6", "type", "unmarked", "explicit", 1, "plain", 1, ""),
("C2", "매일 오후 4시 39분에 환기히라고 스피커로 알려주고 알림도 띄워줘.",
 "Every day at 4:39 PM, tell me through the speaker to ventliate and show a notification too.",
 "D6", "type", "unmarked", "explicit", 2, "noisy", 1, "원문 오타(환기히라고) 를 영어 오타로 옮김"),
("C2", "매일 오후 6시 18분에 모든 조명을 꺼줘.",
 "Every day at 6:18 PM, turn off all the lights.",
 "D6", "type", "all", "explicit", 1, "plain", 1, ""),
("C2", "오후 6시 20분에 모든 조명을 꺼줘",
 "At 6:20 PM, turn off all the lights.",
 "D6", "type", "all", "explicit", 1, "plain", 2,
 "'매일' 이 없음 — 오늘 한 번인지 매일인지 갈림"),
("C2", "매시간 정각마다 스피커로 시간을 알려줘",
 "On the hour, every hour, announce the time through the speaker.",
 "D6", "type", "unmarked", "explicit", 1, "plain", 1, ""),
("C2", "매일 오후 4시 46분에 모든 조명을 꺼줘.",
 "Every day at 4:46 PM, turn off all the lights.",
 "D6", "type", "all", "explicit", 1, "plain", 1, ""),
("C2", "매일 오후 4시 49분에 에어컨을 꺼줘",
 "Every day at 4:49 PM, turn off the air conditioner.",
 "D6", "type", "unmarked", "explicit", 1, "plain", 1, ""),
("C2", "오후 5시에 사람이 감지되면 조명을 20 퍼센트만 켜줘",
 "At 5 PM, if presence is detected, turn on the lights at only 20 percent.",
 "D13", "type", "unmarked", "explicit", 2, "plain", 1, "시각 + 조건"),
("C2", "오후 5시에 사람이 감지되면 에어컨을 켜줘",
 "At 5 PM, if presence is detected, turn on the air conditioner.",
 "D13", "type", "unmarked", "explicit", 2, "plain", 1, ""),
# ── COMMANDS_3: 별명 / 다중 기기 / 지속 / ANY·ALL ──────────────────────────
("C3", "오후 3시에 삼성 공기청정기 큰거를 토글해줘",
 "At 3 PM, toggle the big Samsung air purifier.",
 "D6", "nickname", "unmarked", "explicit", 1, "plain", 1,
 "별명 문자열로 지목 — 공기청정기 3대 중 하나"),
("C3", "투야 장치들 다 꺼줘", "Turn off all the Tuya devices.",
 "D1", "brand", "all", "explicit", 1, "terse", 1,
 "브랜드 지목 — 축으로 늘리지 않기로 한 예외 2건 중 하나(현장 문장이라 보존)"),
("C3", "헤이홈 IR 에어컨 꺼줘", "Turn off the Hejhome IR air conditioner.",
 "D1", "brand", "unmarked", "explicit", 1, "terse", 1, "브랜드+종류 — 예외 2건 중 둘째"),
("C3", "퇴근 후 사람이 감지되면 조명을 켜고 카메라 녹화 시작하고 메일 보내줘",
 "After work hours, if presence is detected, turn on the light, start camera recording, and send an email.",
 "D13", "type", "unmarked", "vague", 3, "plain", 3,
 "'퇴근 후' 의 시각이 안 정해짐 + 메일 수신자 없음 → 되묻기"),
("C3", "오후 6시 27분에 카메라 녹화 시작하고 'lindy@mysmax.kr'로 메일 보내줘",
 "At 6:27 PM, start camera recording and send an email to 'lindy@mysmax.kr'.",
 "D6", "type", "unmarked", "explicit", 2, "plain", 1, ""),
("C3", "오후 6시 30분에 조명을 끄고 카메라 녹화 시작하고 메일 보내줘",
 "At 6:30 PM, turn off the light, start camera recording, and send an email.",
 "D6", "type", "unmarked", "explicit", 3, "plain", 3, "메일 수신자 미지정 → 되묻기"),
("C3", "문이 열리면 카메라로 촬영하고 'lindy@mysmax.kr' 이메일로 보내줘",
 "When the door opens, take a picture with the camera and send it to 'lindy@mysmax.kr'.",
 "D4", "type", "unmarked", "explicit", 2, "plain", 1, ""),
("C3", "CO₂가 1분 이상 1000ppm 이상이면 환기하라고 알려줘",
 "If CO2 stays at 1000 ppm or higher for more than a minute, tell me to ventilate.",
 "D5", "type", "unmarked", "explicit", 1, "plain", 2, "채널 미지정"),
("C3", "CO₂가 1분 이상 1000ppm 이상이면 스피커로 환기하라고 알려줘",
 "If CO2 stays at 1000 ppm or higher for more than a minute, announce through the speaker to ventilate.",
 "D5", "type", "unmarked", "explicit", 1, "plain", 1, "채널 명시판"),
("C3", "문이 1분 이상 열려 있으면 스피커로 문 닫으라고 알려줘",
 "If the door stays open for more than a minute, announce through the speaker to close it.",
 "D5", "type", "unmarked", "explicit", 1, "plain", 1, ""),
("C3", "모든 문이 닫혀 있으면 스피커로 문이 모두 닫혔다고 알려줘",
 "If all the doors are closed, announce through the speaker that every door is closed.",
 "D3", "type", "all", "explicit", 1, "plain", 1, "ALL 판정"),
("C3", "문 하나라도 닫혀있으면 스피커로 알려줘",
 "If any one of the doors is closed, let me know through the speaker.",
 "D3", "type", "any", "explicit", 1, "plain", 1, "ANY 판정"),
("C3", "사람이 한 명이라도 감지되면 스피커로 사람이 있다고 알려줘",
 "If at least one person is detected, announce through the speaker that someone is here.",
 "D3", "type", "any", "explicit", 1, "plain", 1, "ANY 판정"),
("C3", "모든 재실 센서가 사람 없음이면 조명을 꺼줘",
 "If every presence sensor reports no one, turn off the lights.",
 "D3", "type", "all", "explicit", 1, "plain", 1, "부재 조건 ALL"),
("C3", "창문 중 하나라도 닫혀 있으면 창문 열라고 알려줘",
 "If any of the windows is closed, tell me to open the window.",
 "D3", "type", "any", "explicit", 1, "plain", 2, "채널 미지정"),
("C3", "창문이 열려 있는데 에어컨이 켜져 있으면 에어컨을 꺼줘",
 "If a window is open while the air conditioner is on, turn off the air conditioner.",
 "D3", "type", "unmarked", "explicit", 2, "plain", 1, "조건 두 개 AND"),
]

COLS = ["id", "src", "group", "space_id", "command_eng", "command_kor",
        "D", "A1", "A2", "B2", "B3", "C", "E", "note", "connected_devices"]


def main():
    dev = connected_devices()
    dev_json = json.dumps(dev, ensure_ascii=False)
    rows = []
    for i, (g, ko, en, D, A1, A2, B2, B3, C, E, note) in enumerate(R, 1):
        rows.append(dict(id=f"SO{i:02d}", src="run.py", group=g, space_id="LAB01",
                         command_eng=en, command_kor=ko, D=D, A1=A1, A2=A2, B2=B2,
                         B3=B3, C=C, E=E, note=note, connected_devices=dev_json))
    dst = os.path.join(HERE, "smart_office.csv")
    with open(dst, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS); w.writeheader(); w.writerows(rows)

    import collections
    cats = collections.Counter(c for d in dev.values() for c in d["category"])
    print(f"bench/smart_office.csv: {len(rows)}행 · 기기 {len(dev)}대 · "
          f"카테고리 {len(cats)}종 (줄마다 같은 기기 목록)")
    for ax in ("D", "A1", "A2", "B2", "C", "E"):
        print(f"  {ax}:", dict(collections.Counter(r[ax] for r in rows).most_common()))
    # 검산: 문장이 대는 기기가 실제로 있는가 / 카탈로그에 있는 카테고리인가
    cat = json.load(open(os.path.join(os.path.dirname(HERE), "files",
                                      "service_list_ver3.0.0.json"), encoding="utf-8"))
    bad = [c for c in cats if c not in cat]
    print("  검산:", f"카탈로그에 없는 카테고리 {bad}" if bad else "어긋난 것 없음 ✅")


if __name__ == "__main__":
    main()
