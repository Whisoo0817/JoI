# -*- coding: utf-8 -*-
"""기존 dataset.csv(377) 를 벤치마크 분류축으로 자동 재라벨 + 카탈로그 재감사.

자동으로 뽑히는 축만 여기서 붙인다:
  D  로직·시간   ← ir_gt 의 op/슬롯 구조에서 결정론적으로
  B1 서비스 종류 ← 카탈로그의 type/argument_type
  B3 서비스 개수 ← ir_gt 가 부르는 서로 다른 서비스 수
  A2 수량       ← 명령문의 수량어 + 후보 기기 수
나머지(A1 이름 방식, B2 명시성, C 말투, E 정답 종류)는 사람/LLM 라벨 몫.

  python bench/relabel.py            # bench/labels_377.csv + 빈 칸 지도 출력
"""
import collections, csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
CAT = json.load(open(os.path.join(ROOT, "files", "service_list_ver3.0.0.json"),
                    encoding="utf-8"))
# 메서드는 반드시 대문자로 시작 — "Golden.mp3" 같은 인자 문자열을 서비스로 오인하지 않게
SVC_RE = re.compile(r"\b([A-Z][A-Za-z0-9]*)\.([A-Z][A-Za-z0-9]*)\b")

D_NAME = {
    "D1": "지금 한 번", "D2": "순서+지연", "D3": "조건 지금", "D4": "트리거 기다림",
    "D5": "지속 조건", "D6": "정해진 시각", "D7": "주기 반복", "D8": "기간·횟수 제한 반복",
    "D9": "트리거 후 반복", "D10": "제한시간 대기", "D11": "두 번 읽고 비교",
    "D12": "누적·상태 보존", "D13": "복합 중첩", "D0": "시간·로직 없음",
}


def _unquoted(src):
    """문자열 리터럴 제거 — Speaker.Play("Golden.mp3") 의 인자를 서비스로 오인하지 않게."""
    return re.sub(r'\\"(?:[^"\\\\]|\\\\.)*\\"', '""', src)


def features(ir):
    """IR → 구조 특징 집합 (D 축 판정의 재료)."""
    s = json.dumps(ir)
    ops = collections.Counter(re.findall(r'"op": "([a-z_]+)"', s))
    f = set()
    if re.search(r'"cron": "[^"]+"', s): f.add("cron")
    if ops.get("cycle"): f.add("cycle")
    if ops.get("wait"): f.add("wait")
    if ops.get("delay"): f.add("delay")
    if ops.get("if"): f.add("if")
    if ops.get("read"): f.add("read")
    if ops.get("read", 0) >= 2: f.add("read2")
    if ops.get("break"): f.add("break")
    if '"edge": "rising"' in s: f.add("edge")
    if '"for":' in s: f.add("for")
    if '"timeout":' in s: f.add("timeout")
    if re.search(r'"until": "n >=', s): f.add("until_n")
    if re.search(r'"until": "clock', s): f.add("until_clock")
    if re.search(r'"until": "Clock', s): f.add("until_clock")
    if '"count":' in s: f.add("count")
    if '"var":' in s: f.add("var")
    if re.search(r'GlobalVariable', s): f.add("gvar")
    # 자기 참조 인자("min($Light.CurrentBrightness + 10, 100)") = 상태를 이어받는 누적
    if re.search(r'\$[A-Z][A-Za-z0-9]*\.', s): f.add("selfref")
    return f, ops


# 특징 → D 코드. 위에서부터 처음 맞는 것이 주 코드.
D_RULES = [
    ("D10", lambda f: "timeout" in f),
    ("D11", lambda f: "read2" in f),
    ("D12", lambda f: "gvar" in f or "selfref" in f),
    ("D9",  lambda f: "wait" in f and "cycle" in f),
    ("D8",  lambda f: "cycle" in f and ("until_n" in f or "until_clock" in f)),
    ("D5",  lambda f: "for" in f),
    ("D6",  lambda f: "cron" in f),
    ("D7",  lambda f: "cycle" in f),
    ("D4",  lambda f: "wait" in f),
    ("D2",  lambda f: "delay" in f and "if" not in f),
    ("D3",  lambda f: "if" in f),
    ("D1",  lambda f: True),
]
MAJOR = {"cron", "cycle", "wait", "for", "timeout", "read2", "gvar", "delay"}


# 자기 코드 안에 두 특징이 붙어 다니는 것은 복합으로 세지 않는다
#   for  ← 언제나 wait 위에 얹힌다 (지속 조건)
#   D9/D8/D11/D10/D12 ← 정의 자체가 두 특징의 조합
SELF_PAIRED = {"D9", "D8", "D11", "D10", "D12"}


def d_code(f):
    majors = set(f & MAJOR)
    if "for" in majors:
        majors.discard("wait")
    for code, test in D_RULES:
        if test(f):
            composite = len(majors) >= 2 and code not in SELF_PAIRED
            return ("D13" if composite else code), code
    return "D0", "D0"


def b1_of(cat, meth):
    """서비스 종류: read / act / set."""
    v = CAT.get(cat, {}).get(meth)
    if v is None:
        return "unknown"
    if v.get("type") == "value":
        return "read"
    return "set" if v.get("argument_type") else "act"


Q_ALL = re.compile(r"\ball\b|\bevery\b|\bboth\b|\beach\b", re.I)
Q_ANY = re.compile(r"\bany\b|\beither\b|at least one|\bone of\b", re.I)
Q_ONE = re.compile(r"only one|just one|\bone of them\b", re.I)


def a2_of(text, n_dev):
    if Q_ONE.search(text): return "one"
    if Q_ALL.search(text): return "all"
    if Q_ANY.search(text): return "any"
    return "single" if n_dev <= 1 else "unmarked"


def main():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "dataset.csv"), encoding="utf-8")))
    out, missing_svc, dead = [], collections.Counter(), []
    for i, r in enumerate(rows):
        try:
            ir = json.loads(r["ir_gt"])
        except Exception:
            dead.append(i); continue
        f, ops = features(ir)
        d, d_base = d_code(f)
        svcs = sorted(set(SVC_RE.findall(_unquoted(json.dumps(ir)))))
        for c, m in svcs:
            if c not in CAT or m not in CAT.get(c, {}):
                missing_svc[f"{c}.{m}"] += 1
        b1 = sorted({b1_of(c, m) for c, m in svcs})
        try:
            cd = json.loads(r["connected_devices"])
        except Exception:
            cd = {}
        out.append({
            "src": "dataset.csv", "index": r["index"], "old_cat": r["category_v2"],
            "command_eng": r["command_eng"], "D": d, "D_base": d_base,
            "D_name": D_NAME[d], "features": "|".join(sorted(f)),
            "B1": "|".join(b1), "B3": len(svcs),
            "A2": a2_of(r["command_eng"], len(cd)),
            "services": " ".join(f"{c}.{m}" for c, m in svcs),
            "n_connected": len(cd),
        })

    dst = os.path.join(HERE, "labels_377.csv")
    with open(dst, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)

    print(f"라벨 {len(out)}행 → bench/labels_377.csv  (IR 파싱 실패 {len(dead)})\n")

    print("── 카탈로그 3.0.0 재감사 ──")
    if missing_svc:
        print(f"  3.0.0 에 없는 서비스 참조 {len(missing_svc)}종:")
        for k, v in missing_svc.most_common(): print(f"    {v:3d}회  {k}")
    else:
        print("  377개가 쓰는 서비스 전부 3.0.0 에 살아 있음 ✅")

    print("\n── D 축 분포 (현재 377) ──")
    dc = collections.Counter(o["D"] for o in out)
    for k in sorted(D_NAME, key=lambda x: (len(x), x)):
        print(f"  {k:4} {D_NAME[k]:16} {dc.get(k, 0):4d}")

    print("\n── 옛 코드 → 새 D 대조 (섞이면 규칙 손봐야 함) ──")
    cross = collections.defaultdict(collections.Counter)
    for o in out: cross[o["old_cat"]][o["D"]] += 1
    for old in sorted(cross):
        tot = sum(cross[old].values())
        top, n = cross[old].most_common(1)[0]
        mark = "" if n == tot else "  ← 갈림: " + str(dict(cross[old]))
        print(f"  {old} (n={tot:3d}) → {top}{mark}")

    print("\n── B1 / B3 / A2 ──")
    print("  B1:", dict(collections.Counter(o["B1"] for o in out).most_common()))
    print("  B3:", dict(sorted(collections.Counter(o["B3"] for o in out).items())))
    print("  A2:", dict(collections.Counter(o["A2"] for o in out).most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
