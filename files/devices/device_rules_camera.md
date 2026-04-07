[Device Summary]
<Device "Camera">
  <Service "CameraState" type="value">Camera state (on, off, restarting, unavailable)</Service>
  <Service "Image" type="value">Recently captured image</Service>
  <Service "Video" type="value">Recently captured video</Service>
  <Service "Stream" type="value">Current video stream URL</Service>
  <Service "StartStream" type="action">Start streaming</Service>
  <Service "StopStream" type="action">Stop streaming</Service>
  <Service "CaptureImage" type="action">Take a picture</Service>
  <Service "CaptureVideo" type="action">Take a video</Service>
</Device>

# Camera Examples

[Command]
Take a picture with the Camera
["Camera.CaptureImage"]

[Command]
Start the video stream on the Camera
["Camera.StartStream"]

[Command]
Check the current CameraState
["Camera.CameraState"]
