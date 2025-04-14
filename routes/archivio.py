from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required
from database import db_connection
from datetime import datetime

archivio_bp = Blueprint('archivio', __name__)

@archivio_bp.route("/archivia_corso", methods=["POST"])
@login_required
def archivia_corso():
    if 'csrf_token' not in request.form:
        print("CSRF token mancante nella richiesta di archiviazione corso")
        flash("❌ Errore: Token CSRF mancante", "danger")
        return redirect(url_for("lezioni.dashboard"))
        
    id_corso = request.form.get("id_corso")

    if not id_corso:
        flash("⚠️ Seleziona un corso da archiviare.", "warning")
        return redirect(url_for("lezioni.dashboard"))

    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lezioni WHERE id_corso = ?", (id_corso,))
            lezioni = cursor.fetchall()

            if not lezioni:
                flash("⚠️ Nessuna lezione trovata per il corso selezionato.", "warning")
                return redirect(url_for("lezioni.dashboard"))

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
                    INSERT INTO corsi_archiviati (id_corso, nome, data_archiviazione)
                    VALUES (?, ?, ?)
                """, (corso["id_corso"], corso["nome"], data_archiviazione))
            
            cursor.execute("DELETE FROM lezioni WHERE id_corso = ?", (id_corso,))
            cursor.execute("DELETE FROM corsi WHERE id_corso = ?", (id_corso,))
            conn.commit()

        flash(f"✅ Corso '{id_corso}' e relative lezioni archiviate con successo!", "success")

    except Exception as e:
        print(f"Errore in archivia_corso: {e}")
        flash(f"❌ Errore durante l'archiviazione: {str(e)}", "danger")

    return redirect(url_for("lezioni.dashboard"))


@archivio_bp.route("/lezioni_archiviate")
@login_required
def lezioni_archiviate():
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM archiviate")
        lezioni = cursor.fetchall()

    return render_template("archiviate.html", lezioni=lezioni)


@archivio_bp.route("/ripristina_lezioni", methods=["POST"])
@login_required
def ripristina_lezioni():
    lezioni_da_ripristinare = request.form.getlist("lezioni_selezionate[]")

    if not lezioni_da_ripristinare:
        flash("⚠️ Seleziona almeno una lezione da ripristinare.", "warning")
        return redirect(url_for("archivio.lezioni_archiviate"))

    try:
        with db_connection() as conn:
            cursor = conn.cursor()

            query_select = f"SELECT * FROM archiviate WHERE id IN ({','.join(['?'] * len(lezioni_da_ripristinare))})"
            cursor.execute(query_select, lezioni_da_ripristinare)
            lezioni = cursor.fetchall()

            if not lezioni:
                flash("⚠️ Nessuna lezione trovata per il ripristino.", "warning")
                return redirect(url_for("archivio.lezioni_archiviate"))

            for lezione in lezioni:
                cursor.execute("""
                    INSERT INTO lezioni (id_corso, materia, data, ora_inizio, ora_fine, luogo, compenso_orario, stato, fatturato, mese_fatturato)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    lezione["id_corso"], lezione["materia"], lezione["data"],
                    lezione["ora_inizio"], lezione["ora_fine"], lezione["luogo"],
                    lezione["compenso_orario"], lezione["stato"], lezione["fatturato"], lezione["mese_fatturato"]
                ))

            query_delete = f"DELETE FROM archiviate WHERE id IN ({','.join(['?'] * len(lezioni_da_ripristinare))})"
            cursor.execute(query_delete, lezioni_da_ripristinare)
            conn.commit()

        flash(f"✅ {len(lezioni_da_ripristinare)} lezione/i ripristinata/e con successo.", "success")

    except Exception as e:
        flash(f"❌ Errore durante il ripristino: {str(e)}", "danger")

    return redirect(url_for("archivio.lezioni_archiviate"))

@archivio_bp.route("/corsi_archiviati")
@login_required
def corsi_archiviati():
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM corsi_archiviati ORDER BY data_archiviazione DESC")
        corsi = cursor.fetchall()

    return render_template("corsi_archiviati.html", corsi=corsi)


@archivio_bp.route("/elimina_corso_archiviato/<string:id_corso>", methods=["POST"])
@login_required
def elimina_corso_archiviato(id_corso):
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM archiviate WHERE id_corso = ?", (id_corso,))
            
            cursor.execute("DELETE FROM corsi_archiviati WHERE id_corso = ?", (id_corso,))
            conn.commit()
            
        flash(f"✅ Corso archiviato '{id_corso}' e relative lezioni eliminate con successo!", "success")
    except Exception as e:
        print(f"Errore in elimina_corso_archiviato: {e}")
        flash(f"❌ Errore durante l'eliminazione: {str(e)}", "danger")
        
    return redirect(url_for("archivio.corsi_archiviati"))


@archivio_bp.route("/elimina_lezioni_archiviate", methods=["POST"])
@login_required
def elimina_lezioni_archiviate():
    lezioni_da_eliminare = request.form.getlist("lezioni_selezionate[]")
    
    if not lezioni_da_eliminare:
        flash("⚠️ Seleziona almeno una lezione da eliminare.", "warning")
        return redirect(url_for("archivio.lezioni_archiviate"))
    
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            
            query_delete = f"DELETE FROM archiviate WHERE id IN ({','.join(['?'] * len(lezioni_da_eliminare))})"
            cursor.execute(query_delete, lezioni_da_eliminare)
            conn.commit()
            
        flash(f"✅ {len(lezioni_da_eliminare)} lezione/i eliminata/e definitivamente.", "success")
        
    except Exception as e:
        print(f"Errore in elimina_lezioni_archiviate: {e}")
        flash(f"❌ Errore durante l'eliminazione: {str(e)}", "danger")
    
    return redirect(url_for("archivio.lezioni_archiviate"))


@archivio_bp.route("/elimina_lezioni_archiviate_ajax", methods=["POST"])
@login_required
def elimina_lezioni_archiviate_ajax():
    lezioni_da_eliminare = request.form.getlist("lezioni_selezionate[]")
    
    if not lezioni_da_eliminare:
        return jsonify({"success": False, "message": "Nessuna lezione selezionata"}), 400
    
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            
            query_delete = f"DELETE FROM archiviate WHERE id IN ({','.join(['?'] * len(lezioni_da_eliminare))})"
            cursor.execute(query_delete, lezioni_da_eliminare)
            conn.commit()
            
        return jsonify({
            "success": True, 
            "message": f"{len(lezioni_da_eliminare)} lezione/i eliminata/e definitivamente."
        }), 200
        
    except Exception as e:
        print(f"Errore in elimina_lezioni_archiviate_ajax: {e}")
        return jsonify({"success": False, "message": f"Errore durante l'eliminazione: {str(e)}"}), 500
