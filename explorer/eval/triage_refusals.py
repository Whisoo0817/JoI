"""Post-outcome diagnostic attribution of fresh-v4's 46 preparation refusals.

No production/source-candidate mutation, no replacement of benchmark verdicts.
Primary categories count each case once; secondary problems can overlap.
"""
import argparse
from collections import Counter
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


GROUPS = [
    ('generated_contract_mismatch', 'code_capability',
     '생성 코드가 해당 장치에 선언되지 않은 서비스를 사용한다. inventory의 category와 대조했으며 서비스 alias로 간주하지 않는다.',
     'C06_001 C06_003 C06_005 C06_006 C12_010 C17_008 C20_004 C20_011 C20_016'),
    ('generated_contract_mismatch', 'wrong_method_enum',
     'IR의 CleaningMode(stop)를 코드가 RunMode(stop)로 바꿨다. stop은 CleaningMode enum에는 있고 RunMode에는 없다.',
     'C01_023 C02_018'),
    ('generated_contract_mismatch', 'group_in_scalar_position',
     'IR은 한 기기 값을 읽지만 생성 코드는 실제 두 기기에 매칭되는 all/any 집합 읽기를 scalar 대입/인자에 사용한다. 현 scalar 계약·binding과 불일치한다. JoI 전체에서 모든 집합 연산이 불법이라는 판정은 아니다.',
     'C01_008 C01_010 C01_013 C01_016 C03_003 C03_007 C15_008 C17_002 C17_006 C21_005'),
    ('generated_contract_mismatch', 'any_action',
     'any는 조건의 존재 양화사인데 두 기기에 매칭되는 ACTION 호출에 사용됐다. 현 계약에 선택 실행 의미가 없어 거절하며 임의로 첫 기기로 고치지 않는다.',
     'C03_008 C03_012'),
    ('reference_catalog_mismatch', 'void_return_assignment',
     '정답 IR의 call.var가 실제 카탈로그 VOID 함수의 반환값을 받도록 되어 있다. 현 IR 계약에서 var는 반환값 대입이다. 생성 코드에 책임을 전가하거나 반환 대입을 지워 통과시키지 않는다.',
     'C01_006 C01_017 C14_001 C14_005 C14_006'),
    ('reference_catalog_mismatch', 'missing_reference_argument',
     '정답 IR의 IsAvailable args가 비어 있지만 현재 카탈로그는 ServiceName 인자를 요구한다. 코드도 인자를 생략한다. 원본 명세/정답 데이터 정합성 점검 대상이다.',
     'C03_002'),
    ('intentional_unsupported', 'unbounded_modulo_counter',
     '증가하는 n을 나머지 연산 조건에 사용한다. 현재 유한성 인증 밖이며 기존 거절 정책을 유지한다. modulo 전용 추상화를 새로 증명하기 전 임의 포화/축소하지 않는다.',
     'C13_001 C13_002 C13_003 C13_004 C13_005 C13_006 C13_007 C14_003'),
    ('intentional_unsupported', 'unreviewed_or_effectful_return',
     'GenerateImage/ChatWithAI/SetVolume의 반환 대입은 검토된 읽기 함수 모델 밖이다. ACTION과 반환을 동시에 모델링하지 않은 채 조용한 입력으로 바꾸지 않는 합의된 거절이다.',
     'C01_015 C01_019 C17_003'),
    ('intentional_unsupported', 'arithmetic_observation',
     '센서 값의 산술 변형이 ACTION 인자/파생 조건으로 흐른다. 이미 합의한 D7 arith-arg/derived-guard 거절이다.',
     'C14_002'),
    ('intentional_unsupported', 'multi_device_return',
     '정답 binding 자체가 MenuProvider 두 대의 반환을 하나의 scalar 변수로 받는다. 현 IR/explorer에 반환 집계/선택 규칙이 없으므로 의도적으로 거절한다.',
     'C15_009 C15_010'),
    ('input_model_limit', 'large_finite_observable',
     'TemperatureWeather는 [-470,10000] DOUBLE이다. 0.1 격자 값 104701개(+결측/표현 구분)가 필요해 자동 exact-domain 생성 한도를 넘는다. 단순히 무한 센서라서 거절한 것은 아니다.',
     'C01_009'),
    ('input_model_limit', 'unbounded_string_observable',
     'GetMenu의 일반 STRING 반환을 Speak에 그대로 전달한다. 카탈로그에 유한 문자열 집합이 없어 전체값 열거 모델을 자동으로 만들 수 없다. 임의 샘플을 전체 도메인으로 부르지 않는다.',
     'C01_018'),
    ('frontend_extension_candidate', 'bare_boolean_any',
     'BOOL Motion의 any를 not 조건에서 맨 읽기로 사용한다. 현재 grounding은 명시 비교만 펼치므로 거절한다. bool 위치에서 == true로 정규화하는 작은 확장 후보다. 해당 후보 전체의 동등성을 보장한다는 뜻은 아니다.',
     'C18_006'),
]

SECONDARY = {
    'C01_006': ['arith-arg; var 제거만으로 D7 문제가 사라지지 않음'],
    'C03_003': ['arith-arg; 집합 읽기 정리만으로 지원되지 않음'],
    'C03_002': ['코드도 필수 인자 누락', 'IR 두 기기 query 반환의 scalar 집계 규칙 부재', 'catalog ServiceName의 설명은 name이나 타입은 BOOL; 명세 자체도 확인 필요'],
    'C14_001': ['arith-arg/derived-guard', 'IR period100ms, 코드 period1000ms'],
    'C14_005': ['arith-arg/derived-guard', '코드 LevelControl 태그에 Light 서비스 사용 확인 필요'],
    'C14_006': ['arith-arg/derived-guard'],
    'C14_003': ['n 증가 시점이 IR cycle 완료와 코드 매회 실행에서 달라 추가 의미 차이 가능'],
    'C17_003': ['arith-arg', '코드 다중 Speaker scalar 읽기'],
    'C18_006': ['맨 bool any를 명시 비교로 바꾼 진단용 복사본은 현재 IR과 DIVERGE; 아래 probe 참조'],
    'C21_005': ['서로 다른 방의 두 IR 읽기를 코드에서 같은 all 집합으로 반복', 'Switch target selector도 전체 검토 필요'],
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def nodes(value):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from nodes(v)
    elif isinstance(value, list):
        for v in value:
            yield from nodes(v)


def main():
    from explorer.verification.gate import prepare_pair, pair_input_domains, gate_pair
    from explorer.verification.product import check_supported_pair
    from explorer.verification.input_coverage import initial_domains
    from explorer.verification.service_model import ServiceModel
    from explorer.runtime.interp import Unsupported
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    manifest_path = ROOT / 'explorer/eval/results/contract_fresh_v4_2026-09-07_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    source_paths = [manifest_path, Path(__file__).resolve(), ROOT / 'docs/JOI_SPEC.md',
                    ROOT / 'explorer/docs/model/SUPPORTED_FRAGMENT.md', ROOT / 'explorer/docs/model/SERVICE_MODEL.md',
                    ROOT / 'explorer/docs/proof/FRONTEND_CORRECTNESS.md', ROOT / 'timeline_ir/catalog.py']
    source_paths += sorted((ROOT / 'explorer').rglob('*.py'))
    model = ServiceModel({})
    source_paths.append(Path(model.snapshot['path']))
    before = {str(p.relative_to(ROOT)): sha(p) for p in source_paths}
    assignments = {}
    for category, subcategory, reason, ids in GROUPS:
        for key in ids.split():
            assert key not in assignments
            assignments[key] = (category, subcategory, reason)
    refused = [c for c in manifest['cases'] if c['status'] == 'REFUSED']
    assert len(refused) == 46 and set(assignments) == {c['id'] for c in refused}
    rows = []
    for c in refused:
        p = c['payload']
        assert sha(ROOT / c['candidate_path']) == c['candidate_sha256']
        category, subcategory, why = assignments[c['id']]
        stage = 'prepare_pair'
        try:
            pair = prepare_pair(p['ir'], p['binding'], p['devices'], p['joi_block'])
            stage = 'pair_input_domains'
            domains = pair_input_domains(pair)
            stage = 'check_supported_pair'
            axes = check_supported_pair(pair.ir_runner, pair.code_runner, input_domains=domains)
            stage = 'initial_domains'
            initial_domains(axes)
            raise AssertionError('refusal no longer reproduced: ' + c['id'])
        except Unsupported as e:
            assert str(e) == c['reason'], (c['id'], c['reason'], str(e))
        facts = []
        for n in nodes(p['ir']):
            if n.get('op') == 'call' and n.get('var'):
                spec = model.resolve(*n['target'].split('.', 1), 'function')
                facts.append({'ir_target': n['target'], 'ir_var': n['var'],
                              'catalog_return': spec['return_spec']})
        if subcategory == 'void_return_assignment':
            assert any(f['catalog_return']['type'] == 'VOID' for f in facts)
        if c['id'] == 'C03_002':
            facts.append({'required_arguments': model.resolve('CloudServiceProvider', 'IsAvailable', 'function')['arguments']})
        try:
            ServiceModel(p['devices']).normalize_ir(p['ir'], p['binding'])
            reference_check = {'status': 'PASS', 'scope': 'catalog normalization only; not full reference correctness'}
        except Unsupported as e:
            reference_check = {'status': 'REFUSED', 'reason': str(e)}
        rows.append({'id': c['id'], 'original_status': c['status'], 'original_reason': c['reason'],
                     'reproduced_stage': stage, 'reproduced_exact_reason': True,
                     'primary_category': category, 'subcategory': subcategory, 'rationale': why,
                     'secondary_findings': SECONDARY.get(c['id'], []),
                     'reference_catalog_check': reference_check, 'catalog_facts': facts,
                     'candidate_path': c['candidate_path'], 'candidate_sha256': c['candidate_sha256'],
                     'payload': p})
    c = next(c for c in refused if c['id'] == 'C18_006')
    p = copy.deepcopy(c['payload'])
    old = 'any(#MotionSensor).motionSensor_motion'
    assert p['joi_block']['script'].count(old) == 1
    p['joi_block']['script'] = p['joi_block']['script'].replace(old, old + ' == true')
    probe = gate_pair(p['ir'], p['binding'], p['devices'], p['joi_block'], horizon_ms=0)
    assert probe.verdict == 'DIVERGE' and probe.confirmed
    result = {'scope': 'post-outcome attribution of all 46 preparation REFUSED rows; original verdicts preserved',
              'source_hashes': before, 'total': len(rows),
              'primary_counts': dict(Counter(r['primary_category'] for r in rows)),
              'subcategory_counts': dict(Counter(r['subcategory'] for r in rows)),
              'limits': ['Primary attribution is not an exhaustive diagnosis; secondary issues may overlap.',
                         'generated_contract_mismatch is under fixed scalar/selector contract, not proof of universal JoI-language invalidity.',
                         'No original REFUSED case is relabeled DIVERGE/EQUIV; diagnostic copy is not a new benchmark row.',
                         'Reference catalog checks do not prove reference correctness against natural-language intent.',
                         'Counter/catalog mismatch fixes are not authorized or implemented by this classification task.'],
              'cases': rows,
              'diagnostic_probe': {'id': 'C18_006-explicit-bool-copy', 'script': p['joi_block']['script'],
                                   'horizon_ms': 0, 'result': asdict(probe),
                                   'interpretation': 'Explicit bool form is preparable but diverges: IR currently negates AND over all-bound Motion, whereas code negates existential OR. Does not establish the original code is accepted or equivalent.'}}
    assert all(sha(ROOT / path) == h for path, h in before.items())
    for c in refused:
        assert sha(ROOT / c['candidate_path']) == c['candidate_sha256']
    with Path(args.output).open('x') as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=repr)
        f.write('\n')
    print(json.dumps(result['primary_counts'], ensure_ascii=False))


if __name__ == '__main__':
    main()
