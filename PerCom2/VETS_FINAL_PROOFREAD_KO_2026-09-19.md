# VETS.pdf 최종 교정 검토

- 검토 대상: `joi/PerCom2/VETS.pdf`, 10쪽. 아래 쪽수는 PDF 페이지 순서다.
- 검토일: 2026-09-19.
- PDF SHA-256: `ac7965fc024d30c2b02b8ae7693d9d2d5c0eafd6a5e67a314e7533956983a2e2`.
- 범위: 전체 본문·부록·참고문헌, 그림과 표, 수치 일관성, 서지 메타데이터 및 주요 인용의 연결. 원본 PDF/TeX/BibTeX는 수정하지 않았다.
- 방법: PDF 텍스트 추출과 페이지 렌더링을 병행하고, 원본 TeX/BibTeX를 보조 자료로 확인했다. OpenCite 변환은 `markitdown` 의존성 누락으로 실패하여 `pdftotext`와 `pdftoppm`으로 직접 확인했다. 페이지 위치는 최종 PDF 기준이다. 실험을 재실행하거나 검증기의 soundness를 새로 증명한 검토는 아니다.

## 1. 바로 수정할 오타·표기·설명 불일치

| 번호 | 위치 | 현재 표현 | 수정 제안 |
|---|---|---|---|
| T1 | p.1 오른쪽, Running example | `reset below the threshold` | `reset at or below the threshold`. Fig. 1(b)의 `else`는 `temp <= 25`에서 실행되므로 경계값 25에서도 reset된다. |
| T2 | p.5 Fig. 3 코드 상자 제목 | `Generated JoI code` | `Generated JOI code` |
| T3 | p.5 Fig. 3, device binding | `doorSpeaker → hallway speaker` | IR의 호출은 `Speaker.Speak(...)`이다. binding을 `Speaker → hallway speaker`로 바꾸거나 IR 식별자를 맞춘다. |
| T4 | p.6 오른쪽 아래, VI-B | `needs to distinguished two groups of values only` | `needs to distinguish only two groups of values` |
| T5 | p.7 오른쪽, Datasets | `The evaluation datasets is available in out artifact [5].` | `The evaluation datasets are available in our artifact [5].` |
| T6 | p.8 왼쪽, VII-B 첫 문단 | `We constructed 150 pairs IR–JOI pairs` | `We constructed 150 IR–JOI pairs` |
| T7 | p.9 왼쪽, Fig. 5 아래 | `Behavior explorer` | `Behavioral Explorer` |
| T8 | 같은 문장 | `requests that incurs` | `requests that incur` 또는 아래 문단 교체안 사용 |
| T9 | p.7 왼쪽, VI-B 마지막 | `”unsupported”`, `”timeout”` | 여는 따옴표가 잘못되었다. LaTeX의 올바른 여는/닫는 따옴표 또는 `\texttt{unsupported}`, `\texttt{timeout}` 사용. |
| T10 | 본문 전반 및 Fig. 3 | `§1`, `§2`, `§3`, `§5`, `§6`, `§V`, `Section VI` 혼용 | 실제 절 번호는 로마 숫자이므로 `Section~\ref{...}` 등으로 통일. 현재 참조 대상 자체가 틀린 사례는 찾지 못했다. |

소스에서 T4는 `overleaf-paper/main.tex:311`, T5는 339, T6는 384, T7–T8은 456, T9는 317에서 확인된다. 그림 내부 텍스트는 그림 원본을 수정해야 한다.

### 문법과 문장 흐름을 함께 고칠 곳

**p.6 VI-B, 입력 그룹 설명**

현재 문장은 `distinguished` 외에도 `taking each value as separate`가 어색하다. 두 프로그램의 모든 조건을 고려한다는 앞 문장의 조건을 유지하면서 다음처럼 쓸 수 있다.

> If both programs use temperature only to test whether it exceeds 22 degrees, Explorer needs to distinguish only two groups: values at or below 22 and values above 22, rather than exploring each value separately.

**p.8 Decision coverage**

> Eight pairs timed out after reaching the 10-minute limit because of state-space explosion.

`Timeout verdict was made`, `explosive number`, `10 minute time bound`를 한 번에 정리한다. 이어지는 `It incurs infinite number of value states to explore.`는 다음처럼 수정한다.

> This yields an infinite number of possible value states.

**p.9 Fig. 5 아래 문단**

현재는 문법 문제뿐 아니라 `is proven affordable`가 제한된 실험 결과보다 강하고, `Both reached the time limit`의 지시 대상도 멀리 떨어져 있다. 앞쪽 p.8의 마지막 문장부터 다음처럼 교체하는 것을 권한다.

> These results demonstrate the benefit of grouping time states for the tested program family. The two unfinished programs combined six sensors, six stages, and 50 repetitions, or seven sensors, six stages, and 100 repetitions. Both reached the 120 s limit. Checking costs for other program structures may differ.

## 2. 저자가 확인하거나 범위를 명확히 할 내용

### C1. 초록의 `100% accuracy`는 본문보다 강하다 — 우선 수정 권장

- 위치: p.1 Abstract의 `184 verifiable pairs—achieving 100% accuracy`.
- p.8 Table III와 VII-B는 equivalent 64쌍에 대해 **tested inputs**에서 행동이 일치했고, divergent 120쌍에 대해서는 counterexample replay로 차이를 확인했다고 설명한다.
- 독립적인 전체 상태공간 정답 판정을 얻은 것과 테스트 입력에서 일치한 것은 다르다. Explorer의 형식적 보장 자체와 그 보장을 실험으로 교차 확인한 범위도 구분해야 한다.
- 권장 교체:

> On 200 IR–code pairs, Explorer issued 184 definitive verdicts, all of which agreed with independent reference checks on tested inputs or replayed counterexamples.

`184 verifiable pairs`도 결과를 보고 정한 집합처럼 읽히므로 `184 definitive verdicts`가 본문과 더 잘 맞는다. 수치 오류는 아니다.

### C2. 동시 action의 순서를 E1과 Explorer가 다르게 취급한다

- p.6 VI-A: 같은 시각 command의 target, method, arguments, number, **order**를 비교한다.
- p.7 E1: 동시 action을 **unordered group**으로 취급한다.
- E1은 요청 표현력 평가이고 Explorer는 코드 동치성 검사이므로 서로 다른 기준이 의도된 것일 수 있다. 따라서 오류라고 단정하지 않는다.
- 의도된 차이라면 E1 뒤에 다음 설명을 추가하면 된다.

> E1 ignores the order of simultaneous actions; Explorer’s equivalence check additionally preserves their order.

실제 구현도 이 구분과 일치하는지 확인해야 한다.

### C3. LLM judge의 217개가 어디에서 나온 것인지 빠져 있다

- p.4 Table II는 217 programs, p.3은 VII-C의 JOI programs를 사용했다고만 적는다. VII-C의 전체 수는 382개다.
- 로컬 `03_Motivation/experiment_details.md`에는 **equivalent 309개 중 검증된 rewrite가 하나 이상 있는 217개**라고 이미 설명되어 있다.
- 숫자가 틀린 것이 아니라 최종 PDF에서 선택 기준이 생략되었다. 다음 한 문장 추가를 권한다.

> Of the 309 equivalent candidates in Section VII-C, 217 had at least one behavior-preserving rewrite verified by Explorer.

- p.3의 `the 52 originals accepted by each judge through majority vote`도 `the 52 originals accepted by all three judges by majority vote`로 바꾸면 공통 accepted set임이 분명해진다.

### C4. 무한 상태이면 무조건 `unsupported`라는 문장은 범위가 넓다

- 위치: p.7 VI-B 마지막, `In case the number of states is not finite, Explorer’s verdict is ... unsupported`.
- 이는 모든 무한 상태 여부를 판별한다는 뜻으로 읽힐 수 있으며, 앞 문단의 범위 표현·상태 묶기와도 관계를 설명할 필요가 있다.
- 실제 지원 범위를 뜻한다면 p.8과 p.9의 표현에 맞춰 다음처럼 좁히는 편이 안전하다.

> Explorer returns unsupported when a program requires accumulated-variable analyses that it does not support. If exploration does not complete within the time budget, it returns timeout.

### C5. 소제목 `Validation Time Complexity`는 실험 내용보다 이론적으로 읽힌다

- 위치: p.8 VII-D.
- 본문은 점근적 복잡도 분석보다 실행시간·완료율 측정이다. `Verification Cost and Scalability` 또는 `Checking Time and Completion`이 더 정확하다. 필수 오타 수정은 아니다.

## 3. 참고문헌 점검 — 모두 p.10

### R1. [2], [10], [12], [17]의 arXiv 출처 정보가 최종 PDF에 없다

네 항목 모두 저자·제목·연도만 출력되어 있다. 로컬 BibTeX에는 `eprint`와 `archivePrefix`가 있지만 현재 IEEEtran 출력에는 반영되지 않았다. `howpublished = {arXiv preprint arXiv:...}`와 `url` 등 현재 스타일이 출력하는 필드로 보완한 뒤 PDF를 다시 확인해야 한다.

| 번호 | 문헌 | 보완할 식별자 및 확인 출처 |
|---|---|---|
| [2] | AwareAuto 논문 | [arXiv:2408.12687](https://arxiv.org/abs/2408.12687), 2024 |
| [10] | AutoIoT: Automated IoT Platform Using Large Language Models | [arXiv:2411.10665](https://arxiv.org/abs/2411.10665), 2024 |
| [12] | Say What You Mean / LACE | [arXiv:2505.23835](https://arxiv.org/abs/2505.23835), 2025 |
| [17] | SimuHome | [arXiv:2509.24282](https://arxiv.org/abs/2509.24282), 최초 2025; ICLR 2026 채택 정보도 존재 |

예를 들어 [2]에 다음 두 필드를 추가하면 출처 누락을 피할 수 있다.

```bibtex
howpublished = {arXiv preprint arXiv:2408.12687},
url = {https://arxiv.org/abs/2408.12687},
```

### R2. [17] SimuHome의 출판 버전을 정해야 한다

- 현재 PDF는 `2025`만 표시한다.
- [저자 등록 arXiv 기록](https://arxiv.org/abs/2509.24282)은 `Accepted at ICLR 2026 (Oral)`이라고 명시한다.
- 정식 학회판을 인용할 경우 venue를 **ICLR**, 연도를 **2026**으로 업데이트한다.
- 2025 preprint를 의도적으로 인용하는 것 자체가 오류는 아니다. 이 경우 arXiv 번호와 필요한 버전을 명시한다.
- p.3의 scheduling self-correction 한계는 [최신 원문 §5.3](https://arxiv.org/html/2509.24282v3#S5.SS3)에서 확인되어, 다른 논문을 잘못 연결한 사례는 아니다.

### R3. 제목의 고유명사·약어 대소문자가 깨진 항목이 많다

| 번호 | 현재 PDF | 보존할 표기 |
|---|---|---|
| [1] | `Gpiot`, `iot` | `GPIoT`, `IoT` |
| [3] | `text-to-sql` | `text-to-SQL` |
| [5] | `Joi` | `JOI` |
| [6] | `Autotap`, `ltl` | `AutoTap`, `LTL` |
| [9] | `Tapinspector`, `iot` | `TAPInspector`, `IoT` |
| [10] | `Autoiot`, `iot` | `AutoIoT`, `IoT` |
| [11] | `Chatiot`, `iot` | `ChatIoT`, `IoT` |
| [13] | `Tapfixer` | `TAPFixer` |
| [14], [15] | `iot` | `IoT` |
| [16] | `Hawatcher` | `HAWatcher` |
| [17] | `Simuhome`, `llm` | `SimuHome`, `LLM` |
| [19] | `chatbot arena` | 고유명사 `Chatbot Arena` 보존 권장 |

일반 단어를 sentence case로 출력하는 것은 정상이다. 시스템명과 약어만 `{GPIoT}`, `{IoT}`, `{LTL}` 등으로 보호한다. 예: `title = {{GPIoT}: Tailoring Small Language Models for {IoT} Program Synthesis and Development}`.

### R4. 페이지/논문 번호 누락

아래는 다른 논문을 인용한 오류가 아니라 서지정보 보완 사항이다.

| 번호 | 현재 빠진 정보 | 확인한 정보 및 출처 |
|---|---|---|
| [7] IotSan | 쪽수 | **191–203**, [DOI 등록정보](https://doi.org/10.1145/3281411.3281440) |
| [11] ChatIoT | 쪽수, article number | **Article 103, 29 pages**; `pp. 1–29` 또는 스타일에 맞는 article 번호. [저자 공개 원문](https://www.emnets.cn/zh/publication/ubicomp-24-chatiot/chatiot.pdf), [DOI](https://doi.org/10.1145/3678585) |
| [35] How Users Interpret Bugs... | 쪽수 | **1–12**, [DOI 등록정보](https://doi.org/10.1145/3290605.3300782) |

[11]의 BibTeX에는 `articleno = {103}`이 이미 있으나 PDF에 출력되지 않는다. 필드를 넣는 것만으로 끝내지 말고 최종 출력에서 확인해야 한다.

### R5. [5] 익명 artifact 접근은 확인 미완료

[논문에 적힌 artifact 주소](https://anonymous.4open.science/r/VETS-artifact-B248/)는 이번 도구 접근에서 403을 반환했다. 도구 접근 제한일 수 있으므로 **링크가 잘못되었거나 저장소가 없다고 판단할 근거는 아니다**. 제출 전 비로그인 브라우저에서 열어 README, JOI grammar, dataset, 검증 artifact가 실제 제공되는지 확인할 필요가 있다.

### R6. 틀렸다고 지적하면 안 되는 항목

- **[18] TAP-Debug의 2022**: DOI 등록정보상 issue/print 날짜는 2022-12-21, online 날짜는 2023-01-11이다. 2023으로 보이는 자료도 있으나 현재 `vol. 6, no. 4, 2022`를 확정 오류로 볼 수 없다. [DOI](https://doi.org/10.1145/3569506).
- **[33] `M. Pak Yong Ho`**: DOI 등록정보의 given name은 Melwyn, family name은 Pak Yong Ho다. 낯설어 보이지만 임의로 `M. P. Y. Ho`로 고칠 사안은 아니다. [DOI](https://doi.org/10.1145/2556288.2557420).
- **[6] N. Brackenbury와 [35] W. Brackenbury**: 각 논문의 원저자 표기와 맞으므로 서로 같게 통일하지 않는다.
- **[20]–[23] 모델 링크**: [Qwen](https://huggingface.co/Qwen/Qwen3.5-9B), [FP8 배포본](https://huggingface.co/Hyper-AI/Qwen3.5-9B-fp8), [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini), [Claude Sonnet 5](https://www.anthropic.com/news/claude-sonnet-5)는 지정 모델의 공식/배포 페이지로 연결됨을 확인했다. 모델명의 실재 여부에 대한 오류는 발견하지 않았다.

## 4. 정상으로 확인한 항목과 검토 한계

### 수치·그림

- Table III: `64 + 120 + 8 + 8 = 200`; definitive verdicts `64 + 120 = 184`.
- Table IV: `309 + 68 + 3 + 2 = 382`; `309 + 68 = 377`; 각 백분율과 100.00% 합계가 맞는다.
- Repair: `36 + 26 + 6 = 68`; `36 / 68 = 52.9%`.
- E1: `92 + 6 + 2 = 100`.
- Fig. 2 유형별 variant 수 합은 168. Qwen temporal `31/48 = 64.6%`, UNR `10/11 = 90.9%`, PHV `16/17 = 94.1%`가 맞는다.
- Fig. 4의 reminder 10·40·70초, 종료 85초가 본문과 일치한다.
- Fig. 5의 28 대 12, 5초 이내 24개가 초록·본문·결론과 일치한다.
- 미정의 인용을 뜻하는 `[?]`나 깨진 절 참조 `??`, 주요 그림의 겹침/잘림은 발견하지 않았다.

### 서지·주요 인용

- DOI 등록정보로 [1], [3], [6], [7], [9], [11], [14], [18], [24], [26], [27], [28], [33], [34], [35]의 메타데이터를 대조했다. 위에 적은 누락·표기 외에 다른 논문으로 연결되거나 저자/기재 쪽수가 틀린 사례는 발견하지 않았다.
- [13], [15], [16]은 USENIX 공식 BibTeX와 저자·연도·쪽수가 맞는다: [TAPFixer](https://www.usenix.org/conference/usenixsecurity24/presentation/yu-yinbo), [Soteria](https://www.usenix.org/conference/atc18/presentation/celik), [HAWatcher](https://www.usenix.org/conference/usenixsecurity21/presentation/fu-chenglong).
- [4]는 [arXiv 원기록](https://arxiv.org/abs/2107.03374), [19]는 [NeurIPS 공식 기록](https://proceedings.neurips.cc/paper_files/paper/2023/hash/91f18a1287b398d378ef22505bf41832-Abstract-Datasets_and_Benchmarks.html), [25]는 [MIT Press](https://mitpress.mit.edu/9780262032704/model-checking/)와 연결을 확인했다.
- AutoIoT의 네 가지 conflict 설명은 [원문 IV-D](https://arxiv.org/html/2411.10665v1), LACE의 NLI 기반 문장 비교는 [원문](https://arxiv.org/html/2505.23835v1), SimuHome의 self-correction 한계는 [원문 §5.3](https://arxiv.org/html/2509.24282v3#S5.SS3)과 대응한다.
- [29]–[32], [37]의 문서/blueprint/thread 링크는 열렸고 제목과 대상이 맞는다. [38]의 작성자·2024-10-18 날짜 및 반복 점멸·종료·상태 복원 요청은 [원 게시물](https://community.home-assistant.io/t/how-to-automate-open-door-notifications/783900)에서 확인했다.
- [36] GitHub 데이터 폴더는 웹 도구에서 직접 읽지 못했다. 이 검토에서는 엑셀 원본과 Result sheet 내용까지 재확인한 것으로 간주하지 않는다.
- 모든 인용 논문의 전체 본문과 VETS의 모든 기술적 주장을 문장별로 대조한 검토는 아니다. 참고문헌 전부에 대해 무오류를 보증하지 않는다.

## 5. 수정 우선순위

1. T1–T9의 확실한 오타·식별자·경계값 설명 수정.
2. [2]/[10]/[12]/[17] 출처 출력, [17] 인용 버전, 고유명사 대소문자, [7]/[11]/[35] 서지정보 보완.
3. 초록의 accuracy 표현, 동시 action 순서 기준, 217개 선택 기준을 정리.
4. p.9 결론성 문장을 제한된 실험 범위에 맞게 수정하고 절 참조 표기를 통일.
5. 재빌드 후 참고문헌이 늘어난 데 따른 쪽수·넘침과 artifact 링크를 확인.
