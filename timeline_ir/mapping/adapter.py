"""Mapping result → lowering pipeline contract adapter.

generate.py의 device-first 접합점(현행 selector→IR 계약 변환, 대략 L1003-1040)이
만드는 변수들을 resolver 출력에서 동일하게 생성한다. resolver는 실제 태그/
디바이스 id로 작업하므로 현행의 dN 익명화·복원(real_of) 경로가 불필요하다.

반환 계약 (generate.py L1043~ 공유 경로가 기대하는 것):
  selected_services : list[str]  "Cat.Method" (선택 순서, 중복 허용 — 현행과 동일)
  df_selectors      : {svc: ["<quant>(#tag ...)"]}
  df_resolved       : {svc: {"q": quant|"one", "devices": [real_id, ...]}}
  df_read_services  : set[svc]   role=="read"인 것만 (condition 게이트 read는 제외 —
                                 arg_resolve가 $<ref>로 오용하는 것 방지, 현행 주석 참조)
  errors            : list[str]  resolver가 귀속한 실현 불가 사유와 지원 계약
                                 위반 (비면 정상)

지원 계약: 하나의 Service.Method에는 서로 다른 selector를 하나만 허용한다.
한 selector의 all(...)이 여러 기기에 fan-out하는 것은 허용한다. 동일 selector가
여러 번 산출되면 하나로 정규화하고, 서로 다른 selector가 필요하면 fail-closed
오류를 반환한다. 이는 selector 분할을 별도 JoI call로 낮출 때 IR의 단일 call
경계와 충돌하는 경우를 현재 논문/검증 범위에서 제외하기 위한 제한이다.
"""


def to_pipeline_contract(mapping_result):
    selected_services = []
    df_selectors, df_resolved, df_read = {}, {}, set()
    errors = list(mapping_result.get("errors", []))

    for grp in mapping_result["groups"]:
        role = grp["role"]
        for cl in grp["clusters"]:
            svc = cl.get("svc")
            if not svc:
                continue
            quant = cl.get("quant", "") or ""
            sel = "(#" + " #".join(cl["sel"]) + ")"
            rendered = f"{quant}{sel}"
            selected_services.append(svc)
            selectors = df_selectors.setdefault(svc, [])
            if rendered not in selectors:
                if selectors:
                    errors.append(
                        f"{svc}: multiple selectors are outside the supported "
                        f"contract ({selectors[0]} / {rendered})"
                    )
                selectors.append(rendered)
            # devices는 실제 id (cl["ids"]가 이미 real payload id).
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
        "errors": errors,
        "precision": {"selectors": df_selectors, "resolved": df_resolved,
                      "reasoning": "constraint-extract + grounded-select"},
    }
