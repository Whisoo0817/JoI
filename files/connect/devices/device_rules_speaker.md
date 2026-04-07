[Device Summary]
<Device "Speaker">
  <Service "PlaybackState" type="value">Speaker state</Service>
  <Service "Volume" type="value">Speaker volume (0-100)</Service>
  <Service "Play" type="action">Play media (URL/Path)</Service>
  <Service "Pause" type="action">Pause playback</Service>
  <Service "Stop" type="action">Stop playback</Service>
  <Service "SetVolume" type="action">Set volume (when specific value is provided)</Service>
  <Service "VolumeUp" type="action">Increase volume by one</Service>
  <Service "VolumeDown" type="action">Decrease volume by one</Service>
  <Service "Speak" type="action">Output text as speech</Service>
</Device>

# Speaker Examples

[Command]
Play the speaker
["Speaker.Play"]

[Command]
Set the speaker volume to 80
["Speaker.SetVolume"]

[Command]
Announce that dinner is ready through the speaker
["Speaker.Speak"]

[Command]
What is the current speaker volume?
["Speaker.Volume"]
