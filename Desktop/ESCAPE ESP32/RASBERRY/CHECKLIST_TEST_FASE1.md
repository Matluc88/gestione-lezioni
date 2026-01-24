# ✅ CHECKLIST TEST FASE 1 - ESP32 ESTERNO

Esegui questi 5 test nell'ordine indicato per validare il firmware.

---

## 🧪 TEST 1: CAPTIVE PORTAL (Prima Configurazione)

**Obiettivo:** Verificare WiFiManager e configurazione dinamica WiFi

### Procedura:

1. **Flash firmware** con credenziali HiveMQ configurate
2. **Alimenta ESP32** (primo boot, nessun WiFi salvato)
3. **Apri Serial Monitor** (115200 baud)

### ✅ Verifica:

```
Serial Monitor mostra:
[ ] ╔════════════════════════════════════════════════╗
[ ] ║  ESP32 ESTERNO - STABLE CLOUD VERSION         ║
[ ] ╚════════════════════════════════════════════════╝
[ ] 🐕 Hardware WDT attivo (120s timeout)
[ ] 📌 Pin e servo configurati
[ ] 📡 ===== WIFI SETUP =====
[ ] ⚠️  Nessuna rete salvata!
[ ] 📶 Modalità Captive Portal attiva:
[ ]    SSID: EscapeRoom-Esterno
```

4. **Sul telefono/computer:**
   - [ ] Trovi rete WiFi `EscapeRoom-Esterno`
   - [ ] Riesci a connetterti (nessuna password richiesta)
   - [ ] Si apre pagina captive portal automaticamente (o vai a 192.168.4.1)
   - [ ] Vedi lista reti WiFi disponibili

5. **Configura WiFi:**
   - [ ] Selezioni la tua rete WiFi
   - [ ] Inserisci password
   - [ ] Click "Save"
   - [ ] ESP32 riavvia automaticamente

6. **Dopo riavvio:**
   - [ ] ESP32 si connette alla rete configurata
   - [ ] Serial Monitor mostra: `✅ WiFi connesso!`
   - [ ] Serial Monitor mostra SSID e IP corretto

### ⚠️ Se fallisce:
- Verifica libreria WiFiManager installata
- Prova con hotspot telefono (nessuna password)
- Aumenta `PORTAL_TIMEOUT` a 300 secondi

---

## 🧪 TEST 2: CONNESSIONE MQTT + HEARTBEAT

**Obiettivo:** Verificare connessione HiveMQ Cloud e heartbeat periodico

### Procedura:

1. **ESP32 connesso a WiFi** (da Test 1)
2. **Verifica Serial Monitor:**

### ✅ Verifica:

```
Serial Monitor mostra:
[ ] 🔌 ===== MQTT SETUP =====
[ ] ⚠️  TLS INSECURE MODE (solo per test!)
[ ]    Server: your-cluster.hivemq.cloud
[ ]    Port: 8883
[ ] 🔌 MQTT reconnect... ✅
[ ] 📥 Subscribed:
[ ]    - device/esterno/cmd/reset
[ ]    - escape/game-completion/won
[ ] ✅ ===== SISTEMA PRONTO =====
```

3. **Attendi 30 secondi:**
   - [ ] Vedi primo heartbeat nel Serial Monitor
   - [ ] Heartbeat formato: `💓 Heartbeat: {"device_id":"esterno",...}`

4. **Attendi altri 30 secondi:**
   - [ ] Vedi secondo heartbeat
   - [ ] `uptime_s` incrementa correttamente

### ✅ Verifica avanzata (opzionale - se hai MQTT Explorer):

**Tool:** [MQTT Explorer](http://mqtt-explorer.com/) (desktop app gratuita)

1. **Connetti MQTT Explorer a HiveMQ:**
   - Host: `your-cluster.hivemq.cloud`
   - Port: `8883`
   - Protocol: `mqtts://`
   - Username/Password: (tue credenziali)

2. **Subscribe a `device/esterno/#`:**
   - [ ] Vedi topic `device/esterno/heartbeat` arrivare ogni 30s
   - [ ] Vedi topic `device/esterno/status` con valore `online`
   - [ ] Payload heartbeat è JSON valido

### ⚠️ Se fallisce:
- **rc=-2**: Verifica firewall, prova hotspot telefono
- **rc=-4**: Verifica MQTT_SERVER corretto
- **rc=5**: Verifica username/password HiveMQ
- Se MQTT non connette ma WiFi OK → aumenta `MQTT_RESTART_TIMEOUT` temporaneamente

---

## 🧪 TEST 3: WATCHDOG WIFI (Auto-Recovery)

**Obiettivo:** Verificare che ESP32 si auto-recupera da disconnect WiFi

### Procedura:

1. **ESP32 running** (WiFi e MQTT connessi)
2. **Serial Monitor aperto**
3. **Spegni il router WiFi** (o disattiva hotspot se usi telefono)

### ✅ Verifica:

```
Serial Monitor mostra (entro 10 secondi):
[ ] ⚠️  WiFi perso, tentativo reconnect...
```

4. **Attendi 60 secondi** (ESP32 tenta reconnect)

5. **Riaccendi router/hotspot**

```
Serial Monitor mostra (entro 30 secondi):
[ ] ✅ WiFi recuperato!
[ ] 🔌 MQTT reconnect... ✅
[ ] 💓 Heartbeat: ... (riprende normale)
```

### ✅ Verifica watchdog restart:

6. **Spegni di nuovo router/hotspot**
7. **Lascia spento per 130 secondi** (oltre timeout di 120s)

```
Serial Monitor mostra:
[ ] 🔴 ===== WIFI WATCHDOG TIMEOUT =====
[ ]    WiFi offline > 120s → RESTART!
[ ] (ESP32 riavvia automaticamente)
```

8. **Riaccendi router:**
   - [ ] ESP32 ripartito si riconnette automaticamente
   - [ ] Sistema torna operativo senza intervento manuale

### ⚠️ Se fallisce:
- Watchdog non scatta → verifica `esp_task_wdt_reset()` nel loop
- Restart troppo frequenti → aumenta `WIFI_RESTART_TIMEOUT`

---

## 🧪 TEST 4: RESET REMOTO VIA MQTT

**Obiettivo:** Verificare comando reset da remoto

### Procedura:

**Opzione A: Con MQTT Explorer (consigliato)**

1. **ESP32 running e connesso**
2. **MQTT Explorer aperto e connesso a HiveMQ**
3. **Publish messaggio:**
   - Topic: `device/esterno/cmd/reset`
   - Payload: `1` (o qualsiasi stringa)
   - QoS: 0
   - Retained: false

### ✅ Verifica:

```
Serial Monitor mostra (immediatamente):
[ ] 🔴 ===== RESET REMOTO RICEVUTO =====
[ ]    Riavvio tra 1 secondo...
[ ] (ESP32 riavvia)
[ ] ╔════════════════════════════════════════════════╗
[ ] ║  ESP32 ESTERNO - STABLE CLOUD VERSION         ║
[ ] (boot sequence normale...)
```

**Opzione B: Con mosquitto_pub (CLI)**

Se hai mosquitto installato:
```bash
mosquitto_pub \
  -h your-cluster.hivemq.cloud \
  -p 8883 \
  -u escape_device \
  -P your_password \
  --capath /etc/ssl/certs/ \
  -t device/esterno/cmd/reset \
  -m "1"
```

### ⚠️ Se fallisce:
- Verifica topic esatto: `device/esterno/cmd/reset` (no typo)
- Verifica subscribe nel Serial Monitor al boot
- Prova con QoS 1 invece di 0

---

## 🧪 TEST 5: HARDWARE FUNZIONANTE

**Obiettivo:** Verificare che hardware fisico funziona come prima

### Procedura:

1. **ESP32 alimentato e connesso MQTT**
2. **LED e Servo connessi come da schema**

### ✅ Verifica LED Cancello:

- [ ] Sensore IR libero (HIGH) → LED Verde acceso, LED Rosso spento
- [ ] Sensore IR coperto (LOW) → LED Rosso acceso, LED Verde spento

### ✅ Verifica LED Porta:

- [ ] Porta chiusa (posPorta=0) → LED Rosso
- [ ] Porta aperta (posPorta>0) → LED Verde

### ✅ Verifica Servo (movimento smooth):

3. **Copri sensore IR:**
   - [ ] Cancelli (DX e SX) si muovono verso 0° (smooth, non scatto)
   - [ ] Porta si muove verso 0°
   - [ ] Tetto si muove verso 0°

4. **Libera sensore IR:**
   - [ ] Cancelli si muovono verso 90° (smooth)
   - [ ] Porta si muove verso 90°
   - [ ] Tetto si muove verso 180°

### ✅ Verifica RGB Victory (opzionale):

5. **Simula vittoria** (via MQTT Explorer):
   - Publish su `escape/game-completion/won`
   - Payload: `true`
   - [ ] RGB inizia animazione ciclo colori (120ms per colore)

6. **Disattiva vittoria:**
   - Publish su `escape/game-completion/won`
   - Payload: `false`
   - [ ] RGB si spegne

### ✅ Verifica MQTT publish (con MQTT Explorer):

7. **Subscribe a `escape/esterno/999/#`:**
   - [ ] Vedi `escape/esterno/999/led/stato` ("VERDE" o "ROSSO")
   - [ ] Vedi `escape/esterno/999/ir-sensor/stato` ("LIBERO" o "OCCUPATO")
   - [ ] Vedi posizioni servo aggiornate ogni 500ms

### ⚠️ Se fallisce:
- LED non funzionano → verifica pin connections
- Servo non si muovono → verifica alimentazione 5V esterna (non da USB!)
- MQTT publish non arriva → verifica client.connected() nel Serial Monitor

---

## 📊 RISULTATO FINALE

### ✅ TUTTI I TEST PASSATI

**Congratulazioni!** 🎉 Firmware FASE 1 validato con successo.

**Puoi procedere con:**
1. Deploy su hardware definitivo
2. Test in rete scolastica reale
3. Replica pattern su altri 4 ESP32

---

### ⚠️ ALCUNI TEST FALLITI

**Priorità:**

**CRITICI (blocca deployment):**
- [ ] Test 1 (Captive Portal) - senza questo non configuri WiFi
- [ ] Test 2 (MQTT) - senza questo nessun monitoraggio

**IMPORTANTI (risolvi prima di produzione):**
- [ ] Test 3 (Watchdog) - importante per stabilità long-term
- [ ] Test 4 (Reset remoto) - utile per gestione remota

**OPZIONALI (verifica dopo):**
- [ ] Test 5 (Hardware) - solo se usi fisicamente i componenti

---

## 📝 REPORT PROBLEMI

Quando riporti problemi, includi:

1. **Quale test è fallito** (numero test)
2. **Log Serial Monitor completo** (da boot)
3. **Configurazione:**
   - Rete WiFi (nome, tipo: casa/scuola/hotspot)
   - Cluster HiveMQ usato
   - Versione librerie Arduino

4. **Comportamento osservato vs atteso**

---

## 🚀 PROSSIMI PASSI

Dopo validazione FASE 1:

1. **Test rete scolastica:** Porta ESP32 a scuola, connetti alla loro WiFi
2. **Test long-term:** Lascia acceso 24h, verifica stabilità
3. **Test firewall:** Prova su reti diverse (casa, scuola, hotspot)
4. **Documentazione:** Annota eventuali problemi specifici di rete

5. **Replica su altri ESP32:**
   - Soggiorno
   - Cucina
   - Bagno
   - Camera

**Buon testing! 🎯**