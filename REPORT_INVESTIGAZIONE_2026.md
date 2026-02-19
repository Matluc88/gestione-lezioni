# 🔍 Report Investigazione: Discrepanza Resoconto Annuale 2026

## Data: 19 Febbraio 2026

---

## 📋 Problema Riscontrato

Nel **Resoconto Annuale** per il 2026 su https://gestione-lezioni.onrender.com/resoconto_annuale si visualizza:

```
Dettaglio Compensi (2026)
Categoria                    Importo     Percentuale
----------------------------------------------------------
Completate e Fatturate      €175.00     1.2%
```

Ma le **fatture effettive** mostrano:
- **Fattura 03** - IFTS LECCE (2026-02-16): €300.00 (parziale)
- **Fattura 02** - IFTS-CAVALLINO (2026-02-12): €700.00 (parziale)

**Totale fatture: €1,000.00**

---

## 🔍 Analisi del Codice

### 1. Come funziona il Resoconto Annuale (`routes/resoconto.py`)

Il resoconto calcola i compensi nel seguente modo:

```python
# Per ogni lezione del 2026 (attive + archiviate):
compenso = ore * compenso_orario

if lezione['stato'] == 'Completato' and lezione['fatturato'] == 1:
    totale_fatturate += compenso
```

**Formula:** `Totale Fatturate = SOMMA(ore_lezione × compenso_orario)` per tutte le lezioni con:
- `data` dell'anno 2026
- `stato = 'Completato'`
- `fatturato = 1`

### 2. Come funzionano le Fatture (`fatture.py`)

Le fatture hanno un **importo inserito manualmente** che può essere diverso dal compenso calcolato:

```python
importo = float(request.form.get("importo"))  # Inserito manualmente
tipo_fatturazione = "parziale" o "totale"
```

Quando si crea una fattura:
1. Si selezionano le lezioni da fatturare
2. Si inserisce **manualmente** l'importo della fattura
3. Tutte le lezioni selezionate vengono marcate come `fatturato = 1`

---

## 🎯 Cause Possibili della Discrepanza

### Scenario A: Date delle Lezioni Errate
Le lezioni associate alle fatture 02 e 03 potrebbero avere date del **2025** invece che **2026**, anche se le fatture sono del 2026.

**Esempio:**
- Fattura 02: data_fattura = 2026-02-12
- Lezioni associate: date nel 2025-11 (novembre 2025)

### Scenario B: Fatturazione Parziale con Importo Diverso
Le fatture sono marcate come "parziali" con un importo inserito manualmente che **non corrisponde** al compenso calcolato delle lezioni.

**Esempio:**
- Lezioni totali: 3 lezioni × 2 ore × €25/h = €150
- Fattura inserita: €300 (anticipo o acconto)
- Il sistema marca le lezioni come fatturate ma il resoconto conta solo €150

### Scenario C: Lezioni Archiviate (MENO PROBABILE)
Il codice del resoconto **include** anche le lezioni archiviate:
```python
# Query per lezioni attive
cursor.execute("SELECT ... FROM lezioni ... WHERE extract_year(l.data) = %s", (anno_selezionato,))
lezioni = cursor.fetchall()

# Query per lezioni archiviate
cursor.execute("SELECT ... FROM archiviate ... WHERE extract_year(a.data) = %s", (anno_selezionato,))
lezioni_archiviate = cursor.fetchall()

# Combina entrambe
tutte_lezioni = lezioni + lezioni_archiviate
```

Quindi questo scenario è **meno probabile**.

---

## 💡 Soluzioni Proposte

### Soluzione 1: Verificare le Date delle Lezioni

**Query SQL da eseguire sul database:**

```sql
-- Trova le lezioni associate alle fatture 02 e 03
SELECT 
    f.numero_fattura,
    f.data_fattura AS data_fattura,
    f.importo AS importo_fattura,
    f.tipo_fatturazione,
    l.id AS id_lezione,
    l.data AS data_lezione,
    l.ora_inizio,
    l.ora_fine,
    l.compenso_orario,
    l.stato,
    l.fatturato,
    (EXTRACT(EPOCH FROM (TO_TIMESTAMP(l.ora_fine, 'HH24:MI') - TO_TIMESTAMP(l.ora_inizio, 'HH24:MI'))) / 3600) AS ore,
    (EXTRACT(EPOCH FROM (TO_TIMESTAMP(l.ora_fine, 'HH24:MI') - TO_TIMESTAMP(l.ora_inizio, 'HH24:MI'))) / 3600) * l.compenso_orario AS compenso_calcolato
FROM fatture f
INNER JOIN fatture_lezioni fl ON f.id_fattura = fl.id_fattura
LEFT JOIN lezioni l ON fl.id_lezione = l.id
WHERE f.numero_fattura IN ('02', '03')
ORDER BY f.numero_fattura, l.data;
```

**Controlla:**
- Le date delle lezioni sono veramente del 2026?
- Il compenso calcolato (ore × compenso_orario) corrisponde all'importo della fattura?

### Soluzione 2: Aggiungere un Warning nel Resoconto

Modificare `templates/resoconto_annuale.html` per mostrare un avviso quando ci sono discrepanze:

```html
{% if totale_fatturate != totale_importi_fatture %}
<div class="alert alert-warning">
    ⚠️ ATTENZIONE: Il totale fatturato calcolato (€{{ "%.2f"|format(totale_fatturate) }})
    non corrisponde all'importo totale delle fatture emesse (€{{ "%.2f"|format(totale_importi_fatture) }}).
    Questo può accadere con fatture parziali o acconti.
</div>
{% endif %}
```

### Soluzione 3: Creare una Vista "Fatture vs Compensi"

Aggiungere una nuova pagina che mostra il confronto tra:
- Compensi calcolati dalle lezioni
- Importi effettivi delle fatture

```python
# In routes/resoconto.py o fatture.py
@bp.route("/verifica_fatturazione/<anno>")
@login_required
def verifica_fatturazione(anno):
    """
    Mostra il confronto tra compensi calcolati e fatture emesse
    """
    # Query per ottenere entrambi i dati e confrontarli
    ...
```

### Soluzione 4: Modificare il Sistema di Fatturazione

**Opzione A - Fatturazione Automatica:**
Calcolare automaticamente l'importo basandosi sulle lezioni selezionate:

```python
# In fatture.py - aggiungi_fattura
lezioni_selezionate = request.form.getlist("lezioni")
importo_calcolato = 0

for id_lezione in lezioni_selezionate:
    lezione = get_lezione(id_lezione)
    ore = calcola_ore(lezione['ora_inizio'], lezione['ora_fine'])
    importo_calcolato += ore * lezione['compenso_orario']

# Suggerisci l'importo calcolato ma permetti di modificarlo
importo = float(request.form.get("importo", importo_calcolato))
```

**Opzione B - Sistema di Acconti:**
Introdurre un campo "percentuale_fatturata" per tracciare le fatture parziali:

```sql
ALTER TABLE fatture ADD COLUMN percentuale_fatturata INTEGER DEFAULT 100;
ALTER TABLE lezioni ADD COLUMN percentuale_fatturata INTEGER DEFAULT 0;
```

---

## 📊 Raccomandazione Immediata

### Per risolvere il problema subito:

1. **Esegui la query SQL** di Soluzione 1 per verificare le date
2. **Se le lezioni sono del 2025**: Sono state fatturate nel 2026 ma riguardano lezioni del 2025
   - Il resoconto del 2026 mostra €175 (forse ci sono altre lezioni del 2026?)
   - Le fatture 02 e 03 sono acconti per lezioni del 2025
3. **Se le lezioni sono del 2026**: C'è una discrepanza tra importo inserito e compenso calcolato
   - Verifica se gli importi delle fatture sono corretti
   - Considera di aggiungere un campo "note" per spiegare le differenze

---

## 🔧 Script di Investigazione Disponibili

Ho creato 3 script per aiutarti:

1. **`investigazione_postgres.py`** - Connessione diretta a PostgreSQL (richiede psycopg2)
2. **`investigazione_fatture_2026_standalone.py`** - Per database SQLite locale
3. **`investigazione_fatture_2026.py`** - Usa le utility del progetto

Per eseguire lo script PostgreSQL:
```bash
pip3 install --break-system-packages psycopg2-binary
python3 investigazione_postgres.py
```

---

## ✅ Conclusione

La discrepanza è **normale** quando:
- Le fatture sono **parziali** (acconti)
- Le fatture includono **importi non legati alle ore** (spese, rimborsi)
- Le lezioni fatturate hanno **date diverse dall'anno della fattura**

**Soluzione consigliata:**
1. Verificare le date delle lezioni (query SQL)
2. Aggiungere un warning nel resoconto quando ci sono discrepanze
3. Documentare le fatture parziali con note esplicative

---

**Report generato il:** 19/02/2026, 10:40
**Analisi effettuata da:** Sistema di Investigazione Automatico
