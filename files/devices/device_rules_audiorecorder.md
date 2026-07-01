[Device Summary]
<Device "AudioRecorder">
  <Service "AudioFile" type="value">The current audio file of the audio recorder</Service>
  <Service "RecordStatus" type="value">The current status of the audio recorder. Enum values: idle, recording.</Service>
  <Service "RecordStart" type="action">Start recording audio</Service>
  <Service "RecordStop" type="action">Stop recording audio and save the file</Service>
  <Service "RecordWithDuration" type="action">Record audio with a specified duration</Service>
</Device>

# Rules

- Start recording (녹음 시작) → `RecordStart`. Stop and save (녹음 중지) → `RecordStop`. Record a fixed duration ("10초 녹음") → `RecordWithDuration`. Read status → `RecordStatus` (idle/recording).
