"""COMMANDS_1/2/3 전체를 돌려 최종 JoI 코드만 로그 파일로 저장.

    python3 run_all_log.py [출력파일]   # 기본: cmd_all_results.log

run.py의 디바이스 목록/명령어 그룹/설정을 그대로 재사용한다.
파이프라인 추론 로그는 빼고, 명령어 → 최종 코드(name/cron/period + script)만 남긴다.
"""
import sys
import run as R  # run.py가 env 세팅 + 파이프라인 import까지 수행

OUT = sys.argv[1] if len(sys.argv) > 1 else "cmd_all_results.log"
GROUPS = [("COMMANDS_1", R.COMMANDS_1), ("COMMANDS_2", R.COMMANDS_2), ("COMMANDS_3", R.COMMANDS_3)]


def render(command: str) -> str:
    try:
        result = R.generate_joi_code(command, R.CONNECTED_DEVICES, {})
    except Exception as e:
        code = getattr(e, "error_code", "")
        return f"ERROR: {e}" + (f"  [error_code={code}]" if code else "")
    return R._format_code(result.get("code", ""))


with open(OUT, "w", encoding="utf-8") as f:
    # 어떤 백엔드/모델로 돌렸는지 헤더에 박아둔다.
    try:
        from config import get_client, get_model_id
        f.write(f"# backend model: {get_model_id(get_client())}\n")
    except Exception as e:
        f.write(f"# backend model: (unknown: {e})\n")
    for gname, commands in GROUPS:
        f.write(f"\n{'#'*72}\n# {gname}  ({len(commands)} commands)\n{'#'*72}\n")
        for cmd in commands:
            print(f"running: {cmd}")
            f.write(f"\n{'='*72}\n[CMD] {cmd}\n{'-'*72}\n")
            f.write(render(cmd) + "\n")
            f.flush()

print(f"\n✅ saved → {OUT}")
