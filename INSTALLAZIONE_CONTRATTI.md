# 📄 Guida Installazione Modulo Contratti con Claude AI

## 🎉 Implementazione Completata!

Il modulo Contratti è stato completamente implementato e integrato nell'applicazione. Ora puoi gestire i tuoi contratti PDF con analisi AI intelligente powered by Claude.

---

## ⚠️ Installazione Dipendenze Richieste

Prima di utilizzare il modulo, è necessario installare due nuove librerie Python:

### Metodo 1: Con Virtual Environment (Raccomandato)

Se stai usando un virtual environment (venv), attivalo e installa:

```bash
# Attiva il virtual environment (se presente)
source venv/bin/activate  # su macOS/Linux
# oppure
venv\Scripts\activate  # su Windows

# Installa le dipendenze
pip install anthropic pypdf2
```

### Metodo 2: Installazione Diretta

Se non usi un virtual environment:

```bash
python3 -m pip install --break-system-packages anthropic pypdf2
```

### Metodo 3: Verifica e Riprova

Se hai già altre dipendenze installate, prova:

```bash
pip3 install anthropic pypdf2
```

---

## 🚀 Funzionalità Implementate

### 1. **Upload Contratti PDF**
- Caricamento file PDF (max 10MB)
- Estrazione automatica del testo
- Salvataggio nel database

### 2. **Analisi AI con Claude**
- Analisi automatica del contratto all'upload
- Estrazione informazioni chiave:
  - Numero contratto
  - Cliente/Studente
  - Date (inizio, fine, durata)
  - Compenso (orario o totale)
  - Materie/argomenti
  - Numero ore previste

### 3. **Chat Interattiva**
- Interfaccia chat moderna in stile iOS
- Domande in linguaggio naturale
- Risposte precise basate sul contenuto del contratto
- Esempi di domande:
  - "Dammi il numero del corso"
  - "Qual è il compenso orario?"
  - "Quali sono le date del contratto?"
  - "Quante ore sono previste?"

### 4. **Gestione Completa**
- Lista tutti i contratti caricati
- Visualizzazione dettagli
- Collegamento a corsi esistenti
- Eliminazione contratti

---

## 📍 Come Accedere

1. Avvia l'applicazione: `python3 app.py`
2. Fai login
3. Clicca su **"Altro"** nella bottom tab bar
4. Seleziona **"Contratti"** (icona 📄)

---

## 🎯 Esempio di Utilizzo

### Scenario: Caricamento Nuovo Contratto

1. **Carica Contratto**
   - Click sul FAB button "📄" in basso a destra
   - Seleziona il file PDF
   - (Opzionale) Compila numero contratto, cliente
   - (Opzionale) Collega a un corso esistente
   - Click "📤 Carica e Analizza"

2. **Analisi Automatica**
   - Claude AI analizza il PDF (10-20 secondi)
   - Visualizzazione informazioni estratte nella sezione "🤖 Analisi AI"

3. **Chat Interattiva**
   - Usa le domande esempio o scrivi la tua
   - Esempio: "Qual è il compenso orario?"
   - Claude risponde basandosi sul contenuto del contratto

4. **Collegamento Corso**
   - Nella sezione "Azioni" puoi collegare il contratto a un corso
   - Utile per tenere traccia di quale contratto è associato a quale corso

---

## 🗄️ Database

È stata aggiunta una nuova tabella `contratti`:

```sql
CREATE TABLE contratti (
    id SERIAL PRIMARY KEY,
    numero_contratto TEXT,
    nome_file TEXT NOT NULL,
    file_path TEXT NOT NULL,
    data_upload TEXT NOT NULL,
    cliente TEXT,
    contenuto_estratto TEXT,
    id_corso TEXT,
    FOREIGN KEY (id_corso) REFERENCES corsi(id_corso)
);
```

La tabella viene creata automaticamente all'avvio dell'app.

---

## 🔑 API Key Anthropic

La chiave API è già configurata nel file `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-api03-...
```

⚠️ **Importante**: Non condividere mai questa chiave e non commitarla su GitHub!

---

## 📦 File Creati/Modificati

### Nuovi File
- `routes/contratti.py` - Blueprint per gestione contratti
- `templates/contratti.html` - Lista contratti
- `templates/upload_contratto.html` - Form upload
- `templates/dettaglio_contratto.html` - Dettaglio + chat AI
- `uploads/contratti/` - Cartella per PDF caricati
- `INSTALLAZIONE_CONTRATTI.md` - Questa guida

### File Modificati
- `app.py` - Registrazione nuovo blueprint
- `.env` - Aggiunta API key Anthropic
- `requirements.txt` - Aggiunte dipendenze anthropic e pypdf2
- `schema.sql` - Aggiunta tabella contratti
- `schema_postgres.sql` - Aggiunta tabella contratti
- `templates/components/ios_bottomtab.html` - Aggiunta voce menu

---

## 💡 Tips & Best Practices

1. **Formato PDF**: Assicurati che i PDF siano testuali e non scansioni (per migliore estrazione testo)
2. **Dimensione File**: Limite di 10MB per file
3. **Domande Specifiche**: Più la domanda è specifica, migliore sarà la risposta
4. **Collegamento Corsi**: Collega sempre il contratto al corso corrispondente per migliore organizzazione

---

## 🐛 Troubleshooting

### Errore: "Chiave API Anthropic non configurata"
- Verifica che il file `.env` contenga `ANTHROPIC_API_KEY`
- Riavvia l'applicazione

### Errore: "Impossibile estrarre il testo dal PDF"
- Il PDF potrebbe essere una scansione/immagine
- Prova con un PDF testuale

### Errore: "Module 'anthropic' not found"
- Le dipendenze non sono installate
- Segui le istruzioni di installazione sopra

---

## 🎨 Design & UI

L'interfaccia segue lo stile iOS del resto dell'applicazione:
- Design pulito e moderno
- Animazioni fluide
- Chat bubble style per i messaggi
- Card con gradient per l'analisi AI
- Responsive e mobile-friendly

---

## 🚀 Prossimi Passi (Opzionali)

Possibili miglioramenti futuri:
- [ ] Creazione automatica corso da contratto
- [ ] Export analisi contratto in PDF
- [ ] Notifiche scadenza contratti
- [ ] Ricerca full-text nei contratti
- [ ] Statistiche contratti (totali, attivi, ecc.)

---

## ✅ Test Rapido

Per testare che tutto funzioni:

1. Installa le dipendenze (vedi sopra)
2. Avvia l'app: `python3 app.py`
3. Login
4. Menu Altro → Contratti
5. Carica un PDF di test
6. Prova la chat con una domanda

---

**Implementato il**: 19 Febbraio 2026
**Versione**: 1.0
**AI Provider**: Anthropic Claude 3.5 Sonnet

---

Per domande o problemi, consulta la documentazione di Claude AI: https://docs.anthropic.com
