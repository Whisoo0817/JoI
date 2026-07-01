[Device Summary]
<Device "FaceRecognizer">
  <Service "RecognizedResult" type="value">ID of the recognized face</Service>
  <Service "AddFace" type="action">Register a new face</Service>
  <Service "DeleteFace" type="action">Remove a registered face</Service>
  <Service "End" type="action">Stop face recognition</Service>
  <Service "Start" type="action">Start face recognition</Service>
</Device>

# Rules

- Start / stop face recognition (얼굴 인식 시작/중지) → `Start` / `End`. Register a face → `AddFace`; remove one → `DeleteFace`. Read the recognized face id → `RecognizedResult`.
