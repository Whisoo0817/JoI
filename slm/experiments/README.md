# experiments/ — 연구 스크립트·데이터 (런타임은 `../joi_slm/`)

| 폴더 | 내용 | 노트 |
|---|---|---|
| `head/` | 경계 head: 2B 단어 상태 추출(`extract_states.py` → states.npz, gitignore), 라벨(`labels.json`), 학습 | §4–8 |
| `type/` | 절 타입·mods 라벨(`type_labels.json` 382 + `type_labels_extra.json` 29), 증강 세트(`aug_*.json`, 상태 npz는 gitignore), 타입 head 실험 | §9–12, §27 |
| `map/` | 임베딩 매핑: 서비스 검색(`retrieve_services.py` → `ranked.json`), 조건 부분 재질의(`cond_parts.py` → `cond_parts.json`), 기기 선택, paper 정합 데이터셋(`dataset_paper.csv`) | §17–19, §25.1 |
| `assembly/` | 상자 규칙 조립·슬롯·재정렬·IR 빌더(`build_ir.py`, G/G·P/P 평가), 객관식 선택기 실험(`sel_*.py`, `mcq.py`, `sft_*.py`) | §15, §20–21, §25–26 |
| `graph/` | 그래프 정식화: 합성 쌍(`pairs.json`), 프로빙, 파서(`parse.py`), 하이브리드 종단(`e2e.py`), 정규화기 원형(`normalize.py`) | §22–24, §28.2 |
| `para/` | 패러프레이즈 held-out: 직접 작성 세트(`para_claude.json`), 신선 파이프라인(`fresh.py`) | §27–28 |
| `waitk_*` | 스트리밍 wait-k 프로빙 | §6 |

패키지 자산 재생성: `cd slm && python -m joi_slm.train all` (states.npz·pairs_words.npz·aug npz 필요 → `head/extract_states.py`, `graph/extract_words.py`, `type/extract_aug.py`).
