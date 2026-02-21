from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
import os
from datetime import datetime
from utils.time_utils import get_local_now, format_date_for_template, format_datetime_for_db
from werkzeug.utils import secure_filename
from db_utils import db_connection, get_db_connection, get_placeholder
from utils.security import sanitize_input, sanitize_form_data
from utils.sql_utils import sanitize_sql_identifier

fatture_bp = Blueprint('fatture', __name__, url_prefix='/fatture')

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "fatture")
ALLOWED_EXTENSIONS = {'pdf'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
print(f"✅ Cartella per le fatture verificata: {UPLOAD_FOLDER}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_corsi():
    """ Recupera la lista di corsi disponibili nel database """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT id_corso FROM lezioni ORDER BY id_corso")
    corsi = [row[0] for row in cursor.fetchall()]
    conn.close()
    return corsi

def get_fatture():
    """ Recupera tutte le fatture emesse """
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
        WHERE l.fatturato = 1 OR fl.id_fattura IS NOT NULL
        GROUP BY f.id_fattura
        ORDER BY f.data_fattura DESC
    ''')
    fatture = cursor.fetchall()
    conn.close()
    return fatture

@fatture_bp.route("/")
@login_required
def index():
    """ Pagina principale delle fatture e delle lezioni fatturate """
    corsi = get_corsi()
    corso_scelto = sanitize_input(request.args.get("corso_scelto", default="", type=str))
    fatture = get_fatture()

    corso_status = ""
    lezioni_fatturate = []
    ore_fatturate_totali = 0
    ore_totali_corso = 0  # Per verificare se il corso è completamente fatturato

    if corso_scelto:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Recupera le lezioni FATTURATE
        placeholder = get_placeholder()
        cursor.execute(f"""
            SELECT id, data, ora_inizio, ora_fine
            FROM lezioni
            WHERE id_corso = {placeholder} AND fatturato = 1
            ORDER BY data
        """, (corso_scelto,))
        lezioni_fatturate_rows = cursor.fetchall()

        # Convertiamo le lezioni in dizionari per renderle serializzabili in JSON
        lezioni_fatturate = [
            {"id": row["id"], "data": row["data"], "ora_inizio": row["ora_inizio"], "ora_fine": row["ora_fine"]}
            for row in lezioni_fatturate_rows
        ]

        # Recupera il numero totale di lezioni del corso
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

        # Calcola il totale delle ore fatturate
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



@fatture_bp.route("/fattura_corso", methods=["GET", "POST"])
@login_required
def fattura_corso():
    """ Pagina per fatturare un intero corso o singole lezioni """
    corso_scelto = sanitize_input(request.args.get("corso_scelto", default="", type=str))

    if not corso_scelto:
        flash("Seleziona un corso valido.", "danger")
        return redirect(url_for("fatture.index"))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        # Riceviamo i dati dal form e sanitizziamo
        fattura_tutto = sanitize_input(request.form.get("fattura_tutto"))
        lezioni_selezionate = request.form.getlist("lezioni")

        mese_corrente = datetime.now().strftime("%Y-%m")  # Formato YYYY-MM

        if fattura_tutto:
            # Fatturare tutte le lezioni del corso
            placeholder = get_placeholder()
            cursor.execute(f"""
                UPDATE lezioni 
                SET fatturato = 1, mese_fatturato = {placeholder}
                WHERE id_corso = {placeholder} AND fatturato = 0
            """, (mese_corrente, corso_scelto))
        else:
            # Fatturare solo le lezioni selezionate
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

    # Recupera le lezioni NON fatturate
    placeholder = get_placeholder()
    cursor.execute(f"""
        SELECT id, data, ora_inizio, ora_fine
        FROM lezioni
        WHERE id_corso = {placeholder} AND fatturato = 0
        ORDER BY data
    """, (corso_scelto,))
    lezioni_non_fatturate_rows = cursor.fetchall()
    conn.close()

    # Convertiamo le lezioni non fatturate in un formato serializzabile
    lezioni_non_fatturate = [
        {"id": row["id"], "data": row["data"], "ora_inizio": row["ora_inizio"], "ora_fine": row["ora_fine"]}
        for row in lezioni_non_fatturate_rows
    ]

    return render_template("fattura_corso.html", corso_scelto=corso_scelto, lezioni=lezioni_non_fatturate)

@fatture_bp.route("/aggiungi_fattura", methods=["GET", "POST"])
@login_required
def aggiungi_fattura():
    """ Pagina per aggiungere una nuova fattura con tutti i dettagli """
    conn_read = None
    conn_write = None
    
    # Leggi il parametro corso dall'URL per pre-selezione
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
        
        query = """
            SELECT l.id, l.id_corso, l.materia, l.data, l.ora_inizio, l.ora_fine, l.compenso_orario, 
                   COALESCE(c.cliente, 'Sconosciuto') as cliente
            FROM lezioni l
            LEFT JOIN corsi c ON l.id_corso = c.id_corso
            WHERE l.fatturato = 0
            ORDER BY l.id_corso, l.data
        """
        cursor_read.execute(query)
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
                tipo_fatturazione = 'totale'  # Default to 'totale' if invalid value
            print(f"DEBUG: tipo_fatturazione = {tipo_fatturazione}")
            note = sanitize_input(request.form.get("note", ""))
            lezioni_selezionate = request.form.getlist("lezioni")
            
            if not lezioni_selezionate:
                flash("❌ Devi selezionare almeno una lezione per creare una fattura.", "danger")
                return render_template("aggiungi_fattura.html", corsi=corsi, lezioni=lezioni_non_fatturate, clienti=clienti, now=get_local_now(), corso_preselezionato=corso_preselezionato)
            
            # Verifica se esiste già una fattura con lo stesso numero nello stesso anno
            anno_fattura = datetime.strptime(data_fattura, "%Y-%m-%d").year
            placeholder = get_placeholder()
            cursor_write.execute(f"SELECT numero_fattura, data_fattura FROM fatture WHERE numero_fattura = {placeholder}", (numero_fattura,))
            fatture_esistenti = cursor_write.fetchall()
            
            for fattura_esistente in fatture_esistenti:
                anno_esistente = datetime.strptime(fattura_esistente['data_fattura'], "%Y-%m-%d").year
                if anno_esistente == anno_fattura:
                    flash(f"❌ Esiste già una fattura con il numero '{numero_fattura}' per l'anno {anno_fattura}. Scegli un numero diverso.", "danger")
                    return render_template("aggiungi_fattura.html", corsi=corsi, lezioni=lezioni_non_fatturate, clienti=clienti, now=get_local_now(), corso_preselezionato=corso_preselezionato)
            
            file_pdf = ""  # Valore predefinito vuoto invece di None
            if 'file_pdf' in request.files:
                file = request.files['file_pdf']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = format_datetime_for_db().replace('-', '').replace(' ', '').replace(':', '')
                    filename = f"{timestamp}_{filename}"
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(file_path)
                    file_pdf = filename
            
            # Determine id_corso_principale from lezioni_selezionate
            id_corso_principale = ""
            if lezioni_selezionate:
                placeholder = get_placeholder()
                cursor_write.execute(f"SELECT id_corso FROM lezioni WHERE id = {placeholder} LIMIT 1", (lezioni_selezionate[0],))
                corso_result = cursor_write.fetchone()
                if corso_result:
                    id_corso_principale = corso_result['id_corso']
            
            print(f"DEBUG: id_fattura={numero_fattura}, type={type(numero_fattura)}")
            print(f"DEBUG: id_corso={id_corso_principale}, type={type(id_corso_principale)}")
            print(f"DEBUG: data_fattura={data_fattura}, type={type(data_fattura)}")
            print(f"DEBUG: importo={importo}, type={type(importo)}")
            print(f"DEBUG: tipo_fatturazione={tipo_fatturazione}, type={type(tipo_fatturazione)}")
            print(f"DEBUG: note={note}, type={type(note)}")
            print(f"DEBUG: file_pdf={file_pdf}, type={type(file_pdf)}")
            
            placeholder = get_placeholder()
            cursor_write.execute(f"""
                INSERT INTO fatture (numero_fattura, id_corso, data_fattura, importo, tipo_fatturazione, note, file_pdf)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                RETURNING id_fattura
            """, (str(numero_fattura), id_corso_principale, data_fattura, importo, str(tipo_fatturazione), note, file_pdf))
            
            id_fattura = cursor_write.fetchone()[0]
            
            mese_fatturato = datetime.strptime(data_fattura, "%Y-%m-%d").strftime("%Y-%m")
            tipo_fatturazione_val = 1  # 1 = completamente fatturato
            
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
            
            # Determine corsi_selezionati from lezioni_selezionate
            if lezioni_selezionate:  # Additional safety check
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
    
    return render_template("aggiungi_fattura.html", corsi=corsi, lezioni=lezioni_non_fatturate, clienti=clienti, now=get_local_now(), corso_preselezionato=corso_preselezionato)

@fatture_bp.route("/modifica_fattura/<int:id_fattura>", methods=["GET", "POST"])
@login_required
def modifica_fattura(id_fattura):
    """ Pagina per modificare una fattura esistente """
    conn_read = None
    conn_write = None
    
    try:
        conn_read = get_db_connection()
        cursor_read = conn_read.cursor()
        
        # Recupera i dati della fattura
        placeholder = get_placeholder()
        cursor_read.execute(f"""
            SELECT * FROM fatture WHERE id_fattura = {placeholder}
        """, (id_fattura,))
        fattura = cursor_read.fetchone()
        
        if not fattura:
            flash("❌ Fattura non trovata.", "danger")
            return redirect(url_for("fatture.index"))
        
        # Recupera le lezioni associate alla fattura
        cursor_read.execute(f"""
            SELECT id_lezione FROM fatture_lezioni WHERE id_fattura = {placeholder}
        """, (id_fattura,))
        lezioni_associate = [row['id_lezione'] for row in cursor_read.fetchall()]
        
        # Recupera tutte le lezioni non fatturate + quelle già associate
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
        
        # Recupera corsi e clienti
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
                return render_template("modifica_fattura.html", fattura=fattura, corsi=corsi, lezioni=lezioni_disponibili, clienti=clienti, lezioni_associate=lezioni_associate, now=get_local_now())
            
            # Verifica numero fattura duplicato (escludendo la fattura corrente)
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
                    return render_template("modifica_fattura.html", fattura=fattura, corsi=corsi, lezioni=lezioni_disponibili, clienti=clienti, lezioni_associate=lezioni_associate, now=get_local_now())
            
            # Gestione upload PDF (se presente)
            file_pdf = fattura['file_pdf']  # Mantieni quello esistente
            if 'file_pdf' in request.files:
                file = request.files['file_pdf']
                if file and file.filename and allowed_file(file.filename):
                    # Elimina il vecchio file se esiste
                    if fattura['file_pdf']:
                        old_file_path = os.path.join(UPLOAD_FOLDER, fattura['file_pdf'])
                        if os.path.exists(old_file_path):
                            os.remove(old_file_path)
                    
                    # Salva il nuovo file
                    filename = secure_filename(file.filename)
                    timestamp = format_datetime_for_db().replace('-', '').replace(' ', '').replace(':', '')
                    filename = f"{timestamp}_{filename}"
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(file_path)
                    file_pdf = filename
            
            # Aggiorna la fattura
            placeholder = get_placeholder()
            cursor_write.execute(f"""
                UPDATE fatture 
                SET numero_fattura = {placeholder}, data_fattura = {placeholder}, importo = {placeholder}, 
                    tipo_fatturazione = {placeholder}, note = {placeholder}, file_pdf = {placeholder}
                WHERE id_fattura = {placeholder}
            """, (str(numero_fattura), data_fattura, importo, str(tipo_fatturazione), note, file_pdf, id_fattura))
            
            # Gestione lezioni: ripristina le vecchie e imposta le nuove
            lezioni_selezionate_int = [int(l) for l in lezioni_selezionate]
            lezioni_da_rimuovere = set(lezioni_associate) - set(lezioni_selezionate_int)
            lezioni_da_aggiungere = set(lezioni_selezionate_int) - set(lezioni_associate)
            
            # Ripristina lezioni rimosse
            mese_fatturato = datetime.strptime(data_fattura, "%Y-%m-%d").strftime("%Y-%m")
            for id_lezione in lezioni_da_rimuovere:
                placeholder = get_placeholder()
                cursor_write.execute(f"""
                    UPDATE lezioni 
                    SET fatturato = 0, mese_fatturato = NULL
                    WHERE id = {placeholder}
                """, (id_lezione,))
            
            # Imposta nuove lezioni come fatturate
            for id_lezione in lezioni_da_aggiungere:
                placeholder = get_placeholder()
                cursor_write.execute(f"""
                    UPDATE lezioni 
                    SET fatturato = 1, mese_fatturato = {placeholder}
                    WHERE id = {placeholder}
                """, (mese_fatturato, id_lezione))
            
            # Aggiorna tabella fatture_lezioni
            placeholder = get_placeholder()
            cursor_write.execute(f"DELETE FROM fatture_lezioni WHERE id_fattura = {placeholder}", (id_fattura,))
            
            for id_lezione in lezioni_selezionate_int:
                placeholder = get_placeholder()
                cursor_write.execute(f"""
                    INSERT INTO fatture_lezioni (id_fattura, id_lezione)
                    VALUES ({placeholder}, {placeholder})
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
    
    return render_template("modifica_fattura.html", fattura=fattura, corsi=corsi, lezioni=lezioni_disponibili, clienti=clienti, lezioni_associate=lezioni_associate, now=get_local_now())

@fatture_bp.route("/download_file/<filename>")
@login_required
def download_file(filename):
    """ Scarica un file PDF di una fattura """
    from flask import send_from_directory
    return send_from_directory(UPLOAD_FOLDER, filename)

@fatture_bp.route("/elimina_fattura/<id_fattura>", methods=["POST"])
@login_required
def elimina_fattura(id_fattura):
    """ Elimina una fattura e ripristina lo stato delle lezioni associate """
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
                UPDATE lezioni 
                SET fatturato = 0, mese_fatturato = NULL
                WHERE id = {placeholder}
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
