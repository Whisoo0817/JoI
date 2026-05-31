last_detected_time := (#Clock).timestamp
off_30min_done := false

if (all(#ContactSensor #Entrance).contact ==| false or all(#PresenceSensor).presence ==| true) {
	last_detected_time = (#Clock).timestamp
	off_30min_done = false

	if (all(#Switch).switch ==| false) { all(#Switch).on() }
	if (all(#Light).switch ==| false) { all(#Light).on() }
	if (all(#Plug).switch ==| false) { all(#Plug).on() }
}

elapsed = (#Clock).timestamp - last_detected_time

if (elapsed > 30*60 and off_30min_dome == false) {
	if (all(#Switch).switch ==| false) { all(#Switch).on() }
        if (all(#Light).switch ==| false) { all(#Light).on() }
        if (all(#Plug).switch ==| false) { all(#Plug).on() }
	off_30min_done = true
}
