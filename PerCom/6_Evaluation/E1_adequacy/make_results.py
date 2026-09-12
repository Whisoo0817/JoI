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
from grammar_check import check_ir, reason  # noqa: E402

ELEMENTS = ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "B1", "B2", "B3", "B4", "B5"]
# B column — whisoo's semantic audit, 2026-09-12 (verbatim decisions, shortened)
AUDIT = {
    "C01": ("보존", "새 motion off→on 재트리거는 종료 대기를 취소하고 On 재호출, 마지막 no-motion 후 120 s Off. HA 는 인스턴스 재시작·IR 은 내부 반복이지만 action trace 동일"),
    "C03": ("보존", "≤1000→>1000 에 On, 정확히 15분 후 Off, 종료 뒤 다음 crossing 에 새 실행. 진행 중 재교차 무시는 원문 미정 부분의 명시적 [가정]으로 승인"),
    "C04": ("보존", "'At noon' = 매일 12:00. cron→On→15 min→Off 가 직접 보존. 실행기는 cron 소거 후 한 창만 재생(단서 유지)"),
    "C05": ("수정 후 보존", "2분 연속 열림에 첫 SMS, 열린 동안 정확히 60 s 마다, 닫히면 즉시 종료. inner period 100 MSEC 가 회차마다 100 ms 누적 → 0 MSEC 로 수정(E-ZERO-PERIOD)"),
    "C07": ("수정 후 보존", "22:00 이후 10분 열림→B0 snapshot→(blink 10·restore·5분 pause)×≤7 승인. 500+400+period 100 구조는 닫힘 뒤 복원이 최대 100 ms 늦음 → 500+500, inner period 0 MSEC 로 수정"),
    "C09": ("보존 [연구자 변환]", "원문은 안전 속성 → '귀가 absent→present 순간 Lock' 자동화로 구체화해 평가. 초기 absence 확인 후 각 신규 arrival 에 Lock. 원문 속성 자체를 검증했다고 쓰지 않음"),
    "C11": ("보존", "두 독립 TAP rule 을 직전 snapshot(E-PREV)으로 한 흐름에서 판별. 이 사례는 delay·중첩 인스턴스·되먹임이 없어 trace 가 두 rule 과 같다고 감사에서 확인. 이 사례 한정이며 snapshot 이 병렬 rule 을 일반적으로 대체한다는 주장이 아님"),
    "C15": ("보존", "밤 22:00–06:00, 입·퇴실 = presence 변화. 밤 입실에만 On, 06:00 이후 퇴실도 Off. 밤 시작 시 이미 재실이면 On 없음. IR·3 이력이 정확히 보존"),
    "C16": ("보존", "'if it is 10:00pm' = 매일 22:00 정각 한 번 검사. 그 순간 문 닫힘·조명 Off 일 때만 TV Off. Switch binding slot 분리 확인. cron 한 회차 단서 유지"),
    "C18": ("보존", "'3:00 pm' = 15:00–15:59 창, 진행 중 재누름 무시로 구체화([가정] 유지, 원 논문도 해석이 갈림). 새 버튼 사건에 즉시 Unlock, 정확히 10 s 뒤 Lock 보존"),
    "C19": ("수정 후 보존", "'분 단위 과허용' 설명은 오류(race 가 09:00 에 끝나므로 09:00:30 은 통과 안 함). 실제 결함은 시작 시 이미 present 를 arrival 로 오인 → wait(absent) 선행, 마지막 if 단순화, 이력 2개 추가"),
    "C20-O": ("보존 — ordered variant 만", "'AND AFTERWARDS … WITHIN 2 hours' 문장만 사례로 확정. 퇴장이 창을 끝내고 재입장이 새 창 → 재시작 의미와 같은 trace. paired unordered variant requires look-back event memory and is excluded from this ordered-variant case"),
}
ELEMENT_NOTE = {
    "B1": "C07 v3: 닫힘 시각에 B0 복원(감사 후 정확 일치). C01/C20-O: 재시작·취소를 timeout+break 조합으로 표현",
    "B2": ("C11 한 건뿐이고, 두 흐름을 만든 것이 아니라 **단일 흐름으로 환원**한 것이다. 이 사례에는 delay·중첩 인스턴스·"
           "action→trigger 되먹임이 없어 직전 snapshot 판별이 두 TAP 규칙과 같은 trace 를 낸다(감사 확인). 진짜 중첩 "
           "인스턴스가 필요한 요구는 Stage A·probe 모두에서 **미평가**이며, 실행 계약상 단일 제어 흐름이라는 한계로 보고한다"),
    "B3": ("두 가지를 나눠야 한다. **(가) 자동화가 켜지기 전의 과거**는 불가 — 실행 모델이 t=0 에 현재 값만 주므로 이력으로 쓸 수조차 없다"
           "(Timeline 표현력이 아니라 관측 모델의 경계. HA 는 플랫폼의 `last_changed` 로 답한다). **(나) 도는 중에 놓친 과거**는 가능 — "
           "probe P1·P2 가 각각 4/4 정확 일치. 단 Explorer 는 둘 다 거절한다(아래 probe 절)"),
    "B4": "Stage A 에는 사례가 없었고 **probe P3 로 시도**했다. duration 이 컴파일 시점 리터럴이라 표현되지 않는다(아래 probe 절)",
    "R9": "cron 앵커 3건(C04 C16 C19)은 실행기가 거절 → 앵커 소거 후 한 창만 실행. Clock.Hour/Minute 은 분 단위, Clock.Timestamp 는 초 단위",
    "R7": "C05 v1 은 정확 일치 0/4(period 가 회차 종료 후 대기라 100 ms 누적) → 감사에서 inner period 0 MSEC 로 수정, 현재 4/4",
}
ELEMENT_KO = {"R1": "즉시 반응", "R2": "지연 후 호출", "R3": "지속 조건+reset", "R4": "사건 한 번/재무장", "R5": "저장값 흐름",
              "R6": "순차·분기", "R7": "조건까지 반복(주기)", "R8": "고정 횟수 반복", "R9": "시계 앵커·시간대", "R10": "시각 vs 사건 경쟁",
              "B1": "즉시 취소·재시작", "B2": "독립 두 흐름/인스턴스", "B3": "이벤트 기억·look-back", "B4": "가변 간격 반복", "B5": "중첩 반복"}


def probe_section():
    """Boundary probes. Separate denominator: they are pre-identified boundary requirements, not corpus cases."""
    pj = HERE / "runs" / "e1_probes.json"
    if not pj.exists():
        return ["", "## 경계 probe", "", "(`python run_probes.py` 미실행)"]
    from probes import PROBES
    from probe_attempts import ATTEMPTS
    rows = {r["id"]: r for r in json.loads(pj.read_text())}
    out = ["", "## 경계 probe (성공 분모와 분리)", "",
           "Stage A 가 건드리지 못한 경계 B3·B4 를 **따로 지정한 요구**로 시도한 결과다. 요구와 기대 trace 는 인코딩 시도 전에 "
           "`probes.py` 에 고정하고 해시했다(README §6). 이 표는 12건 성공 분모에 들어가지 않으며, probe 가 '완전' 로 끝나는 것도 "
           "정상적인 결과다 — 경계 후보가 사실은 표현 가능했다는 뜻이다.", "",
           "| ID | 경계 | 출처 요구 | A-언어 | A-extractor 문법 | C 실행 일치 (정확) | D 실행기 | E Explorer | 판정 |",
           "|---|---|---|---|---|---|---|---|---|"]
    for pr in PROBES:
        r, a = rows.get(pr["id"], {}), ATTEMPTS[pr["id"]]
        gaps = check_ir(a["ir"])
        e = r.get("E_explorer", {})
        e_txt = e.get("verdict", "-") + (": " + e["reason"][:70] if e.get("reason") else "")
        out.append(f"| {pr['id']} | {pr['probe_of']} | {pr['verbatim'][:80]}… | {a['lang']} | "
                   f"{'안' if not gaps else '**밖**: ' + ', '.join(gaps)} | {r.get('C_match','-')} ({r.get('C_exact','-')}) | "
                   f"{r.get('D_runner','-')[:40]} | {e_txt} | **{a.get('verdict_claim','-')}** |")
    out += ["", "### probe 세부", ""]
    for pr in PROBES:
        r, a = rows.get(pr["id"], {}), ATTEMPTS[pr["id"]]
        out += [f"**{pr['id']} ({pr['probe_of']}) — {pr['source']}**", "",
                f"원문: {pr['verbatim']}", "", f"왜 probe 인가: {pr['why_probe']}", "",
                f"해석: {pr['spec']}", "", "가정: " + " / ".join(pr["assumptions"]), "",
                f"시도한 encoding: {a['note']}", "", f"시도 이력: {a['history']}", ""]
        if a.get("scope_limit"):
            out += [f"**판정 범위 제한: {a['scope_limit']}**", ""]
        if a.get("missing"):
            out += [f"**빠진 실행 기능: {a['missing']}**", ""]
        if r.get("attempt_a_runner"):
            out += [f"요구대로 쓴 attempt A 에 대한 실행기 응답: `{r['attempt_a_runner']}`", ""]
        if a.get("explorer"):
            out += [f"Explorer: {a['explorer']}", ""]
        gaps = check_ir(a["ir"])
        if gaps:
            out += ["extractor 문법 밖 구성: " + "; ".join(f"`{g}` ({reason(g)})" for g in gaps), ""]
        out += ["| 이력 | 종류 | 일치 | 정확 | 기대 n | 실제 n | 첫 차이 |", "|---|---|---|---|---|---|---|"]
        for h in r.get("C_histories", []):
            fd = h.get("first_diff") or h.get("error") or ""
            out.append(f"| {h['name']} | {h.get('kind','')} | {'✓' if h.get('match') else '✗'} | "
                       f"{'✓' if h.get('exact') else '✗'} | {h.get('n_expected','-')} | {h.get('n_actual','-')} | {str(fd)[:120]} |")
        out.append("")
    return out


def main():
    rows = {r["id"]: r for r in json.load(open(HERE / "runs" / "e1_stageA.json"))}
    out = ["# E1 Stage A 결과 (기계 열 자동 채움; B·G 열은 whisoo)", "",
           "생성: `python make_results.py`. 근거: `runs/e1_stageA.json`, `cases.py`, `irs.py`. **논문 결과가 아니다.**", "",
           "## 사례별", "",
           "| ID | 요소 | 경계 | A-언어 | A-frontend | A-extractor 문법 | B 감사(whisoo) | C 실행 일치 (정확) | D 실행기 | E Explorer(참고) | F binding | G JoI | 최종 | 메모 |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
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
        gaps = check_ir(IRS[c["id"]]["ir"])
        gap_txt = "안" if not gaps else "**밖**: " + ", ".join(gaps)
        out.append(f"| {c['id']} | {' '.join(c['elements'])} | {'★' if c['boundary_intent'] else ''} | {IRS[c['id']]['lang']} | "
                   f"{r.get('A_frontend','-')[:40]} | {gap_txt} | **{b_verdict}** — {b_reason} | {r.get('C_match','-')} ({r.get('C_exact','-')}) | {r.get('D_runner','-')[:60]} | "
                   f"{e_txt} | selector/Service.Method 1 ✓ | 미확인(불가/부분 없음) | {final} | {memo} |")
    out += ["", "## 요소 × 사례 (경계 표)", "",
            "| 요소 | 뜻 | 사례 | C 통과/전체 | 비고 |", "|---|---|---|---|---|"]
    for el in ELEMENTS:
        ids = [c["id"] for c in CASES if el in c["elements"]]
        if not ids:
            out.append(f"| {el} | {ELEMENT_KO[el]} | (Stage A 없음) | - | {ELEMENT_NOTE.get(el, 'Stage B 후보 필요')} |")
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
    out += probe_section()
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
