from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from db_utils import db_connection, get_placeholder
from utils.security import sanitize_input
import os
import json

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request
    GOOGLE_CALENDAR_AVAILABLE = True
except ImportError:
    GOOGLE_CALENDAR_AVAILABLE = False

google_calendar_bp = Blueprint('google_calendar', __name__, url_prefix='/google_calendar')

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_credentials_path():
    if os.getenv('GOOGLE_CREDENTIALS_FILE'):
        return os.getenv('GOOGLE_CREDENTIALS_FILE')
    
    render_path = '/etc/secrets/credentials.json'
    if os.path.exists(render_path):
        return render_path
    
    app_root_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'credentials.json')
    return app_root_path

CREDENTIALS_FILE = get_credentials_path()
TOKEN_FILE = os.getenv('GOOGLE_TOKEN_FILE', '/tmp/token.json')
CALENDAR_ID = os.getenv('GOOGLE_CALENDAR_ID', '00f533cf6188a0078221e27c7a1a64867021292f2deab3b214c1dd41e315616d@group.calendar.google.com')

def get_google_calendar_service():
    """Get authenticated Google Calendar service"""
    creds = None
    
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(TOKEN_FILE, 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                print(f"Error refreshing token: {e}")
                return None
        else:
            return None
    
    try:
        service = build('calendar', 'v3', credentials=creds)
        return service
    except Exception as e:
        print(f"Error building calendar service: {e}")
        return None

@google_calendar_bp.route('/sincronizza', methods=['GET', 'POST'])
@login_required
def sincronizza():
    """Show date range selection form for Google Calendar sync"""
    if not GOOGLE_CALENDAR_AVAILABLE:
        flash("❌ Le librerie Google Calendar non sono installate. Esegui: pip install -r requirements.txt", "danger")
        return redirect(url_for('lezioni.dashboard'))
    
    if not os.path.exists(CREDENTIALS_FILE):
        flash("❌ File credentials.json non trovato. Configura prima le credenziali Google Calendar API.", "danger")
        return redirect(url_for('lezioni.dashboard'))
    
    if request.method == 'POST':
        data_inizio = request.form.get('data_inizio')
        data_fine = request.form.get('data_fine')
        
        if not data_inizio or not data_fine:
            flash("❌ Inserisci entrambe le date (inizio e fine)", "danger")
            return redirect(url_for('google_calendar.sincronizza'))
        
        try:
            dt_inizio = datetime.strptime(data_inizio, '%Y-%m-%d')
            dt_fine = datetime.strptime(data_fine, '%Y-%m-%d')
            
            if dt_inizio > dt_fine:
                flash("❌ La data di inizio deve essere precedente alla data di fine", "danger")
                return redirect(url_for('google_calendar.sincronizza'))
        except ValueError:
            flash("❌ Formato data non valido", "danger")
            return redirect(url_for('google_calendar.sincronizza'))
        
        session['sync_data_inizio'] = data_inizio
        session['sync_data_fine'] = data_fine
        
        service = get_google_calendar_service()
        if service is None:
            return redirect(url_for('google_calendar.authorize'))
        
        return redirect(url_for('google_calendar.esegui_sincronizzazione'))
    
    return render_template('sincronizza_google_calendar.html')

@google_calendar_bp.route('/authorize')
@login_required
def authorize():
    """Start OAuth2 authorization flow"""
    if not GOOGLE_CALENDAR_AVAILABLE:
        flash("❌ Le librerie Google Calendar non sono installate.", "danger")
        return redirect(url_for('lezioni.dashboard'))
    
    if not os.path.exists(CREDENTIALS_FILE):
        flash("❌ File credentials.json non trovato.", "danger")
        return redirect(url_for('lezioni.dashboard'))
    
    try:
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE,
            scopes=SCOPES,
            redirect_uri=url_for('google_calendar.oauth2callback', _external=True)
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        session['oauth_state'] = state
        
        return redirect(authorization_url)
    except Exception as e:
        flash(f"❌ Errore durante l'autorizzazione: {str(e)}", "danger")
        return redirect(url_for('lezioni.dashboard'))

@google_calendar_bp.route('/oauth2callback')
@login_required
def oauth2callback():
    """Handle OAuth2 callback"""
    if not GOOGLE_CALENDAR_AVAILABLE:
        flash("❌ Le librerie Google Calendar non sono installate.", "danger")
        return redirect(url_for('lezioni.dashboard'))
    
    state = session.get('oauth_state')
    if not state:
        flash("❌ Stato OAuth non valido", "danger")
        return redirect(url_for('lezioni.dashboard'))
    
    try:
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE,
            scopes=SCOPES,
            state=state,
            redirect_uri=url_for('google_calendar.oauth2callback', _external=True)
        )
        
        flow.fetch_token(authorization_response=request.url)
        
        creds = flow.credentials
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
        
        flash("✅ Autenticazione Google Calendar completata con successo!", "success")
        
        if 'sync_data_inizio' in session and 'sync_data_fine' in session:
            return redirect(url_for('google_calendar.esegui_sincronizzazione'))
        
        return redirect(url_for('google_calendar.sincronizza'))
    except Exception as e:
        flash(f"❌ Errore durante il callback OAuth: {str(e)}", "danger")
        return redirect(url_for('lezioni.dashboard'))

@google_calendar_bp.route('/esegui_sincronizzazione')
@login_required
def esegui_sincronizzazione():
    """Execute the actual synchronization with Google Calendar"""
    if not GOOGLE_CALENDAR_AVAILABLE:
        flash("❌ Le librerie Google Calendar non sono installate.", "danger")
        return redirect(url_for('lezioni.dashboard'))
    
    data_inizio = session.get('sync_data_inizio')
    data_fine = session.get('sync_data_fine')
    
    if not data_inizio or not data_fine:
        flash("❌ Intervallo di date non specificato", "danger")
        return redirect(url_for('google_calendar.sincronizza'))
    
    service = get_google_calendar_service()
    if service is None:
        flash("❌ Autenticazione Google Calendar non valida. Riprova.", "danger")
        return redirect(url_for('google_calendar.authorize'))
    
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            placeholder = get_placeholder()
            
            query = f"""
                SELECT l.id, l.id_corso, l.materia, l.data, l.ora_inizio, l.ora_fine, 
                       l.luogo, l.stato, l.google_calendar_event_id,
                       COALESCE(c.nome, l.id_corso) as nome_corso
                FROM lezioni l
                LEFT JOIN corsi c ON l.id_corso = c.id_corso
                WHERE l.data BETWEEN {placeholder} AND {placeholder}
                ORDER BY l.data, l.ora_inizio
            """
            
            cursor.execute(query, (data_inizio, data_fine))
            lezioni = cursor.fetchall()
            
            if not lezioni:
                flash(f"ℹ️ Nessuna lezione trovata nell'intervallo {data_inizio} - {data_fine}", "info")
                return redirect(url_for('google_calendar.sincronizza'))
            
            lezioni_sincronizzate = 0
            lezioni_aggiornate = 0
            lezioni_create = 0
            
            for lezione in lezioni:
                try:
                    event_summary = f"{lezione['nome_corso']} - {lezione['materia']}"
                    event_description = f"Corso: {lezione['nome_corso']}\nMateria: {lezione['materia']}\nStato: {lezione['stato']}"
                    
                    event_date = lezione['data']
                    start_time = lezione['ora_inizio']
                    end_time = lezione['ora_fine']
                    
                    start_datetime = f"{event_date}T{start_time}:00"
                    end_datetime = f"{event_date}T{end_time}:00"
                    
                    event_body = {
                        'summary': event_summary,
                        'location': lezione['luogo'],
                        'description': event_description,
                        'start': {
                            'dateTime': start_datetime,
                            'timeZone': 'Europe/Rome',
                        },
                        'end': {
                            'dateTime': end_datetime,
                            'timeZone': 'Europe/Rome',
                        },
                    }
                    
                    if lezione['google_calendar_event_id']:
                        try:
                            updated_event = service.events().update(
                                calendarId=CALENDAR_ID,
                                eventId=lezione['google_calendar_event_id'],
                                body=event_body
                            ).execute()
                            lezioni_aggiornate += 1
                        except Exception as e:
                            print(f"Error updating event {lezione['google_calendar_event_id']}: {e}")
                            created_event = service.events().insert(
                                calendarId=CALENDAR_ID,
                                body=event_body
                            ).execute()
                            
                            cursor.execute(
                                f"UPDATE lezioni SET google_calendar_event_id = {placeholder} WHERE id = {placeholder}",
                                (created_event['id'], lezione['id'])
                            )
                            conn.commit()
                            lezioni_create += 1
                    else:
                        created_event = service.events().insert(
                            calendarId=CALENDAR_ID,
                            body=event_body
                        ).execute()
                        
                        cursor.execute(
                            f"UPDATE lezioni SET google_calendar_event_id = {placeholder} WHERE id = {placeholder}",
                            (created_event['id'], lezione['id'])
                        )
                        conn.commit()
                        lezioni_create += 1
                    
                    lezioni_sincronizzate += 1
                    
                except Exception as e:
                    print(f"Error syncing lesson {lezione['id']}: {e}")
                    continue
            
            session.pop('sync_data_inizio', None)
            session.pop('sync_data_fine', None)
            
            if lezioni_sincronizzate > 0:
                msg = f"✅ Sincronizzazione completata! {lezioni_sincronizzate} lezioni sincronizzate "
                msg += f"({lezioni_create} create, {lezioni_aggiornate} aggiornate)"
                flash(msg, "success")
            else:
                flash("⚠️ Nessuna lezione è stata sincronizzata", "warning")
            
            return redirect(url_for('lezioni.dashboard'))
            
    except Exception as e:
        flash(f"❌ Errore durante la sincronizzazione: {str(e)}", "danger")
        return redirect(url_for('google_calendar.sincronizza'))

@google_calendar_bp.route('/disconnetti')
@login_required
def disconnetti():
    """Disconnect Google Calendar by removing token"""
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)
        flash("✅ Disconnesso da Google Calendar", "success")
    else:
        flash("ℹ️ Non sei connesso a Google Calendar", "info")
    
    return redirect(url_for('lezioni.dashboard'))
