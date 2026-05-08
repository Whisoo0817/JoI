[Device Summary]
<Device "Speaker">
  <Service "PlaybackState" type="value">Current playback state. Enum values: paused, playing, stopped, fastforwarding, rewinding, buffering.</Service>
  <Service "Volume" type="value">Current volume level (INTEGER, 0-100)</Service>
  <Service "FastForward" type="action">Fast forward playback</Service>
  <Service "Pause" type="action">Pause playback</Service>
  <Service "Play" type="action">Play media</Service>
  <Service "Rewind" type="action">Rewind playback</Service>
  <Service "SetVolume" type="action">Set volume to a specific value</Service>
  <Service "Speak" type="action">Output text as speech (TTS)</Service>
  <Service "Stop" type="action">Stop playback</Service>
  <Service "VolumeDown" type="action">Decrease volume by one step</Service>
  <Service "VolumeUp" type="action">Increase volume by one step</Service>
</Device>

# Speaker Examples

[Command]
Play the speaker
["Speaker.Play"]

[Command]
Pause the speaker
["Speaker.Pause"]

[Command]
Set the speaker volume to 80
["Speaker.SetVolume"]

[Command]
Increase the speaker volume
["Speaker.VolumeUp"]

[Command]
Announce that dinner is ready through the speaker
["Speaker.Speak"]

[Command]
What is the current speaker volume?
["Speaker.Volume"]

[Command]
When the speaker starts playing, do something
["Speaker.PlaybackState"]
