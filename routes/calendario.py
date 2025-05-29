from flask import Blueprint, render_template
from flask_login import login_required
from db_utils import db_connection, get_placeholder
from datetime import datetime

calendario_bp = Blueprint('calendario', __name__)

def normalizza_data(data_str):
    '''Converte qualsiasi formato di data in YYYY-MM-DD'''
    if not data_str:
        return None
        
    if data_str.count('-') == 2 and len(data_str.split('-')[0]) == 4:
        return data_str
        
    try:
        if '/' in data_str:
            giorno, mese, anno = data_str.split('/')
            return f"{anno}-{mese.zfill(2)}-{giorno.zfill(2)}"
        else:
            return data_str
    except Exception:
        return data_str

@calendario_bp.route("/calendario")
@login_required
def calendario():
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT lezioni.id, lezioni.id_corso, COALESCE(corsi.nome, lezioni.id_corso) as nome, 
                   materia, data, ora_inizio, ora_fine, stato
            FROM lezioni
            LEFT JOIN corsi ON lezioni.id_corso = corsi.id_corso
        """)
        lezioni = cursor.fetchall()

    eventi = []
    for lezione in lezioni:
        colore = "#28a745" if lezione["stato"] == "Completato" else "#007bff"
        eventi.append({
            "id": lezione["id"],
            "title": f"{lezione['nome']} - {lezione['materia']}",
            "start": f"{normalizza_data(lezione['data'])}T{lezione['ora_inizio']}",
            "end": f"{normalizza_data(lezione['data'])}T{lezione['ora_fine']}",
            "backgroundColor": colore,
            "borderColor": colore,
            "extendedProps": {"stato": lezione["stato"]}
        })

    return render_template("calendario.html", eventi=eventi)
