# Timeline IR의 본문 표현 후보

> 최신 사용자 피드백 (2026-09-17): 예제는 분량에 따라 선택하며 현재는 짧게 유지한다. operator 표에 기본 실행 의미를 통합하고 별도 Execution rules와 상세 구현 설명은 본문에서 삭제한다. action trace 정의, D 명제와 짧은 증명 근거를 남긴다. 아래 후보 A의 상세 배치와 확정 기록은 이전 버전 이력이다.

2026-09-17. 사용자 요청에 따라 원저자 공개 PDF의 실제 본문·그림·부록을 확인했다. 체계적 문헌조사나 최신 연구의 순위가 아니라, 중심 언어/표현을 설명하는 서로 다른 집필 방식의 사례다. 네트워킹 시스템과 PL 논문을 골라 시스템 독자용 설명과 형식적 설명을 비교한다. 원문 문장·그림을 복사하지 않는다.

## 확인한 탑티어 논문

| 논문 | 원문에서 확인한 배치 | Timeline에 참고할 점 |
| --- | --- | --- |
| **Flowlog**, *Tierless Programming and Reasoning for Software-Defined Networks*, NSDI 2014, Nelson et al. | §2의 응용 설명 뒤 §3에서 언어를 정의한다. Fig. 2(PDF 5쪽)에 ruleset concrete syntax, Fig. 3(PDF 6쪽)에 rule→formula 변환을 둔다. | 핵심 구조가 기여를 이해하는 데 필요하면 grammar를 본문으로 올린다. Timeline에서는 긴 식 문법 대신 operator/필드/실행 의미 표로 줄일 수 있다. [원문](https://cs.brown.edu/~tbn/publications/nfsk-flowlog-nsdi14.pdf), [학회 페이지](https://www.usenix.org/conference/nsdi14/technical-sessions/presentation/nelson) |
| **Lucid**, *A Language for Control in the Data Plane*, SIGCOMM 2021, Sonchack et al. | §3–§5에서 코드 예제와 실행·상태 접근을 설명한다. Fig. 4(PDF 6쪽)는 event scheduling, Fig. 5(PDF 7쪽)는 잘못된 접근 순서의 코드다. §5.2(PDF 8쪽)에 typing judgment와 soundness 정리가 있다. Appendix A의 Fig. 18·19는 단순화한 모델 언어의 문법·타입 규칙, Appendix B의 Fig. 20과 후속 절은 실행 의미·증명을 제공한다. | 본문에서 실제 사용 모습과 핵심 정리를 보여주고 상세 정의·증명을 뒤로 보낸다. 부록의 모델 언어와 구현 문법을 구별한 점도 중요하다. [원문](https://www.cs.princeton.edu/~dpw/papers/lucid-SIGCOMM-2021.pdf) |
| **NetKAT**, *Semantic Foundations for Networks*, POPL 2014, Anderson et al. | §3의 Fig. 2(PDF 4쪽)에 syntax·denotational semantics·axioms를 모은다. Fig. 3(PDF 5쪽)는 algebraic syntax와 surface syntax를 나란히 대응시킨다. §4.1의 Theorem 1은 본문에 정리와 proof sketch를 두고 full proof는 long version을 가리킨다. | 구현 표기와 수학 표기가 다르면 대응을 보여준다. Timeline의 실제 JSON을 pseudocode로 바꿀 때도 대응을 명시한다. [원문](https://www.cs.cornell.edu/~jnfoster/papers/frenetic-netkat.pdf) |

쪽수는 PDF 첫 장을 1쪽으로 센다. Lucid는 SIGCOMM 2021 논문이며 동명의 다른 Lucid 언어와 구별한다. 배치 제안은 원문에 근거한 **우리의 편집 판단**이다.

## 후보 A: 예제 + operator 표 + 정리 (현재 초안에 적용)

본문 순서:

1. 자연어 한 문장과 실제 JSON을 하나의 예제 패널로 보여준다.
2. 조건·지속시간·행동·일회 실행이 각각 어디에 나타나는지 설명한다.
3. 8개 operator를 `operator / principal fields / execution meaning` 표로 정리한다.
4. snapshot, suspend/resume, sustain reset, period의 의미를 정의한다.
5. 반응 관계, D 정리, 짧은 증명 개요를 둔다.

부록/보조 명세에는 전체 operator grammar, 식의 우선순위, 지원 조건, D의 규칙별 논증을 둔다. **Lucid식 본문/부록 분리 + Flowlog식 구조 요약**이다. PerCom 원고가 언어 자체의 신규성보다 확정 reference를 사용하는 검증 흐름을 설명하므로 이 구성을 추천한다. 가독성이 검증됐다는 주장은 하지 않는다.

## 후보 B: 핵심 grammar를 본문에

예제 다음에 `I ::= start_at ; S`, `S ::= [s*]`, `s ::= wait | delay | read | call | if(S,S) | cycle(S) | break`를 한 패널로 놓고, 각 primitive의 의미를 옆에 붙인다. Flowlog의 본문 syntax 방식에 가깝다.

- 장점: 순차·분기·반복이라는 구조를 한눈에 볼 수 있다.
- 비용: operator 표와 함께 두면 내용이 중복된다. 위 축약 문법은 구조 요약일 뿐 전체 JSON grammar라고 부르면 안 된다.
- 선택 기준: operator 종류보다 composition 구조가 독자에게 불명확할 때 A의 표를 이 패널로 대체한다.

## 후보 C: JSON / abstract syntax / reaction rule 대응

같은 예제를 실제 JSON, 추상 구문, 실행 전이의 세 층으로 대응시킨다. NetKAT의 surface/algebraic syntax 대응을 참고한다. 본문에 핵심 전이 규칙을 더 많이 두고 정리로 바로 연결한다.

- 장점: syntax→semantics→theorem의 관계가 직접 보인다.
- 비용: 표기와 지면이 늘고 형식 언어 논문처럼 읽힐 수 있다.
- 선택 기준: 언어/의미론 자체를 중심 기여로 전환할 때 적합하다. 현재 PerCom framing에는 A보다 우선하지 않는다.

## Grammar와 증명의 위치에 대한 결론

**Grammar를 모두 부록에 둬도 되지만, 본문에서 IR의 실제 모습까지 사라지게 두지는 않는다.** A에서는 실제 JSON과 operator 표가 그 역할을 한다. D도 부록으로 통째로 보내지 않고, 본문에 전제·명제·증명 개요를 유지한다.

후속 확인: [PerCom 2027 공식 CFP](https://percom.org/call-for-papers/)는 본문·그림·표·부록을 합쳐 기술 내용 9쪽, 참고문헌 전용 추가 1쪽을 허용한다. 부록은 별도 무료 지면이 아니다. 별도 supplementary 제출·심사 허용은 확인되지 않았다.

사용자 확정안: 본문의 JSON 예제·operator 표·결정성 수식을 유지하고, 부록은 연산자별 유일성과 반응·trace 귀납 증명으로 압축한다. `DETERMINISM_APPENDIX_COMPACT.md`가 제출 원고용이며, 전체 grammar·상세 명세는 `SYNTAX_AND_DETERMINISM_APPENDIX.md`에 보존한다. 필요한 전제와 증명 단계는 본문과 짧은 부록 안에서 설명하며, 별도 문서를 읽어야만 핵심 보장을 이해할 수 있게 만들지 않는다.

## 현재 자료를 옮길 때의 주의

- SenSys appendix의 nested-cycle 금지·bounded horizon·period cadence 문구를 복사하지 않는다. 현재 실행기의 nested cycle 지원과 경로별 인증 제한을 구분한다.
- `files/timeline_ir/extractor.md`는 생성 프롬프트다. 현재 실행 계약과 어긋나는 edge+sustain 조합 등의 지시가 있으므로 최종 문법·의미론의 근거로 단독 사용하지 않는다. 이번 작업에서 프롬프트나 실행 코드는 수정하지 않았다.
- `SYNTAX_AND_DETERMINISM_APPENDIX.md`는 표준화한 추상 표기다. parser가 받아들이는 모든 별칭·레거시 encoding을 빠짐없이 열거한 JSON Schema라고 주장하지 않는다.
- 문헌 배치 사례를 논문 본문에 억지로 인용하지 않는다. 실제 관련성 주장을 추가할 때만 별도 BibTeX 정리 후 인용한다.
