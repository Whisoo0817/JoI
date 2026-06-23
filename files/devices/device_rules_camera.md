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
  - A short fixed-length video clip (짧은 영상/N초 영상) → `CaptureVideo` (takes a `Duration` in seconds).
  - Start/stop continuous local recording (녹화 시작/중지) → `StartRecording` / `StopRecording`.
- Mute/unmute the mic (마이크 음소거/해제) → `SetMicrophoneMuted`.
- 🛑 There is NO live-stream service. Streaming requests (스트림/라이브/streaming) cannot be fulfilled — do NOT map them to recording or capture.

# Camera Examples

[Command]
Turn off the camera
["Switch.Off"]

[Command]
Take a picture with the camera
["Camera.CaptureImage"]

[Command]
Record a 10-second video with the camera
["Camera.CaptureVideo"]

[Command]
Start recording on the camera
["Camera.StartRecording"]

[Command]
Stop the camera recording
["Camera.StopRecording"]

[Command]
Mute the camera microphone
["Camera.SetMicrophoneMuted"]

[Command]
Check the current CameraState
["Camera.CameraState"]

[Command]
When the camera becomes unavailable, send a notification
["Camera.CameraState", "ToastPublisher.Publish"]
