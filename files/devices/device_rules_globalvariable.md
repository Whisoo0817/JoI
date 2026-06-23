[Device Summary]
<Device "GlobalVariable">
  <Service "SetInteger" type="action">Store an integer under a name. Args: Name (STRING), Value (INTEGER)</Service>
  <Service "SetDouble" type="action">Store a double under a name. Args: Name (STRING), Value (DOUBLE)</Service>
  <Service "SetString" type="action">Store a string under a name. Args: Name (STRING), Value (STRING)</Service>
  <Service "SetBoolean" type="action">Store a boolean under a name. Args: Name (STRING), Value (BOOL)</Service>
  <Service "GetInteger" type="value">Read the integer stored under a name (null if unset). Arg: Name (STRING)</Service>
  <Service "GetDouble" type="value">Read the double stored under a name (null if unset). Arg: Name (STRING)</Service>
  <Service "GetString" type="value">Read the string stored under a name (null if unset). Arg: Name (STRING)</Service>
  <Service "GetBoolean" type="value">Read the boolean stored under a name (null if unset). Arg: Name (STRING)</Service>
</Device>

# Rules

- Named persistent variables shared across scenarios. Pick the **type-specific** Set/Get pair that matches the value's type: integer → `SetInteger`/`GetInteger`, decimal → `SetDouble`/`GetDouble`, text → `SetString`/`GetString`, true/false → `SetBoolean`/`GetBoolean`.
- Storing/updating a value → the `Set*` action. Reading/checking a stored value (e.g. in a condition) → the `Get*` value.
- The first argument is always the variable `Name`.

# GlobalVariable Examples

[Command]
Store the count 5 in a variable named "visits"
["GlobalVariable.SetInteger"]

[Command]
If the global variable "armed" is true, turn on the siren
["GlobalVariable.GetBoolean", "Siren.On"]
