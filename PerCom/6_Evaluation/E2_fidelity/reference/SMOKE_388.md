# SMOKE_388 — crash / REF-UNSUPPORTED scan (not a correctness result)

History: every catalog value (and zero-argument read-role function) of each connected device at a type-valid default at t=0 (BOOL false, numbers 0 clamped into the declared bound, STRING "", ENUM first member, other types missing), `Clock.IsHoliday` false, horizon 10000 ms, t_start 0.

Artefacts of this single default history (not program faults): `arg-range` for `SetChannel(Channel - 1)` with Channel 0, and `history-missing-nonnull` where a `MenuProvider.GetMenu(...)` query has no value (query keys with arguments are not pre-filled). Every other reason is a construct the reference refuses (see SPEC_GAPS.md).

## Candidate JoI blocks (388 files)

| status | count |
|---|---|
| ok | 294 |
| no-joi-block | 59 |
| unsupported | 34 |
| error | 1 |

### unsupported by reason

| reason | count | example |
|---|---|---|
| set-valued-selector | 11 | C01_008: REF-UNSUPPORTED[set-valued-selector]: all(#TemperatureSensor).temperatureSensor_temperature outside a comparison |
| capability | 9 | C06_001: REF-UNSUPPORTED[capability]: Bedroom_TempSensor lacks category AirQualitySensor for airQualitySensor_temperature |
| multi-device-query | 3 | C03_002: REF-UNSUPPORTED[multi-device-query]: IsAvailable = any(#CloudServiceProvider).cloudServiceProvider_isAvailable(...) |
| syntax | 3 | C21_001: REF-UNSUPPORTED[syntax]: 1:54 no viable alternative at input '(all(#PresenceSensor).presenceSensor_presence=='; 1:29 extraneous input '.' expecting {' |
| effectful-return | 2 | C01_015: REF-UNSUPPORTED[effectful-return]: GenerateImage = CloudServiceProvider.GenerateImage(...) (SERVICE_MODEL §2) |
| arg-domain | 2 | C01_023: REF-UNSUPPORTED[arg-domain]: RobotVacuumCleaner.SetRobotVacuumCleanerRunMode.Mode: 'stop' not in RobotVacuumCleanerRunModeEnum |
| selector-no-device | 2 | C08_032: REF-UNSUPPORTED[selector-no-device]: (#Hall_Light_1) |
| arg-range | 1 | C01_006: REF-UNSUPPORTED[arg-range]: Television.SetChannel.Channel: -1 outside [0, 10000] |
| arith-type | 1 | C24_003: REF-UNSUPPORTED[arith-type]: None + 1 |

### error by reason

| reason | count | example |
|---|---|---|
| history-missing-nonnull | 1 | C01_018: REF-ERROR[history-missing-nonnull]: System_MenuProvider.GetMenu('오늘 301동식당 점심',) must be a STRING |

Files without a JoI block (generation error codes): device_not_connected 59

## Dataset IRs with binding_gt (388 rows)

| status | count |
|---|---|
| ok | 380 |
| unsupported | 7 |
| error | 1 |

### unsupported by reason

| reason | count | example |
|---|---|---|
| effectful-return | 2 | C01#15: REF-UNSUPPORTED[effectful-return]: CloudServiceProvider.GenerateImage return assignment (SERVICE_MODEL §2) |
| multi-device-query | 2 | C15#9: REF-UNSUPPORTED[multi-device-query]: MenuProvider.GetMenu on ['Main_MenuProvider', 'Office_MenuProvider'] |
| arg-range | 1 | C01#6: REF-UNSUPPORTED[arg-range]: Television.SetChannel.Channel: -1 outside [0, 10000] |
| ir-call-var | 1 | C17#3: REF-UNSUPPORTED[ir-call-var]: 'Speaker.Volume' |
| read-quantifier | 1 | C18#6: REF-UNSUPPORTED[read-quantifier]: MotionSensor.Motion bound to all ['Main_MotionSensor', 'Garage_MotionSensor'] outside a comparison |

### error by reason

| reason | count | example |
|---|---|---|
| history-missing-nonnull | 1 | C01#18: REF-ERROR[history-missing-nonnull]: System_MenuProvider.GetMenu('오늘 301동식당 점심',) must be a STRING |
