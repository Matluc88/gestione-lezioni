from flask import Blueprint, render_template
from flask_login import login_required
from db_utils import db_connection, get_placeholder

calendario_bp = Blueprint('calendario', __name__)

@calendario_bp.route("/calendario")
@login_required
def calendario():
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT lezioni.id, lezioni.id_corso, corsi.nome, materia, data, ora_inizio, ora_fine, stato
            FROM lezioni
            JOIN corsi ON lezioni.id_corso = corsi.id_corso
        """)
        lezioni = cursor.fetchall()

    eventi = []
    for lezione in lezioni:
        colore = "#28a745" if lezione["stato"] == "Completato" else "#007bff"
        eventi.append({
            "id": lezione["id"],
            "title": f"{lezione['nome']} - {lezione['materia']}",
            "start": f"{lezione['data']}T{lezione['ora_inizio']}",
            "end": f"{lezione['data']}T{lezione['ora_fine']}",
            "backgroundColor": colore,
            "borderColor": colore,
            "extendedProps": {"stato": lezione["stato"]}
        })

    return render_template("calendario.html", eventi=eventi)
