"""v3 매핑을 직접 돌려보는 대화형 도구.

  /home/ikess/joi-llm/venv/bin/python try_command.py            # 대화형 메뉴
  /home/ikess/joi-llm/venv/bin/python try_command.py "불 켜줘"   # 단건
  옵션: --devices (클러스터별 디바이스 목록), --base (베이스라인 비교)

대화형에서는 번호(1~10)로 내장 예제를 실행하거나 임의 명령을 입력한다.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

import run as R  # noqa: E402
from resolver_v3 import resolve_v3  # noqa: E402

DEV = R.CONNECTED_DEVICES
C = {"h": "\033[1;36m", "g": "\033[32m", "y": "\033[33m", "r": "\033[31m",
     "d": "\033[2m", "0": "\033[0m"}

# 엄격판 섀도(2026-07-20)에서 베이스라인과 갈린 8개 — 직접 판정용.
# --base를 붙이면 현행 파이프라인 출력이 ④에 같이 찍힌다.
EXAMPLES = [
    ("미세먼지 좋음이면 창문 닫으라고 알려줘",
     "diff: base=FineDustLevel vs v3=DustLevel — '미세먼지' 어휘 귀속 차이"),
    ("매일 오후 4시 39분에 환기히라고 스피커로 알려주고 알림도 띄워줘.",
     "diff: v3가 Toast 누락 — 추출기 notify 채널 병합 (기지 결함)"),
    ("경제 뉴스 알려줘",
     "diff: v3가 Toast 누락 — 채널 무지정 기본값(Speaker+Toast) 미적용"),
    ("매시간 정각마다 스피커로 시간을 알려줘",
     "diff: base=Clock.Hour+Minute 2회 읽기 vs v3=Datetime 1회 (그룹당 svc 1개 한계)"),
    ("퇴근 후 사람이 감지되면 조명을 켜고 카메라 녹화 시작하고 메일 보내줘",
     "diff: v3가 SendMail→첨부 버전 과잉 승격 ('~하고'=순차인데 dataflow 취급)"),
    ("오후 6시 27분에 카메라 녹화 시작하고 'lindy@mysmax.kr'로 메일 보내줘",
     "diff: 위와 동일 — 메일 첨부 과잉 승격"),
    ("오후 6시 30분에 조명을 끄고 카메라 녹화 시작하고 메일 보내줘",
     "diff: 위와 동일 — 메일 첨부 과잉 승격"),
    ("챗봇에게 대한민국의 수도가 어디인지 물어봐줘",
     "diff: base가 Speak을 AI 챗봇 디바이스에 보냄(라이브 버그) vs v3=JOI 스피커 — v3 우세"),
    ("삼성공기청정기 큰거를 토글해줘",
     "diff: x"),
    ("삼성 공기청정기 큰거 토글해줘",
     "닉네임+속성 지시 — 삼성 공기청정기 중 '큰거' 특정 후 토글"),
    ("불 모두 켜줘",
     "태그 특이성/합집합 — Light∪LightSwitch 전체 켜기(quantifier=all)"),
]

_BASE = None


def baseline_for(command):
    global _BASE
    if _BASE is None:
        _BASE = {}
        path = os.path.join(HERE, "baseline_2026-07-20.jsonl")
        if os.path.exists(path):
            for line in open(path):
                rec = json.loads(line)
                _BASE[rec["command"]] = rec
    rec = _BASE.get(command)
    if not rec:
        return None
    if not rec.get("ok"):
        return f"(거부) {rec.get('error', '')}"
    code = rec["code"] if isinstance(rec["code"], str) \
        else json.dumps(rec["code"], ensure_ascii=False)
    m = re.search(r'"script"\s*:\s*"(.*)"\s*}', code, re.DOTALL)
    return (m.group(1) if m else code).replace("\\n", "\n").replace('\\"', '"').strip()


def show(command, want_devices=False, want_base=False):
    print(f"\n{C['h']}══════ {command}{C['0']}")
    log = []
    res = resolve_v3(command, DEV, log=log)

    print(f"\n{C['h']}① 제약 추출{C['0']} {C['d']}(LLM #1 — 환경 무지){C['0']}")
    for g in res["extracted"]:
        hard = "hard" if g["device_hard"] else "free"
        q = f" 수량={g['quantifier']}" if g["quantifier"] else ""
        a = f"  {C['d']}인자: {g['args_text']}{C['0']}" if g["args_text"] else ""
        print(f"  [{g['role']}] 디바이스={g['device_hint']!r}({hard})"
              f" 효과={g['effect_hint']!r}{q}{a}")

    print(f"\n{C['h']}② 지시 해소{C['0']} {C['d']}(후보=Python 합집합 → 선택=LLM #2, "
          f"후보 dN enum 제한){C['0']}")
    for line in log:
        print(f"  {line}")

    print(f"\n{C['h']}③ 최종 매핑{C['0']} {C['d']}(Python — 능력검사/selector/수량/체이닝){C['0']}")
    for grp in res["groups"]:
        tagline = f"  {C['d']}← {grp['role']}{C['0']}" if "chain" in grp["role"] else ""
        for cl in grp["clusters"]:
            sel = " ".join("#" + t for t in cl["sel"])
            print(f"  {C['g']}{cl['quant']}({sel}).{cl['svc']}{C['0']}"
                  f"  {C['d']}[{len(cl['ids'])}대]{C['0']}{tagline}")
            if want_devices:
                for did in sorted(cl["ids"]):
                    d = DEV[did]
                    print(f"      {C['d']}· {d['nickname']} {d['category']}{C['0']}")
    for e in res["errors"]:
        print(f"  {C['r']}🚫 {e}{C['0']}")
    if not res["groups"] and not res["errors"]:
        print(f"  {C['r']}(해석 결과 없음){C['0']}")

    if want_base:
        b = baseline_for(command)
        print(f"\n{C['h']}④ 베이스라인(현행 파이프라인){C['0']}")
        print("  " + (b.replace("\n", "\n  ") if b
                      else f"{C['d']}(베이스라인 스냅샷에 없는 명령){C['0']}"))


def menu():
    print(f"\n{C['h']}── v3 예제 (번호 입력) ──{C['0']}")
    for i, (cmd, why) in enumerate(EXAMPLES, 1):
        print(f"  {i:>2}. {cmd}")
        print(f"      {C['d']}{why}{C['0']}")
    print(f"  {C['d']}또는 임의 명령 입력 · 'm' 메뉴 다시 보기 · 'q' 종료"
          f" · 끝에 --devices/--base 가능{C['0']}")


if __name__ == "__main__":
    argv = sys.argv[1:]
    g_dev = "--devices" in argv
    g_base = "--base" in argv
    words = [a for a in argv if not a.startswith("--")]

    if words:
        show(" ".join(words), g_dev, g_base)
        sys.exit(0)

    menu()
    while True:
        try:
            line = input(f"\n{C['h']}명령(1-{len(EXAMPLES)}/텍스트)>{C['0']} ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line or line in ("q", "quit", "exit"):
            break
        if line == "m":
            menu()
            continue
        d = g_dev or "--devices" in line
        b = g_base or "--base" in line
        line = re.sub(r"\s*--\w+", "", line).strip()
        if line.isdigit() and 1 <= int(line) <= len(EXAMPLES):
            line = EXAMPLES[int(line) - 1][0]
        if line:
            try:
                show(line, d, b)
            except Exception as e:  # noqa: BLE001
                print(f"{C['r']}에러: {e}{C['0']}")
