[Device Summary]
<Device "Television">
  <Service "Channel" type="value">Current channel number (INTEGER)</Service>
  <Service "ChannelDown" type="action">Go to the previous channel</Service>
  <Service "ChannelUp" type="action">Go to the next channel</Service>
  <Service "SetChannel" type="action">Set specific channel number</Service>
</Device>

# Television Examples

[Command]
Change the TV channel to 7
["Television.SetChannel"]

[Command]
Go to the next channel on the Television
["Television.ChannelUp"]

[Command]
Go back one channel
["Television.ChannelDown"]

[Command]
What channel is the TV currently on?
["Television.Channel"]
