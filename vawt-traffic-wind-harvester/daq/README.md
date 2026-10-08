# Data-acquisition logger

An Arduino Uno with an SD module and a 10 kΩ / 2 kΩ divider that scales up to about 29 V into the 5 V ADC range.

- A sample is written only when the voltage changes by more than the threshold.
- A zero row is written every 10 minutes, so a flat line can be told apart from a dead logger.
- Each power-up opens a new file, `volt1.csv`, `volt2.csv` and so on. The Uno's SD library uses 8.3 file names, so longer names stop working past the ninth file.
- There is no real-time clock. Time stamps are elapsed time since power-up.
- If the SD card fails to initialise, the sketch halts.

`ADC_REF_V` is 4.9 V, the measured rail of our rig; set it for your board. Calibration against a known source gave ±0.05 V.

The sketch differs from the one used for the published records in its file naming (`voltN.csv` instead of `voltageN.csv`) and its elapsed-time stamps, and has not been re-run on the rig. The sketch is in `readVoltage_SDCard/`. Wiring: SD chip select on D10, SPI on D11–D13, divider midpoint on A0.
