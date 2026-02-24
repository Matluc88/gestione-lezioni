from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
import os
import base64
import json
import tempfile
from io import BytesIO
from datetime import datetime
from utils.time_utils import get_local_now, format_date_for_template, format_datetime_for_db
from werkzeug.utils import secure_filename
from db_utils import db_connection, get_db_connection, get_placeholder
from utils.security import sanitize_input, sanitize_form_data
from utils.sql_utils import sanitize_sql_identifier

fatture_bp = Blueprint('fatture', __name__, url_prefix='/fatture')

# ─── Helpers per Claude Vision ────────────────────────────────────────────────
def _pdf_to_base64_images_fattura(file_path, max_pages=10):
    """Converte PDF fattura in immagini JPEG base64 per Claude Vision."""
    import gc
    from pdf2image import convert_from_path
    from PIL import Image
    try:
        images = convert_from_path(file_path, first_page=1, last_page=max_pages, dpi=300)
        base64_images = []
        for img in images:
            max_size = 1568
            if img.width > max_size or img.height > max_size:
                ratio = min(max_size / img.width, max_size / img.height)
                img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.Resampling.LANCZOS)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            buffered = BytesIO()
            img.save(buffered, format="JPEG", quality=92, optimize=True)
            base64_images.append(base64.b64encode(buffered.getvalue()).decode())
            img.close()
            buffered.close()
        del images
        gc.collect()
        return base64_images
    except Exception as e:
        print(f"Errore conversione PDF fattura: {e}")
        gc.collect()
        return None


_PROMPT_ANALISI_FATTURA = """Sei un assistente esperto nell'analisi di fatture e notule italiane.

Analizza questo documento e restituisci un JSON con i seguenti campi (usa null se non trovato):

{
  "numero_fattura": "...",
  "data_fattura": "YYYY-MM-DD",
  "monte_ore": <numero float TOTALE di tutte le ore, es. 94.0>,
  "importo_lordo": <compenso lordo prima delle trattenute, es. 2820.00>,
  "importo_netto": <totale da percepire dopo ritenuta d'acconto, es. 2256.00>,
  "ritenuta_acconto": <importo ritenuta d'acconto, es. 564.00, oppure null se non presente>,
  "compenso_orario": <numero float o null>,
  "codice_corso": "...",
  "nome_corso": "...",
  "corsi": [
    {"codice": "...", "nome": "...", "ore": <numero float>},
    ...
  ],
  "cliente": "...",
  "periodo": "...",
  "note_ai": "breve nota su cosa hai trovato"
}

ISTRUZIONI:
- "monte_ore": la SOMMA TOTALE di tutte le ore di docenza nella fattura (anche se su più corsi).
- "corsi": SE la fattura riguarda PIÙ corsi, elenca ciascuno con codice, nome e ore. Se è un solo corso, puoi omettere o mettere un array con un elemento.
- "codice_corso" e "nome_corso": se c'è un solo corso usali normalmente; se ci sono più corsi, metti il primo/principale (o lascia null).
- "importo_lordo": il COMPENSO LORDO prima di qualsiasi trattenuta/ritenuta. Se non c'è ritenuta, coincide col totale.
- "importo_netto": il TOTALE DA PERCEPIRE dopo la ritenuta d'acconto. Se non c'è ritenuta, coincide col lordo.
- "ritenuta_acconto": l'importo numerico della ritenuta d'acconto (es. 100.00), NON la percentuale.
  Per ricevute di collaborazione occasionale la ritenuta è solitamente il 20% del lordo.
- Se nel documento c'è solo un importo totale senza ritenuta, metti lo stesso valore sia in importo_lordo che importo_netto.
- "periodo": il periodo di riferimento della fattura (es. "Febbraio 2026", "01/01-31/01/2026").
- Rispondi SOLO con il JSON, senza testo aggiuntivo."""


UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "fatture")
ALLOWED_EXTENSIONS = {'pdf'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
print(f"✅ Cartella per le fatture verificata: {UPLOAD_FOLDER}")


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_corsi():
    """Recupera la lista di corsi disponibili nel database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT id_corso FROM lezioni ORDER BY id_corso")
    corsi = [row[0] for row in cursor.fetchall()]
    conn.close()
    return corsi


def get_fatture():
    """Recupera tutte le fatture emesse"""
    conn = get_db_connection()
    cursor = conn.cursor()

    from db_utils import get_group_concat_function
    group_concat_func = get_group_concat_function()

    cursor.execute(f'''
        SELECT f.id_fattura, f.numero_fattura, f.id_corso, f.data_fattura, f.importo, f.tipo_fatturazione,
               f.file_pdf, {group_concat_func}(l.data, ', ') AS lezioni_fatturate
        FROM fatture f
        LEFT JOIN fatture_lezioni fl ON f.id_fattura = fl.id_fattura
        LEFT JOIN lezioni l ON fl.id_lezione = l.id
        GROUP BY f.id_fattura
        ORDER BY f.data_fattura DESC
    ''')
    fatture = cursor.fetchall()
    conn.close()
    return fatture


# ─── Route: Lista fatture ──────────────────────────────────────────────────────

@fatture_bp.route("/")
@login_required
def index():
    """Pagina principale delle fatture e delle lezioni fatturate"""
    corsi = get_corsi()
    corso_scelto = sanitize_input(request.args.get("corso_scelto", default="", type=str))
    fatture = get_fatture()

    corso_status = ""
    lezioni_fatturate = []
    ore_fatturate_totali = 0
    ore_totali_corso = 0

    if corso_scelto:
        conn = get_db_connection()
        cursor = conn.cursor()

        placeholder = get_placeholder()
        cursor.execute(f"""
            SELECT id, data, ora_inizio, ora_fine
            FROM lezioni
            WHERE id_corso = {placeholder} AND fatturato = 1
            ORDER BY data
        """, (corso_scelto,))
        lezioni_fatturate_rows = cursor.fetchall()

        lezioni_fatturate = [
            {"id": row["id"], "data": row["data"], "ora_inizio": row["ora_inizio"], "ora_fine": row["ora_fine"]}
            for row in lezioni_fatturate_rows
        ]

        cursor.execute(f"""
            SELECT COUNT(*) as totale FROM lezioni WHERE id_corso = {placeholder}
        """, (corso_scelto,))
        totale_lezioni = cursor.fetchone()["totale"]

        cursor.execute(f"""
            SELECT COUNT(*) as non_fatturate FROM lezioni WHERE id_corso = {placeholder} AND fatturato = 0
        """, (corso_scelto,))
        lezioni_non_fatturate = cursor.fetchone()["non_fatturate"]

        cursor.execute(f"""
            SELECT f.id_fattura, f.data_fattura, f.importo, f.tipo_fatturazione, COUNT(fl.id_lezione) as num_lezioni
            FROM fatture f
            LEFT JOIN fatture_lezioni fl ON f.id_fattura = fl.id_fattura
            WHERE f.id_corso = {placeholder}
            GROUP BY f.id_fattura
            ORDER BY f.data_fattura DESC
        """, (corso_scelto,))
        fatture_corso = cursor.fetchall()

        if lezioni_non_fatturate == 0 and totale_lezioni > 0:
            corso_status = "✅ Corso completamente fatturato"
        elif lezioni_non_fatturate > 0:
            corso_status = f"⚠️ Mancano {lezioni_non_fatturate} lezioni da fatturare su un totale di {totale_lezioni}"
        else:
            corso_status = "❌ Nessuna lezione presente per questo corso"

        ore_totali_corso = totale_lezioni
        conn.close()

        for lezione in lezioni_fatturate:
            inizio = datetime.strptime(lezione["ora_inizio"], "%H:%M")
            fine = datetime.strptime(lezione["ora_fine"], "%H:%M")
            durata = (fine - inizio).seconds / 3600
            ore_fatturate_totali += durata

    return render_template("fatture.html",
                           corsi=corsi,
                           fatture=fatture,
                           corso_scelto=corso_scelto,
                           corso_status=corso_status,
                           ore_fatturate_totali=round(ore_fatturate_totali, 2),
                           ore_totali_corso=ore_totali_corso,
                           lezioni_fatturate=lezioni_fatturate,
                           current_tab='altro')


# ─── Route: Fattura corso ──────────────────────────────────────────────────────

@fatture_bp.route("/fattura_corso", methods=["GET", "POST"])
@login_required
def fattura_corso():
    """Pagina per fatturare un intero corso o singole lezioni"""
    corso_scelto = sanitize_input(request.args.get("corso_scelto", default="", type=str))

    if not corso_scelto:
        flash("Seleziona un corso valido.", "danger")
        return redirect(url_for("fatture.index"))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        fattura_tutto = sanitize_input(request.form.get("fattura_tutto"))
        lezioni_selezionate = request.form.getlist("lezioni")
        mese_corrente = datetime.now().strftime("%Y-%m")

        if fattura_tutto:
            placeholder = get_placeholder()
            cursor.execute(f"""
                UPDATE lezioni
                SET fatturato = 1, mese_fatturato = {placeholder}
                WHERE id_corso = {placeholder} AND fatturato = 0
            """, (mese_corrente, corso_scelto))
        else:
            for id_lezione in lezioni_selezionate:
                placeholder = get_placeholder()
                cursor.execute(f"""
                    UPDATE lezioni
                    SET fatturato = 1, mese_fatturato = {placeholder}
                    WHERE id = {placeholder}
                """, (mese_corrente, id_lezione))

        conn.commit()
        conn.close()
        flash("Lezione/i fatturata/e con successo!", "success")
        return redirect(url_for("fatture.index", corso_scelto=corso_scelto))

    placeholder = get_placeholder()
    cursor.execute(f"""
        SELECT id, data, ora_inizio, ora_fine
        FROM lezioni
        WHERE id_corso = {placeholder} AND fatturato = 0
        ORDER BY data
    """, (corso_scelto,))
    lezioni_non_fatturate_rows = cursor.fetchall()
    conn.close()

    lezioni_non_fatturate = [
        {"id": row["id"], "data": row["data"], "ora_inizio": row["ora_inizio"], "ora_fine": row["ora_fine"]}
        for row in lezioni_non_fatturate_rows
    ]

    return render_template("fattura_corso.html", corso_scelto=corso_scelto, lezioni=lezioni_non_fatturate)


# ─── Route: Aggiungi fattura ───────────────────────────────────────────────────

@fatture_bp.route("/aggiungi_fattura", methods=["GET", "POST"])
@login_required
def aggiungi_fattura():
    """Pagina per aggiungere una nuova fattura con tutti i dettagli"""
    conn_read = None
    conn_write = None

    corso_preselezionato = sanitize_input(request.args.get("corso", default="", type=str))

    try:
        conn_read = get_db_connection()
        cursor_read = conn_read.cursor()

        cursor_read.execute("SELECT DISTINCT id_corso FROM lezioni ORDER BY id_corso")
        corsi = [row[0] for row in cursor_read.fetchall()]

        cursor_read.execute("""
            SELECT DISTINCT c.cliente
            FROM corsi c
            WHERE c.cliente IS NOT NULL AND c.cliente != ''
            ORDER BY c.cliente
        """)
        clienti = [row[0] for row in cursor_read.fetchall()]

        cursor_read.execute("""
            SELECT l.id, l.id_corso, l.materia, l.data, l.ora_inizio, l.ora_fine, l.compenso_orario,
                   COALESCE(c.cliente, 'Sconosciuto') as cliente
            FROM lezioni l
            LEFT JOIN corsi c ON l.id_corso = c.id_corso
            WHERE l.fatturato = 0
            ORDER BY l.id_corso, l.data
        """)
        lezioni_non_fatturate = cursor_read.fetchall()

    except Exception as e:
        flash(f"❌ Errore durante il caricamento dei dati: {str(e)}", "danger")
        return render_template("aggiungi_fattura.html", corsi=[], lezioni=[], clienti=[], now=get_local_now(), corso_preselezionato="")
    finally:
        if conn_read:
            conn_read.close()

    if request.method == "POST":
        try:
            conn_write = get_db_connection()
            cursor_write = conn_write.cursor()

            numero_fattura = sanitize_input(request.form.get("numero_fattura"))
            data_fattura = request.form.get("data_fattura")
            importo = float(request.form.get("importo"))
            tipo_fatturazione = sanitize_input(request.form.get("tipo_fatturazione", "totale"))
            if tipo_fatturazione not in ['parziale', 'totale']:
                tipo_fatturazione = 'totale'
            print(f"DEBUG: tipo_fatturazione = {tipo_fatturazione}")
            note = sanitize_input(request.form.get("note", ""))
            lezioni_selezionate = request.form.getlist("lezioni")

            if not lezioni_selezionate:
                flash("❌ Devi selezionare almeno una lezione per creare una fattura.", "danger")
                return render_template("aggiungi_fattura.html", corsi=corsi, lezioni=lezioni_non_fatturate,
                                       clienti=clienti, now=get_local_now(), corso_preselezionato=corso_preselezionato)

            anno_fattura = datetime.strptime(data_fattura, "%Y-%m-%d").year
            placeholder = get_placeholder()
            cursor_write.execute(f"SELECT numero_fattura, data_fattura FROM fatture WHERE numero_fattura = {placeholder}", (numero_fattura,))
            fatture_esistenti = cursor_write.fetchall()

            for fattura_esistente in fatture_esistenti:
                anno_esistente = datetime.strptime(fattura_esistente['data_fattura'], "%Y-%m-%d").year
                if anno_esistente == anno_fattura:
                    flash(f"❌ Esiste già una fattura con il numero '{numero_fattura}' per l'anno {anno_fattura}. Scegli un numero diverso.", "danger")
                    return render_template("aggiungi_fattura.html", corsi=corsi, lezioni=lezioni_non_fatturate,
                                           clienti=clienti, now=get_local_now(), corso_preselezionato=corso_preselezionato)

            file_pdf = ""
            if 'file_pdf' in request.files:
                file = request.files['file_pdf']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = format_datetime_for_db().replace('-', '').replace(' ', '').replace(':', '')
                    filename = f"{timestamp}_{filename}"
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(file_path)
                    file_pdf = filename

            id_corso_principale = ""
            if lezioni_selezionate:
                placeholder = get_placeholder()
                cursor_write.execute(f"SELECT id_corso FROM lezioni WHERE id = {placeholder} LIMIT 1", (lezioni_selezionate[0],))
                corso_result = cursor_write.fetchone()
                if corso_result:
                    id_corso_principale = corso_result['id_corso']

            placeholder = get_placeholder()
            cursor_write.execute(f"""
                INSERT INTO fatture (numero_fattura, id_corso, data_fattura, importo, tipo_fatturazione, note, file_pdf)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                RETURNING id_fattura
            """, (str(numero_fattura), id_corso_principale, data_fattura, importo, str(tipo_fatturazione), note, file_pdf))

            id_fattura = cursor_write.fetchone()[0]
            mese_fatturato = datetime.strptime(data_fattura, "%Y-%m-%d").strftime("%Y-%m")
            tipo_fatturazione_val = 1

            for id_lezione in lezioni_selezionate:
                placeholder = get_placeholder()
                cursor_write.execute(f"""
                    UPDATE lezioni
                    SET fatturato = {placeholder}, mese_fatturato = {placeholder}
                    WHERE id = {placeholder}
                """, (tipo_fatturazione_val, mese_fatturato, id_lezione))

                placeholder = get_placeholder()
                cursor_write.execute(f"""
                    INSERT INTO fatture_lezioni (id_fattura, id_lezione)
                    VALUES ({placeholder}, {placeholder})
                """, (id_fattura, id_lezione))

            if lezioni_selezionate:
                placeholder = get_placeholder()
                placeholders = ','.join([placeholder] * len(lezioni_selezionate))
                cursor_write.execute(f"""
                    SELECT DISTINCT id_corso FROM lezioni
                    WHERE id IN ({placeholders})
                """, lezioni_selezionate)
                corsi_selezionati = [row['id_corso'] for row in cursor_write.fetchall()]
            else:
                corsi_selezionati = []

            for id_corso in corsi_selezionati:
                placeholder = get_placeholder()
                cursor_write.execute(f"""
                    SELECT COUNT(*) as totale,
                           SUM(CASE WHEN fatturato > 0 THEN 1 ELSE 0 END) as fatturate
                    FROM lezioni
                    WHERE id_corso = {placeholder}
                """, (id_corso,))

                result = cursor_write.fetchone()
                if result and result['totale'] > 0 and result['totale'] == result['fatturate']:
                    safe_id = sanitize_sql_identifier(id_corso)
                    savepoint_name = f"archive_corso_{safe_id}"
                    cursor_write.execute(f"SAVEPOINT {savepoint_name}")

                    try:
                        placeholder = get_placeholder()
                        cursor_write.execute(f"SELECT * FROM lezioni WHERE id_corso = {placeholder}", (id_corso,))
                        lezioni = cursor_write.fetchall()

                        for lezione in lezioni:
                            placeholder = get_placeholder()
                            cursor_write.execute(f"""
                                INSERT INTO archiviate (id_corso, materia, data, ora_inizio, ora_fine, luogo, compenso_orario, stato, fatturato, mese_fatturato)
                                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                            """, (
                                lezione["id_corso"], lezione["materia"], lezione["data"],
                                lezione["ora_inizio"], lezione["ora_fine"], lezione["luogo"],
                                lezione["compenso_orario"], lezione["stato"], lezione["fatturato"], lezione["mese_fatturato"]
                            ))

                        placeholder = get_placeholder()
                        cursor_write.execute(f"SELECT * FROM corsi WHERE id_corso = {placeholder}", (id_corso,))
                        corso = cursor_write.fetchone()

                        if corso:
                            data_archiviazione = format_datetime_for_db()
                            placeholder = get_placeholder()
                            cursor_write.execute(f"""
                                INSERT INTO corsi_archiviati (id_corso, nome, cliente, data_archiviazione)
                                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})
                            """, (corso["id_corso"], corso["nome"], corso.get("cliente", ""), data_archiviazione))

                        placeholder = get_placeholder()
                        cursor_write.execute(f"DELETE FROM lezioni WHERE id_corso = {placeholder}", (id_corso,))
                        placeholder = get_placeholder()
                        cursor_write.execute(f"DELETE FROM corsi WHERE id_corso = {placeholder}", (id_corso,))

                        cursor_write.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                        flash(f"✅ Corso '{id_corso}' completamente fatturato e archiviato automaticamente!", "success")
                    except Exception as e:
                        cursor_write.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                        print(f"Errore durante l'archiviazione automatica del corso: {e}")

            conn_write.commit()
            flash("✅ Fattura aggiunta con successo!", "success")
            return redirect(url_for("fatture.index"))

        except Exception as e:
            if conn_write:
                conn_write.rollback()
            flash(f"❌ Errore durante l'aggiunta della fattura: {str(e)}", "danger")
        finally:
            if conn_write:
                conn_write.close()

    return render_template("aggiungi_fattura.html", corsi=corsi, lezioni=lezioni_non_fatturate,
                           clienti=clienti, now=get_local_now(), corso_preselezionato=corso_preselezionato)


# ─── Route: Modifica fattura ───────────────────────────────────────────────────

@fatture_bp.route("/modifica_fattura/<int:id_fattura>", methods=["GET", "POST"])
@login_required
def modifica_fattura(id_fattura):
    """Pagina per modificare una fattura esistente"""
    conn_read = None
    conn_write = None

    try:
        conn_read = get_db_connection()
        cursor_read = conn_read.cursor()

        placeholder = get_placeholder()
        cursor_read.execute(f"SELECT * FROM fatture WHERE id_fattura = {placeholder}", (id_fattura,))
        fattura = cursor_read.fetchone()

        if not fattura:
            flash("❌ Fattura non trovata.", "danger")
            return redirect(url_for("fatture.index"))

        cursor_read.execute(f"SELECT id_lezione FROM fatture_lezioni WHERE id_fattura = {placeholder}", (id_fattura,))
        lezioni_associate = [row['id_lezione'] for row in cursor_read.fetchall()]

        if lezioni_associate:
            placeholders = ','.join([get_placeholder()] * len(lezioni_associate))
            cursor_read.execute(f"""
                SELECT l.id, l.id_corso, l.materia, l.data, l.ora_inizio, l.ora_fine, l.compenso_orario,
                       COALESCE(c.cliente, 'Sconosciuto') as cliente
                FROM lezioni l
                LEFT JOIN corsi c ON l.id_corso = c.id_corso
                WHERE l.fatturato = 0 OR l.id IN ({placeholders})
                ORDER BY l.id_corso, l.data
            """, lezioni_associate)
        else:
            cursor_read.execute("""
                SELECT l.id, l.id_corso, l.materia, l.data, l.ora_inizio, l.ora_fine, l.compenso_orario,
                       COALESCE(c.cliente, 'Sconosciuto') as cliente
                FROM lezioni l
                LEFT JOIN corsi c ON l.id_corso = c.id_corso
                WHERE l.fatturato = 0
                ORDER BY l.id_corso, l.data
            """)
        lezioni_disponibili = cursor_read.fetchall()

        cursor_read.execute("SELECT DISTINCT id_corso FROM lezioni ORDER BY id_corso")
        corsi = [row[0] for row in cursor_read.fetchall()]

        cursor_read.execute("""
            SELECT DISTINCT c.cliente
            FROM corsi c
            WHERE c.cliente IS NOT NULL AND c.cliente != ''
            ORDER BY c.cliente
        """)
        clienti = [row[0] for row in cursor_read.fetchall()]

    except Exception as e:
        flash(f"❌ Errore durante il caricamento dei dati: {str(e)}", "danger")
        return redirect(url_for("fatture.index"))
    finally:
        if conn_read:
            conn_read.close()

    if request.method == "POST":
        try:
            conn_write = get_db_connection()
            cursor_write = conn_write.cursor()

            numero_fattura = sanitize_input(request.form.get("numero_fattura"))
            data_fattura = request.form.get("data_fattura")
            importo = float(request.form.get("importo"))
            tipo_fatturazione = sanitize_input(request.form.get("tipo_fatturazione", "totale"))
            if tipo_fatturazione not in ['parziale', 'totale']:
                tipo_fatturazione = 'totale'
            note = sanitize_input(request.form.get("note", ""))
            lezioni_selezionate = request.form.getlist("lezioni")

            if not lezioni_selezionate:
                flash("❌ Devi selezionare almeno una lezione per la fattura.", "danger")
                return render_template("modifica_fattura.html", fattura=fattura, corsi=corsi,
                                       lezioni=lezioni_disponibili, clienti=clienti,
                                       lezioni_associate=lezioni_associate, now=get_local_now())

            anno_fattura = datetime.strptime(data_fattura, "%Y-%m-%d").year
            placeholder = get_placeholder()
            cursor_write.execute(f"""
                SELECT numero_fattura, data_fattura, id_fattura
                FROM fatture
                WHERE numero_fattura = {placeholder} AND id_fattura != {placeholder}
            """, (numero_fattura, id_fattura))
            fatture_esistenti = cursor_write.fetchall()

            for fattura_esistente in fatture_esistenti:
                anno_esistente = datetime.strptime(fattura_esistente['data_fattura'], "%Y-%m-%d").year
                if anno_esistente == anno_fattura:
                    flash(f"❌ Esiste già un'altra fattura con il numero '{numero_fattura}' per l'anno {anno_fattura}.", "danger")
                    return render_template("modifica_fattura.html", fattura=fattura, corsi=corsi,
                                           lezioni=lezioni_disponibili, clienti=clienti,
                                           lezioni_associate=lezioni_associate, now=get_local_now())

            file_pdf = fattura['file_pdf']
            if 'file_pdf' in request.files:
                file = request.files['file_pdf']
                if file and file.filename and allowed_file(file.filename):
                    if fattura['file_pdf']:
                        old_file_path = os.path.join(UPLOAD_FOLDER, fattura['file_pdf'])
                        if os.path.exists(old_file_path):
                            os.remove(old_file_path)
                    filename = secure_filename(file.filename)
                    timestamp = format_datetime_for_db().replace('-', '').replace(' ', '').replace(':', '')
                    filename = f"{timestamp}_{filename}"
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(file_path)
                    file_pdf = filename

            placeholder = get_placeholder()
            cursor_write.execute(f"""
                UPDATE fatture
                SET numero_fattura = {placeholder}, data_fattura = {placeholder}, importo = {placeholder},
                    tipo_fatturazione = {placeholder}, note = {placeholder}, file_pdf = {placeholder}
                WHERE id_fattura = {placeholder}
            """, (str(numero_fattura), data_fattura, importo, str(tipo_fatturazione), note, file_pdf, id_fattura))

            lezioni_selezionate_int = [int(l) for l in lezioni_selezionate]
            lezioni_da_rimuovere = set(lezioni_associate) - set(lezioni_selezionate_int)
            lezioni_da_aggiungere = set(lezioni_selezionate_int) - set(lezioni_associate)
            mese_fatturato = datetime.strptime(data_fattura, "%Y-%m-%d").strftime("%Y-%m")

            for id_lezione in lezioni_da_rimuovere:
                placeholder = get_placeholder()
                cursor_write.execute(f"""
                    UPDATE lezioni SET fatturato = 0, mese_fatturato = NULL WHERE id = {placeholder}
                """, (id_lezione,))

            for id_lezione in lezioni_da_aggiungere:
                placeholder = get_placeholder()
                cursor_write.execute(f"""
                    UPDATE lezioni SET fatturato = 1, mese_fatturato = {placeholder} WHERE id = {placeholder}
                """, (mese_fatturato, id_lezione))

            placeholder = get_placeholder()
            cursor_write.execute(f"DELETE FROM fatture_lezioni WHERE id_fattura = {placeholder}", (id_fattura,))

            for id_lezione in lezioni_selezionate_int:
                placeholder = get_placeholder()
                cursor_write.execute(f"""
                    INSERT INTO fatture_lezioni (id_fattura, id_lezione) VALUES ({placeholder}, {placeholder})
                """, (id_fattura, id_lezione))

            conn_write.commit()
            flash("✅ Fattura modificata con successo!", "success")
            return redirect(url_for("fatture.index"))

        except Exception as e:
            if conn_write:
                conn_write.rollback()
            flash(f"❌ Errore durante la modifica della fattura: {str(e)}", "danger")
        finally:
            if conn_write:
                conn_write.close()

    return render_template("modifica_fattura.html", fattura=fattura, corsi=corsi, lezioni=lezioni_disponibili,
                           clienti=clienti, lezioni_associate=lezioni_associate, now=get_local_now())


# ─── Route: Download PDF ───────────────────────────────────────────────────────

@fatture_bp.route("/download_file/<filename>")
@login_required
def download_file(filename):
    """Scarica un file PDF di una fattura"""
    from flask import send_from_directory
    return send_from_directory(UPLOAD_FOLDER, filename)


# ─── Route: Elimina fattura ────────────────────────────────────────────────────

@fatture_bp.route("/elimina_fattura/<id_fattura>", methods=["POST"])
@login_required
def elimina_fattura(id_fattura):
    """Elimina una fattura e ripristina lo stato delle lezioni associate"""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        placeholder = get_placeholder()
        cursor.execute(f"SELECT file_pdf FROM fatture WHERE id_fattura = {placeholder}", (id_fattura,))
        fattura = cursor.fetchone()

        placeholder = get_placeholder()
        cursor.execute(f"SELECT id_lezione FROM fatture_lezioni WHERE id_fattura = {placeholder}", (id_fattura,))
        lezioni = [row["id_lezione"] for row in cursor.fetchall()]

        for id_lezione in lezioni:
            placeholder = get_placeholder()
            cursor.execute(f"""
                UPDATE lezioni SET fatturato = 0, mese_fatturato = NULL WHERE id = {placeholder}
            """, (id_lezione,))

        placeholder = get_placeholder()
        cursor.execute(f"DELETE FROM fatture_lezioni WHERE id_fattura = {placeholder}", (id_fattura,))
        placeholder = get_placeholder()
        cursor.execute(f"DELETE FROM fatture WHERE id_fattura = {placeholder}", (id_fattura,))

        if fattura and fattura["file_pdf"]:
            file_path = os.path.join(UPLOAD_FOLDER, fattura["file_pdf"])
            if os.path.exists(file_path):
                os.remove(file_path)

        conn.commit()
        flash("✅ Fattura eliminata con successo!", "success")
    except Exception as e:
        if conn:
            conn.rollback()
        flash(f"❌ Errore durante l'eliminazione della fattura: {str(e)}", "danger")
    finally:
        if conn:
            conn.close()

    return redirect(url_for("fatture.index"))


# ─── Route: Verifica conformità fattura con AI ────────────────────────────────

@fatture_bp.route("/<int:id_fattura>/verifica", methods=["GET", "POST"])
@login_required
def verifica_fattura_ai(id_fattura):
    """Verifica conformità fattura: legge PDF con AI e confronta con i dati nel DB."""
    with db_connection() as conn:
        cursor = conn.cursor()
        placeholder = get_placeholder()

        # Dati fattura (prova corsi attivi, poi archiviati)
        cursor.execute(f"""
            SELECT f.*, c.nome as nome_corso, c.cliente as cliente_corso
            FROM fatture f
            LEFT JOIN corsi c ON f.id_corso = c.id_corso
            WHERE f.id_fattura = {placeholder}
        """, (id_fattura,))
        fattura = cursor.fetchone()

        if not fattura:
            cursor.execute(f"""
                SELECT f.*, ca.nome as nome_corso, ca.cliente as cliente_corso
                FROM fatture f
                LEFT JOIN corsi_archiviati ca ON f.id_corso = ca.id_corso
                WHERE f.id_fattura = {placeholder}
            """, (id_fattura,))
            fattura = cursor.fetchone()

        if not fattura:
            flash("❌ Fattura non trovata", "danger")
            return redirect(url_for("fatture.index"))

        # Lezioni associate a questa fattura
        cursor.execute(f"""
            SELECT l.ora_inizio, l.ora_fine, l.data, l.compenso_orario
            FROM fatture_lezioni fl
            JOIN lezioni l ON fl.id_lezione = l.id
            WHERE fl.id_fattura = {placeholder}
        """, (id_fattura,))
        lezioni_db = cursor.fetchall()

        if not lezioni_db:
            cursor.execute(f"""
                SELECT a.ora_inizio, a.ora_fine, a.data, a.compenso_orario
                FROM fatture_lezioni fl
                JOIN archiviate a ON fl.id_lezione = a.id
                WHERE fl.id_fattura = {placeholder}
            """, (id_fattura,))
            lezioni_db = cursor.fetchall()

        # Calcola ore reali dal DB
        ore_db = 0.0
        compenso_orario_db = None
        for lez in lezioni_db:
            try:
                t_inizio = datetime.strptime(lez['ora_inizio'], "%H:%M")
                t_fine = datetime.strptime(lez['ora_fine'], "%H:%M")
                ore_db += (t_fine - t_inizio).seconds / 3600
                if lez['compenso_orario']:
                    compenso_orario_db = float(lez['compenso_orario'])
            except Exception:
                pass
        ore_db = round(ore_db, 2)
        importo_atteso = round(ore_db * compenso_orario_db, 2) if compenso_orario_db and ore_db > 0 else None

        # Totale ore fatturate su questo corso (storico)
        ore_totali_corso_fatturate = 0.0
        if fattura['id_corso']:
            cursor.execute(f"""
                SELECT l2.ora_inizio, l2.ora_fine
                FROM fatture f2
                JOIN fatture_lezioni fl2 ON f2.id_fattura = fl2.id_fattura
                JOIN lezioni l2 ON fl2.id_lezione = l2.id
                WHERE f2.id_corso = {placeholder}
                UNION ALL
                SELECT a2.ora_inizio, a2.ora_fine
                FROM fatture f2
                JOIN fatture_lezioni fl2 ON f2.id_fattura = fl2.id_fattura
                JOIN archiviate a2 ON fl2.id_lezione = a2.id
                WHERE f2.id_corso = {placeholder}
            """, (fattura['id_corso'], fattura['id_corso']))
            for r in cursor.fetchall():
                try:
                    t1 = datetime.strptime(r['ora_inizio'], "%H:%M")
                    t2 = datetime.strptime(r['ora_fine'], "%H:%M")
                    ore_totali_corso_fatturate += (t2 - t1).seconds / 3600
                except Exception:
                    pass
            ore_totali_corso_fatturate = round(ore_totali_corso_fatturate, 2)

        # Monte ore contratto
        monte_ore_contratto = None
        if fattura['id_corso']:
            cursor.execute(f"""
                SELECT contenuto_estratto FROM contratti
                WHERE id_corso = {placeholder}
                ORDER BY data_upload DESC
                LIMIT 1
            """, (fattura['id_corso'],))
            row_contratto = cursor.fetchone()
            if row_contratto and row_contratto['contenuto_estratto']:
                from routes.contratti import estrai_ore_da_contratto
                monte_ore_contratto = estrai_ore_da_contratto(row_contratto['contenuto_estratto'])

    # ─── GET: mostra form upload ────────────────────────────────────────────────
    if request.method == "GET":
        return render_template("verifica_fattura_ai.html",
                               fattura=fattura,
                               ore_db=ore_db,
                               compenso_orario_db=compenso_orario_db,
                               importo_atteso=importo_atteso,
                               ore_totali_corso_fatturate=ore_totali_corso_fatturate,
                               monte_ore_contratto=monte_ore_contratto,
                               lezioni_db=lezioni_db,
                               risultato=None,
                               current_tab='altro')

    # ─── POST: analisi PDF con Claude + confronto ───────────────────────────────
    risposta_raw = ""
    try:
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            flash("❌ Chiave API Anthropic non configurata", "danger")
            return redirect(url_for("fatture.verifica_fattura_ai", id_fattura=id_fattura))

        # Ottieni percorso PDF
        pdf_path_temp = None
        is_temp = False

        if 'file_pdf' in request.files and request.files['file_pdf'].filename:
            file = request.files['file_pdf']
            if allowed_file(file.filename):
                tf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                file.save(tf.name)
                pdf_path_temp = tf.name
                tf.close()
                is_temp = True
        elif fattura['file_pdf']:
            saved_path = os.path.join(UPLOAD_FOLDER, fattura['file_pdf'])
            if os.path.exists(saved_path):
                pdf_path_temp = saved_path

        if not pdf_path_temp:
            flash("⚠️ Nessun PDF disponibile. Carica il PDF della fattura per l'analisi.", "warning")
            return redirect(url_for("fatture.verifica_fattura_ai", id_fattura=id_fattura))

        images = _pdf_to_base64_images_fattura(pdf_path_temp)

        if is_temp:
            try:
                os.unlink(pdf_path_temp)
            except Exception:
                pass

        if not images:
            flash("❌ Impossibile convertire il PDF in immagini.", "danger")
            return redirect(url_for("fatture.verifica_fattura_ai", id_fattura=id_fattura))

        # Chiama Claude Vision
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)

        content = [{"type": "text", "text": _PROMPT_ANALISI_FATTURA}]
        for img_b64 in images:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}
            })

        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": content}]
        )
        risposta_raw = message.content[0].text.strip()

        # Pulisci eventuale blocco markdown ```json```
        if risposta_raw.startswith("```"):
            parts = risposta_raw.split("```")
            risposta_raw = parts[1] if len(parts) > 1 else risposta_raw
            if risposta_raw.startswith("json"):
                risposta_raw = risposta_raw[4:]
        risposta_raw = risposta_raw.strip()

        dati_ai = json.loads(risposta_raw)

        # ─── Confronto AI vs DB ─────────────────────────────────────────────────
        checks = []

        # 1. Numero fattura
        num_ai = dati_ai.get('numero_fattura')
        num_db = fattura['numero_fattura']
        if num_ai:
            uguali = str(num_ai).strip() == str(num_db).strip()
            checks.append({
                'label': 'Numero fattura',
                'stato': 'ok' if uguali else 'warn',
                'ai': num_ai, 'db': num_db,
                'messaggio': 'Numero fattura conforme' if uguali else f'PDF: "{num_ai}" · DB: "{num_db}"'
            })

        # 2. Corso (gestisce sia mono-corso che multi-corso)
        corsi_ai = dati_ai.get('corsi')  # array opzionale per fatture multi-corso
        codice_ai = dati_ai.get('codice_corso') or dati_ai.get('nome_corso') or ''
        id_corso_db = fattura['id_corso'] or ''
        nome_corso_db = fattura.get('nome_corso') or ''

        if corsi_ai and isinstance(corsi_ai, list) and len(corsi_ai) > 1:
            # Fattura multi-corso: mostra riepilogo info
            riepilogo_corsi = ' · '.join(
                f"{c.get('codice','?')} ({c.get('ore','?')}h)" for c in corsi_ai
            )
            ore_totale_corsi = sum(float(c.get('ore', 0) or 0) for c in corsi_ai)
            checks.append({
                'label': 'Corso',
                'stato': 'info',
                'ai': f"{len(corsi_ai)} corsi",
                'db': id_corso_db,
                'messaggio': f'Fattura multi-corso ({len(corsi_ai)} corsi, {ore_totale_corsi:.0f}h totali): {riepilogo_corsi}'
            })
        elif codice_ai:
            ca = codice_ai.lower()
            ic = id_corso_db.lower()
            nc = nome_corso_db.lower()
            match_corso = ca in ic or ic in ca or (nc and (ca in nc or nc in ca))
            checks.append({
                'label': 'Corso',
                'stato': 'ok' if match_corso else 'warn',
                'ai': codice_ai,
                'db': f"{id_corso_db} ({nome_corso_db})" if nome_corso_db else id_corso_db,
                'messaggio': 'Corso conforme' if match_corso else f'Corso PDF: "{codice_ai}" · DB: "{id_corso_db}"'
            })

        # 3. Monte ore
        ore_ai = dati_ai.get('monte_ore')
        if ore_ai is not None:
            try:
                ore_ai_f = float(ore_ai)
                diff_ore = abs(ore_ai_f - ore_db)
                if diff_ore < 0.5:
                    checks.append({'label': 'Monte ore', 'stato': 'ok',
                                   'ai': f'{ore_ai_f}h', 'db': f'{ore_db}h',
                                   'messaggio': f'Ore conformi: {ore_ai_f}h (PDF) = {ore_db}h (DB)'})
                else:
                    checks.append({'label': 'Monte ore', 'stato': 'err',
                                   'ai': f'{ore_ai_f}h', 'db': f'{ore_db}h',
                                   'messaggio': f'Divergenza: PDF indica {ore_ai_f}h, DB registra {ore_db}h'})
            except Exception:
                pass
        elif ore_db > 0:
            checks.append({'label': 'Monte ore', 'stato': 'info',
                           'ai': '(non trovato nel PDF)', 'db': f'{ore_db}h',
                           'messaggio': f'DB registra {ore_db}h per questa fattura'})

        # 4. Importo (gestisce lordo/netto con ritenuta d'acconto)
        importo_lordo_ai = dati_ai.get('importo_lordo')
        importo_netto_ai = dati_ai.get('importo_netto')
        ritenuta_ai = dati_ai.get('ritenuta_acconto')
        # Retrocompatibilità col vecchio campo importo_totale
        if importo_lordo_ai is None:
            importo_lordo_ai = dati_ai.get('importo_totale')
        importo_db_f = float(fattura['importo'])

        if importo_lordo_ai is not None:
            try:
                lordo_f = float(importo_lordo_ai)
                diff_lordo = abs(lordo_f - importo_db_f)

                # Controlla se c'è ritenuta d'acconto
                ha_ritenuta = ritenuta_ai is not None and float(ritenuta_ai) > 0
                netto_f = float(importo_netto_ai) if importo_netto_ai is not None else None

                if diff_lordo < 1.0:
                    # Il lordo nel PDF corrisponde al DB
                    if ha_ritenuta:
                        msg_imp = f'Compenso lordo conforme: €{lordo_f:.2f} · Ritenuta d\'acconto: €{float(ritenuta_ai):.2f} · Netto da percepire: €{netto_f:.2f}'
                    else:
                        msg_imp = f'Importo conforme: €{lordo_f:.2f}'
                    stato_imp = 'ok'
                    label_ai = f'€{lordo_f:.2f} lordo'
                    if ha_ritenuta and netto_f:
                        label_ai += f' (netto €{netto_f:.2f})'
                else:
                    # Il lordo non corrisponde — controlla se il netto corrisponde (caso anomalo)
                    if netto_f is not None and abs(netto_f - importo_db_f) < 1.0:
                        msg_imp = f'⚠️ Il DB ha il netto (€{netto_f:.2f}) ma dovrebbe avere il lordo (€{lordo_f:.2f})'
                        stato_imp = 'warn'
                    else:
                        msg_imp = f'Divergenza: PDF lordo €{lordo_f:.2f} · DB €{importo_db_f:.2f}'
                        if importo_atteso:
                            msg_imp += f' · Atteso da ore×tariffa: €{importo_atteso:.2f}'
                        stato_imp = 'err'
                    label_ai = f'€{lordo_f:.2f}'

                checks.append({'label': 'Importo', 'stato': stato_imp,
                               'ai': label_ai, 'db': f'€{importo_db_f:.2f}',
                               'messaggio': msg_imp})

                # Check aggiuntivo: mostra riepilogo ritenuta se presente
                if ha_ritenuta and netto_f is not None:
                    perc_rit = round((float(ritenuta_ai) / lordo_f) * 100) if lordo_f > 0 else 0
                    checks.append({'label': 'Ritenuta d\'acconto',
                                   'stato': 'info',
                                   'ai': f'{perc_rit}% = €{float(ritenuta_ai):.2f}',
                                   'db': f'Netto da percepire: €{netto_f:.2f}',
                                   'messaggio': f'Ritenuta d\'acconto {perc_rit}%: lordo €{lordo_f:.2f} − €{float(ritenuta_ai):.2f} = netto €{netto_f:.2f}'})
            except Exception:
                pass

        # 5. Contratto - monte ore residuo
        if monte_ore_contratto and ore_totali_corso_fatturate > 0:
            residuo = round(monte_ore_contratto - ore_totali_corso_fatturate, 2)
            perc = round((ore_totali_corso_fatturate / monte_ore_contratto) * 100, 1)
            if residuo > 0:
                stato_contr = 'ok'
                msg_contr = f'Fatturate {ore_totali_corso_fatturate}h / {monte_ore_contratto}h ({perc}%) · Residuo: {residuo}h'
            elif residuo == 0:
                stato_contr = 'warn'
                msg_contr = f'Corso completamente fatturato: {ore_totali_corso_fatturate}h / {monte_ore_contratto}h (100%)'
            else:
                stato_contr = 'err'
                msg_contr = f'⚠️ Superamento monte ore! Fatturate {ore_totali_corso_fatturate}h su {monte_ore_contratto}h previste'
            checks.append({'label': 'Contratto', 'stato': stato_contr,
                           'ai': '', 'db': msg_contr, 'messaggio': msg_contr})

        risultato = {
            'dati_ai': dati_ai,
            'checks': checks,
        }

        return render_template("verifica_fattura_ai.html",
                               fattura=fattura,
                               ore_db=ore_db,
                               compenso_orario_db=compenso_orario_db,
                               importo_atteso=importo_atteso,
                               ore_totali_corso_fatturate=ore_totali_corso_fatturate,
                               monte_ore_contratto=monte_ore_contratto,
                               lezioni_db=lezioni_db,
                               risultato=risultato,
                               current_tab='altro')

    except json.JSONDecodeError:
        flash(f"⚠️ Claude ha risposto ma non in formato JSON valido: {risposta_raw[:300]}", "warning")
        return redirect(url_for("fatture.verifica_fattura_ai", id_fattura=id_fattura))
    except Exception as e:
        flash(f"❌ Errore durante la verifica: {str(e)}", "danger")
        return redirect(url_for("fatture.verifica_fattura_ai", id_fattura=id_fattura))
