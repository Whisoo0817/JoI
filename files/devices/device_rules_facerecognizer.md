[Device Summary]
<Device "FaceRecognizer">
  <Service "RecognizedResult" type="value">ID of the recognized face</Service>
  <Service "AddFace" type="action">Register a new face</Service>
  <Service "DeleteFace" type="action">Remove a registered face</Service>
  <Service "End" type="action">Stop face recognition</Service>
  <Service "Start" type="action">Start face recognition</Service>
</Device>

# FaceRecognizer Examples

[Command]
Start face recognition
["FaceRecognizer.Start"]

[Command]
Stop the FaceRecognizer
["FaceRecognizer.End"]

[Command]
Who is currently at the door?
["FaceRecognizer.RecognizedResult"]

[Command]
Register a new face on the FaceRecognizer
["FaceRecognizer.AddFace"]

[Command]
Delete the registered face from the FaceRecognizer
["FaceRecognizer.DeleteFace"]

[Command]
When a face is recognized, do something
["FaceRecognizer.RecognizedResult"]
