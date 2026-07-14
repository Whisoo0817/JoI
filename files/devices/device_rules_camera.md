[Device Summary]
<Device "Camera">
  <Service "CameraState" type="value">Current camera operational state. Enum values: off, on, restarting, unavailable.</Service>
  <Service "Image" type="value">The latest snapshot image captured by the camera</Service>
  <Service "Video" type="value">The latest video clip captured by the camera</Service>
  <Service "RecordingActive" type="value">Whether local recording is currently in progress</Service>
  <Service "MicrophoneMuted" type="value">Whether the camera microphone is muted</Service>
  <Service "CaptureImage" type="action">Capture a still image and return it as binary JPEG data</Service>
  <Service "CaptureVideo" type="action">Capture a video clip of the given Duration (seconds) and return it as binary MP4 data</Service>
  <Service "StartRecording" type="action">Start local recording (continuous until StopRecording or storage exhausted)</Service>
  <Service "StopRecording" type="action">Stop the active local recording</Service>
  <Service "SetMicrophoneMuted" type="action">Mute or unmute the camera microphone (Muted: true=mute)</Service>
</Device>

# Rules

- `CameraState` is a **read-only** value (off/on/restarting/unavailable). There is NO `SetCameraState` action — you cannot write it.
- **Power the camera on/off via the `Switch` family** (a Camera device carries `Switch`): "카메라 켜/꺼", "turn the camera on/off" → `Switch.On` / `Switch.Off`, NOT `CameraState`.
- **Snapshot vs clip vs recording** — pick by intent:
  - A single picture/snapshot (사진/촬영/스냅샷) → `CaptureImage`.
  - Any video/recording request (영상/녹화/녹화 시작/N초 영상) → **prefer `CaptureVideo`** (takes a `Duration` in seconds and returns a finished MP4 you can attach/send). This is the default for "녹화해줘 / 녹화 시작해줘".
  - Use `StartRecording` / `StopRecording` ONLY when the command explicitly wants open-ended continuous recording with an explicit stop (e.g. "녹화 시작했다가 ~하면 멈춰", "keep recording until…"). ⚠️ `StartRecording` returns NOTHING — never assign its result or attach/send it. If the recording is to be sent/attached, you MUST use `CaptureVideo`.
- Mute/unmute the mic (마이크 음소거/해제) → `SetMicrophoneMuted`.
- 🛑 There is NO live-stream service. Streaming requests (스트림/라이브/streaming) cannot be fulfilled — do NOT map them to recording or capture.

# @ArgResolve

`CaptureVideo` arguments:
- **Duration** — length of the clip in seconds. Use the number the command states ("30초 영상" → 30). **If no duration is stated (e.g. "녹화해줘", "카메라 녹화 시작해줘", "영상 찍어줘"), default to `10`.**

```
[Command] 카메라 녹화 시작해줘   (no duration stated → default 10)
[Selected Services] ["Camera.CaptureVideo"]
Output:
{"Camera.CaptureVideo": {"Duration": 10}}
```
