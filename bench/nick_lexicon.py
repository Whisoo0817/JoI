"""별명을 영어로 옮긴다. 데이터셋이 영어라 별명도 영어여야 한다.
한국어 별명은 spaces.json 에 nickname_ko 로 남는다 (한국어판은 나중).
"""
import re

# 별명 한국어 → 영어. 긴 토큰부터 바꾼다.
NICK_TOKENS = [
    # 브랜드
    ("헤이홈", "HeyHome"), ("스마트빌", "Smartvill"), ("삼성", "Samsung"), ("투야", "Tuya"),
    ("미로", "Miro"), ("스카이라이트", "Skylight"),
    # 복합어 (긴 것 먼저)
    ("재실 상태 인디케이터", "occupancy indicator"), ("재실 감지 센서", "presence sensor"),
    ("재실 센서", "presence sensor"), ("아기 울음 감지", "baby cry sensor"),
    ("베이비 모니터", "baby monitor"), ("응급 호출 버튼", "emergency call button"),
    ("전등 스위치 6구", "6-gang light switch"), ("스마트 Wi-Fi 플러그", "smart plug"),
    ("화재 감지 센서", "smoke sensor"), ("공기질 센서", "air quality sensor"),
    ("온습도 센서", "temperature and humidity sensor"), ("소음 센서", "noise sensor"),
    ("문열림 센서", "door sensor"), ("창문 열림 센서", "window sensor"),
    ("모션&조도 센서", "motion and light sensor"), ("모션 센서", "motion sensor"),
    ("진동 센서", "vibration sensor"), ("토양 센서", "soil sensor"),
    ("적재 기울기 센서", "load tilt sensor"), ("트레이 기울기", "tray tilt"),
    ("배양수 수질 센서", "culture water quality sensor"), ("수질 센서", "water quality sensor"),
    ("암모니아 센서", "ammonia sensor"), ("양액 센서", "nutrient sensor"),
    ("양액 탱크 수위", "nutrient tank level"), ("양액 탱크", "nutrient tank"),
    ("양액 펌프", "nutrient pump"), ("물탱크 수위", "water tank level"),
    ("급수 탱크", "water tank"), ("급수 유량계", "water flow meter"),
    ("탱크 수위", "tank level"), ("태양광 계측기", "solar meter"),
    ("태양광 충전기", "solar charger"), ("가정용 ESS", "home battery"),
    ("비상 발전 배터리", "backup battery"), ("조수 퇴치기", "bird deterrent"),
    ("자동 급식기", "auto feeder"), ("주 급수 밸브", "main water valve"),
    ("관수 밸브", "irrigation valve"), ("관수 펌프", "irrigation pump"),
    ("관정 펌프", "well pump"), ("지하수 펌프", "well pump"),
    ("초저온 냉동고", "deep freezer"), ("시약 냉장고", "reagent fridge"),
    ("항온항습기", "climate chamber"), ("인큐베이터", "incubator"),
    ("육묘 챔버", "seedling chamber"), ("저온 챔버", "chill chamber"),
    ("장비 콘센트", "equipment outlet"), ("공구 충전기", "tool charger"),
    ("EV 충전기", "EV charger"), ("로봇청소기", "robot vacuum"), ("로봇팔", "robot arm"),
    ("3D 프린터", "3D printer"), ("자동문", "automatic door"), ("도크 문", "dock door"),
    ("가동률 현황판", "utilization board"), ("실적 현황판", "performance board"),
    ("생산 현황판", "production board"), ("현황판", "status board"),
    ("화상회의 카메라", "conference camera"), ("화상회의 캠", "conference cam"),
    ("회의 녹음기", "meeting recorder"), ("디스플레이", "display"),
    ("공기청정기", "air purifier"), ("에어드레서", "clothing care unit"),
    ("스타일러", "clothing care unit"), ("보광등", "grow light"), ("무드등", "mood light"),
    ("컬러 스트립", "color strip"), ("벽 디머", "wall dimmer"),
    ("푸시 버튼", "push button"), ("차광막", "shade screen"),
    ("환기팬", "exhaust fan"), ("순환팬", "circulation fan"), ("흄후드", "fume hood"),
    ("스프링클러", "sprinkler"), ("컨베이어", "conveyor"), ("조립기", "assembly machine"),
    ("포장기", "packer"), ("신호등", "status light"), ("계량대", "weigh station"),
    ("체중계", "scale"), ("유량계", "flow meter"), ("전력계", "power meter"),
    ("계량기", "meter"), ("급이기", "feeder"), ("급식기", "feeder"),
    ("에이컨", "AC"), ("에어컨", "AC"), ("가습기", "humidifier"), ("온수기", "water heater"),
    ("보일러", "boiler"), ("냉장고", "fridge"), ("프린터", "printer"), ("펫캠", "pet cam"),
    ("스피커", "speaker"), ("챔버", "chamber"), ("커튼", "curtain"), ("모니터", "monitor"),
    ("금고", "safe"), ("펌프", "pump"), ("밸브", "valve"), ("조명", "light"), ("전등", "light"),
    ("문자 발송", "SMS sender"), ("보안 카메라", "security camera"),
    ("농도 인디케이터", "level indicator"), ("인디케이터", "indicator"),
    ("컬러", "color"), ("농도", "level"),
    ("화면", "screen"), ("재실", "presence"), ("등", "light"), ("문", "door"),
    ("배터리", "battery"), ("조도", "light level"), ("온도", "temperature"),
    ("습도", "humidity"), ("전역 변수", "global variables"), ("알림", "notifications"),
    ("날씨", "weather"), ("일정", "calendar"), ("이메일", "email"), ("뉴스", "news"),
    ("AI 챗봇", "chatbot"), ("토스트 퍼블리셔", "toast publisher"),
    ("내 폰", "my phone"), ("시계", "clock"), ("해", "sun"),
    # 장소·수식
    ("거실", "living room"), ("침실", "bedroom"), ("사무실", "office"), ("서재", "study"),
    ("아기방", "nursery"), ("회의실", "meeting room"), ("창고", "warehouse"),
    ("입구", "entrance"), ("좌측", "left"), ("우측", "right"), ("구역", "zone"),
    ("큰거", "large"), ("작은거", "small"), ("지점", "branch"),
    # 번호 단위
    ("번 하우스", "greenhouse"), ("호기", "machine"), ("라인", "line"), ("열", "row"),
    ("동", "barn"), ("단", "tier"), ("번", ""), ("A방", "room A"), ("B방", "room B"),
    ("C방", "room C"),
]


# "3번 밸브" 는 "valve 3" 이 되어야 한다 — 앞에 붙은 번호를 떼어 뒤로 보낸다
_LEAD = [(re.compile(r"(\d+)번 하우스\s*"), "greenhouse {n} "),
         (re.compile(r"(\d+)호기\s*"), "machine {n} "),
         (re.compile(r"(\d+)라인\s*"), "line {n} "),
         (re.compile(r"(\d+)구역\s*"), "zone {n} "),
         (re.compile(r"(\d+)열\s*"), "row {n} "),
         (re.compile(r"(\d+)동\s*"), "barn {n} "),
         (re.compile(r"(\d+)단\s*"), "tier {n} ")]
_TAIL = re.compile(r"(\d+)번\s*")


def to_en(k):
    s = k
    for rx, tpl in _LEAD:
        s = rx.sub(lambda m: tpl.format(n=m.group(1)), s)
    tail = ""
    m = _TAIL.search(s)
    if m:
        tail = " " + m.group(1)
        s = _TAIL.sub("", s)
    for ko, en in NICK_TOKENS:
        s = s.replace(ko, " " + en + " ")
    s = re.sub(r"\s+", " ", s).strip() + tail
    s = re.sub(r"\(\s*", "(", re.sub(r"\s*\)", ")", s)).strip()
    assert not re.search(r"[가-힣]", s), f"못 옮긴 별명: {k} → {s}"
    return s
