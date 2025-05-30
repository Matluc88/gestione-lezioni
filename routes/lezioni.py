from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from db_utils import db_connection, get_placeholder
from utils import correggi_orario, calcola_ore
from utils.security import sanitize_input, sanitize_form_data

lezioni_bp = Blueprint('lezioni', __name__)

@lezioni_bp.route("/dashboard")
@login_required
def dashboard():
    with db_connection() as conn:
        cursor = conn.cursor()

        placeholder = get_placeholder()
        
        # Recupera l'utente
        cursor.execute(f"SELECT username FROM users WHERE id = {placeholder}", (current_user.id,))
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
            query += f" AND materia LIKE {placeholder}"
            params.append(f"%{materia}%")
        if data:
            query += f" AND data = {placeholder}"
            params.append(data)
        if stato:
            query += f" AND stato = {placeholder}"
            params.append(stato)
        if luogo:
            query += f" AND luogo LIKE {placeholder}"
            params.append(f"%{luogo}%")
        if corso:
            query += f" AND id_corso = {placeholder}"
            params.append(corso)

        # Esegui query lezioni filtrate
        cursor.execute(query, params)
        lezioni = cursor.fetchall()

        cursor.execute("SELECT * FROM corsi ORDER BY nome")
        corsi = cursor.fetchall()
        
        if get_placeholder() == "%s":  # PostgreSQL
            cursor.execute("""
                SELECT TO_CHAR(data::date, 'YYYY-MM') as mese, COUNT(*) as numero_lezioni
                FROM lezioni
                GROUP BY mese
                ORDER BY mese
            """)
        else:  # SQLite
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
            # Otteniamo tutte le liste di input dal form e sanitizziamo
            id_corsi = request.form.getlist("id_corso[]")
            materie = [sanitize_input(materia) for materia in request.form.getlist("materia[]")]
            date = request.form.getlist("data[]")
            ora_inizi = request.form.getlist("ora_inizio[]")
            ora_fini = request.form.getlist("ora_fine[]")
            luoghi = [sanitize_input(luogo) for luogo in request.form.getlist("luogo[]")]
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

                    placeholder = get_placeholder()
                    cursor.execute(f"""
                        INSERT INTO lezioni (id_corso, materia, data, ora_inizio, ora_fine, luogo, compenso_orario, stato)
                        VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
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
            nuova_materia = sanitize_input(request.form["materia"])
            nuova_data = request.form["data"]
            nuova_ora_inizio = request.form["ora_inizio"]
            nuova_ora_fine = request.form["ora_fine"]
            nuovo_luogo = sanitize_input(request.form["luogo"])
            nuovo_compenso_orario = float(request.form["compenso_orario"])
            nuovo_stato = sanitize_input(request.form["stato"])

            ore = calcola_ore(nuova_ora_inizio, nuova_ora_fine)
            if ore is not None:
                nuovo_compenso_totale = ore * nuovo_compenso_orario
            else:
                nuovo_compenso_totale = 0  # Valore predefinito se il calcolo ore fallisce

            placeholder = get_placeholder()
            cursor.execute(f"""
                UPDATE lezioni
                SET materia={placeholder}, data={placeholder}, ora_inizio={placeholder}, ora_fine={placeholder}, luogo={placeholder}, compenso_orario={placeholder}, stato={placeholder}
                WHERE id={placeholder}
            """, (nuova_materia, nuova_data, nuova_ora_inizio, nuova_ora_fine, nuovo_luogo, nuovo_compenso_orario, nuovo_stato, lezione_id))
            conn.commit()
            flash("Lezione modificata con successo.", "success")
            
            # Recupera i parametri di filtro dal form
            filter_params = {}
            for key, value in request.form.items():
                if key.startswith('filter_'):
                    filter_params[key[7:]] = value  # Rimuove il prefisso 'filter_'
            
            return redirect(url_for("lezioni.dashboard", **filter_params))

        placeholder = get_placeholder()
        cursor.execute(f"SELECT * FROM lezioni WHERE id={placeholder}", (lezione_id,))
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
            placeholder = get_placeholder()
            cursor.execute(f"DELETE FROM lezioni WHERE id = {placeholder}", (id_lezione,))
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
        placeholder = get_placeholder()
        cursor.execute(f"UPDATE lezioni SET stato = 'Completato' WHERE id = {placeholder}", (id_lezione,))
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
        
        placeholder = get_placeholder()
        if cliente_filtro:
            query += f" AND (c.cliente = {placeholder} OR ca.cliente = {placeholder})"
            params.append(cliente_filtro)
            params.append(cliente_filtro)
            
        params_archiviate = []
            
        if corso_filtro:
            query += f" AND l.id_corso = {placeholder}"
            params.append(corso_filtro)
            
        if periodo_filtro != "tutti":
            oggi = datetime.now().strftime("%Y-%m-%d")
            
            if periodo_filtro == "giorno" and data_inizio:
                query += f" AND l.data = {placeholder}"
                params.append(data_inizio)
            elif periodo_filtro == "settimana" and data_inizio:
                query += f" AND extract_year_week(l.data) = extract_year_week({placeholder})"
                params.append(data_inizio)
            elif periodo_filtro == "mese" and data_inizio:
                query += f" AND extract_year_month(l.data) = {placeholder}"
                params.append(data_inizio)
            elif periodo_filtro == "anno" and data_inizio:
                query += f" AND extract_year(l.data) = {placeholder}"
                params.append(data_inizio)
            elif periodo_filtro == "intervallo" and data_inizio and data_fine:
                query += f" AND l.data BETWEEN {placeholder} AND {placeholder}"
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
        
        placeholder = get_placeholder()
        if cliente_filtro:
            query_archiviate += f" AND (c.cliente = {placeholder} OR ca.cliente = {placeholder})"
            params_archiviate.append(cliente_filtro)
            params_archiviate.append(cliente_filtro)
            
        if corso_filtro:
            placeholder = get_placeholder()
            query_archiviate += f" AND l.id_corso = {placeholder}"
            params_archiviate.append(corso_filtro)
            
        if periodo_filtro != "tutti":
            if periodo_filtro == "giorno" and data_inizio:
                placeholder = get_placeholder()
                query_archiviate += f" AND l.data = {placeholder}"
                params_archiviate.append(data_inizio)
            elif periodo_filtro == "settimana" and data_inizio:
                placeholder = get_placeholder()
                query_archiviate += f" AND extract_year_week(l.data) = extract_year_week({placeholder})"
                params_archiviate.append(data_inizio)
            elif periodo_filtro == "mese" and data_inizio:
                placeholder = get_placeholder()
                query_archiviate += f" AND extract_year_month(l.data) = {placeholder}"
                params_archiviate.append(data_inizio)
            elif periodo_filtro == "anno" and data_inizio:
                placeholder = get_placeholder()
                query_archiviate += f" AND extract_year(l.data) = {placeholder}"
                params_archiviate.append(data_inizio)
            elif periodo_filtro == "intervallo" and data_inizio and data_fine:
                placeholder = get_placeholder()
                query_archiviate += f" AND l.data BETWEEN {placeholder} AND {placeholder}"
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
            placeholder = get_placeholder()
            placeholders = ','.join([placeholder] * len(ids))
            query = f"DELETE FROM lezioni WHERE id IN ({placeholders})"
            cursor.execute(query, ids)
            conn.commit()
        return "", 200
    except Exception as e:
        print("Errore eliminazione multipla:", e)
        return "Errore interno", 500


@lezioni_bp.route("/cerca_lezioni_vocale", methods=["POST"])
@login_required
def cerca_lezioni_vocale():
    """Cerca lezioni in base a una query vocale"""
    try:
        data = request.json
        query = sanitize_input(data.get('query', '')).lower()
        
        data_cercata = None
        
        oggi = datetime.now().strftime("%Y-%m-%d")
        
        if "oggi" in query:
            data_cercata = oggi
        elif "domani" in query:
            data_cercata = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "ieri" in query:
            data_cercata = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            mesi = {
                "gennaio": "01", "febbraio": "02", "marzo": "03", "aprile": "04",
                "maggio": "05", "giugno": "06", "luglio": "07", "agosto": "08",
                "settembre": "09", "ottobre": "10", "novembre": "11", "dicembre": "12"
            }
            
            for mese, numero in mesi.items():
                if mese in query:
                    for i in range(1, 32):
                        if f" {i} {mese}" in query or f" {i}{mese}" in query:
                            anno = datetime.now().year
                            for anno_possibile in range(anno-1, anno+2):
                                if str(anno_possibile) in query:
                                    anno = anno_possibile
                                    break
                            
                            giorno = f"0{i}" if i < 10 else str(i)
                            data_cercata = f"{anno}-{numero}-{giorno}"
                            break
        
        if not data_cercata:
            return jsonify({"success": False, "message": "Nessuna data riconosciuta nella query"})
        
        with db_connection() as conn:
            cursor = conn.cursor()
            placeholder = get_placeholder()
            cursor.execute(f"""
                SELECT l.*, c.nome as nome_corso
                FROM lezioni l
                LEFT JOIN corsi c ON l.id_corso = c.id_corso
                WHERE l.data = {placeholder}
                ORDER BY l.ora_inizio
            """, (data_cercata,))
            
            lezioni = cursor.fetchall()
            
            lezioni_json = []
            for lezione in lezioni:
                lezione_dict = dict(lezione)
                lezioni_json.append(lezione_dict)
            
            return jsonify({
                "success": True,
                "lezioni": lezioni_json,
                "data": data_cercata
            })
    
    except Exception as e:
        print(f"Errore nella ricerca vocale: {e}")
        return jsonify({"success": False, "message": f"Errore: {str(e)}"})

@lezioni_bp.route("/archivia_lezioni", methods=["POST"])
@login_required
def archivia_lezioni():
    try:
        ids = request.form.getlist("lezioni_selezionate[]")
        if not ids:
            return "Nessuna lezione selezionata", 400

        with db_connection() as conn:
            cursor = conn.cursor()
            
            placeholder = get_placeholder()
            placeholders = ','.join([placeholder] * len(ids))
            query_select = f"SELECT * FROM lezioni WHERE id IN ({placeholders})"
            cursor.execute(query_select, ids)
            lezioni = cursor.fetchall()
            
            for lezione in lezioni:
                placeholder = get_placeholder()
                cursor.execute(f"""
                    INSERT INTO archiviate (id_corso, materia, data, ora_inizio, ora_fine, luogo, compenso_orario, stato, fatturato, mese_fatturato)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                """, (
                    lezione["id_corso"], lezione["materia"], lezione["data"],
                    lezione["ora_inizio"], lezione["ora_fine"], lezione["luogo"],
                    lezione["compenso_orario"], lezione["stato"], lezione["fatturato"], lezione["mese_fatturato"]
                ))
            
            placeholder = get_placeholder()
            placeholders = ','.join([placeholder] * len(ids))
            query_delete = f"DELETE FROM lezioni WHERE id IN ({placeholders})"
            cursor.execute(query_delete, ids)
            conn.commit()
            
        return "", 200
    except Exception as e:
        print("Errore archiviazione multipla:", e)
        return "Errore interno", 500
