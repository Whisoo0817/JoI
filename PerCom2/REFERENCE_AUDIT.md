# 참고문헌 점검 및 보충 — 2026-09-19

범위: 현재 Overleaf `main.tex` 전체의 인용 누락 점검, 해당 PerCom2 한글·영문 원고 반영, 인용 키와 BibTeX 연결 검사. 사용자 요청에 따라 JOI 언어 문서와 익명 artifact 저장소 인용은 제외했다. 실험 결과, 표, 그림, 수치는 변경하지 않았다.

현재 논문이 사용하는 참고문헌 파일은 [Overleaf references.bib](../../overleaf-paper/references.bib)이다. `joi/docs/refs.bib`와 기존 `PerCom` 하위 참고문헌은 이번 논문의 BibTeX 입력이 아니므로 일괄 덮어쓰지 않았다.

## 본문에 보충한 인용

| 위치 | 인용 키 | 인용의 역할 |
| --- | --- | --- |
| §3 LLM judge 소개 | `llmjudge`, `chatiot` | 일반적인 LLM judge 접근과 실제 IoT Evaluator 사례 |
| §3 모델 소개 | `qwen35`, `qwen35fp8`, `gpt54mini`, `claudesonnet5` | 기반 모델, 사용한 FP8 배포본, 클라우드 모델 공식 자료 |
| §6 도입 | `translationvalidation` | 생성된 결과물마다 기준과의 행동 보존을 확인하는 접근의 출처 |
| §6 상태 탐색 | `modelchecking` | 후속 상태 탐색과 방문 상태 재사용 |
| §6 시간 상태 표현 | `bengtsson2004timed` | 시간 검증의 차이 제약/DBM 표현 |
| §6 범위 확대·재검사 및 논문 증명 개요 부록 | `cousot1977` | widening과 고정점 근사의 기반 |
| §6 구현 | `z3` | 산술식·제약 비교에 사용하는 솔버 |
| E1 공식 예제 | `hamotionblueprint`, `hazoneblueprint` | corpus의 두 Home Assistant blueprint 원본 |
| E1 차고 문 예시 | `hagaragedoor` | 반복 점멸·중단·상태 복원을 요청한 실제 게시물 |
| E3 모델 | `qwen35`, `qwen35fp8` | 생성에 사용한 모델과 배포본 |
| E4 비교군 | `modelchecking` | explicit-state 탐색의 일반적인 방법 출처 |

E4 비교군은 Explorer의 시간 상태 묶기 경로를 끈 구현이라는 기존 설명을 유지했다. `modelchecking` 인용은 외부 도구를 실험 비교군으로 사용했다는 뜻이 아니다. 기법 문헌 인용은 Explorer 자체의 정확성 증명을 대신하지 않는다.

## BibTeX 변경

- 신규 8개: `z3`, `cousot1977`, `gpt54mini`, `claudesonnet5`, `qwen35fp8`, `hamotionblueprint`, `hazoneblueprint`, `hagaragedoor`.
- 기존 항목 보완: `qwen35`, `translationvalidation`, `modelchecking`, `tapfixer`, `soteria`, `hawatcher`, `gpiot`, `humaneval`, `iotsan`, `iotguard`, `ur2014`, `llmjudge`. 확인한 DOI, URL, 쪽수, ISBN 등의 누락을 보충했다.
- 미사용 항목은 향후 집필 자료로 보존했다. 등록된 모든 문헌을 본문에 억지로 인용하지 않았다.
- 웹 문서의 새 열람일은 2026-09-19이며, 기존 데이터 수집 시점의 열람일은 보존했다.

## 확인한 출처

- [Translation Validation, Springer](https://link.springer.com/chapter/10.1007/BFb0054170)
- [Model Checking, MIT Press](https://mitpress.mit.edu/9780262032704/model-checking/)
- [Timed Automata: Semantics, Algorithms and Tools, Springer](https://link.springer.com/chapter/10.1007/978-3-540-27755-2_3)
- [Cousot와 Cousot의 POPL 1977 논문, 저자 페이지](https://www.di.ens.fr/~cousot/COUSOTpapers/POPL77.shtml)
- [Z3 원 논문, Microsoft Research](https://www.microsoft.com/en-us/research/publication/z3-an-efficient-smt-solver/)
- [LLM-as-a-Judge, NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2023/hash/91f18a1287b398d378ef22505bf41832-Abstract-Datasets_and_Benchmarks.html)
- 모델·blueprint·게시물의 확인 URL은 해당 BibTeX 항목에 기록했다. GPIoT·Ur 2014·Z3의 쪽수와 DOI는 Crossref 등록 메타데이터와 대조했다.
- E1 blueprint 두 건과 차고 문 예시의 연결은 [corpus_100.csv](../PerCom/08_Evaluation/E1_adequacy/breadth/corpus_100.csv)의 `source_url`과 대조했다. 나머지 개별 커뮤니티 게시물의 원문 위치는 corpus 기록에 유지하며, 모두 별도 BibTeX 항목으로 늘리지 않았다.

## 검사 결과

- BibTeX 파서 검사 통과: 등록 61개, 현재 논문에서 인용 37개. 변경 전은 등록 53개, 인용 24개였다.
- 현재 논문과 PerCom2의 `main*.md`, `appendix*.md`에 미정의 인용 키 없음.
- 현재 논문에서 인용하는 모든 항목에 제목·저자와 DOI/URL/arXiv 식별자/ISBN 중 하나가 있음.
- 수정한 §3·§6·§7의 한글·영문 인용 키 일치.
- 인용을 보충하지 않은 본문 절, 모든 표·그림 내용, label 보존 확인.
- PDF 빌드는 수행하지 않았다. 조판된 참고문헌 페이지 수는 확인하지 않았다.

미완료 범위: JOI 문서·익명 artifact 인용은 사용자 요청에 따라 보류. 모든 기존 문헌의 본문 주장을 원문 전체와 다시 대조하는 별도의 문헌 검토까지 수행한 것은 아니다.
