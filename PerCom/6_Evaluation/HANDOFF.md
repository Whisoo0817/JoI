# Evaluation handoff

상태: **E1 Stage A 완료(2026-09-12), E2–E4 미착수**.

- 실험의 방식·코드·데이터·결과는 이 폴더의 실험별 하위 폴더에 둔다. E1: [`E1_adequacy/`](E1_adequacy/README.md) (README = protocol·결정·버전 고정, `cases.py` = 출처·해석·기대 trace, `irs.py` = IR, `run_e1.py`/`make_results.py` = 실행·표, `results.md` = 결과, `runs/` = 원본·감사 전 보존본).
- E1 Stage A: 12건 완전 12/12, exact 41/41, whisoo B 감사 반영. C05·C07·C19 수정 전후 보존. B3·B4 미평가 → Stage B 8건 후보 또는 limitation. C20 unordered variant는 B3 limitation 후보.
- E1 원고 문단은 `PerCom_version.md`에 초안으로 넣었다. 수치·표는 `results.md` 기준이며 Stage B 결정 뒤 최종 문구 확정.
- E1 계약 사실(period 회차 후 대기, 초기 참 edge, latch 미반영, cron 소거, timeout 문법 부재)은 3_Timeline_IR HANDOFF에도 반영해야 한다.

- E1–E4 번호는 최신 계획대로 고정한다. 구 문서의 E1/E2 번호를 가져오지 않는다.
- 구 fixed-horizon 평가와 그에 종속된 pair 수·transition 감소율·latency 수치는 현재 PerCom 원고에서 제거했다. 이는 과거 audit 기록으로만 보존한다.
- 최종 E3/E4는 현재 H=None 검증 계약의 closure/completion 조건에 맞춰 새로 작성한다.
- Motivation pilot과 LLM-judge experiment는 Fig2/동기 근거로 별도 취급하고 E2/E3에 조용히 합치지 않는다.
- E1 외부 corpus, E2 독립 oracle, E3 동결 생성 평가, E4 scale/ablation을 실행한 후 Methods–Results 병렬 구조로 전면 개정한다.
- 모든 refusal/error/incomplete를 전체 분모에 남긴다.
- transition reduction을 runtime speedup으로 바꿔 쓰지 않는다.
