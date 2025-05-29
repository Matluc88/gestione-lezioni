# Migrazione da SQLite a PostgreSQL

Questo documento fornisce istruzioni dettagliate per migrare l'applicazione "Gestione Lezioni" da SQLite a PostgreSQL su Render.

## 1. Prerequisiti

- Database PostgreSQL creato su Render
- Stringa di connessione PostgreSQL: `postgresql://gestione_lezioni_db_user:mslvJTuaoyj6aqvAOTOVj90x5jgcToHc@dpg-d0s0if95pdvs7392umsg-a/gestione_lezioni_db`
- Python 3.6+ con pip installato

## 2. Installazione delle Dipendenze

```bash
pip install -r requirements.txt
```

## 3. Configurazione dell'Ambiente

Crea un file `.env` nella directory principale dell'applicazione:

```
DATABASE_URL=postgresql://gestione_lezioni_db_user:mslvJTuaoyj6aqvAOTOVj90x5jgcToHc@dpg-d0s0if95pdvs7392umsg-a/gestione_lezioni_db
```

## 4. Creazione delle Tabelle in PostgreSQL

Il file `schema_postgres.sql` contiene la definizione delle tabelle e delle funzioni necessarie per PostgreSQL.

```bash
psql "postgresql://gestione_lezioni_db_user:mslvJTuaoyj6aqvAOTOVj90x5jgcToHc@dpg-d0s0if95pdvs7392umsg-a/gestione_lezioni_db" -f schema_postgres.sql
```

## 5. Migrazione dei Dati

Il file `migrate_to_postgres.py` gestisce la migrazione dei dati da SQLite a PostgreSQL.

```bash
python migrate_to_postgres.py
```

Questo script:
- Esporta tutti i dati da SQLite a file CSV
- Importa i dati dai file CSV a PostgreSQL
- Aggiorna le sequenze per le colonne SERIAL

## 6. Aggiornamento della Configurazione dell'Applicazione

Per utilizzare PostgreSQL invece di SQLite:

1. Rinomina `database_postgres.py` in `database.py` (fai prima un backup del file originale)
2. Assicurati che il file `.env` contenga la stringa di connessione corretta

## 7. Avvio dell'Applicazione con PostgreSQL

```bash
python app.py
```

## 8. Verifica della Migrazione

Dopo la migrazione, verifica che:
- Tutte le lezioni (197) siano state migrate correttamente
- Tutti i corsi (18) siano stati migrati correttamente
- Le fatture e le relazioni fatture-lezioni siano corrette
- La funzionalità di fatturazione parziale funzioni correttamente

## 9. Ottimizzazioni PostgreSQL

L'applicazione è stata ottimizzata per PostgreSQL con:
- Utilizzo di `DictCursor` per risultati come dizionari
- Sostituzione delle funzioni SQLite con equivalenti PostgreSQL
- Gestione corretta delle sequenze SERIAL
- Utilizzo di `RETURNING` per ottenere gli ID generati

## 10. Risoluzione dei Problemi

Se incontri problemi durante la migrazione:

- **Errori di connessione**: Verifica che l'URL del database sia corretto
- **Errori SQL**: Controlla la sintassi delle query, in particolare quelle che usano funzioni specifiche
- **Errori di importazione**: Verifica che i dati CSV siano formattati correttamente
- **Errori di sequenza**: Esegui manualmente l'aggiornamento delle sequenze

## 11. Backup e Ripristino

È consigliabile eseguire regolarmente backup del database:

```bash
pg_dump "postgresql://gestione_lezioni_db_user:mslvJTuaoyj6aqvAOTOVj90x5jgcToHc@dpg-d0s0if95pdvs7392umsg-a/gestione_lezioni_db" > backup.sql
```

Per ripristinare:

```bash
psql "postgresql://gestione_lezioni_db_user:mslvJTuaoyj6aqvAOTOVj90x5jgcToHc@dpg-d0s0if95pdvs7392umsg-a/gestione_lezioni_db" < backup.sql
```
