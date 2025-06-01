# Guida alla Risoluzione dei Problemi di Timezone

## Problema
Se quando selezioni il 10 Giugno dal calendario vedi ancora il 9 Giugno, segui questi passaggi:

## Soluzioni Rapide

### 1. Svuota la Cache del Browser
**Chrome/Edge:**
1. Premi `Ctrl+Shift+Canc`
2. Seleziona "Immagini e file memorizzati nella cache"
3. Clicca "Cancella dati"

**Firefox:**
1. Premi `Ctrl+Shift+Canc`
2. Seleziona "Cache"
3. Clicca "Cancella adesso"

### 2. Ricarica Forzata
- **Windows**: `Ctrl+F5` oppure `Ctrl+Shift+R`
- **Mac**: `Cmd+Shift+R`

### 3. Modalità Incognito/Privata
1. Apri una nuova finestra in modalità incognito/privata
2. Vai all'applicazione
3. Testa la selezione delle date

### 4. Verifica che la Correzione Funzioni
1. Vai alla pagina "Aggiungi Lezioni"
2. Clicca "SELEZIONA DATE DAL CALENDARIO"
3. Seleziona il 10 Giugno 2025
4. Chiudi il calendario (premi Esc)
5. Dovresti vedere "mar 10 giu 2025" nel pannello delle date selezionate

## Se il Problema Persiste

### Controlla la Console del Browser
1. Premi `F12` per aprire gli Strumenti per Sviluppatori
2. Vai alla scheda "Console"
3. Cerca eventuali errori JavaScript
4. Testa la selezione delle date

### Verifica la Rete
1. Negli Strumenti per Sviluppatori, vai alla scheda "Network"
2. Spunta "Disable cache"
3. Ricarica la pagina
4. Testa la funzionalità

## Conferma della Correzione
La correzione è stata implementata e testata con successo:
- ✅ Il 10 Giugno viene visualizzato correttamente come "10 Giugno"
- ✅ Non c'è più lo spostamento di timezone
- ✅ La selezione di date multiple funziona correttamente

Se continui ad avere problemi dopo aver seguito questi passaggi, potrebbe essere necessario verificare l'ambiente di deployment o contattare il supporto tecnico.
