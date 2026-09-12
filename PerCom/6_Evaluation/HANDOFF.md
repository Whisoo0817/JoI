# Evaluation handoff

상태: **E1–E4 final protocols/results incomplete**.

- E1–E4 번호는 최신 계획대로 고정한다. 구 문서의 E1/E2 번호를 가져오지 않는다.
- 구 fixed-horizon 평가와 그에 종속된 pair 수·transition 감소율·latency 수치는 현재 PerCom 원고에서 제거했다. 이는 과거 audit 기록으로만 보존한다.
- 최종 E3/E4는 현재 H=None 검증 계약의 closure/completion 조건에 맞춰 새로 작성한다.
- Motivation pilot과 LLM-judge experiment는 Fig2/동기 근거로 별도 취급하고 E2/E3에 조용히 합치지 않는다.
- E1 외부 corpus, E2 독립 oracle, E3 동결 생성 평가, E4 scale/ablation을 실행한 후 Methods–Results 병렬 구조로 전면 개정한다.
- 모든 refusal/error/incomplete를 전체 분모에 남긴다.
- transition reduction을 runtime speedup으로 바꿔 쓰지 않는다.
