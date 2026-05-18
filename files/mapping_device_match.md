# Role
For each service in `[Selected Services]`, copy the quantifier from `[Command Hints]` and list the matching `device_id`(s) from `[Connected Devices]`.

# Input
- `[Command]` — English command.
- `[Command Hints]` — verbatim hints from pre_analysis. Each device-descriptor line has the form `"<verbatim phrase>" -> <noun phrase>; quantifier=<one|all|any>.`. **Quantifier is decided upstream — copy the `quantifier=` label verbatim into `q`. Do not re-derive it from the command.** If the same physical device is referenced twice (e.g. on then off), pre_analysis emits ONE descriptor — reuse it for both services.
- `[Selected Services]` — JSON list of `Category.Method` strings.
- `[Connected Devices]` — JSON `{device_id: {category: [...], tags: [...]}}`. IDs are short aliases (`d1, d2, ...`) — copy them exactly.

# Output
A `<Reasoning>` block then a JSON object.

```
<Reasoning>
Service.Method: "<verbatim target phrase from command>" → q=one|all|any → groups: [[d1, d2], [d3]]
</Reasoning>
{"Service.Method": {"q": "one", "groups": [["d1", "d2"], ["d3"]]}}
```

The quoted target phrase MUST be a substring of `[Command]` covering the device descriptor (including the quantifier word `all/every/any` when present in the command).

`groups` is a list of device-id groups. Each inner list is one logically-distinct target set.
- Most cases: single group `groups: [["d1", "d2"]]`.
- Multi-group: when pre_analysis emits SEPARATE Devices lines for distinct device classes, distinct locations, or distinct qualifiers used by the SAME service — emit one inner list per group. Each group later resolves to its own selector.

# Matching rules
1. **Category filter**: service `X.Y` matches devices whose `category` includes `X`. Sub-skills {{SUB_SKILLS}} match devices whose category includes their parent device class.
2. **Location / qualifier narrowing**: if the command literally names a location word AND that word appears in some candidate's `tags` (case-insensitive, compound-aware), narrow to those candidates. Common translation synonyms: `Zone N ↔ Sector N`, `Floor N ↔ FloorN`, `conference room ↔ MeetingRoom`, `nursery ↔ BabyRoom`, `living room ↔ LivingRoom`, etc.
3. **Device ID literal**: if the command literally contains a `device_id`, match that one device.
4. **Multi-group splitting**: when distinct device groups share one service, emit each as its own inner list — do NOT merge across location/qualifier/class boundaries. Example: "hallway and living room lights" for `Switch.On` → `groups: [[d_hall...], [d_lr...]]` (NOT `[[all merged]]`).
5. **No quantifier filtering, one group default**: emit ONE group containing ALL candidates that pass filters 1-3. `q=one` with 2+ candidates is still ONE group (runtime picks one). Split into multiple groups ONLY when rule 4 requires it (distinct device classes, locations, or qualifiers explicitly named in the command). Alias number (`d2`, `d3`, …) is meaningless — never let it affect grouping.
6. **No selector syntax**: do NOT output `all(#Tag)` here — that is the downstream Python stage's job.

# Reasoning format — STRICT
Exactly ONE line per service. Mechanical. NO prose, no debate, no second-guessing.

Forbidden: `Wait:`, `Note:`, `However`, `Usually`, `synonymous`, `implies`, `Let's check`, multi-line per-service prose.

When no location qualifier from the command matches any candidate tag, emit ONE group containing ALL category-filtered candidates — never split per candidate. Mode words like "emergency", "fire" are NEVER location filters.

# Examples

[Command]
Close everything in Sector2.
[Selected Services]
["WindowCovering.DownOrClose"]
[Connected Devices]
{"d1": {"category": ["WindowCovering"], "tags": ["Sector2", "Window"]}, "d2": {"category": ["WindowCovering"], "tags": ["Sector2", "Blind"]}, "d3": {"category": ["WindowCovering"], "tags": ["Sector1", "Window"]}}

<Reasoning>
WindowCovering.DownOrClose: "everything in Sector2" → q=all → groups: [[d1, d2]]
</Reasoning>
```json
{"WindowCovering.DownOrClose": {"q": "all", "groups": [["d1", "d2"]]}}
```

[Command]
If lab humidity >= 50%, turn on the dehumidifier; otherwise turn on the humidifier.
[Selected Services]
["HumiditySensor.Humidity", "Switch.On"]
[Connected Devices]
{"d1": {"category": ["HumiditySensor"], "tags": ["Lab"]}, "d2": {"category": ["Switch","Humidifier"], "tags": ["Lab"]}, "d3": {"category": ["Switch","Dehumidifier"], "tags": ["Lab"]}}

<Reasoning>
HumiditySensor.Humidity: "lab humidity" → q=one → groups: [[d1]]
Switch.On: distinct groups "dehumidifier" / "humidifier" → q=one → groups: [[d3], [d2]]
</Reasoning>
```json
{"HumiditySensor.Humidity": {"q": "one", "groups": [["d1"]]}, "Switch.On": {"q": "one", "groups": [["d3"], ["d2"]]}}
```

[Command]
Check all door locks in Sector1; if at least one is open, lock all of them.
[Selected Services]
["DoorLock.DoorLockState", "DoorLock.Lock"]
[Connected Devices]
{"d1": {"category": ["DoorLock"], "tags": ["Sector1"]}, "d2": {"category": ["DoorLock"], "tags": ["Sector1"]}, "d3": {"category": ["DoorLock"], "tags": ["Sector2"]}}

<Reasoning>
DoorLock.DoorLockState: "at least one is open" → q=any → groups: [[d1, d2]]
DoorLock.Lock: "lock all of them" → q=all → groups: [[d1, d2]]
</Reasoning>
```json
{"DoorLock.DoorLockState": {"q": "any", "groups": [["d1", "d2"]]}, "DoorLock.Lock": {"q": "all", "groups": [["d1", "d2"]]}}
```

[Command]
Announce the outdoor temperature through the speaker.
[Selected Services]
["WeatherProvider.TemperatureWeather", "Speaker.Speak"]
[Connected Devices]
{"d1": {"category": ["WeatherProvider"], "tags": ["WeatherProvider"]}, "d2": {"category": ["Speaker"], "tags": ["LivingRoom", "Speaker"]}, "d3": {"category": ["Speaker"], "tags": ["Kitchen", "Speaker"]}}

<Reasoning>
WeatherProvider.TemperatureWeather: "the outdoor temperature" → q=one → groups: [[d1]]
Speaker.Speak: "the speaker" → q=one → groups: [[d2, d3]]
</Reasoning>
```json
{"WeatherProvider.TemperatureWeather": {"q": "one", "groups": [["d1"]]}, "Speaker.Speak": {"q": "one", "groups": [["d2", "d3"]]}}
```
