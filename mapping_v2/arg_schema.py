"""arg_resolve용 guided_json 스키마 자동 생성기 (프로토타입).

카탈로그(SERVICE_DATA)의 각 인자 type/enum members에서 JSON 스키마를 만들어,
arg_resolve LLM 호출에 guided_json으로 강제하면:
  - enum 환각 불가 (멤버 밖 값이 디코딩 레벨에서 차단)
  - 타입 강제 (Duration이 문자열로 안 나옴)
  - 액션 인자의 enum 결정이 arg_resolve에서 처리 → enum_resolve 별도 호출 축소
자유 텍스트 인자(ToastPublisher Message, Speaker Text, 메일 본문)는 string이라
$<ref> 체이닝 참조도 그대로 허용된다.

build_arg_schema(arg_services, details) → JSON Schema dict.
details = extract_service_details(selected_services, SERVICE_DATA) 형식.
"""


def _arg_prop(a):
    atype = a.get("type")
    if atype == "ENUM":
        members = [str(v).split(" - ")[0].strip() for v in a.get("enum_list", [])]
        return {"enum": members} if members else {"type": "string"}
    if atype in ("DOUBLE", "FLOAT", "INT", "INTEGER", "LONG"):
        return {"type": "number"}
    if atype == "BOOL":
        return {"type": "boolean"}
    return {"type": "string"}   # STRING, BINARY, 기타 → 문자열($ref 허용)


def build_arg_schema(arg_services, details):
    props = {}
    for svc in arg_services:
        if "." not in svc:
            continue
        dev, method = svc.split(".", 1)
        method = method.replace("()", "")
        info = (details.get(dev) or {}).get(method) or {}
        args = info.get("arguments", []) if isinstance(info, dict) else []
        aprops, req = {}, []
        for a in args:
            aid = a.get("id")
            if not aid:
                continue
            aprops[aid] = _arg_prop(a)
            req.append(aid)
        props[svc] = {"type": "object", "properties": aprops,
                      "required": req, "additionalProperties": False}
    return {"type": "object", "properties": props,
            "required": list(props), "additionalProperties": False}


if __name__ == "__main__":
    import json
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from loader import SERVICE_DATA
    from pipeline_helpers import extract_service_details

    # enum·숫자·자유텍스트가 섞인 대표 서비스로 스키마 생성 확인
    svcs = ["AirConditioner.SetAirConditionerMode", "Camera.CaptureVideo",
            "ToastPublisher.Publish", "EmailProvider.SendMailWithBinaryFile",
            "RobotVacuumCleaner.SetRobotVacuumCleanerCleaningMode"]
    details = extract_service_details(svcs, SERVICE_DATA)
    schema = build_arg_schema(svcs, details)
    print(json.dumps(schema, ensure_ascii=False, indent=2))
