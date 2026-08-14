"""v3 매핑 결과 → generate.py 하류 계약 어댑터.

generate.py의 device-first 접합점(현행 selector→IR 계약 변환, 대략 L1003-1040)이
만드는 변수들을 v3의 resolve_v3() 출력에서 동일하게 생성한다. v3는 실제 태그/
디바이스 id로 작업하므로 현행의 dN 익명화·복원(real_of) 경로가 불필요하다.

반환 계약 (generate.py L1043~ 공유 경로가 기대하는 것):
  selected_services : list[str]  "Cat.Method" (선택 순서, 중복 허용 — 현행과 동일)
  df_selectors      : {svc: ["<quant>(#tag ...)", ...]}
  df_resolved       : {svc: {"q": quant|"one", "devices": [real_id, ...]}}
  df_read_services  : set[svc]   role=="read"인 것만 (condition 게이트 read는 제외 —
                                 arg_resolve가 $<ref>로 오용하는 것 방지, 현행 주석 참조)
  errors            : list[str]  v3가 귀속한 실현 불가 사유 (비면 정상)
"""


def v3_to_pipeline_contract(v3_result):
    selected_services = []
    df_selectors, df_resolved, df_read = {}, {}, set()

    for grp in v3_result["groups"]:
        role = grp["role"]
        for cl in grp["clusters"]:
            svc = cl.get("svc")
            if not svc:
                continue
            quant = cl.get("quant", "") or ""
            sel = "(#" + " #".join(cl["sel"]) + ")"
            selected_services.append(svc)
            df_selectors.setdefault(svc, []).append(f"{quant}{sel}")
            # devices는 실제 id (v3 cl["ids"]가 이미 real payload id).
            # 같은 svc가 여러 클러스터로 나뉘면(id 분해 등) 기기를 합친다 —
            # 덮어쓰면 마지막 클러스터만 남는 결함이 있었음.
            prev = df_resolved.get(svc)
            if prev:
                prev["devices"] = sorted(set(prev["devices"]) | set(cl["ids"]))
            else:
                df_resolved[svc] = {"q": quant or "one",
                                    "devices": sorted(cl["ids"])}
            if role == "read":       # notify/action/condition은 제외
                df_read.add(svc)

    return {
        "selected_services": selected_services,
        "df_selectors": df_selectors,
        "df_resolved": df_resolved,
        "df_read_services": df_read,
        "errors": v3_result.get("errors", []),
        "precision": {"selectors": df_selectors, "resolved": df_resolved,
                      "reasoning": "[v3] constraint-extract + grounded-select"},
    }


if __name__ == "__main__":
    import os
    import sys
    _here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, _here)
    sys.path.insert(0, os.path.dirname(_here))
    import run as R
    from resolver_v3 import resolve_v3

    for cmd in ["불 켜줘",
                "삼성 공기청정기를 모두 꺼줘",
                "문이 열리면 카메라로 촬영하고 'lindy@mysmax.kr' 이메일로 보내줘",
                "매시간 정각마다 스피커로 시간을 알려줘",
                "커튼 닫아줘"]:
        c = v3_to_pipeline_contract(resolve_v3(cmd, R.CONNECTED_DEVICES))
        print(f"\n══ {cmd}")
        print(f"  selected_services: {c['selected_services']}")
        print(f"  df_selectors     : {c['df_selectors']}")
        print(f"  df_read_services : {c['df_read_services']}")
        if c["errors"]:
            print(f"  errors           : {c['errors']}")
