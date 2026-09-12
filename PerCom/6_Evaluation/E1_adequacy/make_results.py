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
# B column — whisoo's semantic audit, 2026-09-12 (verbatim decisions, shortened)
AUDIT = {
    "C01": ("보존", "새 motion off→on 재트리거는 종료 대기를 취소하고 On 재호출, 마지막 no-motion 후 120 s Off. HA 는 인스턴스 재시작·IR 은 내부 반복이지만 action trace 동일"),
    "C03": ("보존", "≤1000→>1000 에 On, 정확히 15분 후 Off, 종료 뒤 다음 crossing 에 새 실행. 진행 중 재교차 무시는 원문 미정 부분의 명시적 [가정]으로 승인"),
    "C04": ("보존", "'At noon' = 매일 12:00. cron→On→15 min→Off 가 직접 보존. 실행기는 cron 소거 후 한 창만 재생(단서 유지)"),
    "C05": ("수정 후 보존", "2분 연속 열림에 첫 SMS, 열린 동안 정확히 60 s 마다, 닫히면 즉시 종료. inner period 100 MSEC 가 회차마다 100 ms 누적 → 0 MSEC 로 수정(E-ZERO-PERIOD)"),
    "C07": ("수정 후 보존", "22:00 이후 10분 열림→B0 snapshot→(blink 10·restore·5분 pause)×≤7 승인. 500+400+period 100 구조는 닫힘 뒤 복원이 최대 100 ms 늦음 → 500+500, inner period 0 MSEC 로 수정"),
    "C09": ("보존 [연구자 변환]", "원문은 안전 속성 → '귀가 absent→present 순간 Lock' 자동화로 구체화해 평가. 초기 absence 확인 후 각 신규 arrival 에 Lock. 원문 속성 자체를 검증했다고 쓰지 않음"),
    "C11": ("보존", "두 독립 TAP rule 을 직전 snapshot(E-PREV)으로 한 흐름에서 판별. 이 사례는 delay·중첩 인스턴스·되먹임이 없어 trace 가 두 rule 과 같음. 동시 변화 시 curtain close→vacuum idle 순서는 [가정]. 이 사례 한정, 일반화 아님"),
    "C15": ("보존", "밤 22:00–06:00, 입·퇴실 = presence 변화. 밤 입실에만 On, 06:00 이후 퇴실도 Off. 밤 시작 시 이미 재실이면 On 없음. IR·3 이력이 정확히 보존"),
    "C16": ("보존", "'if it is 10:00pm' = 매일 22:00 정각 한 번 검사. 그 순간 문 닫힘·조명 Off 일 때만 TV Off. Switch binding slot 분리 확인. cron 한 회차 단서 유지"),
    "C18": ("보존", "'3:00 pm' = 15:00–15:59 창, 진행 중 재누름 무시로 구체화([가정] 유지, 원 논문도 해석이 갈림). 새 버튼 사건에 즉시 Unlock, 정확히 10 s 뒤 Lock 보존"),
    "C19": ("수정 후 보존", "'분 단위 과허용' 설명은 오류(race 가 09:00 에 끝나므로 09:00:30 은 통과 안 함). 실제 결함은 시작 시 이미 present 를 arrival 로 오인 → wait(absent) 선행, 마지막 if 단순화, 이력 2개 추가"),
    "C20": ("보존 — ordered variant 만", "'AND AFTERWARDS … WITHIN 2 hours' 문장만 사례로 확정. 퇴장이 창을 끝내고 재입장이 새 창 → 재시작 의미와 같은 trace. paired unordered variant requires look-back event memory and is excluded from this ordered-variant case"),
}
ELEMENT_NOTE = {
    "B1": "C07 v3: 닫힘 시각에 B0 복원(감사 후 정확 일치). C01/C20: 재시작·취소를 timeout+break 조합으로 표현",
    "B2": "C11: 두 흐름을 만들지 않고 이전 회차 snapshot(read)으로 '무엇이 바뀌었나'를 판별. 두 TAP 규칙과 같은 행동인지는 감사 판단",
    "B3": "Stage A 에서 **미평가**. C20 의 paired unordered variant(2시간 look-back event memory 필요)는 별도 요구로 분리 — Stage B limitation candidate",
    "R9": "cron 앵커 3건(C04 C16 C19)은 실행기가 거절 → 앵커 소거 후 한 창만 실행. Clock 은 분 단위(C19 근사)",
    "R7": "C05 v1 은 정확 일치 0/4(period 가 회차 종료 후 대기라 100 ms 누적) → v2 inner period 0 MSEC 로 수정(감사)",
}
ELEMENT_KO = {"R1": "즉시 반응", "R2": "지연 후 호출", "R3": "지속 조건+reset", "R4": "사건 한 번/재무장", "R5": "저장값 흐름",
              "R6": "순차·분기", "R7": "조건까지 반복(주기)", "R8": "고정 횟수 반복", "R9": "시계 앵커·시간대", "R10": "시각 vs 사건 경쟁",
              "B1": "즉시 취소·재시작", "B2": "독립 두 흐름/인스턴스", "B3": "이벤트 기억·look-back", "B4": "가변 간격 반복", "B5": "중첩 반복"}


def main():
    rows = {r["id"]: r for r in json.load(open(HERE / "runs" / "e1_stageA.json"))}
    out = ["# E1 Stage A 결과 (기계 열 자동 채움; B·G 열은 whisoo)", "",
           "생성: `python make_results.py`. 근거: `runs/e1_stageA.json`, `cases.py`, `irs.py`. **논문 결과가 아니다.**", "",
           "## 사례별", "",
           "| ID | 요소 | 경계 | A-언어 | A-frontend | B 감사(whisoo) | C 실행 일치 (정확) | D 실행기 | E Explorer(참고) | F binding | G JoI | 최종 | 메모 |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
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
        b_verdict, b_reason = AUDIT.get(c["id"], ("", ""))
        cm = r.get("C_match", "0/1").split("/")
        final = "완전" if (IRS[c["id"]]["lang"] == "full" and b_verdict.startswith(("보존", "수정 후 보존")) and cm[0] == cm[1]) else "—"
        out.append(f"| {c['id']} | {' '.join(c['elements'])} | {'★' if c['boundary_intent'] else ''} | {IRS[c['id']]['lang']} | "
                   f"{r.get('A_frontend','-')[:40]} | **{b_verdict}** — {b_reason} | {r.get('C_match','-')} ({r.get('C_exact','-')}) | {r.get('D_runner','-')[:60]} | "
                   f"{e_txt} | selector/Service.Method 1 ✓ | 미확인(불가/부분 없음) | {final} | {memo} |")
    out += ["", "## 요소 × 사례 (경계 표)", "",
            "| 요소 | 뜻 | 사례 | C 통과/전체 | 비고 |", "|---|---|---|---|---|"]
    for el in ELEMENTS:
        ids = [c["id"] for c in CASES if el in c["elements"]]
        if not ids:
            out.append(f"| {el} | {ELEMENT_KO[el]} | (Stage A 없음) | - | Stage B 후보 필요 |")
            continue
        passed = sum(1 for i in ids if rows.get(i, {}).get("C_match", "0/1").split("/")[0] == rows.get(i, {}).get("C_match", "0/1").split("/")[1])
        out.append(f"| {el} | {ELEMENT_KO[el]} | {' '.join(ids)} | {passed}/{len(ids)} | {ELEMENT_NOTE.get(el, '')} |")
    n_final = sum(1 for c in CASES if AUDIT.get(c["id"], ("",))[0].startswith(("보존", "수정 후 보존")) and IRS[c["id"]]["lang"] == "full"
                  and rows.get(c["id"], {}).get("C_match", "0/1").split("/")[0] == rows.get(c["id"], {}).get("C_match", "0/1").split("/")[1])
    out += ["", f"최종 판정: 완전 {n_final}/{len(CASES)} (완전 = A full ∧ B 보존 ∧ C 모든 이력 일치). 선정한 {len(CASES)}건 중의 건수이며 coverage 비율이 아니다.",
            "", "Explorer 참고 열: IR×IR 자기 product, 120 s 예산. UNKNOWN 은 표현 실패가 아니라 탐색 미완(cap)이며 A 판정을 바꾸지 않는다.",
            "", "## 감사 후 수정 전후 (exact 열)", "",
            "| 사례 | 수정 | 전 (match/exact) | 후 (match/exact) |", "|---|---|---|---|"]
    before = {r["id"]: r for r in json.load(open(HERE / "runs" / "e1_stageA_before_audit.json"))}
    for cid, what in (("C05", "inner cycle period 100 MSEC → 0 MSEC"), ("C07", "half-blink 500+400 → 500+500, inner period 0 MSEC"),
                      ("C19", "wait(absent) 선행, branch 단순화, 이력 +2")):
        b, a = before.get(cid, {}), rows.get(cid, {})
        out.append(f"| {cid} | {what} | {b.get('C_match','-')} / {b.get('C_exact','-')} | {a.get('C_match','-')} / {a.get('C_exact','-')} |")
    out += ["", "## 실행 세부 (이력별)", ""]
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
