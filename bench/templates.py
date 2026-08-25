#!/usr/bin/env python3
"""문형 틀. build_dataset.py 가 여기에 공간·기기·숫자를 끼워 5,000문장을 만든다.

  TRIG  "언제" 를 말하는 부사절. 문장 앞에도 뒤에도 붙을 수 있게 썼다.
  ACT   "무엇을 해라". {dev} 자리에 기기 지목이 들어간다.
  TONE  같은 뜻을 여섯 가지 말투로 낸다.
슬롯: {dev} 기기 지목 · {n} 숫자 · {time} 시각 · {sensor} 센서 이름 · {place} 장소
"""

# ── 언제 ───────────────────────────────────────────────────────────────
TRIG = {
    "sun": ["at sunset", "when the sun goes down", "as the sun sets",
            "at sunrise", "when the sun comes up", "around sundown",
            "once it gets dark outside"],
    "time": ["at {time}", "every day at {time}", "at {time} on weekdays",
             "every morning at {time_am}", "every night at {time_pm}",
             "on {weekday} at {time}", "every {n} minutes"],
    "timer": ["after {n} minutes", "{n} minutes from now", "after waiting {n} minutes",
              "once the {n} minute timer runs out"],
    "motion": ["when the motion sensor picks something up",
               "when {sensor} detects movement", "if motion is detected in the {place}",
               "the moment something moves in the {place}",
               "when nothing has moved for {n} minutes"],
    "presence": ["while someone is in the {place}", "when the {place} is occupied",
                 "once the {place} is empty", "while nobody is around",
                 "when someone shows up in the {place}"],
    "arrive": ["when I get home", "as soon as I arrive home", "when I pull into the driveway",
               "once I am back home", "when I am close to home"],
    "leave": ["when I leave home", "once everyone has left", "after I head out",
              "when I am away from home"],
    "contact": ["when the {place} door opens", "if a window is left open",
                "when {sensor} says the door is open",
                "once the door has been open for {n} minutes",
                "when the door closes"],
    "doorbell": ["when someone rings the doorbell", "if the doorbell goes off",
                 "when there is somebody at the door"],
    "button": ["when I press the button", "with a single press of {dev_t}",
               "when I double-press {dev_t}", "with one tap on the wall switch",
               "when the scene button is pressed"],
    # 문장이 대는 물리량과 시나리오의 센서가 맞아야 한다. 어느 센서에나 붙는
    # 일반 문형("{sensor} 가 300 을 넘으면")을 같이 둔다 — ir.py 가 짝을 맞춘다.
    "threshold": ["when the temperature goes above {deg_hi} degrees",
                  "if the temperature drops below {deg_lo} degrees",
                  "while the temperature stays over {deg_hi} degrees",
                  "when the humidity climbs over {pct} percent",
                  "once the air quality gets worse than {lvl}",
                  "if {sensor} reads more than {lvl}",
                  "once {sensor} goes over {lvl}",
                  "if {sensor} falls under {lvl}",
                  "while {sensor} stays above {lvl}"],
    "weather": ["when it starts raining", "if rain is in the forecast",
                "when it gets hot outside", "if the outside temperature drops below {deg_lo}",
                "when snow is expected", "if the forecast says frost"],
    "calendar": ["when a meeting is about to start", "at the start of my next event",
                 "if my calendar says I am busy", "when today's first event begins"],
    "phone": ["when my phone connects to the home wi-fi",
              "if my phone battery falls under {pct} percent",
              "when my phone goes into sleep mode", "while I am on a call"],
    "battery": ["when the battery drops below {pct} percent",
                "if any sensor battery is running low", "once the battery is full"],
    # 카탈로그의 Camera 는 사람을 감지하지 못한다. 카메라 자신의 상태로 건다.
    "security": ["when the camera starts recording", "if the camera comes on",
                 "while the camera is recording", "once the camera goes offline"],
    "smoke": ["when the smoke detector goes off", "if the smoke alarm sounds",
              "when {sensor} reports smoke"],
    "leak": ["when a water leak is detected", "if {sensor} finds water on the floor",
             "when the leak sensor trips"],
    "gas": ["when the gas sensor goes over {lvl}", "if a gas leak is detected",
            "when {sensor} reads a dangerous level"],
    "power": ["when power draw goes over {watt} watts", "if the meter reads above {watt}",
              "when energy use spikes", "if power draw stays above {watt} watts"],
    # 끝났다는 신호가 기기마다 다르다 — 세탁기는 남은 시간, 생산기계는 상태값
    "finished": ["when the washing machine finishes", "as soon as the load is finished",
                 "when the wash cycle ends", "when the machine finishes its cycle",
                 "once the line run is done", "when {dev_t} reports it is done"],
    "device": ["when {dev_t} turns on", "if {dev_t} is switched off",
               "once {dev_t} has been on for {n} minutes"],
    "vibration": ["when {sensor} picks up heavy vibration",
                  "if vibration goes over {lvl}", "when the machine starts shaking"],
    "tilt": ["when the load tilts past {tilt} degrees", "if {sensor} reports a tilt"],
    "proximity": ["when something comes within {cm} centimeters",
                  "if {sensor} sees an object in the way"],
    "wind": ["when the wind picks up past {wind}", "if wind speed goes over {wind}"],
    "emergency": ["when the emergency stop is hit", "if anyone presses the emergency stop"],
    "barrier": ["when the safety barrier is broken", "if someone crosses the light curtain"],
}

# ── 무엇을 ─────────────────────────────────────────────────────────────
ACT = {
    "light.on": ["turn on {dev}", "switch {dev} on", "put {dev} on", "get {dev} on",
                 "light up {dev}"],
    "light.off": ["turn off {dev}", "switch {dev} off", "shut {dev} off", "kill {dev}"],
    "light.dim": ["dim {dev} to {lo} percent", "set {dev} brightness to {n} percent",
                  "bring {dev} down to {lo} percent", "turn {dev} up to {hi} percent"],
    "light.color": ["set {dev} to {color}", "make {dev} {color}", "change {dev} to {color}",
                    "turn {dev} {color}"],
    # 기기를 안 대는 두 틀도 "무엇의" 장면인지는 밝힌다 — "영화 모드로 해" 만으로는
    # 무엇을 바꾸라는 말인지 알 수 없다 (whisoo). 어느 조명인지는 여전히 안 댄다.
    "light.scene": ["set the lights to the {scene} scene",
                    "switch {dev} to the {scene} scene",
                    "put {dev} into {scene} mode",
                    "run the {scene} scene on the lights"],
    "switch": ["turn on {dev}", "turn off {dev}", "toggle {dev}", "switch {dev} on"],
    "plug": ["turn on {dev}", "cut power to {dev}", "switch {dev} off"],
    "thermostat": ["set {dev} to {n} degrees", "turn the heating up to {n}",
                   "put {dev} on {n} degrees", "turn the heating off"],
    "ac": ["turn on {dev}", "set {dev} to {n} degrees", "put {dev} on cool",
           "turn {dev} off"],
    "fan": ["turn on {dev}", "run {dev} for {n} minutes", "turn {dev} off",
            "set {dev} to high"],
    "purifier": ["turn on {dev}", "put {dev} on auto", "run {dev} on turbo",
                 "turn {dev} off"],
    "humidity": ["turn on {dev}", "set {dev} to {n} percent", "turn {dev} off"],
    "cover": ["close {dev}", "open {dev}", "lower {dev} to {n} percent",
              "pull {dev} shut", "raise {dev}"],
    "lock": ["lock {dev}", "unlock {dev}", "make sure {dev} is locked"],
    "garage": ["close {dev}", "open {dev}", "shut {dev}"],
    "media": ["turn on {dev}", "pause {dev}", "play some music on {dev}",
              "turn {dev} off", "set the volume on {dev} to {n}"],
    "speaker": ["announce it on {dev}", "say it out loud on {dev}",
                "play a chime on {dev}"],
    "camera": ["start recording on {dev}", "take a snapshot with {dev}",
               "turn on {dev}", "stop recording on {dev}"],
    "siren": ["set off {dev}", "sound {dev}", "turn {dev} off"],
    "vacuum": ["start {dev}", "send {dev} back to its dock", "run {dev} in the {place}",
               "stop {dev}"],
    "mower": ["start {dev}", "send {dev} back to the dock", "park {dev}"],
    "coffee": ["start {dev}", "brew a cup on {dev}", "turn {dev} off"],
    "waterheater": ["turn on {dev}", "set {dev} to {n} degrees", "turn {dev} off"],
    # 채널을 안 댄 알림 — 있는 것 중 첫 번째로 간다 (policy.NOTIFY_ORDER)
    "notify": ["send me a notification", "let me know", "push me an alert",
               "tell me about it", "give me a heads-up", "warn me"],
    # 채널을 댄 알림 — 그 채널이 없으면 거절
    "notify.phone":   ["send a warning to my phone", "text my phone", "ping my phone"],
    "notify.speaker": ["say it out loud on the speaker", "announce it", "read it out"],
    "notify.screen":  ["show it on the screen", "pop it up on the display"],
    "query": ["tell me the temperature in the {place}", "what is {dev} doing",
              "check whether {dev} is on", "read out the humidity",
              "how much power is {dev} using"],
    "timer": ["set a {n} minute timer", "start a countdown for {n} minutes",
              "cancel the timer"],
    "sprinkler": ["run {dev} for {n} minutes", "start {dev}", "stop {dev}"],
    "growlight": ["turn on {dev}", "run {dev} for {n} hours", "turn {dev} off"],
    "ventilator": ["turn on {dev}", "run {dev} for {n} minutes", "turn {dev} off"],
    "feeder": ["run {dev}", "dispense feed with {dev}", "skip the next feeding"],
    "pump": ["start {dev}", "stop {dev}", "run {dev} for {n} minutes"],
    "valve": ["close {dev}", "open {dev}", "shut {dev} right away"],
    "chamber": ["set {dev} to {n} degrees", "start {dev}", "stop {dev}"],
    "conveyor": ["stop {dev}", "start {dev}", "slow {dev} down"],
    "compressor": ["start {dev}", "stop {dev}"],
    "statuslight": ["turn {dev} green", "turn {dev} red", "switch {dev} to amber"],
    "armrobot": ["park {dev}", "start {dev}", "stop {dev}"],
}

# ── 기기를 아예 안 대는 문장 ("시원하게 해줘") ──────────────────────────
# 기기도 서비스도 안 댄다. 무엇으로 무엇을 할지 시스템이 정해야 한다.
# 후보 기기가 여러 종류면 되묻기, 하나뿐이면 실행, 하나도 없으면 거절이다.
#
# 두 갈래인데 성질이 다르다.
#   state  "너무 어두워"    — 사실 진술. 조건절·시간절이 붙으면 문장이 깨진다.
#                             ("해질녘에 여기 어둡다" 는 명령이 아니다) → 즉시 실행에만
#   goal   "여기 좀 밝혀줘"  — 명령형. 시간절·조건절을 붙일 수 있다 → 어디든
VAGUE = {
    # 온도·바람
    "ac":         {"state": ["it is too hot in here", "I am sweating",
                             "this room is stuffy and hot"],
                   "goal":  ["cool this place down", "make it less warm",
                             "bring the temperature down"]},
    "fan":        {"state": ["it feels stuffy", "there is no air in here",
                             "the air is not moving"],
                   "goal":  ["get some air moving", "make it breezy"]},
    "thermostat": {"state": ["I am cold", "it is freezing in here", "it is chilly"],
                   "goal":  ["warm this room up", "make it cozy", "take the chill off"]},
    "cover":      {"state": ["the glare is bad", "the sun is in my eyes"],
                   "goal":  ["block the sun", "give me some privacy",
                             "shut out the light from outside"]},
    # 밝기·분위기
    "light.on":   {"state": ["it is too dark in here", "I cannot see anything",
                             "this room is gloomy"],
                   "goal":  ["brighten this place up", "give me some light to read by"]},
    "light.off":  {"state": ["it is too bright", "I am going to sleep"],
                   "goal":  ["kill the lights in here", "make it dark"]},
    "light.dim":  {"state": ["this is harsh on the eyes"],
                   "goal":  ["make it dimmer", "tone it down a bit",
                             "set the mood softer"]},
    "light.color": {"state": ["this white light is harsh"],
                    "goal": ["give this room some color", "make it feel warmer in here",
                             "set a calmer tone"]},
    "light.scene": {"state": [],
                    "goal": ["make it cozy in here", "set the mood for a movie",
                             "get this place ready for guests",
                             "make it feel like morning"]},
    # 공기·습도
    "purifier":   {"state": ["the air feels bad", "it smells in this room",
                             "the air quality is awful"],
                   "goal":  ["clean the air in here", "freshen this room up"]},
    "humidity":   {"state": ["the air is too dry", "my throat is dry",
                             "the windows are fogging up"],
                   "goal":  ["fix the humidity in here"]},
    "ventilator": {"state": ["it smells terrible in here", "the fumes are getting bad"],
                   "goal":  ["air this place out", "get fresh air in here"]},
    # 청소·집안일
    "vacuum":     {"state": ["the floor is dirty", "there are crumbs everywhere",
                             "the carpet needs a pass"],
                   "goal":  ["clean up in here", "tidy the floor"]},
    "mower":      {"state": ["the grass is getting long", "the lawn looks rough"],
                   "goal":  ["deal with the lawn"]},
    "coffee":     {"state": ["I need caffeine", "I am half asleep"],
                   "goal":  ["get me something hot to drink", "make me a cup"]},
    "waterheater": {"state": ["the water is cold", "no hot water again"],
                    "goal": ["I want a hot shower", "get the water hot"]},
    # 소리·화면
    "media":      {"state": ["it is too quiet in here", "I cannot hear the show",
                             "it is too loud"],
                   "goal":  ["put something on", "I want some music",
                             "turn it down a bit"]},
    "speaker":    {"state": [],
                   "goal":  ["say it out loud", "tell everyone in the house",
                             "let me hear it"]},
    # 보안·문단속
    "lock":       {"state": ["I do not feel safe", "I am heading out"],
                   "goal":  ["make sure the place is secure", "lock things up"]},
    "garage":     {"state": ["I am pulling out", "I parked already"],
                   "goal":  ["close things up out front"]},
    "camera":     {"state": [],
                   "goal":  ["keep an eye on the place",
                             "let me see what is going on", "record this"]},
    "siren":      {"state": [],
                   "goal":  ["scare them off", "make some noise", "raise the alarm"]},
    # 전원·에너지
    "switch":     {"state": ["I am done for the day",
                             "nothing needs to be on right now"],
                   "goal":  ["shut everything down in here"]},
    "plug":       {"state": ["we are wasting electricity"],
                   "goal":  ["let us save some power", "cut the standby draw"]},
    # 상태 확인
    "query":      {"state": [],
                   "goal":  ["is everything alright at home", "how are things in here",
                             "did I leave anything on", "what is the situation"]},
    "notify":     {"state": [],
                   "goal":  ["keep me posted", "tell me if something is off",
                             "I want to know when it changes"]},
    "timer":      {"state": [],
                   "goal":  ["remind me in a bit", "give me a few minutes"]},
    # 농장
    "sprinkler":  {"state": ["the crops look dry", "the soil is parched",
                             "these plants need water"],
                   "goal":  ["get water to the field"]},
    "growlight":  {"state": ["the plants are not getting enough light",
                             "it is dim in the grow room"],
                   "goal":  ["give the plants more light"]},
    "feeder":     {"state": ["the animals look hungry", "feeding time is overdue"],
                   "goal":  ["feed them"]},
    "pump":       {"state": ["the tank is running low",
                             "we need more water in the line"],
                   "goal":  ["get the water moving"]},
    # 공장·연구실
    "conveyor":   {"state": ["something is jammed"],
                   "goal":  ["stop the line", "hold production"]},
    "valve":      {"state": ["water is going everywhere", "there is a leak"],
                   "goal":  ["shut the water off", "stop the flow"]},
    "compressor": {"state": ["the air pressure is dropping"],
                   "goal":  ["build the pressure back up"]},
    "statuslight": {"state": [],
                    "goal": ["show everyone we are running",
                             "flag this line as stopped"]},
    "armrobot":   {"state": [], "goal": ["park the arm", "hold the cell"]},
    "chamber":    {"state": ["the samples are getting warm",
                             "this batch is off temperature"],
                   "goal":  ["get the samples back on temperature"]},
}

# ── 시간·로직이 진한 문형 ──────────────────────────────────────────────
# IFTTT·HA 는 반복·누적·제한시간을 표현하지 못해서 원천에 거의 없다.
# 그래도 사람은 이렇게 시킨다. D축이 D1·D4 에만 몰리지 않게 일부를 이 틀로 쓴다.
# {a} 동작절 · {t} 시간절(있으면) · {n},{m} 숫자 · {cond} 조건
#
# 두 묶음으로 나눈다. TAP(IFTTT 같은 트리거-액션 한 줄)이 표현할 수 있느냐가 기준이다.
#   LOGIC_SOFT  조건·지연이 얹힌 정도. IFTTT Pro 의 필터 코드면 어찌어찌 된다
#   LOGIC_HARD  반복·제한시간·누적·비교. TAP 으로는 아예 안 된다
LOGIC_SOFT = [
    ("D3", "if {cond} right now, {a}"),
    ("D3", "{a}, but only if {cond}"),
    ("D2", "{a}, then {n} minutes later turn it back off"),
    ("D2", "wait {n} minutes and then {a}"),
    ("D5", "keep checking and {a} for as long as {cond}"),
    ("D5", "{a} while {cond}, and stop once that changes"),
]
LOGIC_HARD = [
    ("D7", "check every {n} minutes and {a} if {cond}"),
    ("D7", "{a} every {n} minutes"),
    ("D8", "{a} every {n} minutes for the next {m} hours"),
    ("D8", "repeat this {m} times: {a}, then wait {n} minutes"),
    ("D8", "{a} every {n} minutes until {cond}"),
    ("D9", "once {cond}, {a} every {n} minutes"),
    ("D10", "wait up to {n} minutes to see if {cond}; if not, {a}"),
    ("D11", "if it is higher than it was an hour ago, {a}"),
    ("D11", "compare it with yesterday at the same time and {a} if it went up"),
    ("D12", "count how many times it happens and {a} once it passes {m}"),
    ("D13", "{a} every {n} minutes while {cond}, and stop after {m} hours"),
    ("D13", "wait until {cond}, then {a} every {n} minutes for {m} hours"),
]
LOGIC = LOGIC_SOFT + LOGIC_HARD   # 옛 이름

# ── 어떤 동작에 어떤 문형을 붙일 수 있나 ───────────────────────────────
# 되풀이해도 뜻이 있는 동작. 이미 그 상태인 것을 다시 시키는 말은 안 만든다
#   ("10분마다 에어컨 꺼" — 이미 꺼져 있다. "15분마다 블라인드 닫아" — 이미 닫혀 있다)
# 여기 적은 것은 할 때마다 새로 일어난다 — 알리기·읽기·내보내기·정해진 시간 돌리기.
REPEATABLE = {
    "send me a notification", "let me know", "push me an alert", "tell me about it",
    "give me a heads-up", "warn me",
    "send a warning to my phone", "text my phone", "ping my phone",
    "show it on the screen", "pop it up on the display",
    "say it out loud on the speaker", "announce it", "read it out",
    "tell me the temperature in the {place}", "what is {dev} doing",
    "check whether {dev} is on", "read out the humidity",
    "how much power is {dev} using",
    "announce it on {dev}", "say it out loud on {dev}", "play a chime on {dev}",
    "take a snapshot with {dev}", "brew a cup on {dev}",
    "run {dev}", "dispense feed with {dev}",
    "run {dev} for {n} minutes", "run {dev} for {n} hours",
    "set a {n} minute timer", "start a countdown for {n} minutes",
    "set off {dev}", "sound {dev}", "toggle {dev}",
}

# 켜 두었다가 멈출 수 있는 동작. "~인 동안 …하고, 그러다 바뀌면 멈춰"(D5) 와
# "…하고, {n}분 뒤에 다시 꺼"(D2) 는 무언가를 **켠** 뒤라야 말이 된다.
#   ("알림 띄워 주고, 그러다 바뀌면 멈춰" · "23도로 맞춰 주고, 30분 뒤에 다시 꺼")
TURN_ON = {"ac", "fan", "purifier", "ventilator", "humidity", "heater", "growlight",
           "light.on", "plug", "switch", "media", "vacuum", "sprinkler", "pump",
           "conveyor", "compressor", "mower", "chamber", "camera", "coffee",
           "waterheater", "armrobot"}

# ── 물리적으로 거꾸로인 짝 ─────────────────────────────────────────────
# 센서가 없어서 못 하는 명령은 시험 문제로 값이 있다. 그런데 **센서는 있는데
# 시키는 게 해로운** 명령은 다르다 — 지금 판정 축(execute/ask/refuse)에 "위험해서
# 거절" 이 없어서 정답을 적을 수가 없다. 그래서 아예 안 만든다 (whisoo 2026-08-25).
#
# 상황 이름 → 그 상황에서 하면 안 되는 (동작 갈래, 켜냐/끄냐).
#   "on"  = 켜기·올리기·시작 · "off" = 끄기·내리기·잠그기·풀기 · "*" = 둘 다
UNSAFE = {
    "cold":   [("fan", "on"), ("ac", "on"), ("ventilator", "on"),
               ("purifier", "on"), ("thermostat", "off")],  # 추운데 냉방·난방 끄기
    "hot":    [("thermostat", "on"), ("waterheater", "on"),
               ("ventilator", "off"), ("fan", "off"), ("ac", "off")],
    "gas":    [("ventilator", "off"), ("purifier", "off"), ("valve", "on"),
               ("thermostat", "on"), ("siren", "off")],    # 가스인데 환기·경보를 끄다
    "smoke":  [("ventilator", "off"), ("thermostat", "on"), ("siren", "off"),
               ("lock", "on")],                            # 불났는데 문을 잠그다
    "leak":   [("pump", "on"), ("sprinkler", "on"), ("valve", "on"),
               ("siren", "off")],
    "airbad": [("ventilator", "off"), ("purifier", "off")],
    "humid":  [("humidity", "on"), ("sprinkler", "on")],   # 습한데 가습
    "dark":   [("lock", "off"), ("garage", "on"), ("cover", "on"),
               ("light.off", "*")],                        # 어두운데 열고 끄다
    "open":   [("lock", "off"), ("thermostat", "on"), 
               ("ac", "on")],                              # 열려 있는데 냉난방
    "wet":    [("sprinkler", "on"), ("mower", "on"), ("cover", "on")],  # 비·눈
    "frost":  [("fan", "on"), ("ac", "on"), ("cover", "on")],
    "empty":  [("light.on", "on"), ("media", "on"), ("coffee", "on"),
               ("lock", "off"), ("garage", "on")],         # 아무도 없는데 켜고 열다
    # 아래는 재검토(opus 5대)에서 더 나온 것들
    "occupied": [("light.off", "*"), ("light.on", "off"), ("switch", "off"),
                 ("media", "off"), ("camera", "off"), ("lock", "on")],
    "nomotion": [("light.on", "on"), ("media", "on")],     # 아무도 안 움직이는데 켜다
    "windy":  [("cover", "on")],                           # 강풍인데 블라인드 올리다
    "presshigh": [("compressor", "on"), ("pump", "on")],   # 압력이 높은데 더 올리다
    "battlow": [("vacuum", "on"), ("mower", "on"), ("media", "on")],
    "tanklow": [("pump", "on"), ("sprinkler", "on"), ("coffee", "on")],
}

# 방아쇠 틀 → 상황 이름
TRIG_SENSE = {
    "if the temperature drops below {deg_lo} degrees": "cold",
    "if the outside temperature drops below {deg_lo}": "cold",
    "when the temperature goes above {deg_hi} degrees": "hot",
    "while the temperature stays over {deg_hi} degrees": "hot",
    "when it gets hot outside": "hot",
    "when the gas sensor goes over {lvl}": "gas",
    "if a gas leak is detected": "gas",
    "when {sensor} reads a dangerous level": "gas",
    "when the smoke detector goes off": "smoke",
    "if the smoke alarm sounds": "smoke",
    "when {sensor} reports smoke": "smoke",
    "when a water leak is detected": "leak",
    "if {sensor} finds water on the floor": "leak",
    "when the leak sensor trips": "leak",
    "once the air quality gets worse than {lvl}": "airbad",
    "when the humidity climbs over {pct} percent": "humid",
    "at sunset": "dark", "when the sun goes down": "dark",
    "as the sun sets": "dark", "around sundown": "dark",
    "once it gets dark outside": "dark",
    "when the {place} door opens": "open", "if a window is left open": "open",
    "when {sensor} says the door is open": "open",
    "once the door has been open for {n} minutes": "open",
    "when it starts raining": "wet", "if rain is in the forecast": "wet",
    "when snow is expected": "wet",
    "if the forecast says frost": "frost",
    "once the {place} is empty": "empty", "while nobody is around": "empty",
    "while someone is in the {place}": "occupied",
    "when the {place} is occupied": "occupied",
    "when someone shows up in the {place}": "occupied",
    "when I get home": "occupied", "as soon as I arrive home": "occupied",
    "when I pull into the driveway": "occupied", "once I am back home": "occupied",
    "when I am close to home": "occupied",
    "when someone rings the doorbell": "occupied",
    "if the doorbell goes off": "occupied",
    "when there is somebody at the door": "occupied",
    "when nothing has moved for {n} minutes": "nomotion",
    "when the wind picks up past {wind}": "windy",
    "if wind speed goes over {wind}": "windy",
    "if power draw stays above {watt} watts": "presshigh",
    "when the battery drops below {pct} percent": "battlow",
    "if any sensor battery is running low": "battlow",
    "if my phone battery falls under {pct} percent": "battlow",
    "when I leave home": "empty", "once everyone has left": "empty",
    "after I head out": "empty", "when I am away from home": "empty",
}
# 조건절 → 상황 이름
COND_SENSE = {
    "the room is too warm": "hot",
    "the temperature is under 18 degrees": "cold",
    "the humidity is over 60 percent": "humid",
    "it is dark outside": "dark",
    "the door is open": "open", "the window is open": "open",
    "nobody is home": "empty", "nobody is around": "empty",
    "someone is in the room": "occupied",
    "the tank is below half": "tanklow",
    "the battery is under 20 percent": "battlow",
}

# 조건절이 읽는 센서. 방아쇠가 이미 읽고 있는 것을 조건으로 또 읽지 않게 쓴다
#   ("온도가 15도 아래로 떨어지면 온도가 18도 아래인 동안 …")
# 그 센서가 없는 공간에 붙는 것은 막지 않는다 — 못 하는 명령을 알아보는 것도 시험이다.
COND_SENSOR = {
    "the room is too warm": "temp",
    "the temperature is under 18 degrees": "temp",
    "the door is open": "contact",
    "the window is open": "contact",
    "someone is in the room": "occupancy",
    "nobody is home": "occupancy",
    "nobody is around": "occupancy",
    "the humidity is over 60 percent": "humidity",
    "it is dark outside": "light",
    "the washing machine is running": "washer",
    "the tank is below half": "water",
    "the battery is under 20 percent": "battery",
}
# 방아쇠 갈래가 읽는 센서 (COND_SENSOR 와 같은 이름이면 겹치는 것이다)
TRIG_SENSOR = {
    "threshold": "temp", "contact": "contact", "motion": "occupancy",
    "presence": "occupancy", "arrive": "occupancy", "leave": "occupancy",
    "proximity": "occupancy", "finished": "washer", "sun": "light",
    "weather": "light", "battery": "battery",
}
# ── 집이 아닌 공간에서는 "집" 이라는 말을 안 쓴다 ────────────────────────
# 공장·연구실·농장·사무실에 "집에 아무도 없으면" 이 붙어 있었다 (54행).
# 뜻은 같고 말만 바꾼다. 같은 IR·같은 한국어 틀에 걸리도록 ir.py·korean.py 가
# 이 표를 읽어 별명을 만든다 — 표를 늘리지 않는다.
NONHOME = {
    # 조건절
    "nobody is home":                "nobody is around",
    # 시간절 — 도착
    "when I get home":               "when I arrive",
    "as soon as I arrive home":      "as soon as I arrive",
    "when I pull into the driveway": "when I pull into the parking lot",
    "once I am back home":           "once I am back",
    "when I am close to home":       "when I am close by",
    # 시간절 — 나감
    "when I leave home":             "when I leave",
    "when I am away from home":      "when I am away",
    # "once everyone has left", "after I head out" 은 "집" 이 안 들어가 그대로 쓴다
}

COND = ["the room is too warm", "nobody is home", "the door is open",
        "the humidity is over 60 percent", "it is dark outside",
        "the washing machine is running", "someone is in the room",
        "the temperature is under 18 degrees", "the window is open",
        "the tank is below half", "the battery is under 20 percent"]

# ── 말투 ───────────────────────────────────────────────────────────────
# (이름, 틀). {s} 는 완성된 문장.
TONE = [
    ("bare",    "{s}."),
    ("polite",  "please {s}."),
    ("ask",     "can you {s}?"),
    ("wish",    "I'd like you to {s}."),
    ("could",   "could you {s}?"),
    ("terse",   "{s}"),
]

VALUES = {
    "n": {
        "light.dim": [10, 20, 30, 40, 50, 60, 70, 80, 90],
        "thermostat": [18, 19, 20, 21, 22, 23, 24, 25],
        "ac": [20, 21, 22, 23, 24, 25, 26],
        "waterheater": [40, 45, 50, 55, 60],
        "chamber": [4, 20, 25, 30, 37],
        "humidity": [40, 45, 50, 55, 60],
        "media": [10, 20, 30, 40, 50],
        "cover": [10, 20, 30, 50, 70, 80],
        # 보광등만 단위가 '시간' 이다. 기본값을 쓰면 "45시간 동안 켜 둬" 가 나온다.
        "growlight": [2, 3, 4, 6, 8, 10, 12],
        "_default": [2, 3, 5, 10, 15, 20, 30, 45, 60],
    },
    "time": ["6 am", "6:30 am", "7 am", "8 am", "9 am", "10 pm", "10:30 pm",
             "11 pm", "midnight", "noon", "5 pm", "6 pm", "8 pm"],
    "time_am": ["5:30 am", "6 am", "6:30 am", "7 am", "7:30 am", "8 am", "9 am"],
    "time_pm": ["9 pm", "10 pm", "10:30 pm", "11 pm", "11:30 pm", "midnight"],
    "weekday": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                "Saturday", "Sunday", "weekends"],
    "deg": [0, 5, 10, 15, 18, 20, 22, 24, 26, 28, 30],
    # 방향이 있는 문턱. "0도를 넘으면" 은 늘 참이고 "30도 아래로 떨어지면" 도 늘 참이다
    "deg_hi": [24, 26, 28, 30, 32, 35],
    "deg_lo": [0, 5, 10, 12, 15, 18],
    "pct": [30, 40, 50, 55, 60, 65, 70, 80],
    "lvl": [50, 100, 150, 200, 300, 500, 800, 1000],
    "watt": [500, 800, 1000, 1500, 2000, 3000],
    "kwh": [5, 10, 15, 20, 30, 50],
    "tilt": [5, 10, 15, 20, 30],
    "cm": [10, 20, 30, 50, 100],
    "wind": [10, 15, 20, 25, 30],
    "lo": [5, 10, 15, 20, 25, 30],
    "hi": [70, 75, 80, 85, 90, 100],
    "color": ["red", "blue", "green", "warm white", "orange", "purple", "pink",
              "daylight white", "amber"],
    "scene": ["movie", "party", "relax", "reading", "night", "morning", "focus",
              "dinner", "away"],
}
