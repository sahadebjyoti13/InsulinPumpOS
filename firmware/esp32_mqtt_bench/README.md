# ESP32 MQTT Bench Firmware

This firmware is a **bench-test starting point**, not a clinical insulin-pump firmware release.

## What it validates

- ESP32 joins Wi-Fi and MQTT.
- Subscribes to `medical/pump/CIIP002/host`.
- Publishes telemetry to `medical/pump/CIIP002/data` every second.
- Supports dashboard `power` and `reset_fault` message formats.
- Blocks `basal_rate` and `bolus_dose` instead of interpreting dose values as motor movement.
- Has an optional, compile-time-disabled, bounded `test_move_ms` command for unloaded bench testing only.

## Before flashing

1. Confirm actual ESP32 model, TB6612FNG wiring, power supply, encoder wiring and motor mechanical limits.
2. Disconnect all insulin/fluid pathways. Do not test on a person or with medication connected.
3. Keep `ENABLE_BENCH_MOTOR 0` for initial network/dashboard integration.
4. Replace Wi-Fi and MQTT address locally. Do not commit network secrets.
5. The MQTT broker must be reachable through a private VPN or a properly authenticated TLS setup. Do not publish an anonymous port 1883 broker to the public internet.
6. Confirm installed Arduino-ESP32 core version. This sketch uses the LEDC API for core 3.x; adapt the PWM initialization if using core 2.x.
7. Install libraries: PubSubClient and ArduinoJson.

## Dashboard contract

| Direction | Topic | Payload / behavior |
|---|---|---|
| Dashboard → ESP32 | `medical/pump/CIIP002/host` | `{"power":"ON"}`, `{"power":"OFF"}`, `{"reset_fault":true}` |
| ESP32 → dashboard | `medical/pump/CIIP002/data` | `device_id`, `actual_rpm`, `encoder_ticks`, `status`, `mode`, `last_result` |
| Dose-like command | same `/host` topic | `basal_rate` and `bolus_dose` are explicitly blocked |

The dashboard online state currently depends on `/data` or `/cgm` messages reaching its backend. A successful MQTT publish in the UI only confirms that the broker accepted the publish; this is not an actuator acknowledgment.

## First test

1. Flash with motor actuation disabled.
2. Watch serial output and ensure Wi-Fi + MQTT connect.
3. Register device ID `CIIP002` in the dashboard.
4. Verify telemetry appears in Live Monitor / Device Control.
5. Verify `POWER ON`, `POWER OFF` and `RESET FAULT` produce updated `last_command` / `last_result` telemetry.
6. Only after safe unloaded test setup and independent physical stop are confirmed, a developer may deliberately enable the compile-time motor test locally and use `{"test_move_ms":250}`. Maximum allowed time is 500 ms and PWM is capped. Never use a dose field to move the motor.

## Important limitations

- RPM is currently reported as 0.0 and position as 0.0 because encoder counts per output revolution, homing/zero reference, and mechanical transmission calibration have not been verified. Encoder ticks are reported raw.
- This is not closed-loop insulin delivery and does not use CGM to calculate or deliver insulin.
- No authentication, TLS, command signature, replay protection, or production safety case is implemented inside this sketch. The broker/network must be privately protected.
