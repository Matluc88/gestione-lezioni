from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
import sqlite3
from datetime import datetime
import os
from werkzeug.utils import secure_filename

fatture_bp = Blueprint('fatture', __name__, url_prefix='/fatture')

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "fatture")
ALLOWED_EXTENSIONS = {'pdf'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
print(f"✅ Cartella per le fatture verificata: {UPLOAD_FOLDER}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    """ Crea una connessione al database SQLite """
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lezioni.db")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
    cursor.execute('''
        SELECT f.id_fattura, f.id_corso, f.data_fattura, f.importo, f.tipo_fatturazione,
               f.file_pdf, GROUP_CONCAT(l.data, ', ') AS lezioni_fatturate
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
    corso_scelto = request.args.get("corso_scelto", default="", type=str)
    fatture = get_fatture()

    corso_status = ""
    lezioni_fatturate = []
    ore_fatturate_totali = 0
    ore_totali_corso = 0  # Per verificare se il corso è completamente fatturato

    if corso_scelto:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Recupera le lezioni FATTURATE
        cursor.execute("""
            SELECT id, data, ora_inizio, ora_fine
            FROM lezioni
            WHERE id_corso = ? AND fatturato = 1
            ORDER BY data
        """, (corso_scelto,))
        lezioni_fatturate_rows = cursor.fetchall()

        # Convertiamo le lezioni in dizionari per renderle serializzabili in JSON
        lezioni_fatturate = [
            {"id": row["id"], "data": row["data"], "ora_inizio": row["ora_inizio"], "ora_fine": row["ora_fine"]}
            for row in lezioni_fatturate_rows
        ]

        # Recupera il numero totale di lezioni del corso
        cursor.execute("""
            SELECT COUNT(*) as totale FROM lezioni WHERE id_corso = ?
        """, (corso_scelto,))
        totale_lezioni = cursor.fetchone()["totale"]
        
        cursor.execute("""
            SELECT COUNT(*) as non_fatturate FROM lezioni WHERE id_corso = ? AND fatturato = 0
        """, (corso_scelto,))
        lezioni_non_fatturate = cursor.fetchone()["non_fatturate"]
        
        cursor.execute("""
            SELECT f.id_fattura, f.data_fattura, f.importo, f.tipo_fatturazione, COUNT(fl.id_lezione) as num_lezioni
            FROM fatture f
            LEFT JOIN fatture_lezioni fl ON f.id_fattura = fl.id_fattura
            WHERE f.id_corso = ?
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
                           lezioni_fatturate=lezioni_fatturate)  # Ora è un JSON valido



@fatture_bp.route("/fattura_corso", methods=["GET", "POST"])
@login_required
def fattura_corso():
    """ Pagina per fatturare un intero corso o singole lezioni """
    corso_scelto = request.args.get("corso_scelto", default="", type=str)

    if not corso_scelto:
        flash("Seleziona un corso valido.", "danger")
        return redirect(url_for("fatture.index"))

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        # Riceviamo i dati dal form
        fattura_tutto = request.form.get("fattura_tutto")
        lezioni_selezionate = request.form.getlist("lezioni")

        mese_corrente = datetime.now().strftime("%Y-%m")  # Formato YYYY-MM

        if fattura_tutto:
            # Fatturare tutte le lezioni del corso
            cursor.execute("""
                UPDATE lezioni 
                SET fatturato = 1, mese_fatturato = ?
                WHERE id_corso = ? AND fatturato = 0
            """, (mese_corrente, corso_scelto))
        else:
            # Fatturare solo le lezioni selezionate
            for id_lezione in lezioni_selezionate:
                cursor.execute("""
                    UPDATE lezioni 
                    SET fatturato = 1, mese_fatturato = ?
                    WHERE id = ?
                """, (mese_corrente, id_lezione))

        conn.commit()
        conn.close()

        flash("Lezione/i fatturata/e con successo!", "success")
        return redirect(url_for("fatture.index", corso_scelto=corso_scelto))

    # Recupera le lezioni NON fatturate
    cursor.execute("""
        SELECT id, data, ora_inizio, ora_fine
        FROM lezioni
        WHERE id_corso = ? AND fatturato = 0
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
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT id_corso FROM lezioni ORDER BY id_corso")
    corsi = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("""
        SELECT DISTINCT c.cliente 
        FROM corsi c 
        WHERE c.cliente IS NOT NULL AND c.cliente != ''
        ORDER BY c.cliente
    """)
    clienti = [row[0] for row in cursor.fetchall()]
    
    cursor.execute("""
        SELECT l.id, l.id_corso, l.materia, l.data, l.ora_inizio, l.ora_fine, l.compenso_orario, 
               COALESCE(c.cliente, 'Sconosciuto') as cliente
        FROM lezioni l
        LEFT JOIN corsi c ON l.id_corso = c.id_corso
        WHERE l.fatturato = 0
        ORDER BY l.id_corso, l.data
    """)
    lezioni_non_fatturate = cursor.fetchall()
    
    if request.method == "POST":
        try:
            numero_fattura = request.form.get("numero_fattura")
            corsi_selezionati = request.form.get("corsi_selezionati", "").split(",") if request.form.get("corsi_selezionati") else []
            data_fattura = request.form.get("data_fattura")
            importo = float(request.form.get("importo"))
            tipo_fatturazione = request.form.get("tipo_fatturazione")
            note = request.form.get("note", "")
            lezioni_selezionate = request.form.getlist("lezioni")
            
            file_pdf = ""  # Valore predefinito vuoto invece di None
            if 'file_pdf' in request.files:
                file = request.files['file_pdf']
                if file and file.filename and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    filename = f"{timestamp}_{filename}"
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(file_path)
                    file_pdf = filename
            
            id_corso_principale = corsi_selezionati[0] if corsi_selezionati else ""
            
            cursor.execute("""
                INSERT INTO fatture (id_fattura, id_corso, data_fattura, importo, tipo_fatturazione, note, file_pdf)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (numero_fattura, id_corso_principale, data_fattura, importo, tipo_fatturazione, note, file_pdf))
            
            id_fattura = cursor.lastrowid
            
            mese_fatturato = datetime.strptime(data_fattura, "%Y-%m-%d").strftime("%Y-%m")
            tipo_fatturazione_val = 1  # 1 = completamente fatturato
            
            for id_lezione in lezioni_selezionate:
                cursor.execute("""
                    UPDATE lezioni 
                    SET fatturato = ?, mese_fatturato = ?
                    WHERE id = ?
                """, (tipo_fatturazione_val, mese_fatturato, id_lezione))
                
                cursor.execute("""
                    INSERT INTO fatture_lezioni (id_fattura, id_lezione)
                    VALUES (?, ?)
                """, (id_fattura, id_lezione))
            
            # Determine corsi_selezionati from lezioni_selezionate
            cursor.execute("""
                SELECT DISTINCT id_corso FROM lezioni 
                WHERE id IN ({})
            """.format(','.join(['?'] * len(lezioni_selezionate))), lezioni_selezionate)
            
            corsi_selezionati = [row['id_corso'] for row in cursor.fetchall()]
            
            for id_corso in corsi_selezionati:
                cursor.execute("""
                    SELECT COUNT(*) as totale, 
                           SUM(CASE WHEN fatturato > 0 THEN 1 ELSE 0 END) as fatturate 
                    FROM lezioni 
                    WHERE id_corso = ?
                """, (id_corso,))
                
                result = cursor.fetchone()
                if result and result['totale'] > 0 and result['totale'] == result['fatturate']:
                    try:
                        cursor.execute("SELECT * FROM lezioni WHERE id_corso = ?", (id_corso,))
                        lezioni = cursor.fetchall()
                        
                        for lezione in lezioni:
                            cursor.execute("""
                                INSERT INTO archiviate (id_corso, materia, data, ora_inizio, ora_fine, luogo, compenso_orario, stato, fatturato, mese_fatturato)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                lezione["id_corso"], lezione["materia"], lezione["data"],
                                lezione["ora_inizio"], lezione["ora_fine"], lezione["luogo"],
                                lezione["compenso_orario"], lezione["stato"], lezione["fatturato"], lezione["mese_fatturato"]
                            ))
                        
                        cursor.execute("SELECT * FROM corsi WHERE id_corso = ?", (id_corso,))
                        corso = cursor.fetchone()
                        
                        if corso:
                            data_archiviazione = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            cursor.execute("""
                                INSERT INTO corsi_archiviati (id_corso, nome, cliente, data_archiviazione)
                                VALUES (?, ?, ?, ?)
                            """, (corso["id_corso"], corso["nome"], corso.get("cliente", ""), data_archiviazione))
                        
                        cursor.execute("DELETE FROM lezioni WHERE id_corso = ?", (id_corso,))
                        
                        cursor.execute("DELETE FROM corsi WHERE id_corso = ?", (id_corso,))
                        
                        flash(f"✅ Corso '{id_corso}' completamente fatturato e archiviato automaticamente!", "success")
                    except Exception as e:
                        print(f"Errore durante l'archiviazione automatica del corso: {e}")
            
            conn.commit()
            flash("✅ Fattura aggiunta con successo!", "success")
            return redirect(url_for("fatture.index"))
            
        except Exception as e:
            conn.rollback()
            flash(f"❌ Errore durante l'aggiunta della fattura: {str(e)}", "danger")
    
    conn.close()
    return render_template("aggiungi_fattura.html", corsi=corsi, lezioni=lezioni_non_fatturate, clienti=clienti, now=datetime.now())

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
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT file_pdf FROM fatture WHERE id_fattura = ?", (id_fattura,))
        fattura = cursor.fetchone()
        
        cursor.execute("SELECT id_lezione FROM fatture_lezioni WHERE id_fattura = ?", (id_fattura,))
        lezioni = [row["id_lezione"] for row in cursor.fetchall()]
        
        for id_lezione in lezioni:
            cursor.execute("""
                UPDATE lezioni 
                SET fatturato = 0, mese_fatturato = NULL
                WHERE id = ?
            """, (id_lezione,))
        
        cursor.execute("DELETE FROM fatture_lezioni WHERE id_fattura = ?", (id_fattura,))
        
        cursor.execute("DELETE FROM fatture WHERE id_fattura = ?", (id_fattura,))
        
        if fattura and fattura["file_pdf"]:
            file_path = os.path.join(UPLOAD_FOLDER, fattura["file_pdf"])
            if os.path.exists(file_path):
                os.remove(file_path)
        
        conn.commit()
        flash("✅ Fattura eliminata con successo!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"❌ Errore durante l'eliminazione della fattura: {str(e)}", "danger")
    finally:
        conn.close()
    
    return redirect(url_for("fatture.index"))
