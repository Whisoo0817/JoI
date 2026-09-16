# Provenance audit — E1 breadth corpus (pre-audit package)

감사일 2026-09-13, 서버(Claude). 대상: `corpus_100.csv` 100행, `screening_log_150.csv` 150행, seed 12건.
원본 스냅샷은 import 커밋 `35e6043`(파일 무수정). 고친 내용은 `apply_audit_fixes.py` 가 적용하고
`changes_2026-09-13.csv` 에 행·필드별 전후 값을 남긴다.

**이 감사가 확정하지 않는 것.** source-stratum 분포(25×4), screen_status 건수, R/B label 은 이 감사 시점에는 pre-audit 이었다.
출처·위치·원문이 맞는지만 확인했고, 분류와 코딩은 건드리지 않았다.
**이후 확정(2026-09-13):** 출처 26/26/24/25 → 25/26/24/25(C15 research 로 이동), 저자 선별 92/6/2/0(`AUTHOR_SCREENING_2026-09-13.md`,
E1-095 는 IN_SCOPE), 저자 R/B 코딩(`AUTHOR_RB_CODING_2026-09-13.md`). 아래 "whisoo 판단으로 남긴 것" 중 C15·E1-095 는 그렇게 해결됐다.

## 방법

- corpus 와 screening log 에 나오는 URL 36개를 서버에서 모두 받았다(2026-09-13, 36/36 HTTP 200).
  HA Community 는 thread JSON(`/t/<id>.json`)으로, GitHub 파일은 raw 로 받았다. 받은 파일은 저장소에 넣지 않았다(저작권·용량).
- PDF 는 `pdftotext` 로 바꾸고, 원문 비교는 대소문자·문장부호·줄바꿈 하이픈을 정규화한 뒤 부분 문자열로 했다.
- AutoTap User Study 1 xlsx 는 `Result` 시트(헤더 1행 + 질문 문구 1행 + 응답 행)를 셀 단위로 검색했다.
- seed 12행은 저장소의 `../cases.py`(Stage A 출처 기록)와 필드 단위로 대조했다.

## 결과 요약

| 층 | 행 | 원문 존재 | 위치(locator) | 조치 |
|---|---:|---|---|---|
| seed | 12 | 12/12 | **12/12 틀림** — 위치 대신 사례 id(`C01` 등) | 실제 절·표·게시물로 교체 |
| research (새) | 18 | 18/18 | 18/18 맞음 (Ur Table 1 Task·Figure 1, Huang Table 4 P·Table 5 Q 표 배치 확인) | 없음 |
| elicited (새) | 23 | 23/23 셀 일치 | **23/23 틀린 이름** — `participant Pnn` 이 참가자 번호가 아님 | Excel 행·열로 교체 |
| 비보관 AutoTap | 50 | 50/50 셀 일치 | 같은 문제 | 같은 조치 |
| official (새) | 24 | 24/24 | 22/24 맞음, **2건 없는 섹션명** | 실제 제목으로 교체 |
| community (새) | 23 | 23/23 게시물이 정규화 문장을 뒷받침 | 맞음, **제목 23/23 은 GPT 가 붙인 이름** | 실제 thread 제목으로 교체 |

## 발견 사항

1. **seed locator.** 12행 모두 `source_locator` 에 `C01`…`C20-O` 가 들어 있었다. 출처 안의 위치가 아니다.
   `cases.py` 의 출처명과 원문으로 실제 위치를 찾아 넣었다. C20-O 의 URL(par.nsf.gov biblio)은 본문이 없어
   전문 PDF 주소(`/servlets/purl/10106413`)를 locator 에 함께 적었다. 원문은 그 PDF 의 Table 1 에 있다.
2. **seed 접근일.** CSV 는 12행 모두 2026-09-13 이고, `cases.py` 는 2026-09-12 다. 원래 날짜로 되돌렸다.
3. **AutoTap 참가자 번호.** 73행 모두 `Pnn = Excel 행 번호 − 2`(73/73)였다. pandas 행 번호이지 참가자 id 가 아니다.
   예를 들어 P04 는 공개 응답 중 네 번째 사람이 아니다. 논문에 "participant P24" 라고 쓰면 틀리므로 `Excel row R, column X` 로 바꿨다.
   원문 73/73 은 셀과 글자까지 같고(철자 오류 보존), 73행 모두 `ReleaseData=Yes`, `source_context` 23/23 이 원자료와 같다.
4. **Google Home 섹션명 2건.** `Morning blinds with suppression`(E1-074), `Weekday movement notification`(E1-075)은
   페이지에 없는 이름이다. 해당 예제는 있으며, locator 와 source_title 모두 실제 제목으로 교체했다. 설명 문장은 페이지 metadata 와 같고,
   더해진 조건(E1-075 의 09:00–18:00 등)은 YAML 에 있다 — `OFFICIAL_DESCRIPTION_OR_STRUCTURED_EXTRACTION` 에 맞다.
5. **Community 제목.** 23행 모두 `thread N:` 뒤가 실제 제목이 아니라 연구자 요약(예: E1-092 "Independent parallel
   shutdown flows", 실제 "Running groups of actions in Parallel")이었다. 실제 제목으로 바꾸고 첫 게시물 작성일을 locator 에 넣었다.
6. **E1-099 정규화 누락.** 첫 게시물은 두 조건("lights turned on for 5 minutes", "No motion detected by motion sensor
   for 2 minutes")을 말하는데, CSV 문장은 앞쪽만 있었다. frozen case 는 두 조건을 모두 쓰므로 CSV 문장에 뒤쪽을 더했다.
   frozen case 파일은 바꾸지 않았다.
7. **`source_verification`.** 100행 모두 `SOURCE_AND_LOCATOR_CHECKED` 였지만 위 1·3·4·5 가 틀려 있었다.
   서버 확인 결과(`SERVER_CHECKED_2026-09-13`, 고친 행은 `; CORRECTED`)로 바꿨다.
8. **워크북.** `Corpus_100` 시트는 수정 전 CSV 와 셀 단위로 같았다(0 차이). 수정 후 `build_workbook.py` 로 다시 만든다.

## 고치지 않고 whisoo 판단으로 남긴 것

- **C15 의 층.** protocol 은 elicited 를 "released study data 안의 참가자 작성 문장"으로 정의한다.
  C09 는 AutoTap 공개 데이터(Result row 16)에도 있어 맞지만, C15 는 Ur et al. 논문 본문이 인용한 참가자 발언이고
  공개 데이터 locator 가 없다. 정의를 넓히거나 C15 를 research 로 옮기면 elicited 가 24 가 된다.
- **C05·C07 날짜.** `cases.py` 출처명의 날짜(2023-01-18, 2024-10-20)와 첫 게시물 작성일(2023-01-17, 2024-10-18 UTC)이 다르다.
  `cases.py` 는 해시로 고정된 Stage A 기록이라 손대지 않았고, CSV 제목에서만 날짜를 뺐다.
- **C11 의 provenance_type.** "research example" 이지만 출처는 AutoTap §VI-A 의 study task 다(C16·C18·C19 는 "study task").
  층(research)은 같고 코딩 필드라 두었다.
- **E1-095 상태.** `screen_status=AMBIGUOUS` 인데 해석은 2026-09-13 에 확정됐고 frozen case 도 있다. 상태 갱신은 코딩 절차에 맡긴다.
- **`duplicate_family`.** 실제로는 "비슷한 무리" 표시다. E1-039(일몰)와 E1-040(19:00)은 protocol 의 중복 정의에 맞지 않는다.
  protocol 은 screening log 에 DUPLICATE 가 있다고 하지만 150행 중 0건이다.
- **URL 표기.** Huang & Cakmak 은 seed 가 `homes.cs.washington.edu/~mcakmak/…`, 새 행이 `hcrlab.cs.washington.edu/…` 로 같은 PDF 의 두 주소다.
- **E1-098.** 게시일이 2026-09-12 로 수집 하루 전이다. 이후 편집될 수 있어 접근일 기준 인용이 필요하다.
