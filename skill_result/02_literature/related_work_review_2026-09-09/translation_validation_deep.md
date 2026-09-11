# Translation Validation 정밀 검토 — 2026-09-09

논문 흐름상 위치: **Introduction에서 문제의 새로움을 어디에 둘지**, **Related Work에서 compilation correctness와 어떤 관계인지**, **Explorer에서 무엇을 관측하고 증명하는지**를 결정하기 위한 검토다.

## 1. 출판 정보와 이번에 해소한 source gap

- **원조 논문**: A. Pnueli, M. Siegel, E. Singerman, *Translation Validation*, **TACAS 1998**, LNCS 1384, pp.151–166. DOI `10.1007/BFb0054170`. arXiv-only 논문이 아니다. [출판사 기록](https://link.springer.com/chapter/10.1007/BFb0054170)은 TACAS 1998과 ©1998을 명시한다. 페이지의 2006 online 날짜를 학회 연도로 쓰면 안 된다.
- **이번에 원조 전문 확보 성공**: [Springer 16p PDF](https://link.springer.com/content/pdf/10.1007/BFb0054170.pdf). 기존 `formal_prior.md`의 “전문 미확보”는 당시 상태이며, 이 카드가 최신 상태다. `/tmp/formal_prior_read/BFb0054170.pdf`, `tv1998.txt`에 임시 저장했다. 전문을 읽고, PDF p.12/인쇄 p.162의 Rule REF는 로컬 렌더링 이미지로 수식까지 확인했다. 모든 증명의 독립 재증명은 아니다.
- **직전 함께 링크한 다른 논문**: Ngo et al., *Modular Translation Validation of a Full-sized Synchronous Compiler using Off-the-shelf Verification Tools*. 정식 확인되는 버전은 **SCOPES 2015, invited presentation/abstract, pp.109–112**, DOI `10.1145/2764967.2775291`. [저자 publication list](https://channgo2203.github.io/publications/), [4p ACM 형식 원문](https://channgo2203.github.io/pdfs/scopes15.pdf), Crossref DOI metadata가 일치한다.
- **`jar15.pdf`는 별도 37p 저자 manuscript**: [파일](https://channgo2203.github.io/pdfs/jar15.pdf)의 표지는 journal/date placeholders다. 이번에도 정식 journal DOI/volume이나 arXiv 등록을 확인하지 못했다. `jar15` 파일명만으로 JAR 게재 또는 arXiv 논문이라고 부르지 않는다. 세부 방법은 이 manuscript, 서지는 확인된 SCOPES short version과 구별해 사용한다.

## 2. TV1998에서 직접 확인한 방법

출처: [원문](https://link.springer.com/content/pdf/10.1007/BFb0054170.pdf), 아래 쪽수는 인쇄 페이지.

| 위치 | 원문 확인 내용 |
|---|---|
| pp.151–153 | 매번 source/target을 analyzer에 넣는다. 성공 proof script를 작은 checker가 확인하는 구조를 제안한다. |
| pp.154–156 | MUX는 입력 정수부터 1까지 출력한다. `ZN`은 이전 `N`이다. 생성 C의 특정 위치 `l5`에서 source 상태와 대응한다. |
| pp.156–158 | 공통 모델 STS=`(V,Θ,ρ,E)`: typed variables, initial condition, transition relation, observables. volatile signal의 부재는 `⊥`, 과거값은 persistent memorization variable로 표현한다. |
| p.158 | C에는 program counter와 보조 memory를 넣는다. 명시적 `write(N)`을 모델에서 제거하고 memorization으로 대체한다. |
| pp.159–160 | clocked interface mapping은 observable 값을 유지하거나 `⊥`로 숨긴다. 모든 concrete computation을 mapping한 결과가 abstract observable computations에 포함되면 refinement다. |
| pp.160–162 | clocked refinement mapping과 inductive invariant로 초기 대응·전이 대응·관측 조건을 증명한다. |
| pp.162–164 | 자동화는 특정 생성기 구조를 이용한다. clock 계산→입력→출력 계산→출력→과거값 갱신; observation point와 guard 경로로 mapping/invariant를 구성한다. |
| pp.164–165 | MUX의 REF premises를 TLV로 검증했다. detailed algorithms/scripts/checker 설명 일부는 full version으로 미룬다. 대응 범위는 주로 source 한 iteration↔target 한 iteration이다. |

Rule REF의 구조:

```text
R1: ΘC ⇒ inv                     초기 invariant
R2: inv ∧ ρC ⇒ inv′              invariant 보존
R3: ΘC ⇒ ΘA[α]                   초기 상태 대응
R4: inv ∧ ρC ⇒ ρA[α]             전이 대응
R5: inv ⇒ (v[α]=v ∨ v[α]=⊥)      각 observable의 clocked 관측
```

따라서 단순 테스트가 아니다. 반면 sample C를 다루는 refinement theorem을 임의 C 전체의 자동 결정 절차나 물리시간 deadline 보장으로 읽어서는 안 된다.

## 3. Ngo 계열에서 직접 확인한 방법

출처: [SCOPES pp.110–112](https://channgo2203.github.io/pdfs/scopes15.pdf), [상세 manuscript §§3–8](https://channgo2203.github.io/pdfs/jar15.pdf). 아래 세부 페이지는 manuscript 기준.

전체 STS correspondence 문제를 compiler 단계의 자료구조별 검증으로 나눈다.

| 단계 | 표현·검사 |
|---|---|
| Clock synthesis | signal presence/absence와 value 제약을 formula로 만들고 refinement를 SMT로 검사 |
| Scheduling | Synchronous Data-flow Dependency Graph로 의존 관계 보존·deadlock 조건 검사 |
| Generated C | Synchronous Data-flow Value-Graph를 공유 구성, rewrite와 node sharing 후 대응 출력의 동일 node 여부 검사 |

§6(pp.24–31)의 계약은 대응 출력이 모든 논리 시점에서 같은 값을 갖는 것이다. C step function은 assignments/conditionals 중심이며 signal별 clock 변수와 정해진 생성 패턴을 이용한다. 과거값 `m.x`와 현재값을 구분한다. Rewrite는 일반 규칙·최적화별 규칙·동기언어 규칙이다. 입력과 이전 상태 대응도 구성한다. 정해진 normalizer가 일반 프로그램 동등성을 완전히 결정한다는 뜻은 아니다.

§7은 기존 compiler bug 세 개를 보고한다. 두 개는 clock/Boolean 변환, 하나는 검증 준비 중 발견한 C syntax error다. 세 개 모두 semantic validator가 증명한 불일치라고 합산하면 부정확하다. §8의 강한 표현만으로 model builders/rewrites의 mechanized source proof 완료를 추론하지 않는다.

## 4. VETS와의 대조: 이미 겹치는 부분과 남은 의무

이 절은 위 원문과 현재 로컬 VETS 계약을 대조한 **분석**이다. 새 방법의 우월성이나 최초성을 확정하지 않는다.

**그대로 겹치는 핵심**: 생성기를 신뢰하지 않고 생성 결과별로 source의 의미 보존을 검사한다. Timeline IR→LLM JoI→Explorer는 이 원리의 적용으로 설명할 수 있다. 생성기가 compiler인지 LLM인지 자체는 새로운 verification 원리가 아니다.

| 비교 질문 | VETS가 논문에서 구체화할 내용 |
|---|---|
| 무엇이 reference인가? | 사용자 확인 Timeline IR. 그러나 그 확인이 실제 NL 의도와 일치한다는 보장은 별도다. |
| 무엇을 관측하는가? | 시간·대상·method·typed arguments·multiplicity·명시 순서를 포함한 ACTION. 내부 microstep 전체를 비교하는 계약은 아니다. |
| 어떤 clock인가? | 고정 시작·input grid·정확한 내부 deadline·동시 input/timer 순서 등 선언 모델. 물리 장치 실행시간 보장은 아니다. |
| 어떤 implementation을 지원하는가? | 지원되는 준비 경로의 JoI candidates. 임의 코드 전체라고 쓰지 않는다. |
| 어떻게 무한 이력을 다루는가? | 고정 선언 모델 아래 허용 초기상태·입력이력에 대한 closure와 sound abstraction을 구체적으로 제시한다. |
| 무엇을 신뢰하는가? | 두 frontend/runner, service/input 모델, observation adapter, 검증 알고리즘 등. LLM을 신뢰하지 않는다는 설명으로 이 경계가 없어지지 않는다. |

**TV1998과의 의미 있는 방법 차이 후보**는, 정해진 생성 패턴의 observation point와 refinement mapping을 얻는 작업과 VETS의 지원 실행 모델에서 시간별 ACTION 차이를 보존하며 탐색을 닫는 작업의 차이다. 다만 VETS도 지원구조를 제한하므로 “그들은 structured code만, 우리는 arbitrary code”라고 쓰지 않는다.

**Refinement vs equality를 과장하지 않는다.** Refinement는 충분히 구체적인 deterministic reference와 input 대응 아래 equality에 가까운 계약을 담을 수 있다. 관측 대상이 무엇이고 어떤 internal behavior를 숨기는지가 핵심이다. TV1998의 clocked masking을 실제 시간 deadline·API 호출 횟수까지 보존하는 VETS 관측과 같다고 놓으면 안 되지만, TV 틀이 그런 관측을 원리적으로 표현하지 못한다는 뜻도 아니다.

**A/B의 용도**:

- A: 연속 5분과 지연 후 재확인은 다른 reference다. 후보 해석 선택과, 선택된 sustain을 생성 코드가 보존하는 검증은 분리된다. 기존 compiler validation에 시간이 없다는 증거로 사용하지 않는다.
- B: 저장값/현재값의 구분은 원조 MUX와 Ngo의 `m.x`에서도 다룬다. B는 VETS의 value provenance 관측 필요성을 보여주며 그 개념의 신규성을 증명하지 않는다.

## 5. Introduction·Related Work에서 사용할 결론 후보

사용 가능한 방향:

> VETS는 translation validation의 원리를 사용자 확인 스마트홈 행동 명세와 생성 코드에 적용한다. 논문의 기술적 초점은 선언된 센서·서비스·시간 모델에서 두 실행의 ACTION 관측을 연결하고, 그 차이를 놓치지 않는 검증을 제공하는 데 있다.

피할 문구:

- “기존 연구는 명세만 만들고 실제 생성 코드를 검증하지 않는다.”
- “시간과 저장값을 함께 보존하는 구현 검증은 처음이다.”
- “우리는 컴파일러 검증과 달리 생성기를 신뢰하지 않는다.”
- “Translation validation은 정적인 프로그램만 다룬다.”
- “TV가 refinement이므로 exact behavior를 보장할 수 없다.”

**아직 해결하지 않은 novelty 질문**: VETS의 관측 모델·추상화·closure가 기존 검증 기법의 단순 도메인 설정을 넘어 어떤 기술적 난제를 해결하는가? 현재 문헌 근거는 질문을 정확히 만들며, 답을 자동으로 주지는 않는다. Explorer 절에서 이 의무를 구체적으로 드러내야 한다.

## 6. 추가 원문 확인 기록

TACAS1998과 혼동하지 않도록 후속 저자 원문 [Translation Validation: From SIGNAL to C](https://cs.nyu.edu/home/people/in_memoriam/pnueli/pss00.pdf), 25p도 다운로드했다. 이번 카드는 그것을 TACAS1998 전문으로 대체하지 않았으며, 후속 논문의 알고리즘을 1998의 구현 사실로 소급하지 않는다.

`jar15.pdf`의 미확정 journal/arXiv 상태는 유지한다. 이전 카드 원문은 수정하지 않았고 이 파일만 새로 작성했다.
