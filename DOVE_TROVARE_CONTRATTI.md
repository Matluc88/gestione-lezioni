# 📍 Dove Trovare il Tasto Contratti

## 🎯 Posizione del Pulsante Contratti

Il tasto "Contratti" si trova nel **menu "Altro"** nella bottom bar dell'app.

---

## 📱 Come Accedere (Passo per Passo)

### Passo 1: Avvia l'Applicazione
```bash
python3 app.py
```

### Passo 2: Fai Login
- Username: `admin`
- Password: (la tua password)

### Passo 3: Guarda in Basso
Nella parte inferiore della schermata vedrai **5 TAB**:

```
┌──────────────────────────────────────────────────┐
│                                                  │
│            (contenuto pagina)                    │
│                                                  │
└──────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────┐
│  🏠      📅      📚      💰      ⋯               │
│ Home  Calendario Corsi  Fatture Altro            │
└──────────────────────────────────────────────────┘
```

### Passo 4: Clicca sul Tab "Altro" (⋯)
Clicca sull'ultimo tab in basso a destra con l'icona **⋯** (tre puntini)

### Passo 5: Si Apre il Menu
Si aprirà un menu dal basso con tutte le opzioni:

```
┌──────────────────────────────────────────────────┐
│                    Menu                     ✕    │
├──────────────────────────────────────────────────┤
│ 📊 Stato Crediti                            >    │
│ 💵 Compenso                                 >    │
│ 📈 Resoconto Annuale                        >    │
│ 📂 Lezioni Archiviate                       >    │
│ 📁 Corsi Archiviati                         >    │
│ 📄 Contratti                                >    │  ⬅️ QUESTO!
│ 📥 Importa CSV                              >    │
│ 📤 Esporta CSV                              >    │
│ 🔄 Sincronizza Google Calendar              >    │
│ 🚪 Logout                                   >    │
└──────────────────────────────────────────────────┘
```

### Passo 6: Clicca su "📄 Contratti"
È la **sesta voce** dall'alto nel menu!

---

## ✅ Verifica Rapida

**Se non vedi la voce "Contratti":**

1. ⚠️ Hai installato le dipendenze?
   ```bash
   bash INSTALLA_DIPENDENZE.sh
   ```

2. ⚠️ Hai riavviato l'app dopo le modifiche?
   - Chiudi l'app (Ctrl+C nel terminale)
   - Riavvia: `python3 app.py`

3. ⚠️ Controlla che il file `routes/contratti.py` esista
   ```bash
   ls routes/contratti.py
   ```

---

## 🎬 Video Tutorial (Sequenza)

1. **Apri browser** → vai a `http://localhost:5000`
2. **Login**
3. **Guarda in basso** → vedi 5 tab
4. **Clicca "Altro"** (tab con ⋯)
5. **Menu si apre** dal basso
6. **Cerca icona 📄** → "Contratti"
7. **Clicca!**

---

## 🚀 Cosa Succede Dopo

Una volta cliccato su "Contratti", vedrai:

- **Se non hai contratti:** Schermata vuota con pulsante "📄 Carica Contratto"
- **Se hai contratti:** Lista dei contratti caricati

**Clicca sul FAB button 📄 in basso a destra** per caricare il tuo primo contratto PDF!

---

## 💡 Nota Importante

La voce "Contratti" è **SEMPRE** nel menu "Altro", non è un tab separato nella bottom bar. 

Questo perché ci sono già 5 tab principali e "Contratti" fa parte delle funzioni avanzate insieme a:
- Stato Crediti
- Compenso
- Resoconto Annuale
- Archivi
- Import/Export

---

**Hai ancora problemi a trovarlo?** 
Verifica che l'app sia riavviata dopo le modifiche! 🔄
