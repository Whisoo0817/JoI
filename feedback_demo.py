"""
feedback_demo.py — 피드백(수정) 파이프라인을 여러 입력에 순차 실행하며
**reasoning 과정까지 전 출력**을 그대로 보여주는 데모/점검 스크립트.

흐름 (edit 요청당):
  Step 1  edit_understand   — 현재 코드 전체를 이해 (reasoning ON, <think> 노출)
  Step 2  edit_apply_agentic — 이해+코드+수정지시로 코드에 직접 수술.
          필요 시 tool 호출(list_device_categories / find_devices / get_services)
          — tool 왕복과 reasoning 모두 출력.
  검증    validate_joi       — 문법/태그/서비스 검증 (run.py 기기 기준, 정보용)

실행:  /home/ikess/joi-llm/venv/bin/python feedback_demo.py
"""
import json, re, sys, os, difflib, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from config import get_client, get_model_id
from loader import PROMPTS, SERVICE_DATA
from parser.validator import validate_joi
from schemas import JoiLLMResponse   # generate_joi_code API 응답 스키마
from app import _code_item, _success_response  # 실제 API 패키징 경로 재사용
import run  # 대용량 haystack (63 devices)

client = get_client("http://localhost:8002/v1")
MODEL = get_model_id(client)

# ── connected_devices ──────────────────────────────────────────────────
# fixture 시나리오들이 참조하는 태그(#Office, #GlobalVariable, #CO2_Indicator,
# #ModeToggle, #ToastPublisher, #Clock, #EmailProvider …)를 실제로 가진 기기를
# 채워 넣는다. run.py의 63개(대용량 haystack)와 병합 → 규모 + 정합성 둘 다 확보.
DEMO_DEVICES = {
    "tc0_aqs_office":     {"nickname": "사무실 공기질 센서", "category": ["AirQualitySensor"],
                           "tags": ["Office", "AirQualitySensor"]},
    "tc0_airpurifier_off":{"nickname": "사무실 공기청정기", "category": ["AirPurifier", "Switch"],
                           "tags": ["Office", "AirPurifier", "Switch"]},
    "tc0_light_co2":      {"nickname": "CO2 표시등", "category": ["Light", "Switch"],
                           "tags": ["CO2_Indicator", "Light", "Switch"]},
    "tc0_speaker_office": {"nickname": "사무실 스피커", "category": ["Speaker"],
                           "tags": ["Office", "Speaker"]},
    "tc0_button_toggle":  {"nickname": "모드 토글 버튼", "category": ["Button"],
                           "tags": ["Office", "ModeToggle", "Button"]},
    "tc0_humidifier_off": {"nickname": "사무실 가습기", "category": ["Humidifier", "Switch"],
                           "tags": ["Office", "Humidifier", "Switch"]},
    "tc0_clock":          {"nickname": "시계", "category": ["Clock"], "tags": ["Clock"]},
    "tc0_globalvar":      {"nickname": "전역 변수", "category": ["GlobalVariable"],
                           "tags": ["GlobalVariable"]},
    "tc0_toast":          {"nickname": "토스트", "category": ["ToastPublisher"],
                           "tags": ["ToastPublisher"]},
    "tc0_email":          {"nickname": "이메일", "category": ["EmailProvider"],
                           "tags": ["EmailProvider"]},
    # request_log 예제(⑩~⑭)가 참조하는 태그: #LightSwitch, #Door, #AirConditioner …
    "tc0_lightswitch":    {"nickname": "조명 스위치", "category": ["Switch", "LightSwitch"],
                           "tags": ["LightSwitch", "Switch"]},
    "tc0_door":           {"nickname": "현관문", "category": ["ContactSensor"],
                           "tags": ["Door", "ContactSensor"]},
    "tc0_ac_living":      {"nickname": "거실 에어컨", "category": ["AirConditioner", "Switch"],
                           "tags": ["AirConditioner", "Switch"]},
    "tc0_light_main":     {"nickname": "거실 조명", "category": ["Light", "Switch"],
                           "tags": ["Light", "Switch"]},
    "tc0_presence2":      {"nickname": "재실 센서", "category": ["PresenceSensor"],
                           "tags": ["PresenceSensor"]},
    "tc0_temp2":          {"nickname": "온도 센서", "category": ["TemperatureSensor"],
                           "tags": ["TemperatureSensor"]},
}
CONNECTED = {**run.CONNECTED_DEVICES, **DEMO_DEVICES}

# ─────────────────────────────────────────────────────────────────────────
# 출력 헬퍼
# ─────────────────────────────────────────────────────────────────────────
def hr(c="─", n=100): print(c * n)
def title(t): hr("═"); print(t); hr("═")

def split_think(content):
    """<think>…</think> 를 (reasoning, answer) 로 분리."""
    if not content:
        return "", ""
    m = re.search(r"<think>(.*?)</think>(.*)$", content, re.DOTALL)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", content.strip()

# ─────────────────────────────────────────────────────────────────────────
# 저수준 호출 (non-streaming, reasoning 캡처)
# ─────────────────────────────────────────────────────────────────────────
def call(messages, *, tools=None, max_tokens=16384, enable_thinking=True):
    kwargs = dict(model=MODEL, messages=messages, temperature=0.1,
                  max_tokens=max_tokens,
                  extra_body={"chat_template_kwargs": {"enable_thinking": enable_thinking}})
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    t0 = time.perf_counter()
    r = client.chat.completions.create(**kwargs)
    elapsed = time.perf_counter() - t0
    msg = r.choices[0].message
    # vLLM은 reasoning을 (비표준) `reasoning` 필드로 분리해서 준다 → model_extra 로 노출.
    reasoning = ((msg.model_extra or {}).get("reasoning") if msg.model_extra else None) or ""
    answer = msg.content or ""
    if not reasoning:  # fallback: 인라인 <think>
        think, answer = split_think(answer)
        reasoning = think
    ctok = getattr(getattr(r, "usage", None), "completion_tokens", 0) or 0
    call.last = {"elapsed": elapsed, "ctok": ctok, "finish": r.choices[0].finish_reason}
    return msg, reasoning.strip(), answer.strip(), r.choices[0].finish_reason

# ─────────────────────────────────────────────────────────────────────────
# TOOLS — 스키마 + 실행기 (CONNECTED / SERVICE_DATA 기반)
# ─────────────────────────────────────────────────────────────────────────
TOOLS = [
    {"type": "function", "function": {
        "name": "list_device_categories",
        "description": "List the device categories currently connected, with counts.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "find_devices",
        "description": "Search connected devices by keyword (matches nickname / category / tag). "
                       "Returns matching devices with their selector tags.",
        "parameters": {"type": "object",
                       "properties": {"keyword": {"type": "string"}},
                       "required": ["keyword"]}}},
    {"type": "function", "function": {
        "name": "get_services",
        "description": "List the services/methods (with arguments) available for a device category.",
        "parameters": {"type": "object",
                       "properties": {"category": {"type": "string"}},
                       "required": ["category"]}}},
    {"type": "function", "function": {
        "name": "submit_scenario",
        "description": "Return the fully edited scenario. Call this last.",
        "parameters": {"type": "object",
                       "properties": {"name": {"type": "string"},
                                      "cron": {"type": "string"},
                                      "period": {"type": "integer"},
                                      "script": {"type": "string"}},
                       "required": ["name", "cron", "period", "script"]}}},
]

def _cat_counts():
    cc = {}
    for v in CONNECTED.values():
        for c in v.get("category", []):
            cc[c] = cc.get(c, 0) + 1
    return cc

def _code_method(category, method_id):
    """catalog id(PascalCase) → JoI 코드 메서드명 `catCamel_methodCamel` (근사)."""
    cc = category[0].lower() + category[1:]
    mm = method_id[0].lower() + method_id[1:]
    return f"{cc}_{mm}"

def tool_list_device_categories():
    cc = _cat_counts()
    return "\n".join(f"{c} x{n}" for c, n in sorted(cc.items(), key=lambda x: -x[1]))

def tool_find_devices(keyword):
    kw = (keyword or "").lower()
    hits = []
    for did, v in CONNECTED.items():
        hay = " ".join([v.get("nickname", "")] + v.get("category", []) + v.get("tags", [])).lower()
        if kw in hay:
            sel = [t for t in v.get("tags", []) if not t.startswith("tc0_") and t != "tc0_local"]
            hits.append({"nickname": v.get("nickname", ""),
                         "category": v.get("category", []),
                         "selector_tags": sel})
    if not hits:
        return f"(no connected device matches {keyword!r})"
    return json.dumps(hits[:12], ensure_ascii=False, indent=2)

def tool_get_services(category):
    item = SERVICE_DATA.get(category)
    if not item:
        # case-insensitive fallback
        for k in SERVICE_DATA:
            if k.lower() == (category or "").lower():
                item = SERVICE_DATA[k]; category = k; break
    if not item:
        return f"(unknown category {category!r})"
    out = []
    for e in item.get("values", []):
        out.append(f"read  {_code_method(category, e['id'])}"
                   f"  [{e.get('type','')}{('/'+e['format']) if e.get('format') else ''}]"
                   f"  — {e.get('descriptor','')}")
    for e in item.get("functions", []):
        args = ", ".join(f"{a['id']}:{a.get('type','')}" for a in e.get("arguments", []))
        out.append(f"call  {_code_method(category, e['id'])}({args})"
                   f"  — {e.get('descriptor','')}")
    return f"# {category} services\n" + "\n".join(out)

TOOL_IMPL = {
    "list_device_categories": lambda a: tool_list_device_categories(),
    "find_devices": lambda a: tool_find_devices(a.get("keyword", "")),
    "get_services": lambda a: tool_get_services(a.get("category", "")),
}

# ─────────────────────────────────────────────────────────────────────────
# 단일 agentic 편집 (이해+수정 병합). thinking 기본 OFF, 하드캡, tool.
# ─────────────────────────────────────────────────────────────────────────
EDIT_CAP = 4096      # per-call 토큰 하드캡 (30초 예산)
def edit_run(cs, edit, *, think=False, max_iters=8):
    """이해+수정 병합 agentic 루프. 반환: (dict|None, timing, trace).
    trace = 순서대로 쌓인 (kind, ...) 이벤트 리스트 (reasoning / tool / text) —
    출력은 호출측(show_result)에서 ②수정사항 다음에 하도록 여기선 찍지 않는다."""
    user = (f"[Current Scenario]\nname: {cs.get('name','')}\n"
            f"cron: {cs.get('cron','')}\nperiod: {cs.get('period_in_msec','')}\n"
            f"script:\n{cs.get('script','')}\n\n[Edit Request]\n{edit}")
    messages = [{"role": "system", "content": PROMPTS["edit_agentic"]},
                {"role": "user", "content": user}]
    t = {"elapsed": 0.0, "ctok": 0, "llm_calls": 0, "tool_calls": 0, "think": think}
    trace = []
    result = None
    for it in range(max_iters):
        msg, reasoning, answer, fr = call(messages, tools=TOOLS,
                                          max_tokens=EDIT_CAP, enable_thinking=think)
        t["elapsed"] += call.last["elapsed"]; t["ctok"] += call.last["ctok"]; t["llm_calls"] += 1
        if reasoning:
            trace.append(("reasoning", it + 1, reasoning))
        if not msg.tool_calls:
            if answer:
                trace.append(("text", answer))
            break
        am = {"role": "assistant", "content": msg.content or "",
              "tool_calls": [{"id": tc.id, "type": "function",
                              "function": {"name": tc.function.name,
                                           "arguments": tc.function.arguments}}
                             for tc in msg.tool_calls]}
        messages.append(am)
        submitted = False
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            if tc.function.name == "submit_scenario":  # 최종 제출 → 종료
                trace.append(("submit", args.get("name"), args.get("cron"), args.get("period")))
                result = {"name": str(args.get("name", "")), "cron": str(args.get("cron", "")),
                          "period": str(args.get("period", "")),
                          "script": str(args.get("script", "")).rstrip("\n")}
                submitted = True
                break
            t["tool_calls"] += 1
            out = TOOL_IMPL.get(tc.function.name, lambda a: "(unknown tool)")(args)
            trace.append(("tool", tc.function.name, args, out))
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": out})
        if submitted:
            break
    else:
        trace.append(("max_iters", None))
    return result, t, trace


def print_trace(trace, think):
    """모델의 reasoning / tool 과정을 순서대로 출력 (②수정사항 다음 위치)."""
    has_reasoning = any(e[0] == "reasoning" for e in trace)
    if not has_reasoning and think:
        print("🧠 ③ 모델 reasoning/과정: (thinking ON이나 reasoning 미출력)")
    elif not has_reasoning:
        print("🧠 ③ 모델 reasoning/과정: (thinking OFF — reasoning 없이 바로 수정)")
    else:
        print("🧠 ③ 모델 reasoning/과정:")
    for e in trace:
        if e[0] == "reasoning":
            print(f"\n  ── reasoning (turn {e[1]}) ──")
            for ln in e[2].split("\n"):
                print("  " + ln)
        elif e[0] == "tool":
            print(f"\n  🔧 {e[1]}({json.dumps(e[2], ensure_ascii=False)})  →")
            for ln in e[3].splitlines():
                print("     " + ln)
        elif e[0] == "text":
            print(f"\n  💬 (텍스트 응답) {e[1]}")
        elif e[0] == "submit":
            print(f"\n  📤 submit_scenario(name={e[1]!r}, cron={e[2]!r}, period={e[3]})")
        elif e[0] == "max_iters":
            print("\n  ⚠️ max_iters 도달")
    print()

# ─────────────────────────────────────────────────────────────────────────
# 출력 파싱 + 검증
# ─────────────────────────────────────────────────────────────────────────
_SERVICE_MAP = {}
for _cat, _item in SERVICE_DATA.items():
    for _e in _item.get("values", []) + _item.get("functions", []):
        _SERVICE_MAP.setdefault(_e["id"], _cat)

def to_api_response(new) -> JoiLLMResponse:
    """edit 결과를 generate_joi_code API와 '동일 경로'로 패키징한다.
    파이프라인은 code를 {name,cron,period,script} JSON 문자열로 넘기고 app._code_item /
    _success_response 가 JoiLLMResponse(JoiCodeItem 리스트)로 만든다 — 그 경로를 그대로 탄다."""
    pipeline_code = json.dumps({
        "name": new["name"], "cron": new["cron"],
        "period": int(new["period"]) if str(new["period"]).lstrip("-").isdigit() else -1,
        "script": new["script"],
    }, ensure_ascii=False)
    result = {"code": pipeline_code,
              "log": {"response_time": "", "translated_sentence": None, "logs": ""}}
    return _success_response(result)

def _print_scenario(header, name, cron, period, script):
    print(f"┌─ {header} " + "─" * max(0, 92 - len(header)))
    print(f"│ name={name!r}  cron={cron!r}  period={period}")
    print("│")
    for ln in script.split("\n"):
        print("│ " + ln)
    print("└" + "─" * 94)

def show_result(cs, new, edit, trace, think):
    old_s = cs.get("script", "").rstrip("\n")

    # ① 이전 코드
    _print_scenario("① 이전 코드", cs.get("name", ""), cs.get("cron", ""),
                    cs.get("period_in_msec", ""), old_s)
    # ② 수정사항
    print(f"\n✏️  ② 수정사항:  {edit!r}\n")
    # ②-1 모델 reasoning / 과정 (수정사항 다음)
    print_trace(trace, think)
    # ③ 최종 코드
    if not new:
        print("❌ ④ 최종 코드: 없음 (submit 안 됨)\n"); return
    _print_scenario("④ 최종 코드", new["name"], new["cron"], new["period"], new["script"])

    # 부가 정보: 무엇이 바뀌었나 / 검증 / API 스키마
    print()
    if old_s == new["script"]:
        print("변경   SCRIPT ✅ byte-for-byte 동일 (script 불변, wrapper만 변경)")
    else:
        print("변경   SCRIPT diff:")
        for dl in difflib.unified_diff(old_s.splitlines(), new["script"].splitlines(),
                                       lineterm="", n=0):
            if dl.startswith(("+", "-")) and not dl.startswith(("+++", "---")):
                print("       " + dl)
    errs = validate_joi(new["script"], CONNECTED, _SERVICE_MAP)
    print(f"검증   VALIDATE {'✅ 통과' if not errs else '⚠️ ' + str(len(errs)) + '건'}")
    for e in (errs or [])[:6]:
        print("       - " + str(e))

    # ── generate_joi_code API 스키마로 패키징 + 왕복 검증 ──────────────
    resp = to_api_response(new)
    item = resp.code[0] if isinstance(resp.code, list) and resp.code else None
    ok = (isinstance(resp, JoiLLMResponse) and item is not None
          and item.code == new["script"] and item.name == new["name"]
          and item.cron == new["cron"])
    print(f"패키징 API 스키마 {'✅ generate_joi_code 응답과 동일 형태 + 왕복 일치' if ok else '❌ 불일치'}")
    print()

# ─────────────────────────────────────────────────────────────────────────
# 입력 케이스 — 예전에 준 3개(로그) + 여러 추가 (리터럴 / 디바이스교체 / 구조)
# ─────────────────────────────────────────────────────────────────────────
# 예전에 사용자가 준 3개 시나리오 (로그가 최근 10개만 유지하고 회전되므로 fixture로 고정).
_S0_AIRQUALITY = """
st_pm10 := 80.0
st_pm25 := 35.0
st_pm1 := 25.0
st_tvoc := 0.6
st_co2 := 800.0

// CO2 경고 토스트 최소 간격 30분 (period 재호출 간 유지)
co2_toast_cooldown_sec := 30 * 60
last_co2_toast := 0

occupancy = (#GlobalVariable).globalVariable_getBoolean("occupancy")
if (occupancy == true) {
  now = (#Clock).clock_timestamp

  // 현재 센서들로부터 각 지표 합계/개수 집계 (개수 0 나눗셈은 아래 n>0 가드로 회피)
  n_pm10 = 0
  n_pm25 = 0
  n_pm1 = 0
  n_tvoc = 0
  n_co2 = 0
  sum_pm10 = 0
  sum_pm25 = 0
  sum_pm1 = 0
  sum_tvoc = 0
  sum_co2 = 0
  // 지표마다 보고 센서 수가 다를 수 있어 각 지표를 자기 카운트로 나눔(분모 희석/경고 누락 방지)
  for (v : all(#AirQualitySensor #Office).airQualitySensor_dustLevel) { sum_pm10 = sum_pm10 + v; n_pm10 = n_pm10 + 1 }
  for (v : all(#AirQualitySensor #Office).airQualitySensor_fineDustLevel) { sum_pm25 = sum_pm25 + v; n_pm25 = n_pm25 + 1 }
  for (v : all(#AirQualitySensor #Office).airQualitySensor_veryFineDustLevel) { sum_pm1 = sum_pm1 + v; n_pm1 = n_pm1 + 1 }
  for (v : all(#AirQualitySensor #Office).airQualitySensor_tvocLevel) { sum_tvoc = sum_tvoc + v; n_tvoc = n_tvoc + 1 }
  for (v : all(#AirQualitySensor #Office).airQualitySensor_carbonDioxide) { sum_co2 = sum_co2 + v; n_co2 = n_co2 + 1 }

  if (n_pm10 > 0 and n_pm25 > 0 and n_pm1 > 0 and n_tvoc > 0 and n_co2 > 0) {
    avg_pm10 = sum_pm10 / n_pm10
    avg_pm25 = sum_pm25 / n_pm25
    avg_pm1 = sum_pm1 / n_pm1
    avg_tvoc = sum_tvoc / n_tvoc
    avg_co2 = sum_co2 / n_co2

    // 공기청정기: 어느 지표든 임계 초과 -> ON / 모든 지표가 임계 절반 미만 -> OFF (데드밴드)
    if (all(#AirPurifier #Office).switch_switch ==| false and (avg_pm10 > st_pm10 or avg_pm25 > st_pm25 or avg_pm1 > st_pm1 or avg_tvoc > st_tvoc)) {
      (#ToastPublisher).toastPublisher_publish("announce", "공기질 나쁨", "현재 공기질이 불량합니다. 공기청정기를 켭니다.")
      all(#AirPurifier #Office).switch_on()
    }
    if (all(#AirPurifier #Office).switch_switch ==| true and avg_pm10 < (st_pm10 / 2) and avg_pm25 < (st_pm25 / 2) and avg_pm1 < (st_pm1 / 2) and avg_tvoc < (st_tvoc / 2)) {
      all(#AirPurifier #Office).switch_off()
    }

    // CO2: 임계 초과 + 마지막 토스트 후 30분 경과 -> 경고 토스트
    if (avg_co2 > st_co2 and (now - last_co2_toast > co2_toast_cooldown_sec)) {
      (#ToastPublisher).toastPublisher_publish("warning", "이산화탄소 농도 경고", "이산화탄소 농도가 너무 높습니다. 창문을 열어 환기를 해주세요.")
      last_co2_toast = now
    }

    // CO2 농도별 표시등 색상 변경 (< 800 녹 / 800-1000 황 / 1000-1500 주황 / ≥ 1500 적)
    if (avg_co2 < 800.0) { all(#Light #CO2_Indicator).light_moveToColor(0.17, 0.70, 1.0) }
    else if (avg_co2 < 1000.0) { all(#Light #CO2_Indicator).light_moveToColor(0.43, 0.50, 1.0) }
    else if (avg_co2 < 1500.0) { all(#Light #CO2_Indicator).light_moveToColor(0.54, 0.41, 1.0) }
    else { all(#Light #CO2_Indicator).light_moveToColor(0.67, 0.32, 1.0) }
  }
}
""".strip("\n")

_S1_MEETING = """
if ((#Clock).clock_isHoliday == true) { break }

hour = (#Clock).clock_hour
minute = (#Clock).clock_minute

if ((#Speaker).speaker_volume < 90) { (#Speaker).speaker_setVolume(90) }

if (hour == 9 and minute == 30) {
  (#ToastPublisher).toastPublisher_publish("announce", "주간 미팅 30분 전", "주간 미팅이 30분 후에 시작됩니다.")
  (#Speaker #Office).speaker_speak("미팅 시작 30분 전입니다. 미리 미팅 준비를 해주시기 바랍니다.")
}
if (hour == 10 and minute == 0) {
  (#ToastPublisher).toastPublisher_publish("announce", "주간 미팅 시간", "주간 미팅 시간입니다.")
  (#Speaker #Office).speaker_speak("미팅 시작 시간입니다.")
}
""".strip("\n")

_S2_SECURITY = """
was_pushed := false   // 직전 틱 버튼 눌림 상태(상승 엣지 검출용)
armed := false        // 무장 상태 로컬 미러(글로벌 security_mode와 동기). true는 주기 간 유지
synced := false       // 글로벌 security_mode 최초 1회 시드 여부(=로 true 세팅 시 유지)

pushed = false
if ((#Button #Office #ModeToggle).button_button == "pushed") { pushed = true }

// 최초 1회: 글로벌을 현재 무장값(false)으로 시드 -> 침입 감지 시나리오가 null을 읽지 않게
if (synced == false) {
  (#GlobalVariable).globalVariable_setBoolean("security_mode", armed)
  synced = true
}

// 버튼 상승 엣지에서만 토글(분기는 로컬 bool armed로만 -> null 비교 회피)
if (pushed == true and was_pushed == false) {
  if (armed == true) {
    armed = false
    (#GlobalVariable).globalVariable_setBoolean("security_mode", false)
    (#ToastPublisher).toastPublisher_publish("announce", "보안 모드 해제", "보안 모드가 해제되었습니다. 재실이 감지되어도 침입으로 간주하지 않습니다.")
    (#Speaker #Office).speaker_speak("보안 모드가 해제되었습니다.")
  } else {
    armed = true
    (#GlobalVariable).globalVariable_setBoolean("security_mode", true)
    (#ToastPublisher).toastPublisher_publish("announce", "보안 모드 설정", "보안 모드가 설정되었습니다. 재실이 감지되면 침입으로 간주하여 알림이 발송됩니다.")
    (#Speaker #Office).speaker_speak("보안 모드가 설정되었습니다.")
  }
}
was_pushed = pushed
""".strip("\n")

LOG = [
    {"name": "사무실_공기질_관리", "nick_name": "사무실 공기질 관리",
     "command": "", "cron": "", "period_in_msec": 60000, "script": _S0_AIRQUALITY},
    {"name": "주간_미팅_알림", "nick_name": "주간 미팅 알림",
     "command": "", "cron": "* * * * 4", "period_in_msec": -1, "script": _S1_MEETING},
    {"name": "보안_모드_토글", "nick_name": "보안 모드 토글",
     "command": "start", "cron": "", "period_in_msec": 250, "script": _S2_SECURITY},
]   # 0: 공기질(62줄), 1: 미팅(16줄), 2: 보안토글(29줄)

# request_log.jsonl 에서 온 실제 편집 요청들 (각 요청 시점의 current_scenario).
def _scn(name, cron, period, script):
    return {"name": name, "nick_name": name.replace("_", " "), "command": "",
            "cron": cron, "period_in_msec": period, "script": script.strip("\n")}

R_LIGHTS = _scn("20_00_에어컨_끄기", "0 20 * * *", -1,
                "all(#Light).switch_off()\nall(#LightSwitch).switch_off()")
R_AC     = _scn("20_00_에어컨_끄기", "0 20 * * *", -1,
                "(#AirConditioner).switch_off()")
R_AC_ALL = _scn("20_00_에어컨_끄기", "0 20 * * *", -1,
                "(#AirConditioner).switch_off()\nall(#Light).switch_off()\nall(#LightSwitch).switch_off()")
R_DOOR   = _scn("20_00_에어컨_끄기", "", -1,
                "wait until((#Door).contactSensor_contact == false and all(#PresenceSensor).presenceSensor_presence == false)\n"
                "(#AirConditioner).switch_off()")
R_TEMP   = _scn("온도_30_도_이상_경고_토스트", "", -1,
                'wait until(all(#TemperatureSensor).temperatureSensor_temperature >=| 30)\n'
                '(#ToastPublisher).toastPublisher_publish("warning", "온도 30 도 이상", "온도가 30 도 이상입니다.")')

CASES = [
    ("① no-op (기존 예시)",            LOG[0], "."),
    ("② 스케줄 wrapper (기존 예시)",    LOG[1], "금요일로 바꿔줘"),
    ("③ 주기 wrapper (기존 예시)",      LOG[2], "주기를 1초로 바꿔줘"),
    ("④ script 리터럴 (값)",           LOG[1], "볼륨을 80으로 바꿔줘"),
    ("⑤ script 리터럴 (임계값 스코핑)", LOG[0], "CO2 경고 기준을 700으로 낮춰줘"),
    ("⑥ 디바이스 교체 [tool 필요]",     LOG[0], "공기청정기 대신 가습기를 켜고 꺼줘"),
    ("⑦ 서비스 추가 [tool 필요]",       LOG[1], "미팅 시작할 때 이메일도 보내줘"),
    ("⑧ 구조 삭제 [tool 불필요]",       LOG[2], "스피커로 말하는 건 빼고 토스트만 남겨줘"),
    ("⑨ 문구 변경 (speaker+toast)",     LOG[1], '알림 문구를 "회의 준비해주세요"로 줘'),
    # ── request_log.jsonl 실제 편집 요청 ──
    ("⑩ 조건 추가 (로그)",              R_LIGHTS, "사람이 없을 때만 실행되게 바꿔줘"),
    ("⑪ 기기 추가 (로그)",              R_AC,     "조명도 같이 꺼줘"),
    ("⑫ 기기 삭제 (로그)",              R_AC_ALL, "조명은 삭제해줘"),
    ("⑬ 트리거 변경 (로그)",            R_DOOR,   "문이 열리면 실행되게 바꿔줘"),
    ("⑭ 임계값 변경 (로그)",            R_TEMP,   "온도 기준 28도로 바꿔줘"),
]

def main():
    only = None
    if len(sys.argv) > 1:  # 특정 케이스만: python feedback_demo.py 6
        only = int(sys.argv[1])
    # 디바이스/서비스 도입이 필요한 편집만 reasoning ON (adaptive thinking).
    # 디바이스/서비스 도입, 트리거·조건 신설, 문구 애매성 → reasoning ON
    THINK_CASES = {6, 7, 9, 10, 11, 13}
    rows = []
    for i, (label, cs, edit) in enumerate(CASES, 1):
        if only and i != only:
            continue
        think = i in THINK_CASES
        title(f"CASE {i}  {label}\n         edit = {edit!r}   "
              f"(script {cs.get('script','').count(chr(10))+1} lines, thinking={'ON' if think else 'OFF'})")
        new, t, trace = edit_run(cs, edit, think=think)
        hr("·")
        show_result(cs, new, edit, trace, think)
        print(f"⏱️  CASE {i} TOTAL: {t['elapsed']:.1f}s "
              f"({t['llm_calls']} LLM, {t['tool_calls']} tool, {t['ctok']} tok)\n")
        rows.append((i, label.split(" ")[0], think, t["elapsed"],
                     t["llm_calls"], t["tool_calls"], t["ctok"], new is not None))
    # ── latency 요약 ───────────────────────────────────────────────────
    if rows:
        title("LATENCY 요약 (요청별, 단일 콜)")
        print(f"{'#':<3}{'유형':<6}{'think':>6}{'LLM':>5}{'tool':>6}{'tok':>7}{'TOTAL(s)':>11}{'  결과'}")
        for i, tag, th, tot, lc, tcn, tok, ok in rows:
            print(f"{i:<3}{tag:<6}{('ON' if th else 'OFF'):>6}{lc:>5}{tcn:>6}{tok:>7}"
                  f"{tot:>11.1f}{'  ✅' if ok else '  ❌'}")
        n = len(rows)
        u30 = sum(1 for r in rows if r[3] <= 30)
        print(f"\n평균 total: {sum(r[3] for r in rows)/n:.1f}s | "
              f"최대: {max(r[3] for r in rows):.1f}s | 30초 이내: {u30}/{n}")

if __name__ == "__main__":
    main()
