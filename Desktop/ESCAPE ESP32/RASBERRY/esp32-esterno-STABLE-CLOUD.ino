/* =========================================================================
   ESP32 ESTERNO - CLOUD-FIRST STABLE VERSION
   
   FASE 1 - Stabilizzazione Hardware + Cloud MQTT
   
   FEATURES:
   ✅ WiFiManager captive portal (AP: EscapeRoom-Esterno)
   ✅ HiveMQ Cloud MQTT over TLS (porta 8883)
   ✅ Triple watchdog (WiFi + MQTT + Hardware)
   ✅ Heartbeat strutturato ogni 30s
   ✅ Reset remoto via MQTT
   ✅ Last Will & Testament
   ✅ Zero IP hardcoded
   ✅ Zero SSID hardcoded
   
   Hardware:
   - Fotocellula IR (GPIO 19)
   - LED Cancello Verde/Rosso (GPIO 4, 16)
   - LED Porta Verde/Rosso (GPIO 33, 25)
   - RGB (GPIO 21, 22, 23)
   - Servo Cancelli DX/SX (GPIO 5, 17)
   - Servo Porta (GPIO 18)
   - Servo Tetto (GPIO 32)
   ========================================================================= */

#include <ESP32Servo.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <WiFiManager.h>  // https://github.com/tzapu/WiFiManager
#include <esp_task_wdt.h>

// ========================================================================
// CONFIGURAZIONE - MODIFICA QUESTI VALORI
// ========================================================================

// HiveMQ Cloud - SOSTITUISCI CON LE TUE CREDENZIALI
const char* MQTT_SERVER = "your-cluster.hivemq.cloud";  // ← Cambia questo
const int   MQTT_PORT = 8883;                            // TLS port
const char* MQTT_USER = "escape_device";                 // ← Cambia questo
const char* MQTT_PASS = "your_password";                 // ← Cambia questo

// Device ID (univoco per questo ESP32)
#define DEVICE_ID "esterno"

// Session ID temporaneo (fisso per compatibilità)
#define SESSION_ID 999

// Timeout watchdog (millisecondi)
#define WIFI_RESTART_TIMEOUT 120000   // 120s → restart se WiFi offline
#define MQTT_RESTART_TIMEOUT 180000   // 180s → restart se MQTT offline (WiFi OK)
#define WDT_TIMEOUT 120               // 120s → hardware watchdog

// Heartbeat interval
#define HEARTBEAT_INTERVAL 30000      // 30s

// WiFiManager timeout
#define PORTAL_TIMEOUT 180            // 180s in AP mode → restart

// Debug TLS (set to 1 per usare setInsecure() temporaneamente)
#define ALLOW_INSECURE_TLS 1          // ← Per test, poi metti 0 e aggiungi CA cert

// ========================================================================
// PIN HARDWARE (NON MODIFICARE)
// ========================================================================

// LED Bicolore Cancello
#define LED_CANCELLO_VERDE   4
#define LED_CANCELLO_ROSSO   16

// LED Bicolore Porta
#define LED_PORTA_VERDE      33
#define LED_PORTA_ROSSO      25

// Sensore IR Fotocellula
#define IR_PIN               19

// Servo Motors
#define SERVO_DX             5
#define SERVO_SX             17
#define SERVO_PORTA          18
#define SERVO_TETTO          32

// RGB Victory LEDs
#define RGB_R                21
#define RGB_G                22
#define RGB_B                23

// ========================================================================
// OGGETTI GLOBALI
// ========================================================================

WiFiClientSecure espClient;
PubSubClient client(espClient);
Servo cancelloDX, cancelloSX, porta, tetto;
WiFiManager wifiManager;

// ========================================================================
// STATO HARDWARE
// ========================================================================

int posCancelli = 0;
int posPorta = 0;
int posTetto = 0;

const int CANCELLO_OPEN = 90;
const int PORTA_OPEN = 90;
const int TETTO_OPEN = 180;

bool irLibero = false;
bool gameWon = false;

// ========================================================================
// TIMING & WATCHDOG
// ========================================================================

unsigned long tServo = 0;
unsigned long tRGB = 0;
unsigned long tMQTT = 0;
unsigned long tHeartbeat = 0;
int festaStep = 0;

// Watchdog states
enum WiFiWatchdogState {
  WIFI_OK,
  WIFI_RECONNECTING
};

enum MQTTWatchdogState {
  MQTT_OK,
  MQTT_RECONNECTING
};

WiFiWatchdogState wifiWdState = WIFI_OK;
MQTTWatchdogState mqttWdState = MQTT_OK;

unsigned long wifiDisconnectTime = 0;
unsigned long mqttDisconnectTime = 0;
unsigned long mqttLastReconnectAttempt = 0;

// ========================================================================
// MQTT CALLBACK
// ========================================================================

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String topicStr = String(topic);
  
  // Reset remoto
  if (topicStr == "device/" + String(DEVICE_ID) + "/cmd/reset") {
    Serial.println("\n🔴 ===== RESET REMOTO RICEVUTO =====");
    Serial.println("   Riavvio tra 1 secondo...");
    delay(1000);
    ESP.restart();
  }
  
  // Game completion (compatibilità)
  if (topicStr == "escape/game-completion/won") {
    String message = "";
    for (unsigned int i = 0; i < length; i++) {
      message += (char)payload[i];
    }
    gameWon = (message == "true" || message == "1");
    Serial.print("🏆 Game Won: ");
    Serial.println(gameWon ? "YES 🎊" : "NO");
  }
}

// ========================================================================
// SETUP WIFI (WiFiManager)
// ========================================================================

void setupWiFi() {
  Serial.println("\n📡 ===== WIFI SETUP =====");
  
  // Callback quando entra in AP mode
  wifiManager.setAPCallback([](WiFiManager *myWiFiManager) {
    Serial.println("⚠️  Nessuna rete salvata!");
    Serial.println("📶 Modalità Captive Portal attiva:");
    Serial.println("   SSID: EscapeRoom-Esterno");
    Serial.println("   IP: 192.168.4.1");
    Serial.println("   Connettiti con telefono per configurare WiFi");
  });
  
  // Timeout portal (180s)
  wifiManager.setConfigPortalTimeout(PORTAL_TIMEOUT);
  
  // Tenta connessione (auto-AP se fallisce)
  if (!wifiManager.autoConnect("EscapeRoom-Esterno")) {
    Serial.println("❌ WiFi config timeout, riavvio...");
    delay(3000);
    ESP.restart();
  }
  
  Serial.println("✅ WiFi connesso!");
  Serial.print("   SSID: ");
  Serial.println(WiFi.SSID());
  Serial.print("   IP: ");
  Serial.println(WiFi.localIP());
  Serial.print("   RSSI: ");
  Serial.print(WiFi.RSSI());
  Serial.println(" dBm");
}

// ========================================================================
// SETUP MQTT
// ========================================================================

void setupMQTT() {
  Serial.println("\n🔌 ===== MQTT SETUP =====");
  
  // TLS Configuration
  #if ALLOW_INSECURE_TLS
    espClient.setInsecure();
    Serial.println("⚠️  TLS INSECURE MODE (solo per test!)");
  #else
    // TODO: Aggiungi CA certificate qui per produzione
    // espClient.setCACert(hivemq_ca_cert);
    Serial.println("⚠️  ERRORE: CA cert non configurato!");
    Serial.println("   Imposta ALLOW_INSECURE_TLS=1 per test");
  #endif
  
  client.setServer(MQTT_SERVER, MQTT_PORT);
  client.setCallback(mqttCallback);
  
  Serial.print("   Server: ");
  Serial.println(MQTT_SERVER);
  Serial.print("   Port: ");
  Serial.println(MQTT_PORT);
}

// ========================================================================
// MQTT RECONNECT
// ========================================================================

void reconnectMQTT() {
  if (client.connected()) return;
  
  // Evita tentativi troppo frequenti
  if (millis() - mqttLastReconnectAttempt < 5000) return;
  mqttLastReconnectAttempt = millis();
  
  Serial.print("🔌 MQTT reconnect...");
  
  String clientId = "ESP32-Esterno-" + String(random(0xffff), HEX);
  String willTopic = "device/" + String(DEVICE_ID) + "/status";
  
  // Connect con Last Will & Testament
  if (client.connect(
    clientId.c_str(),
    MQTT_USER,
    MQTT_PASS,
    willTopic.c_str(),  // will topic
    1,                   // will QoS
    false,               // will retain (false come da spec)
    "offline"            // will message
  )) {
    Serial.println(" ✅");
    
    // Publish "online" status (retained)
    client.publish(willTopic.c_str(), "online", true);
    
    // Subscribe a comandi
    String resetTopic = "device/" + String(DEVICE_ID) + "/cmd/reset";
    client.subscribe(resetTopic.c_str());
    client.subscribe("escape/game-completion/won");
    
    Serial.println("📥 Subscribed:");
    Serial.print("   - ");
    Serial.println(resetTopic);
    Serial.println("   - escape/game-completion/won");
    
  } else {
    Serial.print(" ❌ (rc=");
    Serial.print(client.state());
    Serial.println(")");
  }
}

// ========================================================================
// HEARTBEAT
// ========================================================================

void sendHeartbeat() {
  if (millis() - tHeartbeat < HEARTBEAT_INTERVAL) return;
  tHeartbeat = millis();
  
  // JSON heartbeat
  StaticJsonDocument<256> doc;
  doc["device_id"] = DEVICE_ID;
  doc["uptime_s"] = millis() / 1000;
  doc["wifi_rssi"] = WiFi.RSSI();
  doc["free_heap"] = ESP.getFreeHeap();
  doc["mqtt_connected"] = client.connected();
  
  char buffer[256];
  serializeJson(doc, buffer);
  
  String topic = "device/" + String(DEVICE_ID) + "/heartbeat";
  
  if (client.publish(topic.c_str(), buffer, true)) {  // retained
    Serial.print("💓 Heartbeat: ");
    Serial.println(buffer);
  }
}

// ========================================================================
// WATCHDOG WIFI
// ========================================================================

void checkWiFiWatchdog() {
  if (WiFi.status() != WL_CONNECTED) {
    if (wifiWdState == WIFI_OK) {
      // Inizia problema
      wifiDisconnectTime = millis();
      wifiWdState = WIFI_RECONNECTING;
      Serial.println("⚠️  WiFi perso, tentativo reconnect...");
      WiFi.reconnect();
    } else {
      // Problema persistente
      if (millis() - wifiDisconnectTime > WIFI_RESTART_TIMEOUT) {
        Serial.println("\n🔴 ===== WIFI WATCHDOG TIMEOUT =====");
        Serial.println("   WiFi offline > 120s → RESTART!");
        delay(1000);
        ESP.restart();
      }
    }
  } else {
    // WiFi OK
    if (wifiWdState == WIFI_RECONNECTING) {
      Serial.println("✅ WiFi recuperato!");
    }
    wifiWdState = WIFI_OK;
  }
}

// ========================================================================
// WATCHDOG MQTT
// ========================================================================

void checkMQTTWatchdog() {
  // Solo se WiFi OK
  if (wifiWdState != WIFI_OK) return;
  
  if (!client.connected()) {
    if (mqttWdState == MQTT_OK) {
      // Inizia problema
      mqttDisconnectTime = millis();
      mqttWdState = MQTT_RECONNECTING;
      Serial.println("⚠️  MQTT perso, tentativo reconnect...");
      reconnectMQTT();
    } else {
      // Problema persistente
      if (millis() - mqttDisconnectTime > MQTT_RESTART_TIMEOUT) {
        Serial.println("\n🔴 ===== MQTT WATCHDOG TIMEOUT =====");
        Serial.println("   MQTT offline > 180s (WiFi OK) → RESTART!");
        delay(1000);
        ESP.restart();
      }
      // Riprova connessione periodicamente
      reconnectMQTT();
    }
  } else {
    // MQTT OK
    if (mqttWdState == MQTT_RECONNECTING) {
      Serial.println("✅ MQTT recuperato!");
    }
    mqttWdState = MQTT_OK;
  }
}

// ========================================================================
// PUBLISH HARDWARE STATE (compatibilità topic esistenti)
// ========================================================================

void publishHardwareState() {
  if (!client.connected()) return;
  
  if (millis() - tMQTT < 500) return;
  tMQTT = millis();
  
  String base = "escape/esterno/" + String(SESSION_ID) + "/";
  
  // Stato LED e sensore
  client.publish((base + "led/stato").c_str(), irLibero ? "VERDE" : "ROSSO");
  client.publish((base + "ir-sensor/stato").c_str(), irLibero ? "LIBERO" : "OCCUPATO");
  
  // Posizioni servo (opzionale, se serve al frontend)
  char posBuffer[8];
  
  sprintf(posBuffer, "%d", posCancelli);
  client.publish((base + "cancello1/posizione").c_str(), posBuffer);
  client.publish((base + "cancello2/posizione").c_str(), posBuffer);
  
  sprintf(posBuffer, "%d", posPorta);
  client.publish((base + "porta/posizione").c_str(), posBuffer);
  
  sprintf(posBuffer, "%d", posTetto);
  client.publish((base + "tetto/posizione").c_str(), posBuffer);
}

// ========================================================================
// SETUP
// ========================================================================

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n");
  Serial.println("╔════════════════════════════════════════════════╗");
  Serial.println("║  ESP32 ESTERNO - STABLE CLOUD VERSION         ║");
  Serial.println("║  Fase 1: WiFiManager + HiveMQ + Watchdog      ║");
  Serial.println("╚════════════════════════════════════════════════╝");
  Serial.println();
  
  // Hardware Watchdog
  Serial.println("🐕 Inizializzazione Hardware Watchdog...");
  esp_task_wdt_init(WDT_TIMEOUT, true);
  esp_task_wdt_add(NULL);
  Serial.println("   ✅ Hardware WDT attivo (120s timeout)");
  
  // Pin configuration
  Serial.println("\n📌 Configurazione pin hardware...");
  pinMode(IR_PIN, INPUT_PULLUP);
  pinMode(LED_CANCELLO_VERDE, OUTPUT);
  pinMode(LED_CANCELLO_ROSSO, OUTPUT);
  pinMode(LED_PORTA_VERDE, OUTPUT);
  pinMode(LED_PORTA_ROSSO, OUTPUT);
  pinMode(RGB_R, OUTPUT);
  pinMode(RGB_G, OUTPUT);
  pinMode(RGB_B, OUTPUT);
  
  // Servo attach
  cancelloDX.attach(SERVO_DX, 500, 2400);
  cancelloSX.attach(SERVO_SX, 500, 2400);
  porta.attach(SERVO_PORTA, 500, 2400);
  tetto.attach(SERVO_TETTO, 500, 2500);
  
  // Posizioni iniziali
  cancelloDX.write(0);
  cancelloSX.write(0);
  porta.write(0);
  tetto.write(0);
  
  Serial.println("   ✅ Pin e servo configurati");
  
  // WiFi setup
  setupWiFi();
  
  // MQTT setup
  setupMQTT();
  
  // Prima connessione MQTT
  reconnectMQTT();
  
  Serial.println("\n✅ ===== SISTEMA PRONTO =====");
  Serial.print("   Device ID: ");
  Serial.println(DEVICE_ID);
  Serial.print("   Session ID: ");
  Serial.println(SESSION_ID);
  Serial.println("\n📡 Topic MQTT:");
  Serial.println("   Heartbeat: device/esterno/heartbeat");
  Serial.println("   Status: device/esterno/status");
  Serial.println("   Reset: device/esterno/cmd/reset (subscribe)");
  Serial.println("   Hardware: escape/esterno/999/* (publish)");
  Serial.println("\n🐕 Watchdog:");
  Serial.println("   WiFi: restart se offline > 120s");
  Serial.println("   MQTT: restart se offline > 180s (WiFi OK)");
  Serial.println("   Hardware: restart se freeze > 120s");
  Serial.println("\n💓 Heartbeat ogni 30 secondi\n");
}

// ========================================================================
// LOOP PRINCIPALE
// ========================================================================

void loop() {
  unsigned long now = millis();
  
  // Feed hardware watchdog
  esp_task_wdt_reset();
  
  // Watchdog checks (priorità alta)
  checkWiFiWatchdog();
  checkMQTTWatchdog();
  
  // MQTT loop
  if (client.connected()) {
    client.loop();
  }
  
  // Heartbeat
  sendHeartbeat();
  
  // Lettura sensore IR
  irLibero = (digitalRead(IR_PIN) == HIGH);
  
  // ===== LED CANCELLO =====
  if (irLibero) {
    digitalWrite(LED_CANCELLO_VERDE, HIGH);
    digitalWrite(LED_CANCELLO_ROSSO, LOW);
  } else {
    digitalWrite(LED_CANCELLO_VERDE, LOW);
    digitalWrite(LED_CANCELLO_ROSSO, HIGH);
  }
  
  // ===== LED PORTA =====
  if (posPorta > 0) {
    digitalWrite(LED_PORTA_VERDE, HIGH);
    digitalWrite(LED_PORTA_ROSSO, LOW);
  } else {
    digitalWrite(LED_PORTA_VERDE, LOW);
    digitalWrite(LED_PORTA_ROSSO, HIGH);
  }
  
  // ===== MOVIMENTO SERVO SMOOTH =====
  if (now - tServo >= 15) {
    tServo = now;
    
    if (irLibero) {
      if (posCancelli < CANCELLO_OPEN) posCancelli++;
      if (posPorta < PORTA_OPEN) posPorta++;
      if (posTetto < TETTO_OPEN) posTetto++;
    } else {
      if (posCancelli > 0) posCancelli--;
      if (posPorta > 0) posPorta--;
      if (posTetto > 0) posTetto--;
    }
    
    cancelloDX.write(posCancelli);
    cancelloSX.write(posCancelli);
    porta.write(posPorta);
    tetto.write(posTetto);
  }
  
  // ===== RGB VICTORY ANIMATION =====
  if (gameWon) {
    if (now - tRGB >= 120) {
      tRGB = now;
      festaStep++;
      
      switch (festaStep % 6) {
        case 0: analogWrite(RGB_R, 255); analogWrite(RGB_G, 0);   analogWrite(RGB_B, 0);   break;
        case 1: analogWrite(RGB_R, 0);   analogWrite(RGB_G, 255); analogWrite(RGB_B, 0);   break;
        case 2: analogWrite(RGB_R, 0);   analogWrite(RGB_G, 0);   analogWrite(RGB_B, 255); break;
        case 3: analogWrite(RGB_R, 255); analogWrite(RGB_G, 255); analogWrite(RGB_B, 0);   break;
        case 4: analogWrite(RGB_R, 255); analogWrite(RGB_G, 0);   analogWrite(RGB_B, 255); break;
        case 5: analogWrite(RGB_R, 0);   analogWrite(RGB_G, 255); analogWrite(RGB_B, 255); break;
      }
    }
  } else {
    analogWrite(RGB_R, 0);
    analogWrite(RGB_G, 0);
    analogWrite(RGB_B, 0);
  }
  
  // ===== PUBLISH HARDWARE STATE =====
  publishHardwareState();
  
  // Small delay
  delay(10);
}