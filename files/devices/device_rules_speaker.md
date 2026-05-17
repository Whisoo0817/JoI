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

Example — provider read + speaker prefix:
```
[Command] Announce today's weather through the speaker.
[Selected Services] ["WeatherProvider.Weather", "Speaker.Speak"]
Output:
{"Speaker.Speak": {"Text": "Today's weather is $Weather"}}
```
