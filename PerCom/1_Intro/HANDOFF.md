# Introduction handoff

상태: **full first draft**.

- Figure 1은 edge-trigger 세 구현 예를 유지하되 [Figure 요구사항](Figures/FIGURE_REQUIREMENTS.md)에 따라 수정한다.
- 현재 본문 대표 사례는 sustained vacancy이며 Fig1의 edge 사례와 중복되지 않게 연결한다.
- LLM-judge **Table 1 결과는 확정됐다(09-16)**. Figure 2 는 원고에서 뺐다. 3–4문장으로 motivation 에 추가하되, 아래 "원고에 쓸 때 지킬 것" 을 따른다. 본문 문장은 아직 넣지 않았다.
- Figure 1 과 Table 1 은 Introduction 에 둔다. Table 1 의 전체 protocol, 통계와 robustness 결과는 Evaluation 또는 Appendix 에서 연결한다.
- 선행연구 부재 주장과 `first` 주장은 금지한다. Related Work의 primary-source 카드와 맞춘다.
- contributions는 C1–C3 작업문이다. E1–E4 결과에 따라 범위를 다시 동결한다.
- SenSys의 edge/on-device/repair 중심 framing을 그대로 재사용하지 않는다.
- 첫 범위 정의는 `reactive-temporal automation implemented as imperative code`, 이후는 `reactive-temporal code`로 통일한다.
- imperative/declarative를 expressive/primitive 축으로 나누지 않으며, 스마트홈 자동화 전체 generality를 주장하지 않는다.

## Table 1 동기 실험 — `motivation_judge/` (2026-09-16 완료)

> 09-16 `6_Evaluation/motivation_judge/` 에서 이리로 옮겼다(whisoo). E1–E4 가 아니라 Introduction 의 Table 1 을
> 받치는 실험이기 때문이다. 스크립트는 저장소 루트를 `../../..` 로 찾으므로 깊이가 같아 그대로 돈다.
> 표의 열 이름은 `Rewrite`, 대조군 행은 `None` 이다(09-16 whisoo).

- E1–E4 **밖의 동기 실험**이다. Introduction 자리이며, "왜 LLM judge 를 배포 게이트로 쓰지 않는가" 를
  받친다. 프로토콜 `motivation_judge/PROTOCOL_2026-09-16.md`, 결과 `RESULTS_2026-09-16.md`.
- **Fig2 는 원고에서 뺀다(09-16 whisoo 결정). Table1 하나로 간다.** 그림 자료(`results/superseded/fig2.png|pdf`)와
  `aggregate.py` 의 축약어 라벨은 **옛 상태 그대로 남겨둔다** — 손대지 않는다. 표만 `render_table.py` 가
  만든다(`results/table1.tex` + 미리보기 png). 그림이 지고 있던 "이름만 바꾸면 안 흔들리는데 반복문을
  펼치면 무너진다" 는 형태 대비는 **본문 문장으로 옮겨야 한다.**
- **옛 SenSys 수치(9B 27.0% / GPT-5.1 10.6%, 유형별 최대 81%)는 폐기.** identity 대조가 없었고, 씨앗이
  확정 명세를 만족한다는 근거가 없었으며, 동등성을 시뮬레이터 trace 한 줄로 판정했고, 불확실성 추정이
  없었다. 그 데이터셋(`equiv_stress_v2.json`)과 생성기는 남아 있지 않다(생성기는 `aa866bd^:paper/build_equiv_stress.py`
  에서 복구 가능, v2 는 커밋된 적 없음). 재현이 아니라 새 실험이다.
- 씨앗은 **E3 최종의 EQUIV-FIXPOINT 309건**. 변환 8유형(표기 4·논리 1·시간 구조 3)으로 357쌍을 만들고,
  **E3 와 같은 동결 평가기**로 전부 EQUIV-FIXPOINT 임을 확인한 것만 채택했다(357/357). 옛 드모르간·이중부정·
  덧셈 순서는 일반 코드 judge 편향이라 뺐다.

### 실험 3단계 (09-16 whisoo 확정)

1. **원본 217개를 똑같이 3번씩** 묻는다. 판이 자기와 얼마나 어긋나는지 잰다. **조건이 하나도 안 붙은
   값**이다.
2. **세 판이 모두 3번 중 2번 이상 "맞다"고 한 원본만** 남긴다 → **52개 / 재작성 168쌍**.
3. 그 168쌍에 대해 각 판에게 재작성을 묻는다.

2단계 덕분에 **분모가 세 판 공통**이다. 표에 n 을 행마다 한 번만 적고 칸은 % 만 남긴다. 세 판이 함께
안정적으로 통과시킨 프로그램이라 **"자연어가 애매해서 거부했다"는 해석도 막힌다.**

**표에 싣는 값은 뒤집힘 비율(`Verdict reversal (%)`)이다.** 재작성은 "동작이 같으면 판정도 같아야 한다"는
관계이고 이 값은 그 관계가 깨진 비율이라, 위반율로 적는 것이 맞다(09-16 whisoo, 100−값 안은 기각).
방향 표기(`lower is better`)는 붙이지 않는다 — "reversal" 이 이미 실패를 뜻한다.

| Condition | n | Qwen3.5-9B | GPT-5.4-mini | Claude-Sonnet-5 |
|---|---|---|---|---|
| None (동일 재질의, 3콜이 갈린 원본) | 217 | **0.0** | 16.6 | 9.7 |
| Notation | 79 | 3.8 | 12.7 | 3.8 |
| Logic | 41 | 2.4 | 14.6 | 9.8 |
| Temporal | 48 | **64.6** [51.0, 79.1] | 2.1 [0.0, 6.7] | 6.2 [0.0, 13.5] |
| All rewrites | 168 | 20.8 | 10.1 | 6.0 |

읽는 법: Qwen 은 **0.0 → 64.6** 으로 튀고, 클라우드 둘은 **자기 열에서 가장 큰 값이 `None` 근처**다.
세 판의 고장 방식이 다르다는 것이 열을 세로로 훑으면 보인다.

**`None` 행은 반드시 표 안에 둔다.** 빼면 GPT 의 `Temporal 0.0` 이 "시간 구조에 강하다"로 읽힌다.

**표본 늘리기 (09-16)**: Logic·Temporal 이 23·24 로 얇아 변환 두 개를 추가했다.
- `else_split`(Logic): `if (C) {A} else {B}` → `if (C) {A}` + `if (not (C)) {B}`. 38개 생성, **11개가
  `DIVERGE_CONFIRMED`** — then 절 A 가 조건 C 가 읽는 변수를 바꾸면 두 번째 검사 값이 달라진다. 검사기가
  걸렀고 증명된 27개만 쓴다. **"변환기는 제안하고 검사기가 판정한다"는 설계의 실제 사례**로 쓸 수 있다.
- `wait_precheck`(Temporal): `wait until(C)` → `if (not (C)) { wait until(C) }`. 62/62 증명.
- 결과(else_split·wait_precheck 까지): 씨앗 201→216, 쌍 357→446, 공통집합 쌍 126→151. **Logic 23→41, Temporal 24→31.** 새 씨앗 15개는
  세 판 공통 통과가 하나도 없어 공통집합은 52개 그대로다.
- **40 채우기는 멈췄다(whisoo).** 대신 GPT `Temporal 0.0` 을 본 뒤 whisoo 가 "어려운 시간 구조 변환 하나"를
  요청했다. **공개할 사실: 이 변환은 칸 값을 본 뒤에 추가됐다.** 그래서 규칙을 돌리기 전에 고정했다.
  - 추가는 **`period_halve` 하나뿐**이다. 주기를 절반으로 줄이고 매 틱 뒤집히는 깃발로 한 번씩 걸러 실행한다
    (`period P` → `period P/2` + `skip := false` / `if (skip == false) {본문}` / `skip = not (skip)`).
    `break`·`wait until`·`delay` 가 있는 본문은 틱이 꼬이므로 제외. 25개 생성, **25/25 증명**.
  - **결과가 어떻게 나오든 그대로 싣고, 이 결과를 보고 변환을 더 넣지 않는다.** GPT 가 여전히 0.0 이면 0.0 이다.
  - 규칙은 GPT·Claude 판정을 열어보기 전에 여기 적었다.
  - **결과(규칙 커밋 `b619555` 뒤)**: 공통집합에 17쌍. **Qwen 16/17**, GPT 1/17, Claude 1/17. Temporal 은
    31→48쌍, Qwen 48.4→64.6%. GPT 는 0/31 → **1/48 = 2.1%, CI [0.0, 6.7]** — 0 에서 한 건 올라갔을 뿐
    0 과 구분되지 않는다. **"GPT 가 시간 구조에 반응한다"고 쓰지 않는다.** 자기 `None` 행 16.6% 보다 훨씬 낮다.
- 추가 비용: GPT $0.09, Claude $0.47(누적 $3.91 / $5.00), Qwen 무료. 세 판 모두 오류 0건.

- **원고에 쓸 때 지킬 것**
  - 주장은 **표기 민감성이 아니라 시간 구조**다. 공통집합에서 Qwen 의 `Cmp-Flip` 은 24.1%→7.7% 로
    내려앉는다. 그 거부들은 `period 0` 같은 애매한 프로그램에 몰려 있었고 그런 건 클라우드도 거부해
    공통집합에서 빠진다. **옛 "표현만 바꿔도 뒤집힌다" 문장을 그대로 쓰면 안 된다.**
  - 클라우드 두 판은 **재작성 이전에 자기와 불일치**한다(16.7% / 9.7%). 이 값이 재작성 거부율과 비슷하거나
    크므로, 클라우드의 거부를 재작성 탓으로 돌리지 않는다.
  - **Qwen `None 0.0` 은 결과다.** 이 칸이 있어야 Qwen `Temporal 64.6` 을 재작성 탓으로 말할 수 있다.
  - `period_halve` 의 **Qwen 16/17** 이 시간 구조 주장에서 가장 강한 단일 결과다. `Loop-Unroll 10/11` 과 함께
    본문 문장으로 쓴다.
  - **본문은 건수로 시작한다.** "반복문을 펼친 11개 중 10개에서 판정이 뒤집혔다", "GPT 는 216개 중 36개에서
    자기와 어긋났다" 가 주장을 지고, 표는 뒷받침이다.
  - `Loop-Unroll` 은 공통집합에서 **10/11** 로 선명하다. 본문 문장으로 따로 쓴다.
  - 유형별(10개) 수치는 공통집합에서 표본이 얇다. **표에는 띠 3개만** 싣고 유형별은 `RESULTS.md` 에만 둔다.
  - 두 클라우드 모델은 temperature 를 설정할 수 없다(400 / 파라미터 없음)는 사실을 함께 적는다.
- 471쌍 중 168쌍만 쓴다. 나머지는 판별 조건을 못 넘은 것이며 `RESULTS.md` 의 판별 관점(판마다 자기
  통과분을 분모로)에 남아 있다. 그 관점의 표·그림은 `results/superseded/` 로 옮겼고 `README.md` 에 왜
  버렸는지 적어두었다.
- **거부율 47–59% 를 "오탐률"로 쓰지 말 것.** Claude 거부 118건 중 92건은 자연어를 상시 규칙으로 읽는데
  확정된 IR 은 1회 검사인 경우다. judge 의 잘못이 아니라 자연어의 애매함이고, **사용자 확정 단계가
  필요하다는 근거** 쪽이다.

### 반드시 인용할 선행연구

**Moon et al., "Don't Judge Code by Its Cover: Exploring Biases in LLM Judges for Code Evaluation",
Findings of EACL 2026 (arXiv:2505.16222).** 우리 Table1 의 최근접 선행연구이며 리뷰어가 꺼낼 것이 거의
확실하다. Table1 의 표기 관례(행 이름을 하이픈 복합어로, 모델 이름을 `GPT-4o-mini` 꼴로, 기준 행 대비
증감을 괄호로)는 이 논문을 따랐다. 차별점은 둘이다.

1. **등가성을 기계가 증명했다.** 그들 6유형 중 권위 문구·오도하는 설명은 프로그램을 건드리지 않고,
   나머지도 구성상 자명한 등가다. 우리는 357/357 을 동결 평가기로 EQUIV-FIXPOINT 확인했다.
2. **진짜 항등 대조군이 있다.** 그들의 `Original` 행은 비교 기준일 뿐 재질의가 아니고 temperature 0 으로
   흔들림을 애초에 지웠다. 우리 Identity 18.4/10.8 은 그 흔들림을 **지우지 않고 잰** 값이다.

**약점도 적어둘 것**: 그들 표의 `Incorr.` 열(버그 있는 코드를 잡아내는 비율)에 해당하는 것이 우리에겐
없다. 전부 "통과시킨 프로그램의 등가 재작성"이라 *judge 가 진짜 버그는 잡는가*에 답하지 않는다. 버그
주입 실험은 별도이며 이번 마감 범위 밖이다 — limitation 한 문장으로 적는다.

- 09-11 `skill_result/05_experiment_plan/motivation_pilot_2026-09-11/` 은 **다른 실험**(silent divergence,
  judge vs Explorer 116 프로그램)이며 09-12 부터 보류다. Fig2/Table1 로 전용하지 않는다.
