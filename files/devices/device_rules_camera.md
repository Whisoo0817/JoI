[Device Summary]
<Device "Camera">
  <Service "CameraState" type="value">Current camera state. Enum values: off, on, restarting, unavailable.</Service>
  <Service "Image" type="value">The latest image captured by the camera</Service>
  <Service "Stream" type="value">The current video stream from the camera</Service>
  <Service "Video" type="value">The latest video captured by the camera</Service>
  <Service "CaptureImage" type="action">Take a picture with the camera - Return the image as binary data</Service>
  <Service "CaptureVideo" type="action">Take a video with the camera - Return the video as binary data</Service>
  <Service "StartStream" type="action">Start the camera stream - Return the stream URL</Service>
  <Service "StopStream" type="action">Stop the camera stream</Service>
</Device>

# Rules

- `CameraState` is a **read-only** value (off/on/restarting/unavailable). There is NO `SetCameraState` action — you cannot write it.
- **Power the camera on/off via the `Switch` family** (a Camera device carries `Switch`): "카메라 켜/꺼", "turn the camera on/off" → `Switch.On` / `Switch.Off`, NOT `CameraState`.
- Capture/stream actions (`CaptureImage`, `CaptureVideo`, `StartStream`, `StopStream`) are the camera's own functions; use them for picture/video/streaming requests.

# Camera Examples

[Command]
Turn off the camera
["Switch.Off"]

[Command]
Take a picture with the Camera
["Camera.CaptureImage"]

[Command]
Start the video stream on the Camera
["Camera.StartStream"]

[Command]
Stop the camera stream
["Camera.StopStream"]

[Command]
Record a video with the camera
["Camera.CaptureVideo"]

[Command]
Check the current CameraState
["Camera.CameraState"]

[Command]
When the camera becomes unavailable, send a notification
["Camera.CameraState", "ToastPublisher.Publish"]
