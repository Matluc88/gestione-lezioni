# 🔧 Istruzioni per Rimuovere il Vincolo UNIQUE su PostgreSQL

Il database PostgreSQL ha ancora un vincolo UNIQUE su `numero_fattura` che impedisce di avere lo stesso numero per anni diversi.

## Opzione 1: Tramite Dashboard Render.com (CONSIGLIATO)

1. Vai su [https://dashboard.render.com/](https://dashboard.render.com/)
2. Accedi al tuo account
3. Clicca sul database **gestione_lezioni_db**
4. Vai nella sezione **"Shell"** o **"SQL Editor"**
5. Esegui questo comando SQL:

```sql
ALTER TABLE fatture DROP CONSTRAINT IF EXISTS fatture_numero_fattura_key;
```

6. Verifica che sia stato rimosso:

```sql
SELECT conname, contype 
FROM pg_constraint 
WHERE conrelid = 'fatture'::regclass 
  AND contype = 'u';
```

Se non vedi output, il vincolo è stato rimosso con successo! ✅

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
