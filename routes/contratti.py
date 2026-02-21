import os
import base64
from io import BytesIO
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from datetime import datetime
from werkzeug.utils import secure_filename
import PyPDF2
from pdf2image import convert_from_path
from PIL import Image
from anthropic import Anthropic
from db_utils import db_connection, get_placeholder
from utils.security import sanitize_input

contratti_bp = Blueprint('contratti', __name__)

# Configurazione upload
UPLOAD_FOLDER = 'uploads/contratti'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Crea la cartella upload se non esiste
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(file_path):
    """Estrae il testo da un PDF"""
    try:
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        print(f"Errore nell'estrazione del testo PDF: {e}")
        return ""

def pdf_to_base64_images(file_path, max_pages=15):
    """Converte PDF in immagini base64 per Claude Vision"""
    try:
        # Converti PDF in immagini (max 15 pagine: info + calendario completo)
        images = convert_from_path(file_path, first_page=1, last_page=max_pages)
        
        base64_images = []
        for img in images:
            # Ridimensiona se troppo grande
            max_size = 1568
            if img.width > max_size or img.height > max_size:
                ratio = min(max_size / img.width, max_size / img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Converti in base64
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            base64_images.append(img_str)
        
        return base64_images
    except Exception as e:
        print(f"Errore nella conversione PDF in immagini: {e}")
        return None

def analyze_contract_with_claude(text, pdf_path=None):
    """Analizza il contratto con Claude AI (testo o immagini)
    
    Returns:
        tuple: (analysis, extracted_text, error)
    """
    try:
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            return None, None, "Chiave API Anthropic non configurata"
        
        client = Anthropic(api_key=api_key)
        
        # Se il testo è vuoto o quasi, usa la visione di Claude
        if (not text or len(text) < 50) and pdf_path:
            print("📸 PDF scansionato rilevato, uso visione Claude...")
            images = pdf_to_base64_images(pdf_path)
            
            if not images:
                return None, None, "Impossibile convertire il PDF in immagini"
            
            # Unica chiamata ottimizzata
            print("🤖 Analisi e estrazione con Claude...")
            content = [{
                "type": "text",
                "text": """Sei un assistente esperto nell'estrazione di dati da contratti di formazione.

ANALIZZA QUESTO CONTRATTO ED ESTRAI:

## 1. INFORMAZIONI PRINCIPALI
- Numero contratto / Codice corso
- Cliente/studente
- Periodo: data inizio e data fine
- Ore totali previste
- Compenso (orario o totale)
- Materia/argomento del corso
- Luogo di svolgimento

## 2. CALENDARIO COMPLETO DELLE LEZIONI (FONDAMENTALE!)

CERCA ATTENTAMENTE il "CALENDARIO" o "ALLEGATO A" nel documento.
Per OGNI lezione del calendario, estrai:
- Data della lezione (giorno/mese/anno)
- Ora inizio e ora fine
- Durata in ore
- Eventuali note

Trascrivi il calendario in formato tabella chiaro come:
```
DATA | INIZIO | FINE | ORE | NOTE
13/02/2026 | 09:00 | 13:00 | 4 | 
...
```

## 3. ALTRE INFORMAZIONI
- Clausole importanti
- Modalità di pagamento
- Referenti/contatti

**IMPORTANTE**: Non saltare nessuna pagina del calendario anche se è lungo.
Trascrivi TUTTE le date presenti.

Rispondi in italiano in modo strutturato e completo."""
            }]
            
            for img_base64 in images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": img_base64
                    }
                })
            
            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=6000,
                messages=[{
                    "role": "user",
                    "content": content
                }]
            )
            
            response = message.content[0].text
            
            return response, response, None
        else:
            # Usa il testo estratto
            message = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": f"""Analizza questo contratto e estrai le seguenti informazioni chiave in formato strutturato:
- Numero contratto (se presente)
- Nome cliente/studente
- Date (inizio, fine, durata)
- Compenso (orario o totale)
- Materie/argomenti
- Numero ore previste
- Altre informazioni rilevanti

Ecco il testo del contratto:

{text}

Rispondi in italiano in modo chiaro e strutturato."""
                }]
            )
            
            return message.content[0].text, text, None
    except Exception as e:
        return None, None, f"Errore nell'analisi con Claude: {str(e)}"

def chat_with_contract(contract_text, user_question, conversation_history=None):
    """Chat interattiva con il contratto usando Claude"""
    try:
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            return None, "Chiave API Anthropic non configurata"
        
        client = Anthropic(api_key=api_key)
        
        # Costruisci i messaggi per la conversazione
        messages = []
        
        # Aggiungi la storia della conversazione se presente
        if conversation_history:
            messages.extend(conversation_history)
        
        # Aggiungi la domanda dell'utente
        messages.append({
            "role": "user",
            "content": f"""Sei un assistente che aiuta a rispondere a domande su un contratto.
            
Ecco il testo completo del contratto:

{contract_text}

Domanda dell'utente: {user_question}

Rispondi in modo preciso basandoti esclusivamente sul contenuto del contratto. Se l'informazione non è presente nel contratto, dillo chiaramente. Rispondi in italiano."""
        })
        
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=messages
        )
        
        return message.content[0].text, None
    except Exception as e:
        return None, f"Errore nella chat con Claude: {str(e)}"


@contratti_bp.route("/contratti")
@login_required
def lista_contratti():
    """Lista di tutti i contratti caricati"""
    with db_connection() as conn:
        cursor = conn.cursor()
        placeholder = get_placeholder()
        
        cursor.execute("""
            SELECT c.*, co.nome as nome_corso
            FROM contratti c
            LEFT JOIN corsi co ON c.id_corso = co.id_corso
            ORDER BY c.data_upload DESC
        """)
        contratti = cursor.fetchall()
    
    # Estrai lista clienti univoci (escludi None/vuoto)
    clienti = sorted(set(
        c['cliente'] for c in contratti if c['cliente']
    ))
    
    return render_template("contratti.html", contratti=contratti, clienti=clienti, current_tab='altro')


@contratti_bp.route("/contratti/nuovo")
@login_required
def nuovo_contratto():
    """Form per caricare un nuovo contratto"""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM corsi ORDER BY nome")
        corsi = cursor.fetchall()
    
    return render_template("upload_contratto.html", corsi=corsi, current_tab='altro')


@contratti_bp.route("/contratti/upload", methods=["POST"])
@login_required
def upload_contratto():
    """Upload e analisi di un contratto PDF"""
    try:
        # Validazione file
        if 'file' not in request.files:
            flash("❌ Nessun file selezionato", "danger")
            return redirect(url_for('contratti.nuovo_contratto'))
        
        file = request.files['file']
        
        if file.filename == '':
            flash("❌ Nessun file selezionato", "danger")
            return redirect(url_for('contratti.nuovo_contratto'))
        
        if not allowed_file(file.filename):
            flash("❌ Formato file non valido. Solo PDF permessi.", "danger")
            return redirect(url_for('contratti.nuovo_contratto'))
        
        # Salva il file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{filename}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        # Estrai il testo dal PDF
        flash("⏳ Estrazione testo dal PDF...", "info")
        text = extract_text_from_pdf(file_path)
        
        # Analizza con Claude (usa visione se testo vuoto o scansione)
        flash("🤖 Analisi del contratto con Claude AI...", "info")
        analysis, extracted_text, error = analyze_contract_with_claude(text, pdf_path=file_path)
        
        if error:
            flash(f"⚠️ {error}", "warning")
            analysis = "Analisi non disponibile"
            extracted_text = text  # Fallback al testo originale
        
        # Usa il testo estratto da Claude se disponibile, altrimenti usa quello di PyPDF2
        final_text = extracted_text if extracted_text else text
        
        # Dati dal form
        numero_contratto = sanitize_input(request.form.get('numero_contratto', ''))
        cliente = sanitize_input(request.form.get('cliente', ''))
        id_corso = request.form.get('id_corso', None)
        if id_corso == '':
            id_corso = None
        
        # Salva nel database con il testo estratto da Claude
        with db_connection() as conn:
            cursor = conn.cursor()
            placeholder = get_placeholder()
            
            cursor.execute(f"""
                INSERT INTO contratti (numero_contratto, nome_file, file_path, data_upload, cliente, contenuto_estratto, id_corso)
                VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            """, (numero_contratto, file.filename, file_path, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                  cliente, final_text, id_corso))
            conn.commit()
            
            # Ottieni l'ID del contratto appena inserito
            if get_placeholder() == "%s":  # PostgreSQL
                cursor.execute("SELECT lastval()")
            else:  # SQLite
                cursor.execute("SELECT last_insert_rowid()")
            contratto_id = cursor.fetchone()[0]
        
        flash("✅ Contratto caricato e analizzato con successo!", "success")
        return redirect(url_for('contratti.dettaglio_contratto', contratto_id=contratto_id))
    
    except Exception as e:
        flash(f"❌ Errore durante l'upload: {str(e)}", "danger")
        return redirect(url_for('contratti.nuovo_contratto'))


@contratti_bp.route("/contratti/<int:contratto_id>")
@login_required
def dettaglio_contratto(contratto_id):
    """Visualizza dettagli contratto con chat AI"""
    with db_connection() as conn:
        cursor = conn.cursor()
        placeholder = get_placeholder()
        
        cursor.execute(f"""
            SELECT c.*, co.nome as nome_corso
            FROM contratti c
            LEFT JOIN corsi co ON c.id_corso = co.id_corso
            WHERE c.id = {placeholder}
        """, (contratto_id,))
        contratto = cursor.fetchone()
        
        if not contratto:
            flash("❌ Contratto non trovato", "danger")
            return redirect(url_for('contratti.lista_contratti'))
        
        # Ottieni analisi iniziale con Claude (usa visione se il contenuto è vuoto)
        analysis, extracted_text, error = analyze_contract_with_claude(
            contratto['contenuto_estratto'], 
            pdf_path=contratto['file_path']
        )
        if error:
            analysis = "Analisi non disponibile. Usa la chat per fare domande."
        
        # Se Claude ha estratto testo e il DB è vuoto, aggiorna il database
        if extracted_text and (not contratto['contenuto_estratto'] or len(contratto['contenuto_estratto']) < 50):
            cursor.execute(f"""
                UPDATE contratti 
                SET contenuto_estratto = {placeholder}
                WHERE id = {placeholder}
            """, (extracted_text, contratto_id))
            conn.commit()
            print(f"✅ Testo estratto salvato nel database per contratto {contratto_id}")
        
        # Ottieni tutti i corsi per collegamento
        cursor.execute("SELECT * FROM corsi ORDER BY nome")
        corsi = cursor.fetchall()
    
    return render_template("dettaglio_contratto.html", 
                          contratto=contratto, 
                          analysis=analysis,
                          corsi=corsi,
                          current_tab='altro')


@contratti_bp.route("/contratti/<int:contratto_id>/chat", methods=["POST"])
@login_required
def chat_contratto(contratto_id):
    """API per chat con il contratto"""
    try:
        data = request.json
        question = sanitize_input(data.get('question', ''))
        
        if not question:
            return jsonify({"success": False, "error": "Domanda non fornita"}), 400
        
        # Recupera il contratto
        with db_connection() as conn:
            cursor = conn.cursor()
            placeholder = get_placeholder()
            
            cursor.execute(f"""
                SELECT contenuto_estratto 
                FROM contratti 
                WHERE id = {placeholder}
            """, (contratto_id,))
            contratto = cursor.fetchone()
        
        if not contratto:
            return jsonify({"success": False, "error": "Contratto non trovato"}), 404
        
        # Chat con Claude
        answer, error = chat_with_contract(contratto['contenuto_estratto'], question)
        
        if error:
            return jsonify({"success": False, "error": error}), 500
        
        return jsonify({
            "success": True,
            "question": question,
            "answer": answer
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@contratti_bp.route("/contratti/<int:contratto_id>/download")
@login_required
def download_contratto(contratto_id):
    """Scarica il PDF del contratto"""
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            placeholder = get_placeholder()
            
            cursor.execute(f"SELECT file_path, nome_file FROM contratti WHERE id = {placeholder}", (contratto_id,))
            contratto = cursor.fetchone()
            
            if not contratto:
                flash("❌ Contratto non trovato", "danger")
                return redirect(url_for('contratti.lista_contratti'))
            
            from flask import send_file
            return send_file(contratto['file_path'], 
                           as_attachment=True, 
                           download_name=contratto['nome_file'])
    
    except Exception as e:
        flash(f"❌ Errore durante il download: {str(e)}", "danger")
        return redirect(url_for('contratti.dettaglio_contratto', contratto_id=contratto_id))


@contratti_bp.route("/contratti/<int:contratto_id>/elimina", methods=["POST"])
@login_required
def elimina_contratto(contratto_id):
    """Elimina un contratto"""
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            placeholder = get_placeholder()
            
            # Recupera il path del file
            cursor.execute(f"SELECT file_path FROM contratti WHERE id = {placeholder}", (contratto_id,))
            contratto = cursor.fetchone()
            
            if not contratto:
                flash("❌ Contratto non trovato", "danger")
                return redirect(url_for('contratti.lista_contratti'))
            
            # Elimina il file fisico
            if os.path.exists(contratto['file_path']):
                os.remove(contratto['file_path'])
            
            # Elimina dal database
            cursor.execute(f"DELETE FROM contratti WHERE id = {placeholder}", (contratto_id,))
            conn.commit()
        
        flash("✅ Contratto eliminato con successo", "success")
        return redirect(url_for('contratti.lista_contratti'))
    
    except Exception as e:
        flash(f"❌ Errore durante l'eliminazione: {str(e)}", "danger")
        return redirect(url_for('contratti.lista_contratti'))


@contratti_bp.route("/contratti/<int:contratto_id>/collega-corso", methods=["POST"])
@login_required
def collega_corso(contratto_id):
    """Collega un contratto a un corso"""
    try:
        id_corso = request.form.get('id_corso')
        
        with db_connection() as conn:
            cursor = conn.cursor()
            placeholder = get_placeholder()
            
            cursor.execute(f"""
                UPDATE contratti 
                SET id_corso = {placeholder}
                WHERE id = {placeholder}
            """, (id_corso if id_corso else None, contratto_id))
            conn.commit()
        
        flash("✅ Corso collegato con successo", "success")
        return redirect(url_for('contratti.dettaglio_contratto', contratto_id=contratto_id))
    
    except Exception as e:
        flash(f"❌ Errore durante il collegamento: {str(e)}", "danger")
        return redirect(url_for('contratti.dettaglio_contratto', contratto_id=contratto_id))


@contratti_bp.route("/contratti/<int:contratto_id>/verifica-conformita")
@login_required
def verifica_conformita(contratto_id):
    """Verifica conformità tra calendario contratto e lezioni in database"""
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            placeholder = get_placeholder()
            
            # Recupera contratto
            cursor.execute(f"""
                SELECT c.*, co.nome as nome_corso
                FROM contratti c
                LEFT JOIN corsi co ON c.id_corso = co.id_corso
                WHERE c.id = {placeholder}
            """, (contratto_id,))
            contratto = cursor.fetchone()
            
            if not contratto:
                flash("❌ Contratto non trovato", "danger")
                return redirect(url_for('contratti.lista_contratti'))
            
            if not contratto['id_corso']:
                flash("⚠️ Nessun corso collegato al contratto. Collega prima un corso per verificare la conformità.", "warning")
                return redirect(url_for('contratti.dettaglio_contratto', contratto_id=contratto_id))
            
            # Parse calendario dal contenuto estratto
            lezioni_contratto = parse_calendario_da_contratto(contratto['contenuto_estratto'])
            
            # Recupera lezioni dal database per questo corso
            cursor.execute(f"""
                SELECT id, data, ora_inizio, ora_fine
                FROM lezioni
                WHERE id_corso = {placeholder}
                ORDER BY data, ora_inizio
            """, (contratto['id_corso'],))
            lezioni_db = cursor.fetchall()
            
            # Confronta e categorizza
            risultato = confronta_lezioni(lezioni_contratto, lezioni_db)
        
        return render_template("verifica_conformita.html",
                             contratto=contratto,
                             risultato=risultato,
                             current_tab='altro')
    
    except Exception as e:
        flash(f"❌ Errore durante la verifica: {str(e)}", "danger")
        return redirect(url_for('contratti.dettaglio_contratto', contratto_id=contratto_id))


def parse_calendario_da_contratto(contenuto_estratto):
    """Estrae le lezioni dal calendario nel contenuto estratto"""
    import re
    from datetime import datetime as dt
    
    lezioni = []
    
    if not contenuto_estratto:
        return lezioni
    
    # Pattern per trovare date in vari formati
    # Pattern 1: DATA | ORA_INIZIO - ORA_FINE (contratti tipo 8195)
    pattern_trattino = r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})\s*\|\s*(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})'
    # Pattern 2: DATA | ORA_INIZIO | ORA_FINE (contratti tipo 2684)
    pattern_pipe = r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})\s*\|\s*(\d{1,2}:\d{2})\s*\|\s*(\d{1,2}:\d{2})'
    
    # Prova prima con pattern trattino
    matches = re.findall(pattern_trattino, contenuto_estratto)
    
    # Se non trova nulla, prova con pattern pipe
    if not matches:
        matches = re.findall(pattern_pipe, contenuto_estratto)
    
    for match in matches:
        data_str, ora_inizio, ora_fine = match
        
        # Normalizza data in formato YYYY-MM-DD
        try:
            if '/' in data_str:
                parti = data_str.split('/')
            else:
                parti = data_str.split('-')
            
            if len(parti) == 3:
                giorno, mese, anno = parti
                data_norm = f"{anno}-{mese.zfill(2)}-{giorno.zfill(2)}"
                
                lezioni.append({
                    'data': data_norm,
                    'ora_inizio': ora_inizio,
                    'ora_fine': ora_fine
                })
        except:
            continue
    
    # Se non trova pattern tabella, cerca date e orari nel testo
    if not lezioni:
        # Pattern alternativo: cerca "13/02/2026 09:00-13:00" o simili
        pattern_alt = r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})\s+(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})'
        matches_alt = re.findall(pattern_alt, contenuto_estratto)
        
        for match in matches_alt:
            data_str, ora_inizio, ora_fine = match
            try:
                if '/' in data_str:
                    parti = data_str.split('/')
                else:
                    parti = data_str.split('-')
                
                if len(parti) == 3:
                    giorno, mese, anno = parti
                    data_norm = f"{anno}-{mese.zfill(2)}-{giorno.zfill(2)}"
                    
                    lezioni.append({
                        'data': data_norm,
                        'ora_inizio': ora_inizio,
                        'ora_fine': ora_fine
                    })
            except:
                continue
    
    return lezioni


def confronta_lezioni(lezioni_contratto, lezioni_db):
    """Confronta lezioni del contratto con quelle nel database"""
    conformi = []
    da_aggiungere = []
    extra_db = []
    differenze_orari = []
    
    # Converti lezioni_db in lista di dict per facilità
    lezioni_db_list = []
    for lez in lezioni_db:
        lezioni_db_list.append({
            'id': lez['id'],
            'data': lez['data'],
            'ora_inizio': lez['ora_inizio'],
            'ora_fine': lez['ora_fine']
        })
    
    # Controlla ogni lezione del contratto
    for lez_contratto in lezioni_contratto:
        trovata = False
        differenza = False
        
        for lez_db in lezioni_db_list:
            # Stesso giorno?
            if lez_contratto['data'] == lez_db['data']:
                # Stesso orario?
                if (lez_contratto['ora_inizio'] == lez_db['ora_inizio'] and 
                    lez_contratto['ora_fine'] == lez_db['ora_fine']):
                    conformi.append({
                        'contratto': lez_contratto,
                        'db': lez_db,
                        'suddiviso': False
                    })
                    lez_db['matched'] = True
                    trovata = True
                    break
                else:
                    # Stessa data ma orari diversi
                    differenze_orari.append({
                        'contratto': lez_contratto,
                        'db': lez_db
                    })
                    lez_db['matched'] = True
                    differenza = True
                    break
        
        # Se non trovata e non differenza, va aggiunta
        if not trovata and not differenza:
            da_aggiungere.append(lez_contratto)
    
    # NUOVA LOGICA: Riconosci lezioni consecutive che combinate corrispondono a una lezione unica
    conformi, differenze_orari = riconosci_lezioni_suddivise(
        lezioni_contratto, lezioni_db_list, conformi, differenze_orari
    )
    
    # Lezioni nel DB ma non nel contratto
    for lez_db in lezioni_db_list:
        if not lez_db.get('matched'):
            extra_db.append(lez_db)
    
    return {
        'conformi': conformi,
        'da_aggiungere': da_aggiungere,
        'extra_db': extra_db,
        'differenze_orari': differenze_orari,
        'totale_contratto': len(lezioni_contratto),
        'totale_db': len(lezioni_db_list)
    }


def riconosci_lezioni_suddivise(lezioni_contratto, lezioni_db_list, conformi, differenze_orari):
    """Riconosce quando più lezioni consecutive del contratto corrispondono a 1 lezione nel DB"""
    
    # Raggruppa lezioni contratto per data
    lezioni_per_data = {}
    for lez in lezioni_contratto:
        data = lez['data']
        if data not in lezioni_per_data:
            lezioni_per_data[data] = []
        lezioni_per_data[data].append(lez)
    
    nuove_conformi = list(conformi)
    nuove_differenze = []
    
    # Per ogni data, controlla se ci sono multiple lezioni che possono essere combinate
    for data, lezioni_data in lezioni_per_data.items():
        if len(lezioni_data) <= 1:
            continue
            
        # Ordina per ora inizio
        lezioni_data_ordinate = sorted(lezioni_data, key=lambda x: x['ora_inizio'])
        
        # Trova lezioni consecutive (dove fine di una = inizio della successiva)
        gruppi_consecutivi = []
        gruppo_corrente = [lezioni_data_ordinate[0]]
        
        for i in range(1, len(lezioni_data_ordinate)):
            lez_prev = gruppo_corrente[-1]
            lez_curr = lezioni_data_ordinate[i]
            
            # Consecutive?
            if lez_prev['ora_fine'] == lez_curr['ora_inizio']:
                gruppo_corrente.append(lez_curr)
            else:
                if len(gruppo_corrente) > 1:
                    gruppi_consecutivi.append(gruppo_corrente)
                gruppo_corrente = [lez_curr]
        
        # Aggiungi ultimo gruppo se consecutivo
        if len(gruppo_corrente) > 1:
            gruppi_consecutivi.append(gruppo_corrente)
        
        # Per ogni gruppo consecutivo, verifica se corrisponde a una lezione DB
        for gruppo in gruppi_consecutivi:
            ora_inizio_combinata = gruppo[0]['ora_inizio']
            ora_fine_combinata = gruppo[-1]['ora_fine']
            
            # Cerca lezione DB con questi orari
            for lez_db in lezioni_db_list:
                if (lez_db['data'] == data and 
                    lez_db['ora_inizio'] == ora_inizio_combinata and 
                    lez_db['ora_fine'] == ora_fine_combinata):
                    
                    # MATCH! Rimuovi dalle differenze e aggiungi a conformi
                    # Rimuovi le singole lezioni del gruppo dalle differenze
                    nuove_differenze_temp = []
                    for diff in differenze_orari:
                        dovrebbe_rimuovere = False
                        for lez_gruppo in gruppo:
                            if (diff['contratto']['data'] == lez_gruppo['data'] and
                                diff['contratto']['ora_inizio'] == lez_gruppo['ora_inizio'] and
                                diff['contratto']['ora_fine'] == lez_gruppo['ora_fine']):
                                dovrebbe_rimuovere = True
                                break
                        
                        if not dovrebbe_rimuovere:
                            nuove_differenze_temp.append(diff)
                    
                    differenze_orari = nuove_differenze_temp
                    
                    # Aggiungi a conformi con flag suddiviso
                    nuove_conformi.append({
                        'contratto': {
                            'data': data,
                            'ora_inizio': ora_inizio_combinata,
                            'ora_fine': ora_fine_combinata
                        },
                        'contratto_dettaglio': gruppo,  # Lezioni separate
                        'db': lez_db,
                        'suddiviso': True
                    })
                    
                    lez_db['matched'] = True
                    break
    
    # Aggiungi le differenze non rimosse
    for diff in differenze_orari:
        if diff not in nuove_differenze:
            nuove_differenze.append(diff)
    
    return nuove_conformi, nuove_differenze
