# utils.py

from datetime import datetime

def correggi_orario(orario):
    try:
        return datetime.strptime(orario.strip(), "%H:%M").strftime("%H:%M")
    except ValueError:
        try:
            return datetime.strptime(orario.strip(), "%H.%M").strftime("%H:%M")
        except ValueError:
            return None

def calcola_ore(ora_inizio, ora_fine):
    try:
        inizio = datetime.strptime(ora_inizio, "%H:%M")
        fine = datetime.strptime(ora_fine, "%H:%M")
        return (fine - inizio).seconds / 3600
    except Exception as e:
        print(f"❌ Errore orario: {e}")
        return
