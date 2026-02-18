# 🔧 Istruzioni per Rimuovere il Vincolo UNIQUE su PostgreSQL

Il database PostgreSQL ha ancora un vincolo UNIQUE su `numero_fattura` che impedisce di avere lo stesso numero per anni diversi.

## 📋 Guida Passo-Passo su Render.com

### Step 1: Accedi a Render.com
1. Vai su [https://dashboard.render.com/](https://dashboard.render.com/)
2. Effettua il login con le tue credenziali

### Step 2: Trova il Database
1. Nella dashboard, cerca **"gestione_lezioni_db"** nella lista dei tuoi servizi
2. Dovrebbe avere l'icona di un database (cilindro) 
3. **Clicca sul nome del database**

### Step 3: Apri la Console SQL
1. Una volta dentro il database, guarda il menu in alto
2. Cerca e clicca su una di queste voci:
   - **"Shell"** oppure
   - **"Connect"** → poi **"External Connection"** → poi copia la stringa e usa un client SQL
   - **Se non vedi "Shell"**, cerca **"PSQL"** o **"Query"**
   
### Step 4: Esegui il Comando SQL

**⚠️ IMPORTANTE: Il vincolo si chiama `numero_fattura_unique`**

Copia e incolla ESATTAMENTE questo comando:

```sql
ALTER TABLE fatture DROP CONSTRAINT IF EXISTS numero_fattura_unique;
```

Premi **INVIO** o clicca **"Execute"** / **"Run"**

### Step 5: Verifica (Opzionale)

Per verificare che sia stato rimosso, esegui:

```sql
SELECT conname, contype 
FROM pg_constraint 
WHERE conrelid = 'fatture'::regclass 
  AND contype = 'u';
```

**Se non vedi nessun risultato** (o solo username_unique), il vincolo è stato rimosso! ✅

## Opzione 2: Tramite psql Locale (se hai psql installato)

```bash
psql "postgresql://gestione_lezioni_db_user:mslvJTuaoyj6aqvAOTOVj90x5jgcToHc@dpg-d0s0if95pdvs7392umsg-a.frankfurt-postgres.render.com/gestione_lezioni_db" -c "ALTER TABLE fatture DROP CONSTRAINT IF EXISTS fatture_numero_fattura_key;"
```

## Dopo la Rimozione

Una volta rimosso il vincolo, potrai:
- ✅ Creare fatture con lo stesso numero in anni diversi (es. "02" per 2024, 2025, 2026)
- ✅ Modificare fatture senza errori di vincolo
- ✅ L'applicazione funzionerà correttamente

## Verifica

Per verificare che tutto funzioni:
1. Riavvia l'applicazione Flask
2. Vai in "Gestione Fatture"
3. Prova a creare o modificare una fattura
4. Non dovrebbero più esserci errori di vincolo! 🎉
