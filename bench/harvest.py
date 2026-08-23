#!/usr/bin/env python3
"""원천 4곳을 한 표(corpus.csv)로 합친다 — 5,000개 선정의 1단계.

원천과 취급:
  ifttt   IFTTT 애플릿 (IoT 2,788건)   CC BY-NC-SA 4.0 → 문장 안 싣는다. 패턴+설치수만.
  ha      HA 커뮤니티 블루프린트 360건  포럼 글        → 제목만 힌트로, 명령문으로 쓰지 않는다.
  acon    acon96/Home-Assistant-Requests-V2  MIT       → 문장 그대로 써도 된다.
  massive AmazonScience/massive en-US iot   CC BY 4.0  → 문장 그대로 써도 된다.

뽑는 것은 "무엇을 자동화하는가" 두 조각이다:
  trig  무엇이 시작시키나 (sun, arrive, motion, voice, time, ...)
  act   무엇을 하나        (light.on, thermostat.set, cover.close, ...)
각각을 우리 3.0.0 카탈로그 카테고리(dev_trig / dev_act)로 옮긴다.
2단계는 이 표를 (trig, act) 로 묶어 설치수를 더해 순위표를 만든다.
"""
import ast
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SP = os.environ.get(
    "SCRATCH",
    "/tmp/claude-1003/-home-gnltnwjstk/95c928fb-f31c-4ff3-9e61-d6c4b3211a7c/scratchpad")
CATALOG = os.path.join(os.path.dirname(HERE), "files", "service_list_ver3.0.0.json")

csv.field_size_limit(10 ** 7)

# ── 트리거 사전 ────────────────────────────────────────────────────────
# (슬러그, 우리 카탈로그 카테고리, 정규식). 위에서부터 먼저 맞는 것을 쓴다.
TRIG = [
    ("motion",    "MotionSensor",     r"\bmotion\b|\bmovement\b|\bmoves? (is )?detect"),
    ("presence",  "PresenceSensor",   r"\boccupan\w+|\bpresence\b|someone is (in|home)|\bis occupied\b|"
                                      r"\bnobody\b|\bno ?one is\b|\bempty\b|\bunoccupied\b"),
    ("doorbell",  "Doorbell",         r"\bdoorbell\b|\bring(s|ing)? the bell\b|button is pressed on (your )?ring"),
    ("contact",   "ContactSensor",    r"\b(door|window|gate|garage|mailbox|drawer|fridge)\b[^.]{0,24}"
                                      r"\b(open|clos|shut|ajar|unlock)"),
    ("sun",       "SunProvider",      r"\bsun ?(set|rise)|sundown|dusk|dawn|nightfall|golden hour|\bsun (shad|elevat|position)"),
    ("arrive",    "PersonTracker",    r"\b(arriv\w+|enter\w*|get(ting)? |come?s? |coming )\s*(back )?home\b|"
                                      r"\benter (the |an? )?area\b|\bgeofence\b|\bpull(ing)? (in|up)\b"),
    ("leave",     "PersonTracker",    r"\b(leav\w+|exit\w*|depart\w*)\s*(the )?(home|house|area)\b|"
                                      r"\bwhen (you|i)\s*(are|am)? ?away\b|\bexit the area\b"),
    ("voice",     "", r"\balexa\b|google assistant|\bok google\b|hey google|siri|"
                                      r"\bsay(ing)? ['\"]|voice command|\btell (alexa|google)"),
    ("finished",  "LaundryWasher",  r"\b(cycle|wash|dry|laundry|dishwash\w*|load|brew|print|charg\w*)\b"
                                      r"[^.]{0,24}\b(finish|complet|done|end)"),
    ("weather",   "WeatherProvider",  r"\brain\w*|\bsnow\w*|\bfrost\b|\bstorm\b|forecast|humidity outside|"
                                      r"\bwind\b|\bcloud\w*|\buv index\b|weather (underground|report)|"
                                      r"outside temperature|\bhot outside\b|\bcold outside\b"),
    ("calendar",  "CalendarProvider", r"\bcalendar\b|\bmeeting\b|\bevent\b[^.]{0,20}\b(start|begin)|"
                                      r"\bappointment\b|\bagenda\b"),
    ("security",  "Camera",           r"\bintrud\w+|\bburglar\w*|\balarm is (trigger|arm)|\barmed\b|"
                                      r"\bsecurity system\b|\bcamera\b[^.]{0,20}\bdetect|\bglass break\b"),
    ("smoke",     "SmokeDetector",    r"\bsmoke\b|\bcarbon monoxide\b|\bco alarm\b|\bfire\b[^.]{0,12}detect"),
    ("leak",      "LeakSensor",       r"\bleak\w*|\bflood\w*|\bwater detect"),
    ("power",     "PowerMeter",       r"\benergy\b|\bpower (usage|consum|draw)|\bwatt\w*|\bkwh\b|"
                                      r"\belectricity price\b"),
    ("battery",   "Battery",          r"\bbattery\b[^.]{0,20}\b(low|below|drops?|under|full|charged)"),
    ("threshold", "TemperatureSensor", r"\btemperature\b|\bhumidity\b|\bthermostat\b[^.]{0,20}\b(above|below|"
                                      r"reaches|drops?|rises?)|\bair quality\b|\bco2\b|\bpm2\.5\b|\bsoil\b"),
    ("timer",     "Clock",            r"\btimer\b|\bcountdown\b|\bstopwatch\b"),
    ("button",    "Button",           r"\bbutton\b|one tap|\bwidget\b|\bflic\b|\bknocki\b|press(ing)? the|"
                                      r"\bremote\b|\bdo button\b|\bswitch is (double )?(press|click)"),
    ("time",      "Clock",            r"\bevery (day|morning|night|hour|week|monday|tuesday|wednesday|"
                                      r"thursday|friday|saturday|sunday)\b|\bat \d{1,2}(:\d\d)? ?(am|pm)\b|"
                                      r"\bschedul\w+|\bdaily\b|\bo'clock\b|\bbedtime\b|\bevery \d+ (min|hour)"),
    ("device",    "Switch",           r"\b(turns?|switch\w*|is) (on|off)\b[^.]{0,16}\b(then|,)|"
                                      r"\bwhen (your|the|a) \w+ (turns|is turned)\b"),
    ("phone",     "PersonTracker",    r"\bwi-?fi\b|\bbluetooth\b|\bphone (is )?(connect|charg|unlock)|"
                                      r"\bdo not disturb\b|\bsleep mode\b|\bscreen (on|off)\b"),
    ("message",   "MessageSender",    r"\bemail\b|\bsms\b|\btext message\b|\btweet\b|\bslack\b|\bdiscord\b|"
                                      r"\btelegram\b|\bfacebook\b|\bwebhook\b"),
]

# ── 액션 사전 ──────────────────────────────────────────────────────────
ACT = [
    ("light.color",   "Light",           r"\bcolou?r\b|\bhue\b[^.]{0,12}\b(blue|red|green|purple|orange|pink)|"
                                         r"\bdisco\b|\bcolou?r loop\b|\bparty\b|\brgb\b|\bblink\w*|\bflash\w*"),
    ("light.scene",   "Light",           r"\bscene\b|\bmood\b|\bmovie mode\b|\bambian\w+"),
    ("light.dim",     "Light",           r"\bdim\w*|\bbrightness\b|\bbrighten\b|\b\d+ ?% bright"),
    ("light.off",     "Light",           r"\b(turn|switch|shut)\w* off\b[^.]{0,24}\b(light|lamp|bulb|hue|lifx|"
                                         r"yeelight|nanoleaf|wiz)\b|\blights? off\b"),
    ("light.on",      "Light",           r"\blights?\b|\blamps?\b|\bbulbs?\b|\bhue\b|\blifx\b|\byeelight\b|"
                                         r"\bnanoleaf\b|\bwiz\b|\billuminat\w+"),
    ("thermostat",    "Thermostat",      r"\bthermostat\b|\bnest\b|\becobee\b|\bheating\b|\bboiler\b|\bradiator\b|"
                                         r"\bset (the )?temperature\b|\bhvac\b|\bfurnace\b"),
    ("ac",            "AirConditioner",  r"\bair ?con\w*|\ba/?c\b|\bcooling\b|\bcool down\b"),
    ("purifier",      "AirPurifier",     r"\bair purifier\b|\bpurif\w+|\bhumidifier\b|\bdehumidif\w+"),
    ("fan",           "Fan",             r"\bfan\b(?! ?mode)|\bventilat\w+"),
    ("lock",          "DoorLock",        r"\block\b|\bunlock\b|\bdeadbolt\b|\baugust\b|\bschlage\b|\byale\b"),
    ("cover",         "WindowCovering",  r"\bblind\w*|\bcurtain\w*|\bshade\w*|\bshutter\w*|\bawning\b|"
                                         r"\bpowerview\b|\bsomfy\b"),
    ("media",         "Television",      r"\bharmony\b|\bmedia player\b|\bnext track\b|"
                                         r"\bplay\w*\b[^.]{0,16}\b(music|song|playlist|spotify|tv|"
                                         r"movie|show)|\btv\b|\bsonos\b|\bchromecast\b|\broku\b|"
                                         r"\bprojector\b|\bvolume\b|\bpause\w*"),
    ("garage",        "GarageDoor",      r"\bgarage\b|\bmyq\b|\bgogogate\b|\bgate\b"),
    ("vacuum",        "RobotVacuumCleaner", r"\bvacuum\w*|\broomba\b|\birobot\b|\bhoover\b|\bmop\w*|\bdeebot\b|\bdust collector\b|\brobot cleaner\b|back to (its|the) (base|dock)"),
    ("mower",         "Mower",           r"\bmower\b|\bmow\w*|\blawn\b"),
    ("sprinkler",     "Sprinkler",       r"\bsprinkler\w*|\birrigat\w+|\bwater(ing)? (the )?(plant|garden|lawn)"),
    ("speaker",       "Speaker",         r"\bspeaker\b|\bannounce\w*|\bsay(s|ing)? out loud\b|\btts\b|"
                                         r"\bvoice announce"),
    ("notify",        "NotificationProvider", r"\bnotif\w+|\bpush\b|\balert\w*|\bremind\w*|\bsend me\b|"
                                         r"\bmessage me\b|\blet me know\b|\bwarn\w*"),
    ("camera",        "Camera",          r"\bcamera\b|\brecord\w*|\bsnapshot\b|\barlo\b|\bblink\b|\bring\b"),
    ("siren",         "Siren",           r"\bsiren\b|\bsound the alarm\b|\bbuzzer\b|\bhorn\b"),
    ("plug",          "Plug",            r"\bplug\b|\boutlet\b|\bwemo\b|\bkasa\b|\bsocket\b|\bsmart switch\b"),
    ("coffee",        "CoffeeMaker",     r"\bcoffee\b|\bespresso\b|\bkettle\b|\bbrew\w*"),
    ("waterheater",   "WaterHeater",     r"\bwater heater\b|\bhot water\b|\bimmersion\b"),
    ("evcharger",     "EvCharger",       r"\bev charg\w+|\bcar charg\w+|\btesla\b|\bwallbox\b"),
    ("humidity",      "Humidifier",      r"\bhumidity\b|\bhumidif\w+"),
    ("timer",         "Clock",           r"\btimer\b|\bcountdown\b|\bset an? alarm\b"),
    ("switch",        "Switch",          r"\bturn (it |them )?(on|off)\b|\bswitch (on|off)\b|\btoggle\b"),
    # 맨 마지막 — 기기 동작이 하나도 안 걸렸을 때만 "상태를 묻는 문장"으로 본다
    ("query",         "",                r"^(what|whats|what's|how|is|are|was|were|does|do|did|"
                                         r"tell me|check|show)\b|\bstatus of\b|\bhow (much|many|hot|cold)\b"),
]

TRIG_RE = [(s, c, re.compile(p)) for s, c, p in TRIG]
ACT_RE = [(s, c, re.compile(p)) for s, c, p in ACT]

# IFTTT 의 triggers_category 는 구조화되어 있어서 본문보다 믿을 만하다.
IFTTT_CAT = {
    "Voice assistants": ("voice", ""),   # 음성은 기기가 아니라 명령 그 자체다
    "Location": ("arrive", "PersonTracker"),
    "Weather": ("weather", "WeatherProvider"),
    "Calendars & scheduling": ("time", "Clock"),
    "Security & monitoring systems": ("security", "Camera"),
    "Environment control & monitoring": ("threshold", "TemperatureSensor"),
    "Power monitoring & management": ("power", "PowerMeter"),
    "Appliances": ("finished", "LaundryWasher"),
    "Notifications": ("message", "MessageSender"),
    "Email": ("message", "MessageSender"),
    "Social networks": ("message", "MessageSender"),
}
# 위젯/버튼은 service_triggers 로만 구분된다
IFTTT_SVC = {
    "Button widget": ("button", "Button"),
    "Date & Time": ("time", "Clock"),
    "Location": ("arrive", "PersonTracker"),
    "Amazon Alexa": ("voice", ""),
    "Google Assistant": ("voice", ""),
    "Flic": ("button", "Button"),
    "Knocki": ("button", "Button"),
}

# 우리가 안 다루기로 한 것 — 표에는 남기되 표시해 둔다 (2단계에서 뺀다)
OFF_PREMISE = {"message"}


# acon96 은 en/es/fr/de/pl 이 섞여 있다 — 영어만 남긴다
NON_EN = re.compile(r"[ąćęłńóśźżüöäßçéèêàùîôœñ¿¡]")
# 영어에는 없는 기능어 — 하나라도 있으면 영어가 아니다.
FOREIGN = re.compile(
    r"\b("
    r"de|la|el|los|las|que|por|una|luz|luces|para|con|del|cambie|ajuste|encienda|"
    r"apague|quiero|puede|puedes|esta|brillo|tono|mi|su|"          # es
    r"sie|das|der|die|den|und|ist|bitte|schalten|stellen|licht|andern|mochte|farbe|"
    r"helligkeit|einen|eine|ein|auf|fur|von|nicht|"                 # de
    r"le|les|des|veuillez|reglez|lumiere|allumez|eteignez|je|vous|dans|pour|du|"
    r"est|sur|avec|"                                                # fr
    r"czy|jest|na|do|aby|swiatlo|ustaw|zmien|prosze|wlacz|wylacz|jasnosc"   # pl
    r")\b")
EN_HINT = re.compile(r"\b(the|to|is|are|please|can|could|would|my|and|"
                     r"turn|set|make|switch|open|close|start|stop|off|on|it)\b")


def is_english(u):
    b = u.lower()
    return (not NON_EN.search(b) and not FOREIGN.search(b) and bool(EN_HINT.search(b)))


def match(text, table):
    for slug, cat, rx in table:
        if rx.search(text):
            return slug, cat
    return "", ""


def match_all(text, table):
    """한 문장이 여러 기기를 건드리는 일이 흔하다 — 걸리는 것을 전부 모은다."""
    return [slug for slug, cat, rx in table if slug != "query" and rx.search(text)]


def pick_trigger(text, tcat, tsvc):
    """구조화된 칸을 먼저 믿고, 본문으로 더 좁힌다."""
    slug, cat = "", ""
    if tsvc in IFTTT_SVC:
        slug, cat = IFTTT_SVC[tsvc]
    elif tcat in IFTTT_CAT:
        slug, cat = IFTTT_CAT[tcat]
    t_slug, t_cat = match(text, TRIG_RE)
    # 본문이 sun/leave/motion 처럼 더 구체적이면 그걸 쓴다
    if t_slug and (not slug or t_slug in ("sun", "leave", "motion", "presence", "doorbell",
                                          "contact", "finished", "smoke", "leak", "timer")):
        return t_slug, t_cat
    return (slug or t_slug), (cat or t_cat)


def read_ifttt(path, src, rows):
    if not os.path.exists(path):
        print(f"  ! 없음 {path}")
        return
    n = 0
    for i, r in enumerate(csv.DictReader(open(path, encoding="utf-8"))):
        # friendly_id 는 "wcC9tfDg-when-i-get-close-to-the-home-..." 처럼
        # 앞 8자 고유 id 뒤에 애플릿 제목이 슬러그로 붙어 있다.
        # 제목은 CC BY-NC-SA 대상이라 싣지 않는다 — 앞 토큰만 남긴다.
        fid = (r.get("friendly_id") or "").split("-")[0] or str(i)
        blob = f"{r.get('name','')} {r.get('description','')}".lower()
        trig, dtrig = pick_trigger(blob, r.get("triggers_category", ""),
                                   r.get("service_triggers", ""))
        # 액션은 트리거 쪽 문구에 안 걸리게 뒤쪽만 본다면 좋겠지만 문장이 짧아 통째로 본다
        act, dact = match(blob, ACT_RE)
        acts = match_all(blob, ACT_RE)
        try:
            score = int(float(r.get("installs_count") or 0))
        except ValueError:
            score = 0
        rows.append(dict(
            src=src, sid=f"{src}:{fid}", score=score,
            trig=trig, dev_trig=dtrig, act=act, dev_act=dact,
            acts="|".join(acts), n_act=len(acts),
            mobile=1 if str(r.get("requires_mobile_app")).lower() == "true" else 0,
            text="", text_ok=0, note=r.get("triggers_category", "")))
        n += 1
    print(f"  {src}: {n}행")


def read_ha(path, rows):
    if not os.path.exists(path):
        print(f"  ! 없음 {path}")
        return
    data = json.load(open(path, encoding="utf-8"))
    for t in data:
        title = t.get("title", "")
        blob = title.lower()   # 본문은 안 본다: 포럼 상용구("hit the button below")에 오염돼 있다
        trig, dtrig = match(blob, TRIG_RE)
        act, dact = match(blob, ACT_RE)
        aa = match_all(blob, ACT_RE)
        rows.append(dict(
            acts="|".join(aa), n_act=len(aa),
            src="ha", sid=f"ha:{t.get('id')}", score=int(t.get("views") or 0),
            trig=trig, dev_trig=dtrig, act=act, dev_act=dact, mobile=0,
            text=title, text_ok=0, note="blueprint"))
    print(f"  ha: {len(data)}행")


def read_acon(rows):
    import pyarrow.parquet as pq
    seen, n = set(), 0
    for i in range(5):
        p = os.path.join(SP, f"acon_{i}.parquet")
        if not os.path.exists(p):
            continue
        for rec in pq.read_table(p, columns=["messages"]).to_pylist():
            for m in rec["messages"]:
                if m["role"] != "user":
                    continue
                for c in m["content"]:
                    u = (c.get("text") or "").strip()
                    if not u or len(u) > 160 or u.lower() in seen:
                        continue
                    if not is_english(u):
                        continue
                    seen.add(u.lower())
                    b = u.lower()
                    trig, dtrig = match(b, TRIG_RE)
                    act, dact = match(b, ACT_RE)
                    aa = match_all(b, ACT_RE)
                    rows.append(dict(
                        acts="|".join(aa), n_act=len(aa),
                        src="acon", sid=f"acon:{n}", score=1,
                        trig=trig or "now", dev_trig=dtrig, act=act, dev_act=dact,
                        mobile=0, text=u, text_ok=1, note="MIT"))
                    n += 1
    print(f"  acon: {n}행 (중복 제거 후)")


def read_massive(rows):
    import pyarrow.parquet as pq
    IOT = 8   # ClassLabel 순서에서 'iot'
    n = 0
    for split in ("train", "test", "validation"):
        p = os.path.join(SP, f"massive_{split}.parquet")
        if not os.path.exists(p):
            continue
        for rec in pq.read_table(p, columns=["scenario", "utt", "intent"]).to_pylist():
            if rec["scenario"] != IOT:
                continue
            u = (rec["utt"] or "").strip()
            b = u.lower()
            trig, dtrig = match(b, TRIG_RE)
            act, dact = match(b, ACT_RE)
            aa = match_all(b, ACT_RE)
            rows.append(dict(
                acts="|".join(aa), n_act=len(aa),
                src="massive", sid=f"massive:{split}:{n}", score=1,
                trig=trig or "now", dev_trig=dtrig, act=act, dev_act=dact,
                mobile=0, text=u, text_ok=1, note="CC BY 4.0"))
            n += 1
    print(f"  massive: {n}행 (iot)")


def main():
    rows = []
    print("원천 읽는 중")
    read_ifttt(os.path.join(SP, "ifttt_iot.csv"), "ifttt", rows)
    read_ifttt(os.path.join(SP, "ifttt_pop.csv"), "ifttt_pop", rows)
    read_ha(os.path.join(SP, "ha_blueprints.json"), rows)
    read_acon(rows)
    read_massive(rows)

    # ifttt_pop 은 ifttt_iot 를 포함한다 — IoT 로 안 잡힌 것만 남긴다
    iot_ids = {r["sid"].split(":", 1)[1] for r in rows if r["src"] == "ifttt"}
    keep = []
    for r in rows:
        if r["src"] == "ifttt_pop":
            if r["sid"].split(":", 1)[1] in iot_ids:
                continue
            if not r["act"]:            # 기기를 건드리지 않으면 우리 것이 아니다
                continue
            # src 는 ifttt_pop 그대로 둔다 — 빈도 순위는 IoT 판정본만 쓴다
        keep.append(r)
    rows = keep

    cols = ["src", "sid", "score", "trig", "dev_trig", "act", "dev_act",
            "acts", "n_act", "mobile", "text_ok", "text", "note"]
    dst = os.path.join(HERE, "corpus.csv")
    with open(dst, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})

    # ── 진단 ───────────────────────────────────────────────────────────
    import collections
    print(f"\ncorpus.csv: {len(rows)}행")
    print("원천별:", dict(collections.Counter(r["src"] for r in rows)))
    miss_t = sum(1 for r in rows if not r["trig"])
    miss_a = sum(1 for r in rows if not r["act"])
    print(f"트리거 못 읽음 {miss_t} ({miss_t/len(rows):.1%}) / "
          f"액션 못 읽음 {miss_a} ({miss_a/len(rows):.1%})")
    print("한 문장이 건드리는 기기 종류 수:",
          dict(sorted(collections.Counter(r.get("n_act", 0) for r in rows).items())))

    inst = collections.Counter()
    for r in rows:
        if r["src"] == "ifttt" and r["trig"]:
            inst[r["trig"]] += r["score"]
    tot = sum(inst.values())
    print(f"\n── IFTTT 설치수로 본 트리거 (합 {tot:,}) ──")
    for k, v in inst.most_common(20):
        print(f"  {k:10s} {v:9,}  {v/tot:5.1%}")

    acts = collections.Counter()
    for r in rows:
        if r["src"] == "ifttt" and r["act"]:
            acts[r["act"]] += r["score"]
    ta = sum(acts.values())
    print(f"\n── IFTTT 설치수로 본 액션 (합 {ta:,}) ──")
    for k, v in acts.most_common(20):
        print(f"  {k:12s} {v:9,}  {v/ta:5.1%}")

    hv = collections.Counter()
    for r in rows:
        if r["src"] == "ha" and r["trig"]:
            hv[r["trig"]] += r["score"]
    th = sum(hv.values())
    print(f"\n── HA 블루프린트 조회수로 본 트리거 (합 {th:,}) ──")
    for k, v in hv.most_common(12):
        print(f"  {k:10s} {v:9,}  {v/th:5.1%}")

    print("\n── 문장을 그대로 쓸 수 있는 행 ──")
    print("  ", dict(collections.Counter(r["src"] for r in rows if r["text_ok"])))
    cats = {r["dev_act"] for r in rows if r["dev_act"]} | \
           {r["dev_trig"] for r in rows if r["dev_trig"]}
    known = {k for k in json.load(open(CATALOG, encoding="utf-8")) if not k.startswith("$")}
    print("  카탈로그에 없는 카테고리로 매핑됨:", sorted(cats - known) or "없음 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
