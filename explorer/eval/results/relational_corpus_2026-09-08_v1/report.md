# 관계 경로의 기존 후보 전체 적용 — 2026-09-08

같은388개 ID를 모두 포함했다. LLM 재생성0회.

- 구조/준비 거절327, 기존 생성 실패59, 준비 오류2.
- 관계 엔진 진입0, 신규 corpus EQUIV-FIXPOINT0.
- 개발 fixture의 인증6건과 corpus 결과를 합산하지 않는다.
- 기존 bounded 인증208건은 여전히 H=3.2초 결과다.
- 총 실행 시간으로 summary의0.012초를 인용하지 않는다: 이는 준비 이후 결과 기록 단계 시간이며 준비 작업 시간은 포함하지 않는다.

## 구조/준비 거절 이유

- 195건: relational path needs IrRunner and periodic PauseRunner
- 50건: relational v1 needs a preserved unbounded named counter
- 30건: relational v1 needs one top-level named cycle
- 12건: relational path needs positive period and no clock reads
- 11건: group read needs an explicit comparison
- 10건: relational v1 cycle period/until is unsupported
- 3건: any method call is not an existential property comparison
- 2건: catalog type/domain mismatch: ('RobotVacuumCleaner', 'SetRobotVacuumCleanerRunMode').Mode expects ENUM, got 'stop'
- 2건: device Bedroom_TempSensor does not declare capability AirQualitySensor
- 2건: query result requires exactly one bound device
- 1건: return-assigned/effectful or unreviewed function cannot be a silent input: ('CloudServiceProvider', 'GenerateImage')
- 1건: return-assigned/effectful or unreviewed function cannot be a silent input: ('CloudServiceProvider', 'ChatWithAI')
- 1건: device Bedroom_HumiditySensor does not declare capability AirQualitySensor
- 1건: device LivingRoom_TempSensor does not declare capability AirQualitySensor
- 1건: device SR_Humid does not declare capability AirQualitySensor
- 1건: return-assigned/effectful or unreviewed function cannot be a silent input: ('Speaker', 'SetVolume')
- 1건: device Grp2_Hum_1 does not declare capability AirQualitySensor
- 1건: device Office_Printer does not declare capability Charger
- 1건: device LivingRoom_TV does not declare capability Charger
- 1건: device Kitchen_Charger does not declare capability Charger
