[Device Summary]
<Device "AudioRecorder">
  <Service "AudioFile" type="value">The current audio file of the audio recorder</Service>
  <Service "RecordStatus" type="value">The current status of the audio recorder. Enum values: idle, recording.</Service>
  <Service "RecordStart" type="action">Start recording audio</Service>
  <Service "RecordStop" type="action">Stop recording audio and save the file</Service>
  <Service "RecordWithDuration" type="action">Record audio with a specified duration</Service>
</Device>

# AudioRecorder Examples

[Command]
Start recording audio
["AudioRecorder.RecordStart"]

[Command]
Stop recording and save the file
["AudioRecorder.RecordStop"]

[Command]
Record audio for 30 seconds
["AudioRecorder.RecordWithDuration"]

[Command]
Check the RecordStatus of the AudioRecorder
["AudioRecorder.RecordStatus"]

[Command]
When the AudioRecorder starts recording, do something
["AudioRecorder.RecordStatus"]
