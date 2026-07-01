[Device Summary]
<Device "Television">
  <Service "Channel" type="value">Current channel number (INTEGER)</Service>
  <Service "ChannelDown" type="action">Go to the previous channel</Service>
  <Service "ChannelUp" type="action">Go to the next channel</Service>
  <Service "SetChannel" type="action">Set specific channel number</Service>
</Device>

# Rules

- A specific channel number ("7번으로") → `SetChannel`. Up/next (다음 채널) → `ChannelUp`; down/prev (이전 채널) → `ChannelDown`. Read current channel → `Channel`.
- On/off → `Switch.On`/`Switch.Off` if the TV has a Switch.
