#!/usr/bin/env python3
"""허브 설정 파일을 만든다 — files/hub_config.json.

무엇인가
  파이프라인이 **입력으로 읽는** 값이다. 정답지가 아니다.
  실제 허브라면 사용자가 미리 맞춰 두었을 것들만 담는다:
  공간 종류별 기준값("덥다"가 몇 도인가), 장면(movie 가 밝기 몇 퍼센트인가),
  알림을 어디로 보낼지 순서, "시원하게" 가 몇 도인지 보폭, 재실 주체 고르는 순서.

무엇이 아닌가
  "덥다 → 온도 센서를 읽는다" 같은 말뜻 풀이(policy.PREDICATE)는 **넣지 않는다.**
  그건 모델이 알아내야 하는 것이다. 여기엔 숫자와 약속만 담는다.

값의 출처는 bench/policy.py 와 bench/ir.py 다. 손으로 옮기지 않고 여기서 뽑아 쓴다 —
베끼다 틀리는 것을 막고, 데이터셋이 바뀌면 이 파일도 같이 바뀌게 하려고.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ir
import policy

OUT = os.path.join(os.path.dirname(HERE), "files", "hub_config.json")

# 재실 주체 고르는 순서 — 위에서부터 있는 것을 쓴다.
# 전역 변수에 Human 이 정의돼 있으면 그것, 없으면 센서, 둘 다 없으면 판단 불가.
# (40개 공간 전부 이 순서로 spaces.json 의 occupancy 와 맞는 것을 확인했다.)
OCCUPANCY_ORDER = [
    {"쓸 것": 'GlobalVariable.Value("Human")', "있어야 하는 것": "GlobalVariable 의 Human 변수"},
    {"쓸 것": "MotionSensor.Motion",           "있어야 하는 것": "MotionSensor"},
    {"쓸 것": "PresenceSensor.Presence",       "있어야 하는 것": "PresenceSensor"},
    {"쓸 것": "PersonTracker.IsHome",          "있어야 하는 것": "PersonTracker"},
]


def scenes():
    """장면 이름 → 조명 값. ir.SCENE 을 서비스 호출 대신 값으로 편다."""
    out = {}
    for name, parts in ir.SCENE.items():
        d = {}
        for kind, v in parts:
            if kind == "bri":
                d["밝기"] = float(v)
            elif kind == "k":
                d["색온도"] = v
            elif kind == "hue":
                d["색상"] = float(ir.HUE[v])
                d["채도"] = 100.0
            elif kind == "off":
                d["끔"] = True
        out[name] = d
    return out


def thresholds():
    """기준값 — 공간 종류마다 다르다."""
    return {name: dict(zip(policy.KINDS, vals))
            for name, vals in policy.CONST.items()}


def main():
    cfg = {
        "$version": "1.0.0",
        "$comment": "허브 설정 — 파이프라인이 입력으로 읽는 값. 정답지가 아니다. "
                    "만드는 법은 bench/build_hub_config.py 참고.",
        "재실주체_순서": OCCUPANCY_ORDER,
        "기준값": thresholds(),
        "장면": scenes(),
        "색상": {name: float(deg) for name, deg in ir.HUE.items()},
        "알림_순서": [{"서비스": svc, "있어야 하는 기기": dev}
                   for svc, dev in policy.NOTIFY_ORDER],
        "값_보폭": policy.DELTA,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print(f"{OUT} 를 썼다")
    print(f"  기준값 {len(cfg['기준값'])}종 × 공간 {len(policy.KINDS)}종")
    print(f"  색 {len(cfg['색상'])}종")
    print(f"  장면 {len(cfg['장면'])}종 · 알림 {len(cfg['알림_순서'])}단계 · "
          f"보폭 {len(cfg['값_보폭'])}개 · 재실주체 {len(OCCUPANCY_ORDER)}단계")

    # 검산 — 말뜻 풀이가 새어 들어가지 않았는가
    flat = json.dumps(cfg, ensure_ascii=False)
    leaked = [k for k in policy.PREDICATE if k in flat]
    print("검산:", f"말뜻 풀이가 샜다: {leaked}" if leaked else "말뜻 풀이 안 들어감 ✅")
    return 1 if leaked else 0


if __name__ == "__main__":
    sys.exit(main())
