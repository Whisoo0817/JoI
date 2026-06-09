[Device Summary]
<Device "Speaker">
  <Service "PlaybackState" type="value">Current playback state. Enum values: paused, playing, stopped, fastforwarding, rewinding, buffering.</Service>
  <Service "Volume" type="value">Current volume level (INTEGER, 0-100)</Service>
  <Service "FastForward" type="action">Fast forward playback</Service>
  <Service "Pause" type="action">Pause playback</Service>
  <Service "Play" type="action">Play media</Service>
  <Service "Rewind" type="action">Rewind playback</Service>
  <Service "SetVolume" type="action">Set volume to a specific value</Service>
  <Service "Speak" type="action">Output text as speech (TTS)</Service>
  <Service "Stop" type="action">Stop playback</Service>
  <Service "VolumeDown" type="action">Decrease volume by one step</Service>
  <Service "VolumeUp" type="action">Increase volume by one step</Service>
</Device>

# Speaker Examples

[Command]
Play the speaker
["Speaker.Play"]

[Command]
Pause the speaker
["Speaker.Pause"]

[Command]
Set the speaker volume to 80
["Speaker.SetVolume"]

[Command]
Increase the speaker volume
["Speaker.VolumeUp"]

[Command]
Announce that dinner is ready through the speaker
["Speaker.Speak"]

[Command]
What is the current speaker volume?
["Speaker.Volume"]

[Command]
When the speaker starts playing, do something
["Speaker.PlaybackState"]

[Command]
Raise the speaker volume by 5
["Speaker.Volume", "Speaker.SetVolume"]


# @ArgResolve

`Speak.Text` with embedded `$Var` — wrap or pass raw based on what produced the variable:
- **Sensor / provider single fact** (e.g. `$Weather` from `WeatherProvider.Weather`, `$Temp` from `TemperatureSensor.Temperature`, `$TodayMenu`): wrap with a short NL-implied lead-in drawn from the command's own wording. Example: command "오늘의 날씨를 말해줘" / "Announce today's weather through the speaker" → `Speak.Text = "Today's weather is $Weather"`. Do NOT invent filler like "Hi!" or "Here's the info...".
- **Function-call return that is already a complete sentence** (e.g. `$ChatWithAI`, `$AskQuestion`): pass raw. `Speak.Text = "$ChatWithAI"` — NOT `"The answer is $ChatWithAI"`.

`SetVolume.Volume` accepts INTEGER 0–100. "maximum" / "최대" → `100`. "minimum" / "최소" → `0`. "half" / "절반" → `50`.

Example — provider read + speaker prefix (English input → English Text):
```
[Command] Announce today's weather through the speaker.
[Selected Services] ["WeatherProvider.Weather", "Speaker.Speak"]
Output:
{"Speaker.Speak": {"Text": "Today's weather is $Weather"}}
```
Plain announcement (English input → English Text):
```
[Command] Announce that the meeting starts at 2 PM through the speaker.
[Selected Services] ["Speaker.Speak"]
Output:
{"Speaker.Speak": {"Text": "The meeting starts at 2 PM."}}
```

# @ArgResolveKo

`Speak.Text`는 사용자에게 들리는 음성이다. 한글 입력일 때는 **한글 존댓말 평서문**("~합니다" / "~하세요")으로, `[User Command (original, verbatim)]`의 표현·시각·대상을 살려 자연스러운 안내문 한 문장으로 작문한다. 명령을 그대로 복붙하지 말 것. 따옴표 인용 리터럴은 그대로 사용.

`$Var` 임베드 규칙(공통):
- **센서/프로바이더 단일 값** (`$Weather`, `$Temp`, `$TodayMenu` 등): 명령 표현에서 끌어온 짧은 한글 lead-in으로 감싼다. 예: "오늘 날씨 말해줘" → `Speak.Text = "오늘의 날씨는 $Weather 입니다"`. "Hi!" 같은 군더더기 금지.
- **이미 완성 문장인 함수 반환** (`$ChatWithAI` 등): 그대로 전달. `"$ChatWithAI"`.

`SetVolume.Volume`은 INTEGER 0–100. "최대"→`100`, "최소"→`0`, "절반"→`50`.

예시:
```
[Command] Announce that the meeting starts at 2 PM through the speaker.
[User Command (original, verbatim)] 오후 2시에 회의를 시작한다고 스피커로 알려줘
[Selected Services] ["Speaker.Speak"]
Output:
{"Speaker.Speak": {"Text": "현재 시각 오후 2시. 회의를 시작합니다."}}
```
```
[Command] Tell me to ventilate through the speaker.
[User Command (original, verbatim)] 환기하라고 스피커로 알려줘
[Selected Services] ["Speaker.Speak"]
Output:
{"Speaker.Speak": {"Text": "환기해 주세요."}}
```
```
[Command] Announce today's weather through the speaker.
[User Command (original, verbatim)] 오늘 날씨 스피커로 알려줘
[Selected Services] ["WeatherProvider.Weather", "Speaker.Speak"]
Output:
{"Speaker.Speak": {"Text": "오늘의 날씨는 $Weather 입니다"}}
```
