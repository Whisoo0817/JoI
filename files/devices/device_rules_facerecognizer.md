[Device Summary]
<Device "FaceRecognizer">
  <Service "RecognizedResult" type="value">ID of the recognized face</Service>
  <Service "Start" type="action">Start face recognition</Service>
  <Service "End" type="action">End face recognition</Service>
</Device>

# FaceRecognizer Examples

[Command]
Who is currently at the door? (Ask FaceRecognizer)
["FaceRecognizer.RecognizedResult"]

[Command]
Start recognition on the FaceRecognizer
["FaceRecognizer.Start"]
