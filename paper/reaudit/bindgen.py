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
    for s in steps:
        if not isinstance(s, dict):
            continue
        for f in ("cond", "until"):
            if s.get(f):
                out.extend(cond_services(s[f]))
        if s.get("op") == "read" and s.get("src"):
            svc = s["src"].partition(".")[0]
            if svc != "clock":
                out.append(svc)
        if s.get("op") == "call":
            out.append(s["target"].partition(".")[0])
            for v in (s.get("args") or {}).values():
                if isinstance(v, str):
                    out.extend(cond_services(v))
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


# 휴리스틱이 원리상 못 가르는 행 (예: DoorLock 태그가 전 후보 공유 —
# "금고"와 "도어락"을 태그 부재로 구분 불가) — 수기 명세
OVERRIDE = {
    "C16_002": {"DoorLock": ["Main_DoorLock"], "DoorLock#2": ["Entrance_Lock"],
                "Speaker": ["Living_Speaker"]},
    "C16_004": {"DoorLock": ["Main_DoorLock"], "DoorLock#2": ["Entrance_Lock"],
                "Speaker": ["Living_Speaker"]},
}


def build(r):
    devs = json.loads(r["connected_devices"]) if r["connected_devices"] else {}
    ir = json.loads(r["ir_gt"])
    eng = r["command_eng"].lower()
    kor = r["command_kor"]
    seq = walk_slots(ir.get("timeline") or [], [])
    # 서비스별 자리 수 (연속 중복은 한 자리로 — 같은 원자 반복 읽기)
    by_svc = {}
    order = []
    for svc in seq:
        if svc not in by_svc:
            by_svc[svc] = 0
            order.append(svc)
        by_svc[svc] += 1
    binding, ways, flags = {}, {}, []
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
        # 애매하면: ① 캐시 셀렉터 증거 ② Main 태그 ③ 첫 후보 (규약)
        fixed = []
        for devices, way in picks:
            if way == "ambig":
                cev = from_cache(cgroups, svc, cands, devs)
                if cev:
                    devices, way = cev, "cache"
                else:
                    mains = [d for d in cands
                             if "Main" in devs[d].get("tags", [])]
                    if len(mains) == 1:
                        devices, way = mains, "main"
                    else:
                        devices, way = cands[:1], "first"
            fixed.append((devices, way))
        picks = fixed
        # 같은 집합이면 자리 합치기
        seen = []
        for devices, way in picks:
            if any(sorted(devices) == sorted(p) for p in seen):
                continue
            seen.append(devices)
            name = svc if not any(x == svc or x.startswith(svc + "#")
                                  for x in binding) else \
                f"{svc}#{sum(1 for x in binding if x == svc or x.startswith(svc + '#')) + 1}"
            binding[name] = devices
            ways[name] = way
            if way in ("main", "first"):
                flags.append(f"{name}[{way}]: 후보 {cands} → {devices}")
    return binding, ways, flags


def main():
    rows = list(csv.DictReader(open("dataset.csv")))
    n_flag = 0
    stats = {"only": 0, "loc": 0, "all": 0, "cache": 0, "main": 0, "first": 0,
             "manual": 0}
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
