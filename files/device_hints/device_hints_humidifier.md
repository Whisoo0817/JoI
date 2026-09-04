# @ArgResolve

`SetHumidifierMode.Mode` (ENUM: auto, low, medium, high). Map the command's strength word:
- "auto / 자동" → `auto`
- "weak / low / 약하게 / 약" → `low`
- "medium / 중간" → `medium`
- "strong / high / max / 세게 / 강" → `high`

```
[Command] Set the humidifier to the strongest mode.
[Selected Services] ["Humidifier.SetHumidifierMode"]
Output:
{"Humidifier.SetHumidifierMode": {"Mode": "high"}}
```
