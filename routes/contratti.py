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

def pdf_to_base64_images(file_path, max_pages=5):
    """Converte PDF in immagini base64 per Claude Vision"""
    try:
        # Converti PDF in immagini (max 10 pagine per non superare limiti)
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
                "text": """Analizza questo contratto PDF ed estrai:

1. INFORMAZIONI CHIAVE (per l'analisi):
   - Numero contratto
   - Cliente/studente
   - Date (inizio, fine)
   - Compenso
   - Materie
   - Ore previste

2. TESTO COMPLETO DEL DOCUMENTO:
   Trascrivi tutto il contenuto del PDF inclusi calendari, tabelle e allegati.

Formatta in modo chiaro in italiano."""
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
                max_tokens=4000,
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
    
    return render_template("contratti.html", contratti=contratti, current_tab='altro')


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
