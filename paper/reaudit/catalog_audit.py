"""382행 카탈로그 감사 — dataset.csv의 IR·기기·바인딩을 v2.0.7과 대조.

검사 항목:
  1) call 표적 서비스·함수·인자 이름이 카탈로그에 있는가
  2) 조건·read·args의 읽기 키(Service.Attr)가 값(value)으로 있는가
     (함수를 값처럼 읽으면 별도 분류)
  3) 기기 카테고리가 카탈로그 스킬인가
  4) binding_gt: 기기 id 존재 + IR의 모든 서비스 자리 커버
  5) 행 내 태그 표기 요동(같은 위치의 두 표기 혼용)

Run:  joi 디렉토리에서  python3 paper/reaudit/catalog_audit.py
"""
import collections
import csv
import json
import re

CATALOG = "files/service_list_ver2.0.7.json"
REF = re.compile(r"\b([A-Z][A-Za-z0-9]+)\.([A-Za-z_][A-Za-z0-9_]*)")


def load_catalog():
    d = json.load(open(CATALOG))
    idx = {}
    for s in d["skills"]:
        idx[s["id"]] = {
            "values": {v["id"] for v in s.get("values", [])},
            "functions": {f["id"]: [a["id"] for a in f.get("arguments", [])]
                          for f in s.get("functions", [])},
        }
    return idx


def main():
    idx = load_catalog()
    rows = list(csv.DictReader(open("dataset.csv")))
    bad = collections.Counter()
    ex = collections.defaultdict(list)

    def note(kind, key, detail):
        bad[kind] += 1
        if len(ex[kind]) < 10:
            ex[kind].append(f"{key}: {detail}")

    def check_ref(svc, attr, key, where):
        if svc in ("clock", "Clock"):
            return
        if svc not in idx:
            return  # 파일명(x.mp3) 같은 오탐은 서비스가 아니면 무시
        if attr not in idx[svc]["values"]:
            kind = ("함수를 값처럼 읽음" if attr in idx[svc]["functions"]
                    else "값(attr) 없음")
            note(kind, key, f"{where}: {svc}.{attr}")

    def walk(steps, key):
        for s in steps:
            if not isinstance(s, dict):
                continue
            op = s.get("op")
            if op == "call":
                tgt = s.get("target", "")
                svc, _, m = tgt.partition(".")
                if svc not in idx:
                    note("서비스 없음", key, f"call: {tgt}")
                elif m not in idx[svc]["functions"]:
                    note("함수 없음", key, f"call: {tgt}")
                else:
                    for a in (s.get("args") or {}):
                        if a not in set(idx[svc]["functions"][m]):
                            note("인자 이름 없음", key, f"{tgt} arg {a}")
                for a, v in (s.get("args") or {}).items():
                    if isinstance(v, str):
                        for sv, at in REF.findall(v):
                            check_ref(sv, at, key, f"arg {a}")
            elif op in ("wait", "if"):
                c = re.sub(r'"[^"]*"|\'[^\']*\'', "", s.get("cond", "") or "")
                for sv, at in REF.findall(c):
                    check_ref(sv, at, key, f"{op} cond")
            elif op == "read":
                sv, _, at = s.get("src", "").partition(".")
                check_ref(sv, at, key, "read")
            if s.get("until"):
                c = re.sub(r'"[^"]*"|\'[^\']*\'', "", s["until"])
                for sv, at in REF.findall(c):
                    check_ref(sv, at, key, "until")
            for v in s.values():
                if isinstance(v, list):
                    walk(v, key)

    for r in rows:
        key = f'{r["category_v2"]}_{int(float(r["index"])):03d}'
        try:
            ir = json.loads(r["ir_gt"])
        except Exception as e:
            note("IR 파싱 실패", key, str(e)[:40])
            continue
        walk(ir.get("timeline") or [], key)
        devs = json.loads(r["connected_devices"]) if r["connected_devices"] else {}
        for did, d in devs.items():
            for c in d.get("category", []):
                if c not in idx:
                    note("기기 카테고리 없음", key, f"{did}: {c}")
        # 바인딩 검사
        b = json.loads(r.get("binding_gt") or "{}")
        svcs = {m for m, _ in REF.findall(r["ir_gt"])
                if m in idx and m != "Clock"}
        bound = {k.split("#")[0] for k in b}
        for name, ds in b.items():
            if isinstance(ds, dict):     # 다기기 읽기 자리: {"any"/"all": [...]}
                if len(ds) != 1 or next(iter(ds)) not in ("any", "all"):
                    note("바인딩 한정자 표기 이상", key, f"{name}: {ds}")
                    continue
                ds = next(iter(ds.values()))
                if len(ds) < 2:
                    note("한정자인데 1대", key, f"{name}: {ds}")
            if not ds or any(x not in devs for x in ds):
                note("바인딩 기기 없음", key, f"{name}: {ds}")
        if svcs - bound:
            note("바인딩 커버 안 됨", key, str(svcs - bound))

    print(f"행 {len(rows)} | 문제:", dict(bad) or "0 — 전부 통과")
    for k, xs in ex.items():
        print(f"\n== {k} ({bad[k]}건)")
        for x in xs:
            print("  ", x)


if __name__ == "__main__":
    main()
