"""E4 하네스 — HA 고유 fault class 주입 → 게이트 검출표 + profile 비용(LoC).

참조 lowering(게이트 EQUIV 확인, 388/388)의 YAML을 클래스별로 비틀어
전부 DIVERGE(반례 재생 확인) 또는 REFUSED(조각 밖 fail-closed)가 되는지
본다. 변형이 실제로 문서를 바꿨는지 가드(no-op 검사)를 두어 "치환 실패
= 조용한 EQUIV" 함정을 막는다 (explorer/e1.py의 교훈).

fault class (percom.md §4.4):
  trigger↔condition 혼동 / 지속(for) 누락 / mode 변조 / timeout 방치 /
  above·below exclusive 경계 / while↔until 혼동 / helper 미시드 /
  entity 오선택 (wrong-binding HA판)

Run:  python -m ha.e4        # 표 출력 + explorer/runs/e4.md 갱신
"""

from __future__ import annotations

import copy
import csv
import glob
import json
import os

import yaml

from .gate_ha import gate_pair_ha


def load(key: str) -> dict:
    with open(f"ha/gt/{key}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def rows_by_key() -> dict:
    out = {}
    for r in csv.DictReader(open("dataset.csv")):
        out[f'{r["category_v2"]}_{int(float(r["index"])):03d}'] = r
    return out


# ── 변형들 (각각 문서를 제자리에서 비튼다) ───────────────────────────────────

def trigger_to_condition(doc: dict) -> None:
    """엣지 trigger를 레벨 condition으로 옮겨 적는 문법 위치 오류 —
    JoI의 엣지→레벨 idiom 버그가 HA에서 형태만 바뀐 것 (§4.2)."""
    au = doc["automation"]
    t = au["triggers"][0]
    assert t["trigger"] == "state", t
    au["triggers"] = [{"trigger": "time_pattern", "seconds": "/1"}]
    au["conditions"] = list(au.get("conditions") or []) + \
        [{"condition": "state", "entity_id": t["entity_id"],
          "state": t["to"]}]


def drop_sustain(doc: dict) -> None:
    """지속(for) 누락: '2분간 계속 감지되면'의 지속 관용구를 즉발 wait로."""
    seq = doc["script"]["sequence"]
    rp = seq[0]["repeat"]
    first = rp["sequence"][0]
    assert "wait_template" in first
    seq[0] = {"wait_template": first["wait_template"]}


def wrong_mode(doc: dict) -> None:
    root = doc.get("automation") or doc.get("script")
    assert root["mode"] == "single"
    root["mode"] = "restart"


def drop_timeout_branch(doc: dict) -> None:
    """timeout 방치: 초과 분기(if not wait.completed)를 지워 조용히 계속
    진행 — continue_on_timeout 기본값(true)의 silent-divergence 발생기."""
    seq = doc["script"]["sequence"]
    for i, a in enumerate(seq):
        if "if" in a and "wait.completed" in json.dumps(a["if"]):
            del seq[i]
            return
    raise AssertionError("timeout 분기 없음")


def ge_to_above(doc: dict) -> None:
    """>= 를 exclusive above로 잘못 내림 — comparator 클래스의 HA판.
    경계값 셀(딱 N)에서만 갈린다."""
    import re

    def walk(node):
        if isinstance(node, list):
            for x in node:
                if walk(x):
                    return True
        elif isinstance(node, dict):
            for k, v in list(node.items()):
                if k == "if" and isinstance(v, list) and len(v) == 1 \
                        and v[0].get("condition") == "template":
                    m = re.fullmatch(
                        r"\{\{ states\('([^']+)'\)\|float >= ([\d.]+) \}\}",
                        v[0]["value_template"])
                    if m:
                        node[k] = [{"condition": "numeric_state",
                                    "entity_id": m.group(1),
                                    "above": float(m.group(2))}]
                        return True
                if walk(v):
                    return True
        return False
    assert walk(doc), ">= 템플릿 조건 없음"


def while_to_until(doc: dict) -> None:
    """while↔until 혼동: until은 최소 1회 실행 — 이미 종료 조건인 채로
    시작한 셀에서 몸통이 한 번 더 돈다."""
    au = doc["automation"]
    rp = au["actions"][0]["repeat"]
    wc = rp.pop("while")
    assert len(wc) == 1 and wc[0]["condition"] == "time" \
        and "before" in wc[0]
    rp["until"] = [{"condition": "time", "after": wc[0]["before"]}]


def drop_helpers(doc: dict) -> None:
    assert doc.get("helpers")
    del doc["helpers"]


def drop_one_target(doc: dict) -> None:
    """집합 탈락: 여러 대 액션에서 한 대를 빠뜨림 (entity 오선택 —
    wrong-binding fault의 HA판)."""
    def walk(node):
        if isinstance(node, list):
            return any(walk(x) for x in node)
        if isinstance(node, dict):
            ents = node.get("target", {}).get("entity_id") \
                if "action" in node else None
            if isinstance(ents, list) and len(ents) > 1:
                node["target"]["entity_id"] = ents[:1]
                return True
            return any(walk(v) for v in node.values())
        return False
    assert walk(doc), "여러 대 target 없음"


def swap_read_entity(doc: dict, frm: str, to: str) -> None:
    """읽기 재배선: 조건이 엉뚱한 방 센서를 본다."""
    s = json.dumps(doc)
    assert frm in s, frm
    doc.clear()
    doc.update(json.loads(s.replace(frm, to)))


MUTS = [
    ("trigger→condition (엣지를 레벨 자리에)", "C08_012", "DIVERGE",
     trigger_to_condition),
    ("지속(for) 누락 — 즉발로 강등", "C20_001", "DIVERGE", drop_sustain),
    ("mode 변조 single→restart", "C08_012", "REFUSED", wrong_mode),
    ("timeout 초과 분기 삭제(방치)", "C26_001", "DIVERGE",
     drop_timeout_branch),
    (">= 를 above(exclusive)로 — 경계 셀", "C03_005", "DIVERGE",
     ge_to_above),
    ("while→until — 최소 1회 실행", "C18_001", "DIVERGE", while_to_until),
    ("helper 선언 삭제(미시드)", "C13_001", "REFUSED", drop_helpers),
    ("집합 탈락 — 사이렌 2대 중 1대", "C05_016", "DIVERGE",
     drop_one_target),
    ("읽기 재배선 — 거실 재실을 침실 센서로", "C05_016", "DIVERGE",
     lambda d: swap_read_entity(
         d, "binary_sensor.living_presence_presence",
         "binary_sensor.bedroom_presence_presence")),
]


def profile_loc() -> list[tuple[str, int]]:
    out = []
    for f in sorted(glob.glob("ha/*.py")) + ["ha/skill_map.json"]:
        if f.endswith("__init__.py"):
            continue
        with open(f, encoding="utf-8") as fh:
            out.append((f, sum(1 for _ in fh)))
    return out


def main() -> None:
    rows = rows_by_key()
    lines = []
    n_bad = 0
    for name, key, want, fn in MUTS:
        doc = load(key)
        before = json.dumps(doc, sort_keys=True, ensure_ascii=False)
        fn(doc)
        after = json.dumps(doc, sort_keys=True, ensure_ascii=False)
        assert before != after, f"no-op 변형: {name}"
        r = rows[key]
        g = gate_pair_ha(json.loads(r["ir_gt"]),
                         json.loads(r["binding_gt"] or "{}"),
                         json.loads(r["connected_devices"]), doc)
        tag = g.verdict
        if g.verdict == "DIVERGE":
            tag += " (재생 확인)" if g.confirmed else " (재생 미확인!)"
        ok = g.verdict == want and (g.verdict != "DIVERGE" or g.confirmed)
        if not ok:
            n_bad += 1
        lines.append((name, key, want, tag, "✓" if ok else "✗"))
        print(f"  {name:38s} {key}  기대 {want:8s} → {tag} "
              f"{'✓' if ok else '✗'}")

    loc = profile_loc()
    total = sum(n for _, n in loc)
    print(f"\nprofile 비용: {total} 줄 "
          f"({', '.join(f'{f.split(chr(47))[-1]} {n}' for f, n in loc)})")
    print(f"검출 {len(MUTS) - n_bad}/{len(MUTS)}")

    os.makedirs("explorer/runs", exist_ok=True)
    with open("explorer/runs/e4.md", "w", encoding="utf-8") as f:
        f.write("# E4 — HA fault class 주입 검출표\n\n")
        f.write("생성: `python -m ha.e4` (참조 lowering GT 388행은 게이트 "
                "EQUIV 388/388 확인 후 주입).\n\n")
        f.write("| fault class | 행 | 기대 | 판정 | |\n|---|---|---|---|---|\n")
        for name, key, want, tag, ok in lines:
            f.write(f"| {name} | {key} | {want} | {tag} | {ok} |\n")
        f.write(f"\n## profile 비용\n\n총 {total} 줄 (탐색기·비교기 본체 "
                f"무변경):\n\n")
        for fn_, n in loc:
            f.write(f"- `{fn_}` {n}\n")
    print("explorer/runs/e4.md 기록 완료")


if __name__ == "__main__":
    main()
