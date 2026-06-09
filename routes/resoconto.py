from flask import Blueprint, render_template, request
from flask_login import login_required
from db_utils import db_connection, get_placeholder
import json
from datetime import datetime
from utils.time_utils import get_local_now, calcola_ore

resoconto_bp = Blueprint('resoconto', __name__)

@resoconto_bp.route("/resoconto_annuale")
@login_required
def resoconto_annuale():
    anno_selezionato = request.args.get('anno', get_local_now().strftime('%Y'))
    
    with db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT extract_year(data) as anno 
            FROM lezioni 
            UNION 
            SELECT DISTINCT extract_year(data) as anno 
            FROM archiviate
            ORDER BY anno DESC
        """)
        anni_disponibili = [row['anno'] for row in cursor.fetchall()]
        
        if not anni_disponibili or anno_selezionato not in anni_disponibili:
            anno_selezionato = get_local_now().strftime('%Y')
            if not anni_disponibili:
                anni_disponibili = [anno_selezionato]
        
        totale_fatturate = 0
        totale_da_fatturare = 0
        totale_pianificate = 0
        totale_cancellate = 0
        
        cursor.execute("""
            SELECT l.*, 
                   EXTRACT(MONTH FROM TO_DATE(l.data, 'YYYY-MM-DD'))::TEXT as mese,
                   COALESCE(c.cliente, ca.cliente, 'Sconosciuto') as cliente
            FROM lezioni l
            LEFT JOIN corsi c ON l.id_corso = c.id_corso
            LEFT JOIN corsi_archiviati ca ON l.id_corso = ca.id_corso
            WHERE extract_year(l.data) = %s
        """, (anno_selezionato,))
        
        lezioni = cursor.fetchall()
        
        cursor.execute("""
            SELECT a.*, 
                   EXTRACT(MONTH FROM TO_DATE(a.data, 'YYYY-MM-DD'))::TEXT as mese,
                   COALESCE(c.cliente, ca.cliente, 'Sconosciuto') as cliente
            FROM archiviate a
            LEFT JOIN corsi c ON a.id_corso = c.id_corso
            LEFT JOIN corsi_archiviati ca ON a.id_corso = ca.id_corso
            WHERE extract_year(a.data) = %s
        """, (anno_selezionato,))
        
        lezioni_archiviate = cursor.fetchall()
        
        tutte_lezioni = lezioni + lezioni_archiviate
        
        mesi = ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno', 
                'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre']
        
        dati_mensili_fatturate = [0] * 12
        dati_mensili_da_fatturare = [0] * 12
        dati_mensili_pianificate = [0] * 12
        dati_mensili_cancellate = [0] * 12
        
        clienti_dict = {}
        
        for lezione in tutte_lezioni:
            ore = calcola_ore(lezione['ora_inizio'], lezione['ora_fine'])
            if ore is None:
                continue
                
            compenso = ore * lezione['compenso_orario']
            
            if lezione['stato'] == 'Completato':
                if lezione['fatturato'] == 1:
                    totale_fatturate += compenso
                    dati_mensili_fatturate[int(lezione['mese']) - 1] += compenso
                else:
                    totale_da_fatturare += compenso
                    dati_mensili_da_fatturare[int(lezione['mese']) - 1] += compenso
            elif lezione['stato'] == 'Pianificato':
                totale_pianificate += compenso
                dati_mensili_pianificate[int(lezione['mese']) - 1] += compenso
            elif lezione['stato'] == 'Cancellato':
                totale_cancellate += compenso
                dati_mensili_cancellate[int(lezione['mese']) - 1] += compenso
            
            try:
                cliente = lezione['cliente'] if lezione['cliente'] is not None else 'Sconosciuto'
            except (KeyError, IndexError):
                cliente = 'Sconosciuto'
            if cliente not in clienti_dict:
                clienti_dict[cliente] = {
                    'fatturate': 0,
                    'da_fatturare': 0,
                    'pianificate': 0,
                    'cancellate': 0
                }
            
            if lezione['stato'] == 'Completato':
                if lezione['fatturato'] == 1:
                    clienti_dict[cliente]['fatturate'] += compenso
                else:
                    clienti_dict[cliente]['da_fatturare'] += compenso
            elif lezione['stato'] == 'Pianificato':
                clienti_dict[cliente]['pianificate'] += compenso
            elif lezione['stato'] == 'Cancellato':
                clienti_dict[cliente]['cancellate'] += compenso
        
        clienti = list(clienti_dict.keys())
        dati_clienti_fatturate = [clienti_dict[c]['fatturate'] for c in clienti]
        dati_clienti_da_fatturare = [clienti_dict[c]['da_fatturare'] for c in clienti]
        dati_clienti_pianificate = [clienti_dict[c]['pianificate'] for c in clienti]
        dati_clienti_cancellate = [clienti_dict[c]['cancellate'] for c in clienti]
        
        totale_complessivo = totale_fatturate + totale_da_fatturare + totale_pianificate + totale_cancellate
        
        if totale_complessivo > 0:
            percentuale_fatturate = (totale_fatturate / totale_complessivo) * 100
            percentuale_da_fatturare = (totale_da_fatturare / totale_complessivo) * 100
            percentuale_pianificate = (totale_pianificate / totale_complessivo) * 100
            percentuale_cancellate = (totale_cancellate / totale_complessivo) * 100
        else:
            percentuale_fatturate = percentuale_da_fatturare = percentuale_pianificate = percentuale_cancellate = 0
        
        totali_per_anno = {}
        
        cursor.execute("""
            SELECT l.*, extract_year(l.data) as anno,
                   COALESCE(c.cliente, ca.cliente, 'Sconosciuto') as cliente
            FROM lezioni l
            LEFT JOIN corsi c ON l.id_corso = c.id_corso
            LEFT JOIN corsi_archiviati ca ON l.id_corso = ca.id_corso
            UNION ALL
            SELECT a.*, extract_year(a.data) as anno,
                   COALESCE(c.cliente, ca.cliente, 'Sconosciuto') as cliente
            FROM archiviate a
            LEFT JOIN corsi c ON a.id_corso = c.id_corso
            LEFT JOIN corsi_archiviati ca ON a.id_corso = ca.id_corso
        """)
        
        tutte_lezioni_storiche = cursor.fetchall()
        
        for lezione in tutte_lezioni_storiche:
            anno = lezione['anno']
            if anno not in totali_per_anno:
                totali_per_anno[anno] = {
                    'fatturate': 0,
                    'da_fatturare': 0,
                    'pianificate': 0,
                    'cancellate': 0,
                    'totale': 0,
                    'n_completate': 0,
                    'n_fatturate': 0
                }

            ore = calcola_ore(lezione['ora_inizio'], lezione['ora_fine'])
            if ore is None:
                continue

            compenso = ore * lezione['compenso_orario']

            if lezione['stato'] == 'Completato':
                totali_per_anno[anno]['n_completate'] += 1
                if lezione['fatturato'] == 1:
                    totali_per_anno[anno]['fatturate'] += compenso
                    totali_per_anno[anno]['n_fatturate'] += 1
                else:
                    totali_per_anno[anno]['da_fatturare'] += compenso
            elif lezione['stato'] == 'Pianificato':
                totali_per_anno[anno]['pianificate'] += compenso
            elif lezione['stato'] == 'Cancellato':
                totali_per_anno[anno]['cancellate'] += compenso

            totali_per_anno[anno]['totale'] += compenso

        anni_grafico = sorted(totali_per_anno.keys())
        dati_fatturate_per_anno = [totali_per_anno[a]['fatturate'] for a in anni_grafico]
        dati_da_fatturare_per_anno = [totali_per_anno[a]['da_fatturare'] for a in anni_grafico]
        dati_pianificate_per_anno = [totali_per_anno[a]['pianificate'] for a in anni_grafico]
        dati_cancellate_per_anno = [totali_per_anno[a]['cancellate'] for a in anni_grafico]
        dati_totali_per_anno = [totali_per_anno[a]['totale'] for a in anni_grafico]
        n_completate_per_anno = [totali_per_anno[a]['n_completate'] for a in anni_grafico]
        n_fatturate_per_anno = [totali_per_anno[a]['n_fatturate'] for a in anni_grafico]
        
        # ========== NUOVA SEZIONE: FATTURE EMESSE NELL'ANNO ==========
        cursor.execute("""
            SELECT f.id_fattura, f.numero_fattura, f.id_corso, f.data_fattura, 
                   f.importo, f.tipo_fatturazione, f.note,
                   COALESCE(c.cliente, ca.cliente, 'Sconosciuto') as cliente,
                   COALESCE(c.nome, ca.nome, f.id_corso) as nome_corso
            FROM fatture f
            LEFT JOIN corsi c ON f.id_corso = c.id_corso
            LEFT JOIN corsi_archiviati ca ON f.id_corso = ca.id_corso
            WHERE EXTRACT(YEAR FROM TO_DATE(f.data_fattura, 'YYYY-MM-DD')) = %s
            ORDER BY f.data_fattura DESC, f.numero_fattura DESC
        """, (anno_selezionato,))
        
        fatture_emesse = cursor.fetchall()
        
        # Calcola il totale delle fatture emesse
        totale_fatture_emesse = sum(f['importo'] for f in fatture_emesse)
        
        # Raggruppa fatture per tipo
        fatture_totali = [f for f in fatture_emesse if f['tipo_fatturazione'] == 'totale']
        fatture_parziali = [f for f in fatture_emesse if f['tipo_fatturazione'] == 'parziale']
        
        totale_fatture_totali = sum(f['importo'] for f in fatture_totali)
        totale_fatture_parziali = sum(f['importo'] for f in fatture_parziali)
        
        # Prepara dati mensili per fatture emesse
        dati_mensili_fatture_emesse = [0] * 12
        for fattura in fatture_emesse:
            mese_fattura = int(fattura['data_fattura'].split('-')[1]) - 1
            dati_mensili_fatture_emesse[mese_fattura] += fattura['importo']

        # ========== CADENZA MEDIA DI FATTURAZIONE (tutte le fatture storiche) ==========
        cursor.execute("""
            SELECT data_fattura FROM fatture
            WHERE data_fattura IS NOT NULL
            ORDER BY data_fattura ASC
        """)
        date_fatture = []
        for row in cursor.fetchall():
            try:
                date_fatture.append(datetime.strptime(row['data_fattura'][:10], '%Y-%m-%d'))
            except (ValueError, TypeError):
                continue

        cadenza_fatturazione = None
        if len(date_fatture) >= 2:
            date_fatture.sort()
            n_fatt = len(date_fatture)
            span_giorni = (date_fatture[-1] - date_fatture[0]).days
            gaps = [(date_fatture[i] - date_fatture[i - 1]).days
                    for i in range(1, n_fatt)]
            gaps_sorted = sorted(gaps)
            m = len(gaps_sorted)
            if m % 2 == 1:
                mediana_giorni = gaps_sorted[m // 2]
            else:
                mediana_giorni = (gaps_sorted[m // 2 - 1] + gaps_sorted[m // 2]) / 2
            media_giorni = span_giorni / (n_fatt - 1) if n_fatt > 1 else 0
            mesi_totali = span_giorni / 30.44 if span_giorni > 0 else 0
            fatture_per_mese = (n_fatt / mesi_totali) if mesi_totali > 0 else 0
            cadenza_fatturazione = {
                'n_fatture': n_fatt,
                'prima_data': date_fatture[0].strftime('%d/%m/%Y'),
                'ultima_data': date_fatture[-1].strftime('%d/%m/%Y'),
                'media_giorni': round(media_giorni, 1),
                'mediana_giorni': round(mediana_giorni, 1),
                'fatture_per_mese': round(fatture_per_mese, 1),
            }

        # ========== RITMO DI FATTURAZIONE PER MESE (tutti gli anni) ==========
        # Quanti mesi passano, tipicamente, tra un mese in cui fatturi e il successivo.
        ritmo_mesi = None
        fatture_per_mese_labels = []
        fatture_per_mese_counts = []
        if date_fatture:
            mesi_nomi = ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu',
                         'Lug', 'Ago', 'Set', 'Ott', 'Nov', 'Dic']
            # conteggio fatture per (anno, mese)
            counts = {}
            for d in date_fatture:
                chiave = (d.year, d.month)
                counts[chiave] = counts.get(chiave, 0) + 1

            # timeline continua dal primo all'ultimo mese (inclusi i mesi a zero)
            primo, ultimo = date_fatture[0], date_fatture[-1]
            anno_cur, mese_cur = primo.year, primo.month
            while (anno_cur, mese_cur) <= (ultimo.year, ultimo.month):
                fatture_per_mese_labels.append(f"{mesi_nomi[mese_cur - 1]} {anno_cur}")
                fatture_per_mese_counts.append(counts.get((anno_cur, mese_cur), 0))
                mese_cur += 1
                if mese_cur > 12:
                    mese_cur = 1
                    anno_cur += 1

            # gap in mesi tra mesi "attivi" consecutivi (con almeno una fattura)
            mesi_attivi = sorted(counts.keys())
            gap_mesi = [(mesi_attivi[i][0] - mesi_attivi[i - 1][0]) * 12
                        + (mesi_attivi[i][1] - mesi_attivi[i - 1][1])
                        for i in range(1, len(mesi_attivi))]
            if gap_mesi:
                gs = sorted(gap_mesi)
                k = len(gs)
                gap_mediano = gs[k // 2] if k % 2 == 1 else (gs[k // 2 - 1] + gs[k // 2]) / 2
                gap_medio = sum(gap_mesi) / len(gap_mesi)
                max_gap = max(gap_mesi)
            else:
                gap_mediano = gap_medio = max_gap = 0
            ritmo_mesi = {
                'n_mesi_periodo': len(fatture_per_mese_labels),
                'n_mesi_attivi': len(mesi_attivi),
                'gap_medio_mesi': round(gap_medio, 1),
                'gap_mediano_mesi': round(gap_mediano, 1),
                'max_gap_mesi': max_gap,
            }

        return render_template(
            'resoconto_annuale.html',
            anno=anno_selezionato,
            anni_disponibili=anni_disponibili,
            totale_fatturate=totale_fatturate,
            totale_da_fatturare=totale_da_fatturare,
            totale_pianificate=totale_pianificate,
            totale_cancellate=totale_cancellate,
            totale_complessivo=totale_complessivo,
            percentuale_fatturate=percentuale_fatturate,
            percentuale_da_fatturare=percentuale_da_fatturare,
            percentuale_pianificate=percentuale_pianificate,
            percentuale_cancellate=percentuale_cancellate,
            mesi=json.dumps(mesi),
            dati_mensili_fatturate=json.dumps(dati_mensili_fatturate),
            dati_mensili_da_fatturare=json.dumps(dati_mensili_da_fatturare),
            dati_mensili_pianificate=json.dumps(dati_mensili_pianificate),
            dati_mensili_cancellate=json.dumps(dati_mensili_cancellate),
            clienti=json.dumps(clienti),
            dati_clienti_fatturate=json.dumps(dati_clienti_fatturate),
            dati_clienti_da_fatturare=json.dumps(dati_clienti_da_fatturare),
            dati_clienti_pianificate=json.dumps(dati_clienti_pianificate),
            dati_clienti_cancellate=json.dumps(dati_clienti_cancellate),
            anni_grafico=json.dumps(anni_grafico),
            dati_fatturate_per_anno=json.dumps(dati_fatturate_per_anno),
            dati_da_fatturare_per_anno=json.dumps(dati_da_fatturare_per_anno),
            dati_pianificate_per_anno=json.dumps(dati_pianificate_per_anno),
            dati_cancellate_per_anno=json.dumps(dati_cancellate_per_anno),
            dati_totali_per_anno=json.dumps(dati_totali_per_anno),
            n_completate_per_anno=json.dumps(n_completate_per_anno),
            n_fatturate_per_anno=json.dumps(n_fatturate_per_anno),
            # Nuovi dati per fatture emesse
            fatture_emesse=fatture_emesse,
            totale_fatture_emesse=totale_fatture_emesse,
            fatture_totali=fatture_totali,
            fatture_parziali=fatture_parziali,
            totale_fatture_totali=totale_fatture_totali,
            totale_fatture_parziali=totale_fatture_parziali,
            dati_mensili_fatture_emesse=json.dumps(dati_mensili_fatture_emesse),
            cadenza_fatturazione=cadenza_fatturazione,
            ritmo_mesi=ritmo_mesi,
            fatture_per_mese_labels=json.dumps(fatture_per_mese_labels),
            fatture_per_mese_counts=json.dumps(fatture_per_mese_counts)
        )
