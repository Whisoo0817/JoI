# Evaluation handoff

상태: **E1 Stage A 완료(2026-09-12), E2–E4 미착수**.

- 실험의 방식·코드·데이터·결과는 이 폴더의 실험별 하위 폴더에 둔다. E1: [`E1_adequacy/`](E1_adequacy/README.md) (README = protocol·결정·버전 고정, `cases.py` = 출처·해석·기대 trace, `irs.py` = IR, `run_e1.py`/`make_results.py` = 실행·표, `results.md` = 결과, `runs/` = 원본·감사 전 보존본).
- E1 Stage A: 12건 완전 12/12, exact 41/41, whisoo B 감사 반영. C05·C07·C19 수정 전후 보존. B3·B4 미평가 → Stage B 8건 후보 또는 limitation. C20 unordered variant는 B3 limitation 후보.
- E1 원고 문단은 `PerCom_version.md`에 초안으로 넣었다. 수치·표는 `results.md` 기준이며 Stage B 결정 뒤 최종 문구 확정.
- E1 계약 사실(period 회차 후 대기, 초기 참 edge, latch 미반영, cron 소거, timeout 문법 부재, **미초기화 변수 = null**)은 3_Timeline_IR HANDOFF에도 반영해야 한다.
- **경계 probe(2026-09-12 추가).** Stage A 는 성공 사례뿐이라 경계를 말할 수 없었다. B3·B4 를 사전 지정 요구 3건으로 따로 시도했다(성공 분모와 분리, `probes.py` 해시 후 `probe_attempts.py` 작성).
  - P1·P2(B3 이벤트 기억): **표현 가능**, 4/4 정확 일치. `Clock.Timestamp` 스냅샷 + `$t != null`. 그러나 Explorer 는 둘 다 fail-closed 거절 → **언어는 되고 인증은 안 되는** 경계.
    B3 는 두 가지로 나눠 쓴다. (가) 자동화가 켜지기 전의 과거 = **불가**(실행 모델이 t=0 에 현재 값만 준다. Timeline 표현력이 아니라 관측 모델의 경계. HA 는 플랫폼 `last_changed` 로 답한다). (나) 도는 중에 놓친 과거 = 가능. P1·P2 는 (나) 에 한정된 판정이다.
  - P3(B4 가변 간격): **불가**. duration 이 컴파일 시점 리터럴(`Unsupported: duration format: '$d_min MIN'`), 설정값이 DOUBLE 이라 열거도 무한.
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
