// tec_pid.ino : control loop for the Peltier refrigerator.
// Gains and sensor setup follow the configuration in the report (Table 1). The sketch has not been
// run on the original hardware. The OLED and rotary encoder are omitted; the setpoint is changed over
// serial ("s5.0" sets 5.0 C).
// Requires libraries: PID_v1 (Brett Beauregard), OneWire, DallasTemperature.
//
// The loop uses the conventional PID(&input,&output,&setpoint,..., REVERSE) form, so the derivative
// term acts on the measured temperature and not on the setpoint. (The version we first ran passed
// the setpoint as input and the temperature as setpoint, with DIRECT.)

#include <OneWire.h>
#include <DallasTemperature.h>
#include <PID_v1.h>

const uint8_t PIN_ONEWIRE = 2;   // DS18B20 data, 4.7 k pull-up to 5 V
const uint8_t PIN_PWM     = 3;   // to IRF520 gate lines (via the MOSFET modules)

double input = 25.0, output = 0.0, setpoint = 5.0;
const double KP = 100.0, KI = 0.1, KD = 1000.0;     // final gains from the report

OneWire ow(PIN_ONEWIRE);
DallasTemperature ds(&ow);
PID pid(&input, &output, &setpoint, KP, KI, KD, REVERSE);   // more output when warmer than setpoint

void setup() {
  Serial.begin(115200);
  ds.begin();
  ds.setResolution(11);                // 0.125 C, ~375 ms conversion
  ds.setWaitForConversion(false);      // non-blocking read
  ds.requestTemperatures();
  pid.SetOutputLimits(0, 255);
  pid.SetSampleTime(500);
  pid.SetMode(AUTOMATIC);
  pinMode(PIN_PWM, OUTPUT);
}

void loop() {
  static unsigned long tReq = 0;
  if (millis() - tReq >= 500) {
    const float t = ds.getTempCByIndex(0);
    ds.requestTemperatures();
    tReq = millis();
    if (t > -100.0f) input = t;        // ignore disconnected-sensor value (-127)
  }
  if (pid.Compute()) {
    analogWrite(PIN_PWM, (int)output);
    Serial.print(input, 2); Serial.print(','); Serial.print(setpoint, 1);
    Serial.print(','); Serial.println((int)output);
  }
  if (Serial.available() && Serial.read() == 's') {
    const double sp = Serial.parseFloat();
    if (sp >= 2.0 && sp <= 12.0) setpoint = sp;   // same range as the encoder
  }
}
