# @ArgResolve

`SetAirPurifierMode.Mode` (ENUM: auto, sleep, low, medium, high, quiet, windFree, off). Map the command:
- "auto / 자동" → `auto`; "sleep / 취침" → `sleep`; "quiet / silent / 조용" → `quiet`; "wind-free / no cold draft / 무풍" → `windFree`
- "strong / strong wind / high / 세게 / 강" → `high`; "medium / 중간" → `medium`; "weak / low / 약하게 / 약" → `low`
- "off / 끄기 (as a mode)" → `off`

```
[Command] Put the air purifier in sleep mode.
[Selected Services] ["AirPurifier.SetAirPurifierMode"]
Output:
{"AirPurifier.SetAirPurifierMode": {"Mode": "sleep"}}
```
