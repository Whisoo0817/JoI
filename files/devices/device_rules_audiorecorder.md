[Device Summary]
<Device "AudioRecorder">
  <Service "RecordStatus" type="value">Recording status (standby, recording)</Service>
  <Service "AudioFile" type="value">Recorded audio file</Service>
  <Service "RecordStart" type="action">Start recording</Service>
  <Service "RecordStop" type="action">Stop recording and save file</Service>
  <Service "RecordWithDuration" type="action">Record for a specified duration (in seconds)</Service>
</Device>

# AudioRecorder Examples

[Command]
Turn on the AudioRecorder
["AudioRecorder.On"]

[Command]
Turn off the AudioRecorder
["AudioRecorder.Off"]

[Command]
Toggle the AudioRecorder
["AudioRecorder.Toggle"]

[Command]
Check the RecordStatus of the AudioRecorder
["AudioRecorder.RecordStatus"]
