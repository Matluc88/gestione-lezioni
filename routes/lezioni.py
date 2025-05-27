from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from database import db_connection
from utils import correggi_orario, calcola_ore

lezioni_bp = Blueprint('lezioni', __name__)

@lezioni_bp.route("/dashboard")
@login_required
def dashboard():
    with db_connection() as conn:
        cursor = conn.cursor()

        # Recupera l'utente
        cursor.execute("SELECT username FROM users WHERE id = ?", (current_user.id,))
        user = cursor.fetchone()

        # Filtro dai parametri GET
        materia = request.args.get("materia", "").strip()
        data = request.args.get("data", "").strip()
        stato = request.args.get("stato", "").strip()
        luogo = request.args.get("luogo", "").strip()
        corso = request.args.get("corso", "").strip()

        # Costruzione query con filtri dinamici
        query = "SELECT * FROM lezioni WHERE id_corso IS NOT NULL"
        params = []

        if materia:
            query += " AND materia LIKE ?"
            params.append(f"%{materia}%")
        if data:
            query += " AND data = ?"
            params.append(data)
        if stato:
            query += " AND stato = ?"
            params.append(stato)
        if luogo:
            query += " AND luogo LIKE ?"
            params.append(f"%{luogo}%")
        if corso:
            query += " AND id_corso = ?"
            params.append(corso)

        # Esegui query lezioni filtrate
        cursor.execute(query, params)
        lezioni = cursor.fetchall()

        cursor.execute("SELECT * FROM corsi ORDER BY nome")
        corsi = cursor.fetchall()
        
        cursor.execute("""
            SELECT strftime('%Y-%m', data) as mese, COUNT(*) as numero_lezioni
            FROM lezioni
            GROUP BY mese
            ORDER BY mese
        """)
        dati_grafico = cursor.fetchall()
        
        mesi = []
        conteggi = []
        for dato in dati_grafico:
            mesi.append(dato['mese'])
            conteggi.append(dato['numero_lezioni'])
        
        cursor.execute("SELECT * FROM corsi_archiviati ORDER BY data_archiviazione DESC")
        corsi_archiviati = cursor.fetchall()

    return render_template("dashboard.html", 
                          username=user['username'], 
                          lezioni=lezioni, 
                          corsi=corsi,
                          corsi_archiviati=corsi_archiviati,
                          mesi=mesi,
                          conteggi=conteggi)


@lezioni_bp.route("/aggiungi_lezione", methods=["GET", "POST"])
@login_required
def aggiungi_lezione():
    if request.method == "POST":
        try:
            # Otteniamo tutte le liste di input dal form
            id_corsi = request.form.getlist("id_corso[]")
            materie = request.form.getlist("materia[]")
            date = request.form.getlist("data[]")
            ora_inizi = request.form.getlist("ora_inizio[]")
            ora_fini = request.form.getlist("ora_fine[]")
            luoghi = request.form.getlist("luogo[]")
            compensi = request.form.getlist("compenso_orario[]")
            stati = request.form.getlist("stato[]")

            with db_connection() as conn:
                cursor = conn.cursor()
                for i in range(len(materie)):
                    id_corso = id_corsi[i]
                    materia = materie[i]
                    data = date[i]
                    ora_inizio = correggi_orario(ora_inizi[i])
                    ora_fine = correggi_orario(ora_fini[i])
                    luogo = luoghi[i]
                    compenso_orario = float(compensi[i]) if compensi[i] else 0.0
                    stato = stati[i]

                    cursor.execute("""
                        INSERT INTO lezioni (id_corso, materia, data, ora_inizio, ora_fine, luogo, compenso_orario, stato)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (id_corso, materia, data, ora_inizio, ora_fine, luogo, compenso_orario, stato))
                conn.commit()

            flash("✅ Lezioni aggiunte con successo!", "success")
            filter_params = {k: v for k, v in request.args.items() if v}
            return redirect(url_for("lezioni.dashboard", **filter_params))

        except Exception as e:
            flash(f"❌ Errore durante l'aggiunta delle lezioni: {str(e)}", "danger")
            return redirect(url_for("lezioni.aggiungi_lezione"))

    # GET request: mostra la pagina
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM corsi ORDER BY nome")
        corsi = cursor.fetchall()

    return render_template("aggiungi_lezione.html", corsi=corsi)


@lezioni_bp.route("/modifica_lezione/<int:lezione_id>", methods=["GET", "POST"])
@login_required
def modifica_lezione(lezione_id):
    with db_connection() as conn:
        cursor = conn.cursor()

        if request.method == "POST":
            nuova_materia = request.form["materia"]
            nuova_data = request.form["data"]
            nuova_ora_inizio = request.form["ora_inizio"]
            nuova_ora_fine = request.form["ora_fine"]
            nuovo_luogo = request.form["luogo"]
            nuovo_compenso_orario = float(request.form["compenso_orario"])
            nuovo_stato = request.form["stato"]

            ore = calcola_ore(nuova_ora_inizio, nuova_ora_fine)
            if ore is not None:
                nuovo_compenso_totale = ore * nuovo_compenso_orario
            else:
                nuovo_compenso_totale = 0  # Valore predefinito se il calcolo ore fallisce

            cursor.execute("""
                UPDATE lezioni
                SET materia=?, data=?, ora_inizio=?, ora_fine=?, luogo=?, compenso_orario=?, stato=?
                WHERE id=?
            """, (nuova_materia, nuova_data, nuova_ora_inizio, nuova_ora_fine, nuovo_luogo, nuovo_compenso_orario, nuovo_stato, lezione_id))
            conn.commit()
            flash("Lezione modificata con successo.", "success")
            
            # Recupera i parametri di filtro dal form
            filter_params = {}
            for key, value in request.form.items():
                if key.startswith('filter_'):
                    filter_params[key[7:]] = value  # Rimuove il prefisso 'filter_'
            
            return redirect(url_for("lezioni.dashboard", **filter_params))

        cursor.execute("SELECT * FROM lezioni WHERE id=?", (lezione_id,))
        lezione = cursor.fetchone()

    return render_template("modifica_lezione.html", lezione=lezione)


@lezioni_bp.route("/elimina_lezione/<int:id_lezione>", methods=["POST"])
@login_required
def elimina_lezione(id_lezione):
    try:
        if 'csrf_token' not in request.form:
            print("CSRF token mancante nella richiesta")
            flash("❌ Errore: Token CSRF mancante", "danger")
            filter_params = {k: v for k, v in request.args.items() if v}
            return redirect(url_for("lezioni.dashboard", **filter_params))
            
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM lezioni WHERE id = ?", (id_lezione,))
            conn.commit()

        flash("✅ Lezione eliminata con successo!", "success")
        filter_params = {k: v for k, v in request.args.items() if v}
        return redirect(url_for("lezioni.dashboard", **filter_params))
    except Exception as e:
        print(f"Errore in elimina_lezione: {e}")
        flash("❌ Errore durante l'eliminazione della lezione", "danger")
        filter_params = {k: v for k, v in request.args.items() if v}
        return redirect(url_for("lezioni.dashboard", **filter_params))


@lezioni_bp.route("/completa_lezione/<int:id_lezione>", methods=["POST"])
@login_required
def completa_lezione(id_lezione):
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE lezioni SET stato = 'Completato' WHERE id = ?", (id_lezione,))
        conn.commit()

    flash("✅ Lezione segnata come completata!", "success")
    return redirect(url_for("calendario.calendario"))

@lezioni_bp.route("/compenso")
@login_required
def compenso():
    cliente_filtro = request.args.get("cliente", "")
    periodo_filtro = request.args.get("periodo", "tutti")
    data_inizio = request.args.get("data_inizio", "")
    data_fine = request.args.get("data_fine", "")
    corso_filtro = request.args.get("corso", "")
    
    with db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT cliente FROM corsi 
            WHERE cliente IS NOT NULL AND cliente != ''
            UNION
            SELECT DISTINCT cliente FROM corsi_archiviati 
            WHERE cliente IS NOT NULL AND cliente != ''
            ORDER BY cliente
        """)
        clienti = [row['cliente'] for row in cursor.fetchall()]
        
        cursor.execute("""
            SELECT c.id_corso, c.nome, c.cliente 
            FROM corsi c
            UNION
            SELECT ca.id_corso, ca.nome, ca.cliente 
            FROM corsi_archiviati ca
        """)
        corsi_info = cursor.fetchall()
        
        corsi_dict = {}
        for corso in corsi_info:
            id_corso = corso["id_corso"]
            nome = corso["nome"]
            cliente = corso["cliente"] if corso["cliente"] is not None else ""
            corsi_dict[id_corso] = {"id_corso": id_corso, "nome": nome, "cliente": cliente}
        
        corsi = sorted([c["id_corso"] for c in corsi_info])

        query = """
            SELECT l.id, l.id_corso, l.materia, l.data, l.ora_inizio, l.ora_fine, 
                   l.luogo, l.compenso_orario, l.stato, l.fatturato, l.mese_fatturato,
                   COALESCE(c.cliente, ca.cliente, 'Sconosciuto') as cliente
            FROM lezioni l
            LEFT JOIN corsi c ON l.id_corso = c.id_corso
            LEFT JOIN corsi_archiviati ca ON l.id_corso = ca.id_corso
            WHERE l.ora_inizio IS NOT NULL AND l.ora_fine IS NOT NULL
        """
        params = []
        
        if cliente_filtro:
            query += " AND (c.cliente = ? OR ca.cliente = ?)"
            params.append(cliente_filtro)
            params.append(cliente_filtro)
            
        params_archiviate = []
            
        if corso_filtro:
            query += " AND l.id_corso = ?"
            params.append(corso_filtro)
            
        if periodo_filtro != "tutti":
            oggi = datetime.now().strftime("%Y-%m-%d")
            
            if periodo_filtro == "giorno" and data_inizio:
                query += " AND l.data = ?"
                params.append(data_inizio)
            elif periodo_filtro == "settimana" and data_inizio:
                query += " AND strftime('%Y-%W', l.data) = strftime('%Y-%W', ?)"
                params.append(data_inizio)
            elif periodo_filtro == "mese" and data_inizio:
                query += " AND strftime('%Y-%m', l.data) = ?"
                params.append(data_inizio)
            elif periodo_filtro == "anno" and data_inizio:
                query += " AND strftime('%Y', l.data) = ?"
                params.append(data_inizio)
            elif periodo_filtro == "intervallo" and data_inizio and data_fine:
                query += " AND l.data BETWEEN ? AND ?"
                params.append(data_inizio)
                params.append(data_fine)
        
        cursor.execute(query, params)
        lezioni = cursor.fetchall()
        
        query_archiviate = """
            SELECT l.id, l.id_corso, l.materia, l.data, l.ora_inizio, l.ora_fine, 
                   l.luogo, l.compenso_orario, l.stato, l.fatturato, l.mese_fatturato,
                   COALESCE(c.cliente, ca.cliente, 'Sconosciuto') as cliente
            FROM archiviate l
            LEFT JOIN corsi c ON l.id_corso = c.id_corso
            LEFT JOIN corsi_archiviati ca ON l.id_corso = ca.id_corso
            WHERE l.ora_inizio IS NOT NULL AND l.ora_fine IS NOT NULL
        """
        params_archiviate = []
        
        if cliente_filtro:
            query_archiviate += " AND (c.cliente = ? OR ca.cliente = ?)"
            params_archiviate.append(cliente_filtro)
            params_archiviate.append(cliente_filtro)
            
        if corso_filtro:
            query_archiviate += " AND l.id_corso = ?"
            params_archiviate.append(corso_filtro)
            
        if periodo_filtro != "tutti":
            if periodo_filtro == "giorno" and data_inizio:
                query_archiviate += " AND l.data = ?"
                params_archiviate.append(data_inizio)
            elif periodo_filtro == "settimana" and data_inizio:
                query_archiviate += " AND strftime('%Y-%W', l.data) = strftime('%Y-%W', ?)"
                params_archiviate.append(data_inizio)
            elif periodo_filtro == "mese" and data_inizio:
                query_archiviate += " AND strftime('%Y-%m', l.data) = ?"
                params_archiviate.append(data_inizio)
            elif periodo_filtro == "anno" and data_inizio:
                query_archiviate += " AND strftime('%Y', l.data) = ?"
                params_archiviate.append(data_inizio)
            elif periodo_filtro == "intervallo" and data_inizio and data_fine:
                query_archiviate += " AND l.data BETWEEN ? AND ?"
                params_archiviate.append(data_inizio)
                params_archiviate.append(data_fine)
        
        cursor.execute(query_archiviate, params_archiviate)
        lezioni_archiviate = cursor.fetchall()
        
        tutte_lezioni = lezioni + lezioni_archiviate

    compensi = {
        "completate": 0,
        "fatturate": 0,
        "da_fatturare": 0,
        "pianificate": 0,
        "cancellate": 0
    }
    
    compensi_cliente = {}
    
    for lezione in tutte_lezioni:
        ore = calcola_ore(lezione["ora_inizio"], lezione["ora_fine"])
        if ore is None:
            continue
            
        compenso = ore * lezione["compenso_orario"]
        
        if lezione["stato"] == "Completato":
            if lezione["fatturato"] == 1:
                compensi["fatturate"] += compenso
            else:
                compensi["da_fatturare"] += compenso
            compensi["completate"] += compenso
        elif lezione["stato"] == "Pianificato":
            compensi["pianificate"] += compenso
        elif lezione["stato"] == "Cancellato":
            compensi["cancellate"] += compenso
            
        cliente = None
        
        if "cliente" in lezione and lezione["cliente"] and lezione["cliente"] != "Sconosciuto":
            cliente = lezione["cliente"]
        
        if not cliente or cliente == "Sconosciuto":
            corso_info = corsi_dict.get(lezione["id_corso"], None)
            if corso_info and "cliente" in corso_info and corso_info["cliente"]:
                cliente = corso_info["cliente"]
        
        if not cliente:
            cliente = "Sconosciuto"
        
        if cliente not in compensi_cliente:
            compensi_cliente[cliente] = {
                "completate": 0,
                "fatturate": 0,
                "da_fatturare": 0,
                "pianificate": 0,
                "cancellate": 0
            }
            
        if lezione["stato"] == "Completato":
            if lezione["fatturato"] == 1:
                compensi_cliente[cliente]["fatturate"] += compenso
            else:
                compensi_cliente[cliente]["da_fatturare"] += compenso
            compensi_cliente[cliente]["completate"] += compenso
        elif lezione["stato"] == "Pianificato":
            compensi_cliente[cliente]["pianificate"] += compenso
        elif lezione["stato"] == "Cancellato":
            compensi_cliente[cliente]["cancellate"] += compenso

    return render_template(
        "compenso.html", 
        corsi=corsi, 
        compensi=compensi,
        clienti=clienti,
        compensi_cliente=compensi_cliente,
        cliente_filtro=cliente_filtro,
        periodo_filtro=periodo_filtro,
        data_inizio=data_inizio,
        data_fine=data_fine,
        corso_filtro=corso_filtro
    )

@lezioni_bp.route("/elimina_lezioni", methods=["POST"])
@login_required
def elimina_lezioni():
    try:
        ids = request.form.getlist("lezioni_selezionate[]")
        if not ids:
            return "Nessuna lezione selezionata", 400

        with db_connection() as conn:
            cursor = conn.cursor()
            query = f"DELETE FROM lezioni WHERE id IN ({','.join(['?'] * len(ids))})"
            cursor.execute(query, ids)
            conn.commit()
        return "", 200
    except Exception as e:
        print("Errore eliminazione multipla:", e)
        return "Errore interno", 500


@lezioni_bp.route("/archivia_lezioni", methods=["POST"])
@login_required
def archivia_lezioni():
    try:
        ids = request.form.getlist("lezioni_selezionate[]")
        if not ids:
            return "Nessuna lezione selezionata", 400

        with db_connection() as conn:
            cursor = conn.cursor()
            
            query_select = f"SELECT * FROM lezioni WHERE id IN ({','.join(['?'] * len(ids))})"
            cursor.execute(query_select, ids)
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
            
            query_delete = f"DELETE FROM lezioni WHERE id IN ({','.join(['?'] * len(ids))})"
            cursor.execute(query_delete, ids)
            conn.commit()
            
        return "", 200
    except Exception as e:
        print("Errore archiviazione multipla:", e)
        return "Errore interno", 500
