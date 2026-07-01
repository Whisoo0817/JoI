[Device Summary]
<Device "Valve">
  <Service "ValveState" type="value">Valve state (true: open, false: closed)</Service>
  <Service "Close" type="action">Close the valve</Service>
  <Service "Open" type="action">Open the valve</Service>
</Device>

# Rules

- Open (열어/개방) → `Open`. Close (닫아/차단) → `Close`. Read state → `ValveState` (true=open).
