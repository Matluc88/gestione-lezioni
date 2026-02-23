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

def pdf_to_base64_images(file_path, max_pages=20):
    """Converte PDF in immagini base64 per Claude Vision.
    Usa 300 DPI per OCR preciso e JPEG (qualità 92) per ridurre RAM e payload.
    """
    import gc
    try:
        images = convert_from_path(file_path, first_page=1, last_page=max_pages, dpi=300)

        base64_images = []
        for img in images:
            # Ridimensiona se troppo grande (1568px è il limite consigliato da Anthropic)
            max_size = 1568
            if img.width > max_size or img.height > max_size:
                ratio = min(max_size / img.width, max_size / img.height)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # Converti in JPEG (60-70% meno RAM rispetto a PNG, qualità ottima per OCR)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            buffered = BytesIO()
            img.save(buffered, format="JPEG", quality=92, optimize=True)
            img_str = base64.b64encode(buffered.getvalue()).decode()
            base64_images.append(img_str)

            # Libera subito la memoria dell'immagine
            img.close()
            buffered.close()

        # Pulizia esplicita della lista immagini originali
        del images
        gc.collect()

        return base64_images
    except Exception as e:
        print(f"Errore nella conversione PDF in immagini: {e}")
        gc.collect()
        return None

# ----- Prompt unificato per l'analisi dei contratti -----
_PROMPT_ANALISI_CONTRATTO = """Sei un assistente esperto nell'estrazione di dati da contratti di formazione italiani.

ANALIZZA QUESTO CONTRATTO ED ESTRAI:

## 1. INFORMAZIONI PRINCIPALI
- Numero contratto / Codice corso
- Cliente/studente
- Periodo: data inizio e data fine
- Ore totali previste (monte ore)
- Compenso (orario o totale)
- Materia/argomento del corso
- Luogo di svolgimento

## 2. CALENDARIO COMPLETO DELLE LEZIONI (PRIORITÀ MASSIMA!)

CERCA IN TUTTO IL DOCUMENTO sezioni chiamate "CALENDARIO", "ALLEGATO A", "PROGRAMMA", "PIANO DIDATTICO" o simili.

Per OGNI lezione/giornata trovata, trascrivila in questo formato ESATTO:
```
DATA | INIZIO | FINE | ORE | NOTE
13/02/2026 | 09:00 | 13:00 | 4 |
14/02/2026 | 14:00 | 18:00 | 4 |
```

REGOLE IMPORTANTI:
- Usa SEMPRE il formato DD/MM/YYYY per le date
- Usa SEMPRE il formato HH:MM per gli orari (es. 09:00, non 9:00)
- NON saltare nessuna riga del calendario
- Se il calendario è su più pagine, trascrivi TUTTE le pagine
- Se una data ha sessioni mattino + pomeriggio, trascrivile come righe separate

## 3. RIEPILOGO
- Totale lezioni nel calendario: N
- Totale ore dal calendario: N

## 4. ALTRE INFORMAZIONI
- Clausole importanti
- Modalità di pagamento
- Referenti/contatti

Rispondi in italiano in modo strutturato e completo."""


def _testo_contiene_date(text):
    """Verifica se il testo PyPDF2 contiene almeno 2 date italiane ben formate.
    Se sì, il PDF è testuale e leggibile. Se no, serve Vision.
    """
    import re
    if not text or len(text) < 100:
        return False
    pattern = r'\d{1,2}[/\-]\d{1,2}[/\-]\d{4}'
    matches = re.findall(pattern, text)
    return len(matches) >= 2


def analyze_contract_with_claude(text, pdf_path=None, force_vision=False):
    """Analizza il contratto con Claude AI.

    Strategia:
    - Se pdf_path disponibile E (force_vision OPPURE testo non contiene date):
        → usa Vision (immagini PDF a 300 DPI) + eventuale testo come contesto
    - Altrimenti:
        → usa solo testo con prompt unificato e max_tokens=4096

    Returns:
        tuple: (analysis, extracted_text, error)
    """
    try:
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            return None, None, "Chiave API Anthropic non configurata"

        client = Anthropic(api_key=api_key)

        # Decide se usare Vision
        usar_vision = pdf_path and (force_vision or not _testo_contiene_date(text))

        if usar_vision:
            print("📸 Uso Vision Claude (300 DPI) per OCR potenziato...")
            images = pdf_to_base64_images(pdf_path)

            if not images:
                print("⚠️ Conversione PDF→immagini fallita, fallback al testo")
                usar_vision = False
            else:
                prompt_text = _PROMPT_ANALISI_CONTRATTO

                # Aggiungi il testo PyPDF2 come contesto se disponibile ma incompleto
                if text and 50 < len(text) < 5000:
                    prompt_text += (
                        f"\n\nNOTA SISTEMA: Il layer testuale del PDF contiene il seguente testo "
                        f"(potrebbe essere parziale o corrotto — usa le immagini per verificare):\n"
                        f"---\n{text[:3000]}\n---"
                    )

                content = [{"type": "text", "text": prompt_text}]
                for img_base64 in images:
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": img_base64
                        }
                    })

                message = client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=6000,
                    messages=[{"role": "user", "content": content}]
                )
                response = message.content[0].text
                return response, response, None

        # Percorso testuale (PDF nativo con testo leggibile)
        if not text:
            return None, None, "Nessun testo disponibile e nessun PDF fornito"

        print("📝 Analisi testuale con Claude...")
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": f"{_PROMPT_ANALISI_CONTRATTO}\n\nTESTO DEL CONTRATTO:\n\n{text}"
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

        cursor.execute("""
            SELECT c.*, co.nome as nome_corso
            FROM contratti c
            LEFT JOIN corsi co ON c.id_corso = co.id_corso
            ORDER BY c.data_upload DESC
        """)
        contratti = cursor.fetchall()

        # Mappa nome_corso → lista numeri fattura (query unica)
        cursor.execute("SELECT id_corso, numero_fattura FROM fatture")
        fatture_per_corso = {}
        for f in cursor.fetchall():
            nome = f['id_corso']
            if nome:
                if nome not in fatture_per_corso:
                    fatture_per_corso[nome] = []
                fatture_per_corso[nome].append(f['numero_fattura'])

    # Estrai lista clienti univoci (escludi None/vuoto)
    clienti = sorted(set(
        c['cliente'] for c in contratti if c['cliente']
    ))

    return render_template("contratti.html", contratti=contratti, clienti=clienti,
                           fatture_per_corso=fatture_per_corso, current_tab='altro')


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

        # Trova le fatture collegate tramite il nome del corso
        fatture_collegate = []
        if contratto['nome_corso']:
            cursor.execute(f"""
                SELECT numero_fattura, importo, data_fattura, tipo_fatturazione
                FROM fatture
                WHERE id_corso = {placeholder}
                ORDER BY data_fattura
            """, (contratto['nome_corso'],))
            fatture_collegate = cursor.fetchall()

    return render_template("dettaglio_contratto.html",
                          contratto=contratto,
                          analysis=analysis,
                          corsi=corsi,
                          fatture_collegate=fatture_collegate,
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


@contratti_bp.route("/contratti/elimina-multipli", methods=["POST"])
@login_required
def elimina_contratti_multipli():
    """Elimina più contratti selezionati in batch"""
    try:
        ids = request.form.getlist("contratti_ids[]")
        if not ids:
            return jsonify({"success": False, "error": "Nessun contratto selezionato"}), 400

        eliminati = 0
        with db_connection() as conn:
            cursor = conn.cursor()
            placeholder = get_placeholder()

            for contratto_id in ids:
                try:
                    contratto_id_int = int(contratto_id)
                    cursor.execute(f"SELECT file_path FROM contratti WHERE id = {placeholder}", (contratto_id_int,))
                    contratto = cursor.fetchone()
                    if contratto:
                        if contratto['file_path'] and os.path.exists(contratto['file_path']):
                            os.remove(contratto['file_path'])
                        cursor.execute(f"DELETE FROM contratti WHERE id = {placeholder}", (contratto_id_int,))
                        eliminati += 1
                except Exception as e:
                    print(f"Errore eliminazione contratto {contratto_id}: {e}")
                    continue

            conn.commit()

        return jsonify({"success": True, "eliminati": eliminati})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


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

            # --- Carica lezioni rinunciate per questo contratto ---
            _ensure_lezioni_rinunciate_table(cursor)
            cursor.execute(f"""
                SELECT data, ora_inizio, ora_fine FROM lezioni_rinunciate
                WHERE id_contratto = {placeholder}
            """, (contratto_id,))
            rinunciate_set = {
                (r['data'], r['ora_inizio'], r['ora_fine'])
                for r in cursor.fetchall()
            }

            # Separa da_aggiungere in "da aggiungere" e "rinunciate"
            da_aggiungere_effettive = []
            lezioni_rinunciate_list = []
            for lez in risultato['da_aggiungere']:
                key = (lez['data'], lez['ora_inizio'], lez['ora_fine'])
                if key in rinunciate_set:
                    lezioni_rinunciate_list.append(lez)
                else:
                    da_aggiungere_effettive.append(lez)
            risultato['da_aggiungere'] = da_aggiungere_effettive
            risultato['rinunciate'] = lezioni_rinunciate_list

            # --- Fallback ore totali quando nessun calendario trovato ---
            ore_contratto_estratte = None
            ore_db_totali = None
            if risultato['totale_contratto'] == 0:
                ore_contratto_estratte = estrai_ore_da_contratto(contratto['contenuto_estratto'])

                cursor.execute(f"""
                    SELECT SUM(calcola_ore(ora_inizio, ora_fine))
                    FROM lezioni
                    WHERE id_corso = {placeholder}
                """, (contratto['id_corso'],))
                row = cursor.fetchone()
                ore_db_totali = round(float(row[0]), 2) if row and row[0] is not None else 0.0

            # Fatture collegate (via nome corso)
            fatture_collegate = []
            if contratto['nome_corso']:
                cursor.execute(f"""
                    SELECT numero_fattura, importo, data_fattura, tipo_fatturazione
                    FROM fatture
                    WHERE id_corso = {placeholder}
                    ORDER BY data_fattura
                """, (contratto['nome_corso'],))
                fatture_collegate = cursor.fetchall()

        return render_template("verifica_conformita.html",
                             contratto=contratto,
                             risultato=risultato,
                             ore_contratto_estratte=ore_contratto_estratte,
                             ore_db_totali=ore_db_totali,
                             fatture_collegate=fatture_collegate,
                             current_tab='altro')
    
    except Exception as e:
        flash(f"❌ Errore durante la verifica: {str(e)}", "danger")
        return redirect(url_for('contratti.dettaglio_contratto', contratto_id=contratto_id))


def _ensure_lezioni_rinunciate_table(cursor):
    """Crea la tabella lezioni_rinunciate se non esiste (compatibile SQLite e PostgreSQL)"""
    if get_placeholder() == "%s":  # PostgreSQL
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lezioni_rinunciate (
                id SERIAL PRIMARY KEY,
                id_contratto INTEGER NOT NULL,
                data VARCHAR(10) NOT NULL,
                ora_inizio VARCHAR(5) NOT NULL,
                ora_fine VARCHAR(5) NOT NULL,
                data_rinuncia TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(id_contratto, data, ora_inizio, ora_fine)
            )
        """)
    else:  # SQLite
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lezioni_rinunciate (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_contratto INTEGER NOT NULL,
                data VARCHAR(10) NOT NULL,
                ora_inizio VARCHAR(5) NOT NULL,
                ora_fine VARCHAR(5) NOT NULL,
                data_rinuncia TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(id_contratto, data, ora_inizio, ora_fine)
            )
        """)


@contratti_bp.route("/contratti/<int:contratto_id>/segna-rinunciata", methods=["POST"])
@login_required
def segna_rinunciata(contratto_id):
    """Marca una lezione del contratto come rinunciata (foglio rinuncia)"""
    try:
        data = request.json
        data_lez = data.get('data', '').strip()
        ora_inizio = data.get('ora_inizio', '').strip()
        ora_fine = data.get('ora_fine', '').strip()

        if not data_lez or not ora_inizio or not ora_fine:
            return jsonify({"success": False, "error": "Dati mancanti"}), 400

        with db_connection() as conn:
            cursor = conn.cursor()
            placeholder = get_placeholder()
            _ensure_lezioni_rinunciate_table(cursor)

            try:
                cursor.execute(f"""
                    INSERT INTO lezioni_rinunciate (id_contratto, data, ora_inizio, ora_fine)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder})
                """, (contratto_id, data_lez, ora_inizio, ora_fine))
            except Exception:
                pass  # Già presente (UNIQUE constraint)

            conn.commit()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@contratti_bp.route("/contratti/<int:contratto_id>/rimuovi-rinuncia", methods=["POST"])
@login_required
def rimuovi_rinuncia(contratto_id):
    """Rimuove la marcatura 'rinunciata' da una lezione del contratto"""
    try:
        data = request.json
        data_lez = data.get('data', '').strip()
        ora_inizio = data.get('ora_inizio', '').strip()
        ora_fine = data.get('ora_fine', '').strip()

        if not data_lez or not ora_inizio or not ora_fine:
            return jsonify({"success": False, "error": "Dati mancanti"}), 400

        with db_connection() as conn:
            cursor = conn.cursor()
            placeholder = get_placeholder()
            _ensure_lezioni_rinunciate_table(cursor)

            cursor.execute(f"""
                DELETE FROM lezioni_rinunciate
                WHERE id_contratto = {placeholder}
                  AND data = {placeholder}
                  AND ora_inizio = {placeholder}
                  AND ora_fine = {placeholder}
            """, (contratto_id, data_lez, ora_inizio, ora_fine))
            conn.commit()

        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@contratti_bp.route("/contratti/<int:contratto_id>/rianalizza", methods=["POST"])
@login_required
def rianalizza_ocr(contratto_id):
    """Forza ri-analisi OCR potenziata con Vision Claude a 300 DPI.
    Aggiorna contenuto_estratto nel DB e restituisce il nuovo testo come JSON.
    """
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            placeholder = get_placeholder()

            cursor.execute(f"SELECT file_path FROM contratti WHERE id = {placeholder}", (contratto_id,))
            contratto = cursor.fetchone()

            if not contratto:
                return jsonify({"success": False, "error": "Contratto non trovato"}), 404

            if not contratto['file_path'] or not os.path.exists(contratto['file_path']):
                return jsonify({"success": False, "error": "File PDF non trovato sul disco"}), 404

            # Forza sempre Vision a 300 DPI
            analysis, extracted_text, error = analyze_contract_with_claude(
                "", pdf_path=contratto['file_path'], force_vision=True
            )

            if error:
                return jsonify({"success": False, "error": error}), 500

            # Aggiorna il DB con il nuovo testo estratto
            cursor.execute(f"""
                UPDATE contratti
                SET contenuto_estratto = {placeholder}
                WHERE id = {placeholder}
            """, (extracted_text, contratto_id))
            conn.commit()

        return jsonify({"success": True, "analysis": analysis})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def estrai_ore_da_contratto(testo):
    """Cerca nel testo estratto il monte ore totale previsto dal contratto.
    
    Returns:
        float or None: numero di ore trovate, None se non trovato
    """
    import re

    if not testo:
        return None

    # Lista di pattern ordinati per specificità (decrescente)
    patterns = [
        # "Ore Operatore: 116" / "Ore Operatore 116"
        r'ore\s+operatore\s*[:=]?\s*(\d+(?:[.,]\d+)?)',
        # "Monte ore: 116" / "Monte ore totale 116"
        r'monte\s+ore\s+(?:totale\s+)?[:=]?\s*(\d+(?:[.,]\d+)?)',
        # "Totale ore: 116" / "Totale ore 116h"
        r'totale\s+ore\s*[:=]?\s*(\d+(?:[.,]\d+)?)',
        # "Ore totali: 116" / "Ore totali 116"
        r'ore\s+totali\s*[:=]?\s*(\d+(?:[.,]\d+)?)',
        # "Durata: 116 ore" / "Durata 116 ore"
        r'durata\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*ore',
        # "116 ore" generico (cattura il primo numero prima di "ore")
        r'(\d+(?:[.,]\d+)?)\s*ore\b',
        # "ore: 116" generico
        r'\bore\s*[:=]\s*(\d+(?:[.,]\d+)?)',
    ]

    testo_lower = testo.lower()

    for pattern in patterns:
        match = re.search(pattern, testo_lower)
        if match:
            try:
                valore = float(match.group(1).replace(',', '.'))
                # Sanity check: ore ragionevoli tra 1 e 2000
                if 1 <= valore <= 2000:
                    return valore
            except ValueError:
                continue

    return None


# Mappa mesi italiani → numero
_MESI_IT = {
    'gennaio': '01', 'febbraio': '02', 'marzo': '03', 'aprile': '04',
    'maggio': '05', 'giugno': '06', 'luglio': '07', 'agosto': '08',
    'settembre': '09', 'ottobre': '10', 'novembre': '11', 'dicembre': '12',
    'gen': '01', 'feb': '02', 'mar': '03', 'apr': '04',
    'mag': '05', 'giu': '06', 'lug': '07', 'ago': '08',
    'set': '09', 'ott': '10', 'nov': '11', 'dic': '12',
}


def _normalizza_data(data_str):
    """Normalizza una stringa data in formato YYYY-MM-DD. Restituisce None se non riesce."""
    import re
    data_str = data_str.strip()

    # DD/MM/YYYY o DD-MM-YYYY
    m = re.match(r'^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$', data_str)
    if m:
        g, me, a = m.group(1), m.group(2), m.group(3)
        return f"{a}-{me.zfill(2)}-{g.zfill(2)}"

    # "13 febbraio 2026" / "13 feb 2026"
    m = re.match(r'^(\d{1,2})\s+([a-zà-ü]+)\s+(\d{4})$', data_str.lower())
    if m:
        g, nome_mese, a = m.group(1), m.group(2), m.group(3)
        mese_num = _MESI_IT.get(nome_mese)
        if mese_num:
            return f"{a}-{mese_num}-{g.zfill(2)}"

    return None


def _normalizza_ora(ora_str):
    """Normalizza stringa ora in HH:MM. Gestisce '9:00', '09:00', '0900'."""
    import re
    ora_str = ora_str.strip()
    # già HH:MM
    m = re.match(r'^(\d{1,2}):(\d{2})$', ora_str)
    if m:
        return f"{m.group(1).zfill(2)}:{m.group(2)}"
    # formato 0900 / 900
    m = re.match(r'^(\d{2,4})$', ora_str)
    if m:
        s = m.group(1).zfill(4)
        return f"{s[:2]}:{s[2:]}"
    return ora_str


def parse_calendario_da_contratto(contenuto_estratto):
    """Estrae le lezioni dal calendario nel contenuto estratto.
    Prova una serie di pattern in ordine di affidabilità.
    """
    import re

    lezioni = []

    if not contenuto_estratto:
        return lezioni

    # ---- Lista di pattern (data_group, ora_inizio_group, ora_fine_group) ----
    # Sep = separatore flessibile: spazio, tab, pipe, virgola, punto e virgola
    SEP = r'[\s\t]*[|,;\t][\s\t]*'

    PATTERNS = [
        # 1. DATA | HH:MM - HH:MM   (trattino o en-dash tra orari)
        r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})' + SEP + r'(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})',
        # 2. DATA | HH:MM | HH:MM
        r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})' + SEP + r'(\d{1,2}:\d{2})' + SEP + r'(\d{1,2}:\d{2})',
        # 3. DATA  HH:MM-HH:MM  (senza separatore pipe — es. "13/02/2026 09:00-13:00")
        r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})\s+(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})',
        # 4. DATA  HH:MM  HH:MM  (solo spazi, comune in export PDF tabellari)
        r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})\s+(\d{1,2}:\d{2})\s+(\d{1,2}:\d{2})',
        # 5. "13 febbraio 2026 | 09:00 - 13:00" (mesi in italiano)
        r'(\d{1,2}\s+[a-zàèéìòù]+\s+\d{4})' + SEP + r'(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})',
        # 6. Formato senza ":": "13/02/2026 | 0900 - 1300"
        r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})' + SEP + r'(\d{3,4})\s*[-–]\s*(\d{3,4})',
    ]

    seen = set()  # evita duplicati

    for pattern in PATTERNS:
        matches = re.findall(pattern, contenuto_estratto, re.IGNORECASE)
        if matches:
            for match in matches:
                data_str, ora_i_raw, ora_f_raw = match
                data_norm = _normalizza_data(data_str)
                if not data_norm:
                    continue
                ora_i = _normalizza_ora(ora_i_raw)
                ora_f = _normalizza_ora(ora_f_raw)

                key = (data_norm, ora_i, ora_f)
                if key not in seen:
                    seen.add(key)
                    lezioni.append({
                        'data': data_norm,
                        'ora_inizio': ora_i,
                        'ora_fine': ora_f
                    })
            # Se abbiamo trovato lezioni con questo pattern, usciamo
            if lezioni:
                break

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
