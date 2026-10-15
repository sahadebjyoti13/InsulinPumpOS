/*
 * InsulinPumpOS — ESP32 MQTT bench-test firmware
 *
 * Purpose: validate MQTT command/telemetry round-trip and short unloaded
 * motor motion on a bench. This is NOT a medical-device firmware release.
 *
 * SAFETY DEFAULTS:
 *   - Motor actuation is disabled unless ENABLE_BENCH_MOTOR is changed locally.
 *   - No insulin, fluid, syringe, tubing, or patient may be connected.
 *   - Do not expose an anonymous MQTT broker to the public internet.
 *   - Use a private VPN (e.g., Tailscale/WireGuard) or authenticated TLS broker.
 *   - This firmware does not implement insulin-dose calibration or delivery.
 *
 * Topic contract (matches dashboard):
 *   subscribe: medical/pump/CIIP002/host
 *   publish:   medical/pump/CIIP002/data
 *
 * Dashboard commands supported safely here:
 *   {"power":"ON"}          -> enable driver only (unless motor interlock enabled)
 *   {"power":"OFF"}         -> immediate motor/driver disable
 *   {"reset_fault":true}    -> clear latched software fault if inputs are safe
 *   {"test_move_ms":250}    -> accepted only with compile-time bench switch enabled,
 *                              bounded to <= 500 ms and speed cap
 *
 * Dose-like fields (basal_rate, bolus_dose) are acknowledged as BLOCKED and
 * NEVER converted into motion. Automated/meal-derived dosing is intentionally
 * not implemented here.
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ---- REQUIRED: set locally, never commit credentials ----
static const char *WIFI_SSID = "REPLACE_WITH_WIFI_SSID";
static const char *WIFI_PASSWORD = "REPLACE_WITH_WIFI_PASSWORD";

// Use the LAN/private-VPN address of the broker reachable from the ESP32.
// Do not point this at an open public broker.
static const char *MQTT_HOST = "192.168.1.10";
static constexpr uint16_t MQTT_PORT = 1883;
static const char *MQTT_USER = "";       // Set if broker authentication enabled
static const char *MQTT_PASSWORD = "";   // Set if broker authentication enabled

static const char *DEVICE_ID = "CIIP002";

// ---- Hardware pins: verify wiring against the physical board before powering ----
static constexpr int PIN_PWM  = 13;
static constexpr int PIN_IN1  = 22;
static constexpr int PIN_IN2  = 23;
static constexpr int PIN_STBY = 21;
static constexpr int PIN_ENC_A = 18;
static constexpr int PIN_ENC_B = 19;

// Motor movement is deliberately disabled by default.
// Enable only for a supervised, unloaded bench test after checking wiring,
// a physical disconnect/emergency stop, and mechanical travel limits.
#define ENABLE_BENCH_MOTOR 0

static constexpr uint32_t TELEMETRY_INTERVAL_MS = 1000;
static constexpr uint32_t WIFI_TIMEOUT_MS = 30000;
static constexpr uint32_t MQTT_RETRY_MS = 3000;
static constexpr uint32_t MAX_TEST_MOVE_MS = 500;
static constexpr uint8_t MAX_TEST_PWM = 70; // low duty cap for bench observation

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

String topicHost;
String topicData;
volatile int32_t encoderTicks = 0;

bool powerRequested = false;
bool faultLatched = false;
bool motorActive = false;
uint32_t motorStopAt = 0;
uint32_t lastTelemetryAt = 0;
uint32_t lastMqttAttemptAt = 0;
String lastCommand = "BOOT";
String lastResult = "READY";
String mode = "IDLE";

void IRAM_ATTR onEncoderA() {
  const int b = digitalRead(PIN_ENC_B);
  encoderTicks += b ? 1 : -1;
}

void stopMotor(const char *reason) {
  ledcWrite(PIN_PWM, 0);
  digitalWrite(PIN_IN1, LOW);
  digitalWrite(PIN_IN2, LOW);
  digitalWrite(PIN_STBY, LOW);
  motorActive = false;
  motorStopAt = 0;
  mode = "IDLE";
  lastResult = reason;
}

void driverStandbyOnly() {
  ledcWrite(PIN_PWM, 0);
  digitalWrite(PIN_IN1, LOW);
  digitalWrite(PIN_IN2, LOW);
  digitalWrite(PIN_STBY, LOW);
  motorActive = false;
  motorStopAt = 0;
  mode = "IDLE";
}

void publishTelemetry(bool force = false) {
  const uint32_t now = millis();
  if (!force && (now - lastTelemetryAt < TELEMETRY_INTERVAL_MS)) return;
  lastTelemetryAt = now;

  int32_t ticks;
  noInterrupts();
  ticks = encoderTicks;
  interrupts();

  StaticJsonDocument<512> doc;
  doc["device_id"] = DEVICE_ID;
  doc["ts_ms"] = now;
  doc["uptime_s"] = now / 1000;
  doc["wifi_connected"] = (WiFi.status() == WL_CONNECTED);
  doc["mqtt_connected"] = mqtt.connected();
  doc["power"] = powerRequested ? "ON" : "OFF";
  doc["actual_rpm"] = 0.0;  // RPM estimation requires verified encoder CPR/gearing.
  doc["encoder_ticks"] = ticks;
  doc["position_deg"] = 0.0; // Do not imply calibrated position without a homing reference.
  doc["status"] = faultLatched ? "FAULT" : (motorActive ? "TEST_MOVING" : "READY");
  doc["mode"] = mode;
  doc["last_command"] = lastCommand;
  doc["last_result"] = lastResult;
  doc["actuation_enabled"] = (ENABLE_BENCH_MOTOR != 0);
  doc["firmware"] = "mqtt-bench-guarded-0.1";

  char buffer[512];
  const size_t n = serializeJson(doc, buffer, sizeof(buffer));
  if (mqtt.connected()) {
    mqtt.publish(topicData.c_str(), buffer, n);
  }
}

void rejectCommand(const char *why) {
  lastResult = why;
  publishTelemetry(true);
}

void handleCommand(const byte *payload, unsigned int length) {
  StaticJsonDocument<512> doc;
  const DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    lastCommand = "INVALID_JSON";
    rejectCommand("REJECTED_INVALID_JSON");
    return;
  }

  lastCommand = "MQTT_COMMAND";
  if (doc.containsKey("power")) {
    const char *p = doc["power"] | "";
    if (strcmp(p, "OFF") == 0) {
      powerRequested = false;
      stopMotor("POWER_OFF");
      publishTelemetry(true);
      return;
    }
    if (strcmp(p, "ON") == 0) {
      if (faultLatched) {
        rejectCommand("REJECTED_FAULT_LATCHED");
        return;
      }
      powerRequested = true;
      driverStandbyOnly();
      lastResult = "POWER_ON_ACCEPTED_DRIVER_STANDBY";
      publishTelemetry(true);
      return;
    }
    rejectCommand("REJECTED_INVALID_POWER_VALUE");
    return;
  }

  if (doc["reset_fault"] | false) {
    stopMotor("FAULT_RESET");
    faultLatched = false;
    lastResult = "FAULT_RESET_ACCEPTED";
    publishTelemetry(true);
    return;
  }

  // Never convert a dose field into motor movement. These are explicitly blocked.
  if (doc.containsKey("bolus_dose") || doc.containsKey("basal_rate")) {
    stopMotor("DOSE_COMMAND_BLOCKED");
    rejectCommand("BLOCKED_DOSE_FIELDS_BENCH_FIRMWARE");
    return;
  }

  if (doc.containsKey("test_move_ms")) {
#if ENABLE_BENCH_MOTOR
    const uint32_t requestedMs = doc["test_move_ms"].as<uint32_t>();
    if (!powerRequested || faultLatched || motorActive) {
      rejectCommand("REJECTED_INTERLOCK");
      return;
    }
    if (requestedMs == 0 || requestedMs > MAX_TEST_MOVE_MS) {
      rejectCommand("REJECTED_DURATION_LIMIT");
      return;
    }
    // This is only a short, low-duty, unloaded bench movement.
    digitalWrite(PIN_STBY, HIGH);
    digitalWrite(PIN_IN1, HIGH);
    digitalWrite(PIN_IN2, LOW);
    ledcWrite(PIN_PWM, MAX_TEST_PWM);
    motorActive = true;
    motorStopAt = millis() + requestedMs;
    mode = "BENCH_TEST";
    lastResult = "BOUNDED_BENCH_MOVE_STARTED";
    publishTelemetry(true);
#else
    rejectCommand("MOTOR_ACTUATION_DISABLED_COMPILE_TIME");
#endif
    return;
  }

  rejectCommand("REJECTED_UNKNOWN_COMMAND");
}

void mqttCallback(char *topic, byte *payload, unsigned int length) {
  if (String(topic) != topicHost) return;
  handleCommand(payload, length);
}

bool connectMqtt() {
  if (WiFi.status() != WL_CONNECTED) return false;
  String clientId = String("InsulinPumpOS-") + DEVICE_ID + "-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  bool connected = false;
  if (strlen(MQTT_USER) > 0) {
    connected = mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASSWORD);
  } else {
    connected = mqtt.connect(clientId.c_str());
  }
  if (connected) {
    mqtt.subscribe(topicHost.c_str(), 1);
    publishTelemetry(true);
  }
  return connected;
}

void setup() {
  Serial.begin(115200);
  delay(200);

  topicHost = String("medical/pump/") + DEVICE_ID + "/host";
  topicData = String("medical/pump/") + DEVICE_ID + "/data";

  pinMode(PIN_IN1, OUTPUT);
  pinMode(PIN_IN2, OUTPUT);
  pinMode(PIN_STBY, OUTPUT);
  pinMode(PIN_ENC_A, INPUT_PULLUP);
  pinMode(PIN_ENC_B, INPUT_PULLUP);
  driverStandbyOnly();

  // Arduino-ESP32 core 3.x LEDC API. For core 2.x, replace with ledcSetup/
  // ledcAttachPin according to the installed board-package version.
  const bool pwmAttached = ledcAttach(PIN_PWM, 1000, 8);
  if (!pwmAttached) {
    faultLatched = true;
    lastResult = "FAULT_PWM_INIT_FAILED";
  }

  attachInterrupt(digitalPinToInterrupt(PIN_ENC_A), onEncoderA, CHANGE);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("\nInsulinPumpOS bench firmware: %s\n", DEVICE_ID);
  Serial.printf("MQTT host=%s port=%u\n", MQTT_HOST, MQTT_PORT);
  Serial.printf("Host topic: %s\nData topic: %s\n", topicHost.c_str(), topicData.c_str());
  Serial.printf("Motor actuation enabled at compile time: %s\n", ENABLE_BENCH_MOTOR ? "YES" : "NO");

  const uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < WIFI_TIMEOUT_MS) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Wi-Fi IP: ");
    Serial.println(WiFi.localIP());
  } else {
    lastResult = "WIFI_CONNECT_TIMEOUT";
  }

  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(mqttCallback);
  mqtt.setBufferSize(512);
  mqtt.setKeepAlive(20);
}

void loop() {
  const uint32_t now = millis();

  if (motorActive && motorStopAt != 0 && (int32_t)(now - motorStopAt) >= 0) {
    stopMotor("BENCH_MOVE_TIMEOUT_STOPPED");
    publishTelemetry(true);
  }

  if (WiFi.status() != WL_CONNECTED) {
    // Local actuator fail-safe: stop and disable driver when network is lost.
    if (motorActive) stopMotor("WIFI_LOSS_STOP");
    driverStandbyOnly();
  } else if (!mqtt.connected() && now - lastMqttAttemptAt >= MQTT_RETRY_MS) {
    lastMqttAttemptAt = now;
    connectMqtt();
  }

  if (mqtt.connected()) mqtt.loop();
  publishTelemetry();
  delay(5);
}
