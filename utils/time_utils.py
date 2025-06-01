from datetime import datetime
import pytz

def correggi_orario(orario):
    """
    Corregge il formato dell'orario assicurandosi che sia nel formato HH:MM
    """
    try:
        return datetime.strptime(orario.strip(), "%H:%M").strftime("%H:%M")
    except ValueError:
        try:
            return datetime.strptime(orario.strip(), "%H.%M").strftime("%H:%M")
        except ValueError:
            return None

def calcola_ore(ora_inizio, ora_fine):
    """
    Calcola le ore tra ora_inizio e ora_fine
    """
    try:
        inizio = datetime.strptime(ora_inizio, "%H:%M")
        fine = datetime.strptime(ora_fine, "%H:%M")
        return (fine - inizio).seconds / 3600
    except Exception as e:
        print(f"❌ Errore orario: {e}")
        return 0.0

def get_local_now():
    """
    Restituisce la data/ora corrente nel timezone locale (Europe/Rome)
    """
    try:
        rome_tz = pytz.timezone('Europe/Rome')
        return datetime.now(rome_tz)
    except:
        return datetime.now()

def format_date_for_template(date_obj=None):
    """
    Formatta una data per l'uso nei template, usando il timezone locale
    """
    if date_obj is None:
        date_obj = get_local_now()
    return date_obj.strftime('%Y-%m-%d')

def format_datetime_for_db(date_obj=None):
    """
    Formatta una data/ora per l'inserimento nel database
    """
    if date_obj is None:
        date_obj = get_local_now()
    return date_obj.strftime('%Y-%m-%d %H:%M:%S')
