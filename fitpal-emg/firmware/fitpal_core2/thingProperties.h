// Arduino IoT Cloud properties for FitPal. Put the Thing and device IDs from your own cloud
// account in the two constants below. Three variables are published: the activation at 2 Hz and
// the two repetition counters when they change.
#pragma once
#include <ArduinoIoTCloud.h>
#include <Arduino_ConnectionHandler.h>
#include "secrets.h"

const char THING_ID[]           = "your-thing-id";
const char DEVICE_LOGIN_NAME[]  = "your-device-id";
const char SSID[]               = SECRET_SSID;
const char PASS[]               = SECRET_PASS;
const char DEVICE_KEY[]         = SECRET_DEVICE_KEY;

int   effectivereps;     // effective repetitions this set
bool  effectiveornot;    // last repetition effective?
float mvwifi;            // activation, % of MVC

void initProperties() {
  ArduinoCloud.setBoardId(DEVICE_LOGIN_NAME);
  ArduinoCloud.setSecretDeviceKey(DEVICE_KEY);
  ArduinoCloud.setThingId(THING_ID);
  ArduinoCloud.addProperty(effectivereps, READ, ON_CHANGE, NULL);
  ArduinoCloud.addProperty(effectiveornot, READ, ON_CHANGE, NULL);
  ArduinoCloud.addProperty(mvwifi, READ, 500 * MILLISECONDS, NULL);
}
WiFiConnectionHandler ArduinoIoTPreferredConnection(SSID, PASS);
