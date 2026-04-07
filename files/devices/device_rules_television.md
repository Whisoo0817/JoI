[Device Summary]
<Device "Television">
  <Service "Channel" type="value">Current channel number</Service>
  <Service "ChannelUp/Down" type="action">Change channel up/down</Service>
  <Service "SetChannel" type="action">Set specific channel</Service>
</Device>

# Television Examples

[Command]
Change the TV channel to 7
["Television.SetChannel"]

[Command]
Go to the next channel on the Television
["Television.ChannelUp/Down"]

[Command]
What channel is the TV currently on?
["Television.Channel"]
