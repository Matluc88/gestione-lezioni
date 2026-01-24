# 🚀 ISTRUZIONI FLASH ESP32 ESTERNO - FASE 1

## 📋 PRE-REQUISITI

### Software
1. **Arduino IDE** (v1.8.19 o v2.x)
2. **Driver ESP32** installato
3. **Librerie necessarie** (vedi sotto)

### Hardware
- ESP32 DevKit
- Cavo USB
- Computer con porta USB

---

## 📦 INSTALLAZIONE LIBRERIE

Apri Arduino IDE → Tools → Manage Libraries → cerca e installa:

```
1. WiFiManager by tzapu (v2.0.16-rc.2 o superiore)
2. PubSubClient by Nick O'Leary (v2.8.0 o superiore)
3. ArduinoJson by Benoit Blanchon (v6.21.0 o superiore)
4. ESP32Servo by Kevin Harrington (v0.13.0 o superiore)
```

**Note:**
- `WiFi.h`, `WiFiClientSecure.h`, `esp_task_wdt.h` sono incluse nell'ESP32 core (già presenti)

---

## ⚙️ CONFIGURAZIONE FIRMWARE

### 1. Apri il file
```
/Users/matteo/Desktop/ESCAPE ESP32/RASBERRY/esp32-esterno-STABLE-CLOUD.ino
```

### 2. Modifica credenziali HiveMQ (OBBLIGATORIO)

Linee 34-37:
```cpp
const char* MQTT_SERVER = "your-cluster.hivemq.cloud";  // ← Cambia questo
const int   MQTT_PORT = 8883;                            
const char* MQTT_USER = "escape_device";                 // ← Cambia questo
const char* MQTT_PASS = "your_password";                 // ← Cambia questo
```

**Sostituisci con:**
- `MQTT_SERVER`: URL del tuo cluster HiveMQ (es: `abc123.hivemq.cloud`)
- `MQTT_USER`: Username creato su HiveMQ
- `MQTT_PASS`: Password creata su HiveMQ

### 3. Verifica flag TLS (opzionale)

Linea 55:
```cpp
#define ALLOW_INSECURE_TLS 1  // 1 = test mode (no cert check), 0 = produzione
```

**Per test rapidi:** lascia `1`  
**Per produzione:** metti `0` e aggiungi CA certificate (vedi TODO nel codice)

---

## 🔌 FLASH SU ESP32

### 1. Collega ESP32 via USB

### 2. Configura Arduino IDE

**Tools → Board:**
- `ESP32 Dev Module` (o il modello specifico del tuo ESP32)

**Tools → Upload Speed:**
- `115200` (consigliato)

**Tools → Port:**
- Seleziona la porta COM/tty dove è collegato l'ESP32
  - macOS: `/dev/cu.usbserial-XXX` o `/dev/cu.SLAB_USBtoUART`
  - Windows: `COM3`, `COM4`, etc.
  - Linux: `/dev/ttyUSB0`

### 3. Compila e carica

1. Click su **Verify** (✓) per compilare
2. Attendi compilazione (circa 30-60 secondi)
3. Se OK, click su **Upload** (→)
4. Attendi upload (circa 10-20 secondi)

**Output atteso:**
```
Sketch uses 865616 bytes (65%) of program storage space.
...
Hard resetting via RTS pin...
```

---

## 🖥️ MONITOR SERIALE

### 1. Apri Serial Monitor

Tools → Serial Monitor (o `Ctrl+Shift+M` / `Cmd+Shift+M`)

### 2. Configura baudrate

In basso a destra: seleziona **115200 baud**

### 3. Output atteso (primo boot senza WiFi salvato)

```
╔════════════════════════════════════════════════╗
║  ESP32 ESTERNO - STABLE CLOUD VERSION         ║
║  Fase 1: WiFiManager + HiveMQ + Watchdog      ║
╚════════════════════════════════════════════════╝

🐕 Inizializzazione Hardware Watchdog...
   ✅ Hardware WDT attivo (120s timeout)

📌 Configurazione pin hardware...
   ✅ Pin e servo configurati

📡 ===== WIFI SETUP =====
⚠️  Nessuna rete salvata!
📶 Modalità Captive Portal attiva:
   SSID: EscapeRoom-Esterno
   IP: 192.168.4.1
   Connettiti con telefono per configurare WiFi
```

### 4. Configurazione WiFi (primo boot)

1. **Sul telefono/computer:**
   - Cerca reti WiFi
   - Trovi `EscapeRoom-Esterno`
   - Connettiti (senza password)

2. **Si apre automaticamente pagina config:**
   - Se non si apre, vai su `http://192.168.4.1`

3. **Configura WiFi:**
   - Click su "Configure WiFi"
   - Seleziona la tua rete WiFi
   - Inserisci password
   - Click "Save"

4. **ESP32 riavvia automaticamente** e si connette alla rete configurata

### 5. Output atteso (dopo config WiFi)

```
✅ WiFi connesso!
   SSID: TuaReteWiFi
   IP: 192.168.1.123
   RSSI: -45 dBm

🔌 ===== MQTT SETUP =====
⚠️  TLS INSECURE MODE (solo per test!)
   Server: your-cluster.hivemq.cloud
   Port: 8883

🔌 MQTT reconnect... ✅
📥 Subscribed:
   - device/esterno/cmd/reset
   - escape/game-completion/won

✅ ===== SISTEMA PRONTO =====
   Device ID: esterno
   Session ID: 999

📡 Topic MQTT:
   Heartbeat: device/esterno/heartbeat
   Status: device/esterno/status
   Reset: device/esterno/cmd/reset (subscribe)
   Hardware: escape/esterno/999/* (publish)

🐕 Watchdog:
   WiFi: restart se offline > 120s
   MQTT: restart se offline > 180s (WiFi OK)
   Hardware: restart se freeze > 120s

💓 Heartbeat ogni 30 secondi

💓 Heartbeat: {"device_id":"esterno","uptime_s":35,"wifi_rssi":-45,"free_heap":234567,"mqtt_connected":true}
```

---

## ❌ TROUBLESHOOTING

### Problema: Compilazione fallisce

**Errore:** `WiFiManager.h: No such file or directory`

**Soluzione:** Installa libreria WiFiManager (vedi sezione Librerie)

---

### Problema: Upload fallisce

**Errore:** `A fatal error occurred: Failed to connect to ESP32`

**Soluzione:**
1. Premi e tieni premuto il pulsante `BOOT` sull'ESP32
2. Click Upload in Arduino IDE
3. Rilascia `BOOT` quando vedi "Connecting..."

---

### Problema: MQTT non si connette

**Serial Monitor mostra:** `🔌 MQTT reconnect... ❌ (rc=-2)`

**Soluzioni:**
1. Verifica credenziali HiveMQ (server, user, password)
2. Verifica che cluster HiveMQ sia attivo
3. Verifica firewall non blocchi porta 8883
4. Prova con `ALLOW_INSECURE_TLS = 1`

**Codici errore MQTT:**
- `rc=-2`: Network error (verifica WiFi e firewall)
- `rc=-4`: Connection timeout (verifica server address)
- `rc=5`: Autenticazione fallita (verifica username/password)

---

### Problema: WiFi non si connette

**Captive portal non appare**

**Soluzione:**
1. Disconnetti ESP32
2. Tieni premuto pulsante `BOOT`
3. Ricollega alimentazione
4. Rilascia `BOOT` dopo 3 secondi
5. ESP32 parte in safe mode → captive portal attivo

---

### Problema: Reset continuo

**Serial Monitor mostra restart loop**

**Causa:** Watchdog scatta (WiFi o MQTT non funzionanti)

**Soluzione temporanea:**
Aumenta timeout nelle linee 43-45:
```cpp
#define WIFI_RESTART_TIMEOUT 300000   // 5 minuti
#define MQTT_RESTART_TIMEOUT 300000   // 5 minuti
```

---

## 🔄 RESET CONFIGURAZIONE WIFI

Se vuoi riconfigurare WiFi (es: cambio scuola):

**Opzione 1: Via codice**

Aggiungi nel `setup()` prima di `setupWiFi()`:
```cpp
wifiManager.resetSettings();  // Cancella WiFi salvato
```

Flash, poi rimuovi quella riga e reflasha.

**Opzione 2: Via pulsante fisico (da implementare)**

TODO: Aggiungi pulsante su GPIO per reset WiFi

---

## ✅ VERIFICA SUCCESSO

Dopo flash e configurazione, dovresti vedere nel Serial Monitor:

- ✅ WiFi connesso con SSID e IP
- ✅ MQTT connesso con subscriptions
- ✅ Heartbeat ogni 30s
- ✅ LED hardware funzionanti
- ✅ Servo che rispondono a sensore IR

**Sistema pronto per test!** 🎉

---

## 📞 SUPPORTO

In caso di problemi:
1. Verifica questa guida
2. Controlla Serial Monitor per errori specifici
3. Verifica credenziali HiveMQ
4. Prova su rete WiFi diversa (hotspot telefono)