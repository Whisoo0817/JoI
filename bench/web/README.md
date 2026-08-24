# 공간 시뮬레이터 (`bench/web`)

명령어를 고르면 **어느 기기를 골라야 하는지**와 **세상에서 무엇이 바뀌는지**를
평면도 위에 보여준다. 실제 허브·센서는 없다 — 전부 그림이다.

최종 목적은 **모델 비교**다. 2B~9B 여러 모델이 같은 명령을 받고 무엇을 골랐는지
같은 그림 위에 겹쳐 보이는 것.

## 켜는 법

```bash
cd bench/web
npm install        # 처음 한 번
npm run dev        # http://localhost:5173
```

원격(SSH)에서 켜면 VS Code 가 5173 포트를 알아서 넘겨준다. 안 되면
아래 **포트(PORTS)** 탭에서 손으로 5173 을 추가한다.

## 왜 3D 가 아닌가

- 3D 는 벽·물체에 가려 기기가 안 보인다. 우리가 봐야 할 것이 **"어느 기기를 골랐나"**
  인데 그걸 가린다. 위에서 곧게 내려다보는 2D 는 항상 전부 보인다.
- 한 방에 기기가 최대 65개 몰린 공간이 있다. 3D 면 뭉개지고, 2D 격자면 다 보인다.
- `spaces.json` 에는 좌표가 없다(방 이름만). 3D 든 2D 든 배치를 만들어야 하는데
  2D 는 네모만 정하면 되고 3D 는 높이·카메라·조명까지 정해야 한다. 그걸 공간 40개에.

## 파일

| | |
|---|---|
| `gen_data.py` | `spaces.json` + `dataset_5k.csv` + `effects.py` → `public/data/*.json` |
| `src/Floorplan.jsx` | 평면도 SVG. 방은 네모, 기기는 동그라미 |
| `src/effects.js` | `call` 한 줄 → 실세계 효과 (`effects.py` 의 어휘 35개) |
| `src/theme.css` | 색은 전부 여기. 밝은 화면이 기본, `[data-theme=dark]` 가 값만 바꾼다 |
| `src/App.jsx` | 화면 전체 |

## 데이터 다시 만들기

```bash
python bench/web/gen_data.py           # HOME06 만
python bench/web/gen_data.py --all     # 40 공간 전부
```

`public/data/*.json` 은 만들어진 파일이지만 **커밋한다** — 받아서 `npm install` 만 하면
바로 뜨게 하려고. (`dataset_5k.csv` 도 같은 이유로 커밋돼 있다.)

### 방 배치

`spaces.json` 에 좌표가 없으므로 `gen_data.py` 의 `LAYOUT` 에 방 네모를 손으로 적는다.
안 적은 공간은 기기 수에 맞춰 격자로 깔린다 — **밑그림일 뿐 실제 집 모양이 아니다.**
지금 손으로 적은 것은 `HOME06` 하나.

`LAB01` 은 실제 연구실이라 기기 이름이 `tc0_Speaker_D83ADDD14F4B` 꼴이고 방 정보가
없다. 태그에서 방을 찾고, 못 찾으면 `Unplaced` 로 간다. 실제 도면에 맞춰 따로 배치해야 한다.

## 기기 표시

| 모양 | 뜻 |
|---|---|
| 투명한 회색 | 평소 |
| **선명한 파란 테두리** | 모델이 골랐고 정답 |
| 빨간 테두리 | 모델이 골랐는데 오답 |
| 파란 점선 | 정답인데 놓침 |
| 더 흐림 | 이 명령과 무관 |

지금은 모델을 안 붙였으므로 **정답만 파랑**으로 칠한다.

## 모델을 붙일 때 — 화면이 필요로 하는 것

`App.jsx` 는 명령 하나에 대해 아래 모양이면 바로 그린다. 코드 생성 API 를 만들 때
이 모양으로 맞추면 화면 쪽은 손댈 게 거의 없다.

```jsonc
{
  "model": "joi-2b",            // 비교 차트의 가로축
  "command": "cool down the living room",
  "space_id": "HOME06",
  "verdict": "execute",         // execute | ask | refuse   ← dataset 의 expect 와 견준다
  "why": "",                    // 거절일 때 no_device | no_service | no_channel | no_context
  "ir": { "timeline": [ ... ] },      // dataset 의 ir_gt 와 같은 모양
  "targets": ["HOME06_LivingRoom_AirConditioner_1", "..."],  // 고른 기기 id
  "latency_ms": 812,
  "raw": "..."                  // 원문 (코드 패널에 그대로 보여줄 것)
}
```

채점은 `dataset_5k.csv` 의 `expect` · `targets` 와 견주면 된다. 채점 방식은 `expect` 가
정한다 — `execute` 면 targets 가 집합으로 정확히 같아야 하고, `ask` 는 되묻어야 맞고,
`refuse` 는 지목할 기기가 없다.

## 아직 안 한 것

- 공간 40개 중 39개가 자동 격자 배치 — `HOME06` 디자인이 확정되면 넓힌다
- 공간별 페이지 나누기 (지금은 `App.jsx` 의 `SPACE` 상수 하나)
- 모델 결과 붙이기 + 정확도 비교 차트
- 효과 애니메이션은 방 물들이기·소리 파동까지만. 블라인드·문 열림 등은 아직
