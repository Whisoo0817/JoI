"""Build results.md from runs/e1_stageA.json + cases.py + irs.py.

Columns B (semantic audit) and G (JoI feasibility) are left for whisoo; the script only pre-fills what the
machine knows (A, C, D, E) and the author's pre-execution claim.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cases import CASES  # noqa: E402
from irs import IRS  # noqa: E402

ELEMENTS = ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "B1", "B2", "B3", "B4", "B5"]
ELEMENT_NOTE = {
    "B1": "C07: 취소가 100 ms 격자에서 감지(정확 일치 1건 실패, 1초 허용 안). C01/C20: 재시작·취소를 timeout+break 조합으로 표현",
    "B2": "C11: 두 흐름을 만들지 않고 이전 회차 snapshot(read)으로 '무엇이 바뀌었나'를 판별. 두 TAP 규칙과 같은 행동인지는 감사 판단",
    "B3": "C20 은 순서 있는 변형만 통과. 순서 없는(look-back) 변형은 **작성하지 않음** — B3 자체는 Stage A 에서 미평가",
    "R9": "cron 앵커 3건(C04 C16 C19)은 실행기가 거절 → 앵커 소거 후 한 창만 실행. Clock 은 분 단위(C19 근사)",
    "R7": "C05: 정확 일치 0/4 — period 가 회차 종료 후 대기라 회차마다 100 ms 누적(1초 허용 안)",
}
ELEMENT_KO = {"R1": "즉시 반응", "R2": "지연 후 호출", "R3": "지속 조건+reset", "R4": "사건 한 번/재무장", "R5": "저장값 흐름",
              "R6": "순차·분기", "R7": "조건까지 반복(주기)", "R8": "고정 횟수 반복", "R9": "시계 앵커·시간대", "R10": "시각 vs 사건 경쟁",
              "B1": "즉시 취소·재시작", "B2": "독립 두 흐름/인스턴스", "B3": "이벤트 기억·look-back", "B4": "가변 간격 반복", "B5": "중첩 반복"}


def main():
    rows = {r["id"]: r for r in json.load(open(HERE / "runs" / "e1_stageA.json"))}
    out = ["# E1 Stage A 결과 (기계 열 자동 채움; B·G 열은 whisoo)", "",
           "생성: `python make_results.py`. 근거: `runs/e1_stageA.json`, `cases.py`, `irs.py`. **논문 결과가 아니다.**", "",
           "## 사례별", "",
           "| ID | 요소 | 경계 | A-언어(작성자 주장) | A-frontend | B 감사 | C 실행 일치 (정확) | D 실행기 | E Explorer(참고) | F binding | G JoI | 메모 |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in CASES:
        r = rows.get(c["id"], {})
        e = r.get("E_explorer", {})
        e_txt = e.get("verdict", "-")
        if e.get("claim"):
            e_txt += f" ({e['claim']})"
        if e.get("reason"):
            e_txt += ": " + e["reason"][:80]
        fails = [h["name"] for h in r.get("C_histories", []) if not h.get("match")]
        memo = IRS[c["id"]].get("history", "")
        memo = (memo[:1] and "encoding 수정 이력 있음(irs.py)") or ""
        if fails:
            memo += (" " if memo else "") + "불일치: " + ", ".join(fails)
        out.append(f"| {c['id']} | {' '.join(c['elements'])} | {'★' if c['boundary_intent'] else ''} | {IRS[c['id']]['lang']} | "
                   f"{r.get('A_frontend','-')[:40]} |  | {r.get('C_match','-')} ({r.get('C_exact','-')}) | {r.get('D_runner','-')[:60]} | "
                   f"{e_txt} | selector/Service.Method 1 ✓ |  | {memo} |")
    out += ["", "## 요소 × 사례 (경계 표)", "",
            "| 요소 | 뜻 | 사례 | C 통과/전체 | 비고 |", "|---|---|---|---|---|"]
    for el in ELEMENTS:
        ids = [c["id"] for c in CASES if el in c["elements"]]
        if not ids:
            out.append(f"| {el} | {ELEMENT_KO[el]} | (Stage A 없음) | - | Stage B 후보 필요 |")
            continue
        passed = sum(1 for i in ids if rows.get(i, {}).get("C_match", "0/1").split("/")[0] == rows.get(i, {}).get("C_match", "0/1").split("/")[1])
        out.append(f"| {el} | {ELEMENT_KO[el]} | {' '.join(ids)} | {passed}/{len(ids)} | {ELEMENT_NOTE.get(el, '')} |")
    out += ["", "Explorer 참고 열: EQUIV-FIXPOINT 8건, UNKNOWN 4건(C07·C20 transition cap, C15·C18 state cap — 120 s 예산 안, "
            "IR×IR 자기 product). UNKNOWN 은 표현 실패가 아니라 탐색 미완이며 A 판정을 바꾸지 않는다.", "", "## 실행 세부 (이력별)", ""]
    for c in CASES:
        r = rows.get(c["id"], {})
        out.append(f"### {c['id']} — {c['source']}")
        out.append("")
        out.append(f"원문: {c['verbatim']}")
        out.append("")
        out.append("가정: " + " / ".join(c["assumptions"]))
        out.append("")
        out.append("encoding: " + IRS[c["id"]]["note"])
        if IRS[c["id"]].get("history"):
            out.append("")
            out.append("수정 이력: " + IRS[c["id"]]["history"])
        out.append("")
        out.append("| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |")
        out.append("|---|---|---|---|---|---|---|")
        for h in r.get("C_histories", []):
            fd = h.get("first_diff") or h.get("error") or ""
            out.append(f"| {h['name']} | {h.get('kind','')} | {'✓' if h.get('match') else '✗'} | {'✓' if h.get('exact') else '✗'} | "
                       f"{h.get('n_expected','-')} | {h.get('n_actual','-')} | {str(fd)[:120]} |")
        out.append("")
    (HERE / "results.md").write_text("\n".join(out))
    print(f"-> {HERE / 'results.md'}")


if __name__ == "__main__":
    main()
