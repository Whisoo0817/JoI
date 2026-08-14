"""행별 레퍼런스 바인딩 생성 (§9.4).

바인딩 표 = IR의 서비스 자리(등장 순서) → 인벤토리 기기 id 목록.
자리 이름 = 서비스명, 같은 서비스가 다른 기기 집합으로 또 나오면 "#2".

자리 걷기 순서: 타임라인 위→아래, 한 스텝 안은 cond 원자 왼→오 →
call target → args의 $읽기, 그 다음 then/else/body 재귀.

휴리스틱(순서대로):
  1) 후보 1개 → 확정
  2) "all/any/모든/... + 기기 종류" 어구 → (위치 한정 시 그 위치의) 전부
  3) 변별 태그(후보끼리 다른 태그)를 camelCase 분해해 NL에서 찾기
     - 자리 1개: 정확히 한 후보만 맞으면 확정
     - 자리 k개: 맞은 후보가 k개면 NL 등장 순서대로 자리에 배정
  4) 실패 → 검토 필요로 보고

실행: joi 디렉토리에서  python3 scratchpad/bindgen.py [--write]
"""
import csv
import json
import re
import sys

# 한국어 → 태그 (영어는 태그 camelCase 분해로 자동 매칭)
KOR = {
    "거실": "LivingRoom", "침실": "Bedroom", "주방": "Kitchen", "부엌": "Kitchen",
    "차고": "Garage", "현관": "Entrance", "욕실": "Bathroom", "화장실": "Bathroom",
    "회의실": "MeetingRoom", "사무실": "Office", "로비": "Lobby", "지하": "Basement",
    "다용도": "Utility", "세탁실": "LaundryRoom", "식당": "Dining", "복도": "Hallway",
    "서재": "Study", "팬트리": "Pantry", "발코니": "Balcony", "지붕": "Roof",
    "정원": "Garden", "마당": "Yard", "와인": "WineCellar", "아기": "BabyRoom",
    "주차장": "ParkingLot", "창고": "Warehouse", "서버": "ServerRoom",
    "1층": "Floor1", "2층": "Floor2", "3층": "Floor3", "북쪽": "North",
    "남쪽": "South", "실내": "Indoor", "실외": "Outdoor", "짝수": "Even",
    "홀수": "Odd", "앞": "Front", "뒤": "Back", "메인": "Main",
    "안방": "MasterBedroom", "뒷마당": "Backyard", "앞마당": "Frontyard",
    "프린터": "Printer", "모니터": "Monitor", "충전기": "Charger",
    "티비": "TV", "밥솥": "RiceCooker", "사운드바": "Soundbar",
    "위쪽": "Up", "아래쪽": "Down", "가운데": "Mid",
    "상단": "Top", "하단": "Bottom", "중단": "Middle",
}
# 영어 동의어 (어구, 태그) — 다대다 허용
SYN = [
    ("upper", "Up"), ("upper", "Top"), ("top", "Top"),
    ("lower", "Down"), ("lower", "Bottom"), ("bottom", "Bottom"),
    ("middle", "Mid"), ("middle", "Middle"),
    ("1st floor", "Floor1"), ("first floor", "Floor1"),
    ("2nd floor", "Floor2"), ("second floor", "Floor2"),
    ("3rd floor", "Floor3"), ("third floor", "Floor3"),
    ("zone 1", "Sector1"), ("zone 2", "Sector2"),
    ("sector b", "SectorB"), ("laundry room", "LaundryRoom"),
    ("data center", "DataCenter"), ("even-tagged", "Even"),
    ("odd-tagged", "Odd"),
]
# 집합 어구(all/any/at least one) — either/both는 자리 분배라 별개
QUANT_RE = re.compile(
    r"\b(?:all|any|at least one)\s+(?:the\s+)?([^,.;]{0,60})", re.I)

REF = re.compile(r"\b([A-Z][A-Za-z0-9]+)\.([A-Za-z_][A-Za-z0-9_]*)")


def words_of(tag):
    """camelCase 태그 → 소문자 어구. 'FrontDoor' → 'front door'."""
    parts = re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]*|\d+", tag)
    return " ".join(p.lower() for p in parts) if parts else tag.lower()


_CATALOG = None

def catalog_ids():
    global _CATALOG
    if _CATALOG is None:
        d = json.load(open("files/service_list_ver2.0.7.json"))
        _CATALOG = {s["id"] for s in d["skills"]}
    return _CATALOG


def cond_services(c):
    c = re.sub(r'"[^"]*"|\'[^\']*\'', "", c or "")
    return [m[0] for m in REF.findall(c)
            if m[0] not in ("clock", "Clock") and m[0] in catalog_ids()]


def walk_slots(steps, out):
    """자리 걷기 — (서비스, 자리 성격) 목록. 성격: "cond"(조건 — 참/거짓
    맥락) / "scalar"(read op·인자 — 값 하나를 담는 자리) / "call"(액션
    표적). 순서가 곧 자리 번호 (§9.4)."""
    for s in steps:
        if not isinstance(s, dict):
            continue
        for f in ("cond", "until"):
            if s.get(f):
                out.extend((x, "cond") for x in cond_services(s[f]))
        if s.get("op") == "read" and s.get("src"):
            svc = s["src"].partition(".")[0]
            if svc != "clock":
                out.append((svc, "scalar"))
        if s.get("op") == "call":
            out.append((s["target"].partition(".")[0], "call"))
            for v in (s.get("args") or {}).values():
                if isinstance(v, str):
                    out.extend((x, "scalar") for x in cond_services(v))
        for v in s.values():
            if isinstance(v, list):
                walk_slots(v, out)
    return out


def mention_pos(tag, eng, kor):
    """태그가 NL에 언급되는 첫 위치 (영문 우선, 한국어는 영문 길이만큼 밀기)."""
    w = words_of(tag)
    for v in (w, w.replace(" ", ""), tag.lower()):
        i = eng.find(v)
        if i >= 0:
            return i
    for sw, t in SYN:
        if t == tag:
            j = eng.find(sw)
            if j >= 0:
                return j
    for kw, t in KOR.items():
        if t == tag:
            j = kor.find(kw)
            if j >= 0:
                return len(eng) + j
    return -1


def assign(svc, k, cands, devs, eng, kor):
    """서비스 svc의 자리 k개에 기기 배정. [(devices, way)] × k."""
    if len(cands) == 1:
        return [(cands[:], "only")] * k

    # 변별 태그(모든 후보가 공유하지 않는 태그)의 NL 언급: 후보별 (개수, 첫 위치)
    shared = set.intersection(*(set(devs[d].get("tags", [])) for d in cands))
    pos, score = {}, {}
    for d in cands:
        ps = [mention_pos(t, eng, kor)
              for t in devs[d].get("tags", []) if t not in shared]
        ps = [p for p in ps if p >= 0]
        if ps:
            pos[d] = min(ps)
            score[d] = len(ps)
    top = max(score.values(), default=0)
    best = sorted((d for d in score if score[d] == top), key=pos.get)

    # "all/any/… + 이 기기 종류" 어구 (영문에서만 판정 — 한국어는 번역 병행).
    # 제약 필터는 그 어구 '안'의 단어로만 — NL 다른 곳의 위치어는 남의 몫.
    kind_tokens = {w for d in cands for t in devs[d].get("tags", [])
                   for w in words_of(t).split()}
    kind_tokens |= {w for d in cands for c in devs[d].get("category", [])
                    for w in words_of(c).split()}
    def quant_set():
        for m in QUANT_RE.finditer(eng):
            phrase = m.group(1).lower()
            toks = {t.rstrip("s") for t in re.split(r"[^a-z0-9]+", phrase) if t}
            if not (toks & kind_tokens):
                continue
            sc = {}
            for d in cands:
                sc[d] = sum(1 for t in devs[d].get("tags", []) if t not in shared
                            and mention_pos(t, phrase, "") >= 0)
            mx = max(sc.values())
            return [d for d in cands if sc[d] == mx]
        return None

    q = quant_set()          # "all X" 집합 어구는 짝짓기보다 우선
    if q:
        return [(q, "all")] * k
    if k == 1:
        if len(best) == 1:
            return [(best, "loc")]
        return [(best or cands[:], "ambig")]
    # 자리 k개: 서로 다른 위치에서 언급된 후보가 k개면 순서대로 짝짓기
    if len(pos) == k and len(set(pos.values())) == k:
        ordered = sorted(pos, key=pos.get)
        return [([d], "loc") for d in ordered]
    if len(pos) == 1:        # 한 기기를 여러 자리에서 읽고·움직이는 행
        return [(list(pos), "loc")] * k
    if pos:                  # 언급이 겹침(같은 태그 쌍 등) → 집합으로
        return [(sorted(pos, key=pos.get), "loc")] * k
    return [(best or cands[:], "ambig")] * k


def candidates(devs, svc):
    return [did for did, d in devs.items()
            if svc in d.get("category", []) or svc in d.get("tags", [])]


# ---- 캐시(정답 307쌍)의 JoI 셀렉터에서 확정 바인딩 추출 ----

def cache_groups(key):
    """캐시 행의 JoI에서 태그 그룹들을 뽑는다. {(svc소문자): [태그집합,...]}"""
    import glob
    import os
    path = f"paper/simulators/cache/{key}.json"
    if not os.path.exists(path):
        return None
    try:
        sys.path.insert(0, ".")
        from explorer.interp import parse
        from explorer.m3_check import build_maps
        d = json.load(open(path))
        jb = d.get("joi_block")
        if not jb:
            return None
        name_map, bind = build_maps(parse(jb["script"]))
        out = {}
        for (svc, m), groups in bind.items():
            out.setdefault(svc.lower(), []).extend(
                [set(g) for g in groups if g])
        for nm, wk in name_map.items():
            tags = wk.rsplit(".", 1)[0].split("+")
            svc = tags[-1].lower()
            grp = set(tags)
            if grp not in out.setdefault(svc, []):
                out[svc].append(grp)
        return out
    except Exception:
        return None


def from_cache(groups, svc, cands, devs):
    """캐시 태그 그룹이 후보 중 정확히 한 부분집합을 고르면 그 기기들."""
    if not groups:
        return None
    gs = groups.get(svc.lower())
    if not gs:
        return None
    picked = []
    for g in gs:
        hit = [d for d in cands if g <= set(devs[d].get("tags", []))]
        if hit and hit not in picked:
            picked.append(hit)
    if len(picked) == 1 and len(picked[0]) < len(cands):
        return picked[0]
    return None


# 여러 대를 읽는 자리의 뜻: "하나라도"(any)가 기본, "전부"(all)만 수기 표기.
# (2026-08-14 검수: 다기기 읽기 19행 중 any 17, all 2 — §9.10)
READ_QUANT_ALL = {("C17_008", "HumiditySensor"), ("C03_024", "TemperatureSensor")}

# 센서류를 조건에서 읽는 자리를 규약(첫 후보 1대)으로 좁히지 않고 후보
# 전체 집합으로 두는 정책 (2026-08-14 whisoo 결정, §9.11). "연기가
# 감지되면"의 자연스러운 뜻은 "아무 센서나". 값 하나를 담는 scalar
# 자리(알림용 읽기 등)는 집합 불가라 제외. 극성: 재실류 부재 감시
# (Presence/Motion == false)는 all(전부 미감지), 그 외는 any.
SENSORISH = lambda svc: svc.endswith("Sensor") or svc.endswith("Detector")
ABSENCE_SVCS = {"PresenceSensor", "MotionSensor", "PresenceVitalSensor"}


def absence_read(svc, ir_text):
    """부재 감시인가 — 재실류 서비스를 false/not으로 비교하면 all."""
    if svc not in ABSENCE_SVCS:
        return False
    return bool(re.search(rf"{svc}\.\w+\s*==\s*false|not\s+{svc}\.", ir_text))

# 휴리스틱이 원리상 못 가르는 행 (예: DoorLock 태그가 전 후보 공유 —
# "금고"와 "도어락"을 태그 부재로 구분 불가) — 수기 명세.
# 2026-08-14 게이트 가동(W3)이 드러낸 4행 추가:
#   C05_016·C16_001  장소 없는 "감지되면"(아무 센서나)을 무지정 단수 규약이
#                    첫 후보로 좁혔음 → any 집합으로 정정
#   C10_005          "모든 긴급 사이렌"(3대 전부)인데 집합 어구 판정이 앞
#                    구절의 "house"에 걸려 2대로 좁혔음
#   C05_026          "에어컨 켜기/가습기 끄기" 두 자리를 언급 겹침으로
#                    4기기 한 자리로 뭉갰음 → 자리 분리
# §9.12(무표지 액션→전체) 반영: 무표지 스피커·사이렌 액션 자리는 후보 전체.
# C05_026의 에어컨·가습기는 와인셀러 문맥이 기기를 명시적으로 좁힘 — 단수 유지.
OVERRIDE = {
    "C16_002": {"DoorLock": ["Main_DoorLock"], "DoorLock#2": ["Entrance_Lock"],
                "Speaker": ["Living_Speaker", "Bedroom_Speaker"]},
    "C16_004": {"DoorLock": ["Main_DoorLock"], "DoorLock#2": ["Entrance_Lock"],
                "Speaker": ["Living_Speaker", "Bedroom_Speaker"]},
    "C05_016": {"PresenceSensor": {"any": ["Living_Presence", "Bedroom_Presence"]},
                "SmokeDetector": {"any": ["Kitchen_Smoke", "Bedroom_Smoke"]},
                "Siren": ["Main_Siren", "Entrance_Siren"],
                "Speaker": ["Living_Speaker", "Bedroom_Speaker"]},
    "C16_001": {"LeakSensor": {"any": ["Basement_Leak", "Kitchen_Leak"]},
                "Siren": ["Main_Siren", "Entrance_Siren"]},
    "C10_005": {"PresenceSensor": {"any": ["House_Presence_1", "House_Presence_2"]},
                "Siren": ["Main_Siren", "Sub_Siren", "Garden_Siren"]},
    "C05_026": {"TemperatureSensor": ["WineCellar_Temp"],
                "HumiditySensor": ["WineCellar_Hum"],
                "Switch": ["AC"], "Switch#2": ["WineCellar_Humidifier"]},
}


def build(r):
    devs = json.loads(r["connected_devices"]) if r["connected_devices"] else {}
    ir = json.loads(r["ir_gt"])
    eng = r["command_eng"].lower()
    kor = r["command_kor"]
    seq = walk_slots(ir.get("timeline") or [], [])
    # 서비스별 자리 수 + 자리 성격(read/call) 등장 순서
    by_svc = {}
    kinds_by_svc = {}
    order = []
    for svc, kind in seq:
        if svc not in by_svc:
            by_svc[svc] = 0
            kinds_by_svc[svc] = []
            order.append(svc)
        by_svc[svc] += 1
        kinds_by_svc[svc].append(kind)
    binding, ways, flags = {}, {}, []
    read_slots = set()
    key = f'{r["category_v2"]}_{int(float(r["index"])):03d}'
    if key in OVERRIDE:
        return OVERRIDE[key], {k: "manual" for k in OVERRIDE[key]}, []
    cgroups = cache_groups(key)
    for svc in order:
        cands = candidates(devs, svc)
        if not cands:
            flags.append(f"{svc}: 후보 기기 없음")
            continue
        k = by_svc[svc]
        picks = assign(svc, k, cands, devs, eng, kor)
        # 애매하면(무표지): ① 액션 자리 = 후보 전체(§9.12 무표지→all)
        # ② 캐시 셀렉터 증거 ③ 센서류 조건 읽기 = 후보 전체 집합(§9.11)
        # ④ Main 태그 ⑤ 첫 후보 (규약). 읽기 자리(cond/scalar)에는
        # 무표지→all을 적용하지 않는다 (whisoo 결정 §9.12).
        kinds = kinds_by_svc[svc]
        # 1차: 읽기 자리(cond/scalar)와 무표지 아닌 자리 먼저 확정 (기존 규약)
        fixed = [None] * len(picks)
        for i, (devices, way) in enumerate(picks):
            if way == "ambig" and kinds[i] == "call":
                continue                     # 액션 무표지는 2차에서
            if way == "ambig":
                cev = from_cache(cgroups, svc, cands, devs)
                if cev:
                    devices, way = cev, "cache"
                elif kinds[i] == "cond" and SENSORISH(svc):
                    devices, way = cands[:], "set"
                else:
                    mains = [d for d in cands
                             if "Main" in devs[d].get("tags", [])]
                    if len(mains) == 1:
                        devices, way = mains, "main"
                    else:
                        devices, way = cands[:1], "first"
            fixed[i] = (devices, way)
        # 2차: 액션 무표지 자리. 같은 서비스를 읽는 자리가 이 행에 있으면
        # 같은 대상을 물려받는다 ("안 잠겨있으면 잠가줘" — 보던 그 기기를
        # 잠가야지 후보 전부가 아님). 없으면 후보 전체 (§9.12 무표지→all:
        # "조명을 켜줘"에 조명이 여럿이면 전부. 옛 Main/첫 후보 규약과
        # 옛 규약 산물인 캐시 증거는 액션 자리에서 폐기).
        for i in range(len(picks)):
            if fixed[i] is not None:
                continue
            ref = next((fixed[j][0] for j in range(len(picks))
                        if fixed[j] is not None and kinds[j] != "call"), None)
            if ref:
                fixed[i] = (list(ref), "coref")
            else:
                fixed[i] = (cands[:], "act-all")
        picks = fixed
        # 같은 집합이면 자리 합치기 (합쳐진 자리의 조건 성격은 누적)
        seen = []                      # [(sorted(devices), 자리 이름)]
        for i, (devices, way) in enumerate(picks):
            hit = next((nm for ds, nm in seen if sorted(devices) == ds), None)
            if hit:
                if kinds[i] == "cond":
                    read_slots.add(hit)
                continue
            name = svc if not any(x == svc or x.startswith(svc + "#")
                                  for x in binding) else \
                f"{svc}#{sum(1 for x in binding if x == svc or x.startswith(svc + '#')) + 1}"
            seen.append((sorted(devices), name))
            binding[name] = devices
            ways[name] = way
            if kinds[i] == "cond":
                read_slots.add(name)
            if way in ("main", "first"):
                flags.append(f"{name}[{way}]: 후보 {cands} → {devices}")
    # 조건에서 여러 대를 읽는 자리 → 한정자 표기 ({"any"/"all": [...]}),
    # 액션 전용은 목록 그대로. 부재 감시(재실류 == false)는 all.
    for name in list(binding):
        if len(binding[name]) > 1 and name in read_slots:
            svc = name.split("#")[0]
            q = ("all" if (key, name) in READ_QUANT_ALL
                 or absence_read(svc, r["ir_gt"]) else "any")
            binding[name] = {q: binding[name]}
            flags.append(f"{name}[읽기 {q}]: {binding[name][q]}")
    return binding, ways, flags


def main():
    rows = list(csv.DictReader(open("dataset.csv")))
    n_flag = 0
    stats = {"only": 0, "loc": 0, "all": 0, "cache": 0, "set": 0, "act-all": 0,
             "coref": 0, "main": 0, "first": 0, "manual": 0}
    for r in rows:
        key = f'{r["category_v2"]}_{int(float(r["index"])):03d}'
        try:
            binding, ways, flags = build(r)
        except Exception as e:
            print(f"!! {key}: {type(e).__name__} {e}")
            continue
        for w in ways.values():
            stats[w] += 1
        if flags:
            n_flag += 1
            print(f"{key} | {r['command_eng'][:64]}")
            for fl in flags:
                print("     ?", fl)
        r["_binding"] = json.dumps(binding, ensure_ascii=False)
    print("\n자리 판정 분포:", stats, "| 검토 필요 행:", n_flag)

    if "--write" in sys.argv:
        fields = [c for c in rows[0].keys() if c != "_binding"]
        if "binding_gt" not in fields:
            fields.append("binding_gt")
        for r in rows:
            r["binding_gt"] = r.pop("_binding", "{}")
        with open("dataset.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        print("binding_gt 열 기록 완료")


if __name__ == "__main__":
    main()
