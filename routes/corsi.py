from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from db_utils import db_connection, get_placeholder
from datetime import datetime

corsi_bp = Blueprint('corsi', __name__)

@corsi_bp.route("/aggiungi_corso", methods=["GET", "POST"])
@login_required
def aggiungi_corso():
    if request.method == "POST":
        id_corso = request.form["id_corso"].strip().upper()
        nome = request.form["nome"].strip()
        cliente = request.form.get("cliente", "").strip()

        if not id_corso or not nome:
            flash("⚠️ Devi compilare tutti i campi obbligatori!", "danger")
            return redirect(url_for("corsi.aggiungi_corso"))

        with db_connection() as conn:
            cursor = conn.cursor()
            placeholder = get_placeholder()
            cursor.execute(f"SELECT COUNT(*) FROM corsi WHERE id_corso = {placeholder}", (id_corso,))
            if cursor.fetchone()[0] > 0:
                flash("⚠️ Questo corso esiste già!", "warning")
                return redirect(url_for("corsi.aggiungi_corso"))

            placeholder = get_placeholder()
            cursor.execute(f"INSERT INTO corsi (id_corso, nome, cliente) VALUES ({placeholder}, {placeholder}, {placeholder})", 
                          (id_corso, nome, cliente))
            conn.commit()

        flash("✅ Corso aggiunto con successo!", "success")
        return redirect(url_for("lezioni.aggiungi_lezione"))

    return render_template("aggiungi_corso.html")


@corsi_bp.route("/elimina_corso/<string:id_corso>", methods=["POST"])
@login_required
def elimina_corso(id_corso):
    with db_connection() as conn:
        cursor = conn.cursor()
        placeholder = get_placeholder()
        cursor.execute(f"SELECT id_corso FROM corsi WHERE id_corso = {placeholder}", (id_corso,))
        corso = cursor.fetchone()

        if corso:
            cursor.execute(f"DELETE FROM lezioni WHERE id_corso = {placeholder}", (id_corso,))
            cursor.execute(f"DELETE FROM corsi WHERE id_corso = {placeholder}", (id_corso,))
            conn.commit()
            flash("🗑️ Corso e lezioni associate eliminati con successo!", "success")
        else:
            flash("❌ Corso non trovato!", "danger")

    filter_params = {k: v for k, v in request.args.items() if v}
    return redirect(url_for("lezioni.dashboard", **filter_params))


@corsi_bp.route("/dettagli_corso/<string:corso>")
@login_required
def dettagli_corso(corso):
    if not corso:
        flash("Nessun corso selezionato!", "danger")
        return redirect(url_for("corsi.lista_corsi"))

    with db_connection() as conn:
        cursor = conn.cursor()
        
        placeholder = get_placeholder()
        cursor.execute(f"SELECT nome FROM corsi WHERE id_corso = {placeholder}", (corso,))
        corso_info = cursor.fetchone()
        if not corso_info:
            flash("Corso non trovato!", "danger")
            return redirect(url_for("corsi.lista_corsi"))
            
        nome_corso = corso_info["nome"]
        
        cursor.execute(f"SELECT COUNT(*) FROM lezioni WHERE id_corso = {placeholder}", (corso,))
        esiste = cursor.fetchone()[0]
        ha_lezioni = esiste > 0

        placeholder = get_placeholder()
        def ore(sql):
            cursor.execute(sql, (corso,))
            return cursor.fetchone()[0] or 0

        ore_totali = ore(f"""
            SELECT SUM(calcola_ore(ora_inizio, ora_fine))
            FROM lezioni WHERE id_corso = {placeholder}
        """)

        placeholder = get_placeholder()
        ore_completate = ore(f"""
            SELECT SUM(calcola_ore(ora_inizio, ora_fine))
            FROM lezioni WHERE id_corso = {placeholder} AND stato = 'Completato'
        """)

        placeholder = get_placeholder()
        ore_fatturate = ore(f"""
            SELECT SUM(ore_fatturate)
            FROM lezioni WHERE id_corso = {placeholder} AND fatturato > 0
        """)

        placeholder = get_placeholder()
        cursor.execute(f"""
            SELECT SUM(ore_fatturate * compenso_orario)
            FROM lezioni WHERE id_corso = {placeholder} AND fatturato > 0
        """, (corso,))
        totale_fatturato_lordo = cursor.fetchone()[0] or 0

    return render_template("dettagli_corso.html",
                           corso=corso,
                           nome_corso=nome_corso,
                           ore_totali=ore_totali,
                           ore_completate=ore_completate,
                           ore_fatturate=ore_fatturate,
                           totale_fatturato_lordo=totale_fatturato_lordo,
                           ha_lezioni=ha_lezioni)


@corsi_bp.route("/lista_corsi")
@login_required
def lista_corsi():
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM corsi ORDER BY nome")
        corsi_rows = cursor.fetchall()
        
        corsi = []
        for corso_row in corsi_rows:
            corso = dict(corso_row)
            placeholder = get_placeholder()
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as totale,
                    SUM(CASE WHEN fatturato = 1 THEN 1 ELSE 0 END) as completamente_fatturate,
                    SUM(CASE WHEN fatturato = 2 THEN 1 ELSE 0 END) as parzialmente_fatturate,
                    SUM(calcola_ore(ora_inizio, ora_fine)) as ore_totali,
                    SUM(ore_fatturate) as ore_fatturate
                FROM lezioni 
                WHERE id_corso = {placeholder}
            """, (corso['id_corso'],))
            
            result = cursor.fetchone()
            if result and result['totale'] > 0:
                corso['completamente_fatturato'] = (result['totale'] == result['completamente_fatturate'])
                corso['parzialmente_fatturato'] = (result['parzialmente_fatturate'] > 0)
                corso['ore_totali'] = result['ore_totali'] or 0
                corso['ore_fatturate'] = result['ore_fatturate'] or 0
                corso['ore_rimanenti'] = corso['ore_totali'] - corso['ore_fatturate']
            else:
                corso['completamente_fatturato'] = False
                corso['parzialmente_fatturato'] = False
                corso['ore_totali'] = 0
                corso['ore_fatturate'] = 0
                corso['ore_rimanenti'] = 0
            
            corsi.append(corso)
                
    return render_template("corsi.html", corsi=corsi)


@corsi_bp.route("/modifica_corso/<string:id_corso>", methods=["GET", "POST"])
@login_required
def modifica_corso(id_corso):
    with db_connection() as conn:
        cursor = conn.cursor()
        placeholder = get_placeholder()
        cursor.execute(f"SELECT * FROM corsi WHERE id_corso = {placeholder}", (id_corso,))
        corso = cursor.fetchone()
        
        if not corso:
            flash("❌ Corso non trovato!", "danger")
            return redirect(url_for("corsi.lista_corsi"))
        
        if request.method == "POST":
            nuovo_nome = request.form["nome"].strip()
            nuovo_cliente = request.form.get("cliente", "").strip()
            
            if not nuovo_nome:
                flash("⚠️ Il nome del corso è obbligatorio!", "danger")
                return render_template("modifica_corso.html", corso=corso)
            
            placeholder = get_placeholder()
            cursor.execute(f"UPDATE corsi SET nome = {placeholder}, cliente = {placeholder} WHERE id_corso = {placeholder}", 
                          (nuovo_nome, nuovo_cliente, id_corso))
            conn.commit()
            
            flash("✅ Corso aggiornato con successo!", "success")
            return redirect(url_for("corsi.lista_corsi"))
        
        return render_template("modifica_corso.html", corso=corso)


@corsi_bp.route("/archivia_corso/<string:id_corso>", methods=["POST"])
@login_required
def archivia_corso(id_corso):
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            placeholder = get_placeholder()
            cursor.execute(f"SELECT * FROM lezioni WHERE id_corso = {placeholder}", (id_corso,))
            lezioni = cursor.fetchall()

            if not lezioni:
                flash("⚠️ Nessuna lezione trovata per il corso selezionato.", "warning")
                return redirect(url_for("corsi.lista_corsi"))

            for lezione in lezioni:
                placeholder = get_placeholder()
                cursor.execute(f"""
                    INSERT INTO archiviate (id_corso, materia, data, ora_inizio, ora_fine, luogo, compenso_orario, stato, fatturato, mese_fatturato, ore_fatturate)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                """, (
                    lezione["id_corso"], lezione["materia"], lezione["data"],
                    lezione["ora_inizio"], lezione["ora_fine"], lezione["luogo"],
                    lezione["compenso_orario"], lezione["stato"], lezione["fatturato"], 
                    lezione["mese_fatturato"], lezione.get("ore_fatturate", 0)
                ))

            placeholder = get_placeholder()
            cursor.execute(f"SELECT * FROM corsi WHERE id_corso = {placeholder}", (id_corso,))
            corso = cursor.fetchone()
            
            if corso:
                data_archiviazione = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                placeholder = get_placeholder()
                cursor.execute(f"""
                    INSERT INTO corsi_archiviati (id_corso, nome, cliente, data_archiviazione)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})
                """, (corso["id_corso"], corso["nome"], corso.get("cliente", ""), data_archiviazione))
            
            placeholder = get_placeholder()
            cursor.execute(f"DELETE FROM lezioni WHERE id_corso = {placeholder}", (id_corso,))
            cursor.execute(f"DELETE FROM corsi WHERE id_corso = {placeholder}", (id_corso,))
            conn.commit()

        flash(f"✅ Corso '{id_corso}' e relative lezioni archiviate con successo!", "success")

    except Exception as e:
        print(f"Errore in archivia_corso: {e}")
        flash(f"❌ Errore durante l'archiviazione: {str(e)}", "danger")

    return redirect(url_for("corsi.lista_corsi"))


@corsi_bp.route("/elimina_corsi_multipli", methods=["POST"])
@login_required
def elimina_corsi_multipli():
    try:
        corsi_selezionati = request.form.getlist("corsi_selezionati[]")
        if not corsi_selezionati:
            flash("⚠️ Nessun corso selezionato.", "warning")
            return redirect(url_for("corsi.lista_corsi"))

        with db_connection() as conn:
            cursor = conn.cursor()
            corsi_eliminati = 0
            
            for id_corso in corsi_selezionati:
                placeholder = get_placeholder()
                cursor.execute(f"SELECT id_corso FROM corsi WHERE id_corso = {placeholder}", (id_corso,))
                corso = cursor.fetchone()
                
                if corso:
                    cursor.execute(f"DELETE FROM lezioni WHERE id_corso = {placeholder}", (id_corso,))
                    cursor.execute(f"DELETE FROM corsi WHERE id_corso = {placeholder}", (id_corso,))
                    corsi_eliminati += 1
            
            conn.commit()
            
            if corsi_eliminati > 0:
                flash(f"🗑️ {corsi_eliminati} corsi e relative lezioni eliminati con successo!", "success")
            else:
                flash("❌ Nessun corso trovato tra quelli selezionati.", "danger")
                
    except Exception as e:
        print(f"Errore in elimina_corsi_multipli: {e}")
        flash(f"❌ Errore durante l'eliminazione: {str(e)}", "danger")
        
    return redirect(url_for("corsi.lista_corsi"))


@corsi_bp.route("/archivia_corsi_multipli", methods=["POST"])
@login_required
def archivia_corsi_multipli():
    try:
        corsi_selezionati = request.form.getlist("corsi_selezionati[]")
        if not corsi_selezionati:
            flash("⚠️ Nessun corso selezionato.", "warning")
            return redirect(url_for("corsi.lista_corsi"))

        with db_connection() as conn:
            cursor = conn.cursor()
            corsi_archiviati = 0
            
            for id_corso in corsi_selezionati:
                placeholder = get_placeholder()
                cursor.execute(f"SELECT * FROM lezioni WHERE id_corso = {placeholder}", (id_corso,))
                lezioni = cursor.fetchall()
                
                if lezioni:
                    for lezione in lezioni:
                        placeholder = get_placeholder()
                        cursor.execute(f"""
                            INSERT INTO archiviate (id_corso, materia, data, ora_inizio, ora_fine, luogo, compenso_orario, stato, fatturato, mese_fatturato, ore_fatturate)
                            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                        """, (
                            lezione["id_corso"], lezione["materia"], lezione["data"],
                            lezione["ora_inizio"], lezione["ora_fine"], lezione["luogo"],
                            lezione["compenso_orario"], lezione["stato"], lezione["fatturato"], 
                            lezione["mese_fatturato"], lezione.get("ore_fatturate", 0)
                        ))
                    
                    placeholder = get_placeholder()
                    cursor.execute(f"SELECT * FROM corsi WHERE id_corso = {placeholder}", (id_corso,))
                    corso = cursor.fetchone()
                    
                    if corso:
                        data_archiviazione = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        placeholder = get_placeholder()
                        cursor.execute(f"""
                            INSERT INTO corsi_archiviati (id_corso, nome, cliente, data_archiviazione)
                            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})
                        """, (corso["id_corso"], corso["nome"], corso.get("cliente", ""), data_archiviazione))
                    
                    placeholder = get_placeholder()
                    cursor.execute(f"DELETE FROM lezioni WHERE id_corso = {placeholder}", (id_corso,))
                    cursor.execute(f"DELETE FROM corsi WHERE id_corso = {placeholder}", (id_corso,))
                    corsi_archiviati += 1
            
            conn.commit()
            
            if corsi_archiviati > 0:
                flash(f"✅ {corsi_archiviati} corsi e relative lezioni archiviate con successo!", "success")
            else:
                flash("⚠️ Nessuna lezione trovata per i corsi selezionati.", "warning")
                
    except Exception as e:
        print(f"Errore in archivia_corsi_multipli: {e}")
        flash(f"❌ Errore durante l'archiviazione: {str(e)}", "danger")
        
    return redirect(url_for("corsi.lista_corsi"))
