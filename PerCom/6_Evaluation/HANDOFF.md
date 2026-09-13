# Evaluation handoff

상태: **E1 Stage A 완료(2026-09-12), E2–E4 미착수**.

- 실험의 방식·코드·데이터·결과는 이 폴더의 실험별 하위 폴더에 둔다. E1: [`E1_adequacy/`](E1_adequacy/README.md) (README = protocol·결정·버전 고정, `cases.py` = 출처·해석·기대 trace, `irs.py` = IR, `run_e1.py`/`make_results.py` = 실행·표, `results.md` = 결과, `runs/` = 원본·감사 전 보존본).
- E1 Stage A: 12건 완전 12/12, exact 41/41, whisoo B 감사 반영. C05·C07·C19 수정 전후 보존. B3·B4 는 Stage A 사례에 없었고, 아래 경계 probe P1–P3 로 따로 시험했다(언어·실행기 통과, Explorer 만 거절). C20 unordered variant 는 probe P1.
- **E1 breadth corpus(2026-09-13 가져옴, pre-audit).** `E1_adequacy/breadth/` — 100건(층별 25), 선별 기록 150건, 새 depth 8건의 IR 없는 frozen case(해시 `FREEZE_MANIFEST.md`). 출처 감사 완료(`audit/PROVENANCE_AUDIT.md`): URL 36/36 접속, 원문 전부 확인, locator 60행·제목 26행 교정. **층 분포·screen_status·R/B label 은 논문 결과로 확정하지 않았다**(두 코더 코딩·판정 전). 다음: 코더 결정 → 새 depth 8건 인코딩(frozen case 무수정).
- E1 원고 문단은 `PerCom_version.md`에 초안으로 넣었다. 수치·표는 `results.md` 기준이며 Stage B 결정 뒤 최종 문구 확정.
- E1 계약 사실(period 회차 후 대기, 초기 참 edge, latch 미반영, cron 소거, timeout 문법 부재, **미초기화 변수 = null**)은 3_Timeline_IR HANDOFF에도 반영해야 한다.
- **경계 probe(2026-09-12 추가).** Stage A 는 성공 사례뿐이라 경계를 말할 수 없었다. B3·B4 를 사전 지정 요구 3건으로 따로 시도했다(성공 분모와 분리, `probes.py` 해시 후 `probe_attempts.py` 작성).
  - **세 후보 모두 언어 경계가 아니었다**(시험 전 예상과 반대). P1·P2(도는 중 이벤트 기억) 각 4/4 정확, P3(가변 간격) 3/3 정확.
    P3 는 duration 피연산자가 리터럴이라 `delay "$d MIN"` 은 거절되지만 `cycle(until "k >= $n", count "k"){ delay "1 단위" }` 로 펼치면 된다. 단위 = 해상도 = 상태 수.
    B3 는 두 가지로 나눠 쓴다. (가) 켜지기 전 과거 = **서비스/카탈로그 문제**(SensorHistory 류 서비스를 만들면 `read` 한 줄. "Timeline 이 못 한다" 고 쓰지 말 것). (나) 도는 중 과거 = 가능.
  - **실제 구속은 검증기다.** probe 3건 전부 Explorer 거절, 사유가 같은 종류(실행 중 값끼리 비교하는 joint-guard). E2·E4 의 핵심 입력.
  - **구조적으로 남는 언어 한계(논증, probe 미실시 — 표시 유지):** ① 유한 상태(겹치는 인스턴스·기억 사건 수가 입력에 따라 무한히 늘면 불가) ② 대입 없음(누적 집계 불가; GV 우회는 관측 ACTION 에 찍혀 검증 대상이 바뀜) ③ 단일 제어 흐름.
    셋 다 probe 로 확인하는 것이 Stage B 의 1순위다. 지금까지 예상한 경계가 두 번 연속 틀렸으므로 논증만으로 쓰지 않는다.
  - B2 진짜 중첩 인스턴스는 probe 없이 실행 계약(단일 제어 흐름) 근거로 한계 보고. C11 은 "두 흐름 지원" 이 아니라 단일 흐름 환원으로 표기.
- **A-extractor(= NL→IR LLM 프롬프트 `files/timeline_ir/extractor.md`) 문법 열 추가.** Stage A 12건 중 4건(C01 C05 C07 C20-O)이 `wait.timeout` 등 `files/timeline_ir/extractor.md` 밖 구성을 쓴다. 현재 NL→IR 경로로는 생성되지 않는 encoding 이다. 문법 확장은 E3 입력을 바꾸므로 **E3 시작 전에 별도 결정**해야 한다.
- C20 은 C20-O(ordered)로 개명했다. 짝을 이루는 unordered 문장은 probe P1 이며, 성공 분모에서 뺀 것이 아니라 별개 요구로 분리해 시도했다.
- Limitations 절에 넣을 것: 12/12 는 선정 사례 중의 건수(coverage 아님), B2 중첩 인스턴스 미평가, B5 중첩 반복은 C07 한 건, Explorer 미인증 경계.

- E1–E4 번호는 최신 계획대로 고정한다. 구 문서의 E1/E2 번호를 가져오지 않는다.
- 구 fixed-horizon 평가와 그에 종속된 pair 수·transition 감소율·latency 수치는 현재 PerCom 원고에서 제거했다. 이는 과거 audit 기록으로만 보존한다.
- 최종 E3/E4는 현재 H=None 검증 계약의 closure/completion 조건에 맞춰 새로 작성한다.
- Motivation pilot과 LLM-judge experiment는 Fig2/동기 근거로 별도 취급하고 E2/E3에 조용히 합치지 않는다.
- E1 외부 corpus, E2 독립 oracle, E3 동결 생성 평가, E4 scale/ablation을 실행한 후 Methods–Results 병렬 구조로 전면 개정한다.
- 모든 refusal/error/incomplete를 전체 분모에 남긴다.
- transition reduction을 runtime speedup으로 바꿔 쓰지 않는다.
