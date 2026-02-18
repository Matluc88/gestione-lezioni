from flask import Blueprint, render_template
from flask_login import login_required
from db_utils import db_connection, get_placeholder

stato_crediti_bp = Blueprint('stato_crediti', __name__)

@stato_crediti_bp.route("/stato_crediti")
@login_required
def stato_crediti():
    """Mostra lo stato di completamento e i crediti maturati per ogni corso, raggruppati per cliente"""
    with db_connection() as conn:
        cursor = conn.cursor()
        placeholder = get_placeholder()
        
        # Query compatibile sia con SQLite che PostgreSQL
        if placeholder == "%s":  # PostgreSQL
            query = """
            SELECT 
                COALESCE(c.cliente, 'Senza Cliente') as cliente,
                l.id_corso,
                COALESCE(c.nome, l.id_corso) as nome_corso,
                COUNT(l.id) as totale_lezioni,
                SUM(CASE WHEN l.stato = 'Completato' THEN 1 ELSE 0 END) as lezioni_completate,
                SUM(CASE WHEN l.stato = 'Completato' THEN calcola_ore(l.ora_inizio, l.ora_fine) * l.compenso_orario ELSE 0 END) as credito_completato,
                SUM(CASE WHEN l.stato = 'Completato' AND l.fatturato = 1 THEN calcola_ore(l.ora_inizio, l.ora_fine) * l.compenso_orario ELSE 0 END) as credito_fatturato,
                SUM(CASE WHEN l.stato = 'Completato' AND l.fatturato = 0 THEN calcola_ore(l.ora_inizio, l.ora_fine) * l.compenso_orario ELSE 0 END) as credito_maturato,
                SUM(CASE WHEN l.stato != 'Completato' THEN calcola_ore(l.ora_inizio, l.ora_fine) * l.compenso_orario ELSE 0 END) as credito_futuro
            FROM lezioni l
            LEFT JOIN corsi c ON l.id_corso = c.id_corso
            GROUP BY COALESCE(c.cliente, 'Senza Cliente'), l.id_corso, c.nome
            ORDER BY cliente, nome_corso
            """
        else:  # SQLite
            query = """
            SELECT 
                COALESCE(c.cliente, 'Senza Cliente') as cliente,
                l.id_corso,
                COALESCE(c.nome, l.id_corso) as nome_corso,
                COUNT(l.id) as totale_lezioni,
                SUM(CASE WHEN l.stato = 'Completato' THEN 1 ELSE 0 END) as lezioni_completate,
                SUM(CASE WHEN l.stato = 'Completato' THEN 
                    ((julianday(l.ora_fine) - julianday(l.ora_inizio)) * 24) * l.compenso_orario 
                ELSE 0 END) as credito_completato,
                SUM(CASE WHEN l.stato = 'Completato' AND l.fatturato = 1 THEN 
                    ((julianday(l.ora_fine) - julianday(l.ora_inizio)) * 24) * l.compenso_orario 
                ELSE 0 END) as credito_fatturato,
                SUM(CASE WHEN l.stato = 'Completato' AND l.fatturato = 0 THEN 
                    ((julianday(l.ora_fine) - julianday(l.ora_inizio)) * 24) * l.compenso_orario 
                ELSE 0 END) as credito_maturato,
                SUM(CASE WHEN l.stato != 'Completato' THEN 
                    ((julianday(l.ora_fine) - julianday(l.ora_inizio)) * 24) * l.compenso_orario 
                ELSE 0 END) as credito_futuro
            FROM lezioni l
            LEFT JOIN corsi c ON l.id_corso = c.id_corso
            GROUP BY COALESCE(c.cliente, 'Senza Cliente'), l.id_corso, c.nome
            ORDER BY cliente, nome_corso
            """
        
        cursor.execute(query)
        risultati = cursor.fetchall()
        
        # Raggruppamento per cliente
        corsi_per_cliente = {}
        for row in risultati:
            cliente = row['cliente']
            if cliente not in corsi_per_cliente:
                corsi_per_cliente[cliente] = {
                    'corsi': [],
                    'totale_completato': 0,
                    'totale_fatturato': 0,
                    'totale_maturato': 0
                }
            
            totale_lezioni = row['totale_lezioni'] or 0
            lezioni_completate = row['lezioni_completate'] or 0
            percentuale = (lezioni_completate / totale_lezioni * 100) if totale_lezioni > 0 else 0
            
            credito_completato = float(row['credito_completato'] or 0)
            credito_fatturato = float(row['credito_fatturato'] or 0)
            credito_maturato = float(row['credito_maturato'] or 0)
            credito_futuro = float(row['credito_futuro'] or 0)
            
            corso_info = {
                'id_corso': row['id_corso'],
                'nome': row['nome_corso'],
                'totale_lezioni': totale_lezioni,
                'lezioni_completate': lezioni_completate,
                'percentuale': round(percentuale, 1),
                'credito_completato': credito_completato,
                'credito_fatturato': credito_fatturato,
                'credito_maturato': credito_maturato,
                'credito_futuro': credito_futuro,
                'pronto_fatturazione': percentuale == 100 and credito_maturato > 0
            }
            
            corsi_per_cliente[cliente]['corsi'].append(corso_info)
            corsi_per_cliente[cliente]['totale_completato'] += credito_completato
            corsi_per_cliente[cliente]['totale_fatturato'] += credito_fatturato
            corsi_per_cliente[cliente]['totale_maturato'] += credito_maturato
        
        # Calcoli generali
        totale_generale_completato = sum(c['totale_completato'] for c in corsi_per_cliente.values())
        totale_generale_fatturato = sum(c['totale_fatturato'] for c in corsi_per_cliente.values())
        totale_generale_maturato = sum(c['totale_maturato'] for c in corsi_per_cliente.values())
        
        corsi_pronti = sum(1 for cliente in corsi_per_cliente.values() 
                          for corso in cliente['corsi'] 
                          if corso['pronto_fatturazione'])
    
    return render_template(
        'stato_crediti.html',
        corsi_per_cliente=corsi_per_cliente,
        totale_generale_completato=totale_generale_completato,
        totale_generale_fatturato=totale_generale_fatturato,
        totale_generale_maturato=totale_generale_maturato,
        corsi_pronti=corsi_pronti
    )
