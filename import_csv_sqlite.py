#!/usr/bin/env python3

import os
import sys
import csv
import sqlite3
from datetime import datetime

SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lezioni.db")

def get_sqlite_connection():
    """Crea una connessione al database SQLite"""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def calcola_ore(ora_inizio, ora_fine):
    """Calcola le ore tra ora_inizio e ora_fine"""
    try:
        if not ora_inizio or not ora_fine:
            return 0.0
        
        formato = "%H:%M"
        inizio = datetime.strptime(ora_inizio, formato)
        fine = datetime.strptime(ora_fine, formato)
        
        if fine < inizio:
            fine = fine.replace(day=inizio.day + 1)
        
        differenza = fine - inizio
        ore = differenza.total_seconds() / 3600
        return round(ore, 1)
    except Exception as e:
        print(f"Errore nel calcolo delle ore: {e}")
        return 0.0

def converti_data_formato(data_str, formato_input, formato_output):
    """Converte una data da un formato all'altro"""
    try:
        if not data_str:
            return None
        data = datetime.strptime(data_str, formato_input)
        return data.strftime(formato_output)
    except Exception as e:
        print(f"Errore nella conversione della data '{data_str}': {e}")
        return None

def importa_csv(file_path, delimiter=';'):
    """Importa dati da un file CSV nel database SQLite"""
    print(f"\n=== Importazione CSV: {file_path} ===")
    
    if not os.path.exists(file_path):
        print(f"❌ File non trovato: {file_path}")
        return False
    
    conn = get_sqlite_connection()
    cursor = conn.cursor()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            sample = f.read(1024)
            f.seek(0)
            
            if ';' in sample:
                delimiter = ';'
            elif ',' in sample:
                delimiter = ','
            elif '\t' in sample:
                delimiter = '\t'
            
            print(f"Delimitatore rilevato: '{delimiter}'")
            
            first_line = f.readline().strip()
            headers = first_line.split(delimiter)
            headers = [h.strip() for h in headers]
            
            print(f"Intestazioni rilevate: {headers}")
            
            column_map = {
                'id_corso': ['id_corso', 'id corso', 'corso', 'codice_corso', 'codice corso'],
                'materia': ['materia', 'subject', 'argomento'],
                'data': ['data', 'date', 'giorno'],
                'ora_inizio': ['ora_inizio', 'ora inizio', 'inizio', 'start'],
                'ora_fine': ['ora_fine', 'ora fine', 'fine', 'end'],
                'luogo': ['luogo', 'location', 'posto'],
                'compenso_orario': ['compenso_orario', 'compenso', 'tariffa', 'tariffa_oraria'],
                'stato': ['stato', 'status', 'completato'],
                'fatturato': ['fatturato', 'billed', 'fattura'],
                'mese_fatturato': ['mese_fatturato', 'mese fatturato', 'mese_fattura'],
                'ore_fatturate': ['ore_fatturate', 'ore fatturate', 'ore'],
                'cliente': ['cliente', 'client', 'customer']
            }
            
            column_indices = {}
            for db_col, possible_names in column_map.items():
                for name in possible_names:
                    if name.lower() in [h.lower() for h in headers]:
                        idx = [h.lower() for h in headers].index(name.lower())
                        column_indices[db_col] = idx
                        break
            
            print(f"Mappatura colonne: {column_indices}")
            
            essential_columns = ['id_corso', 'materia', 'data', 'ora_inizio', 'ora_fine']
            missing_essential = [col for col in essential_columns if col not in column_indices]
            
            if missing_essential:
                print(f"❌ Colonne essenziali mancanti: {', '.join(missing_essential)}")
                print("Colonne disponibili:", ", ".join(headers))
                return False
            
            f.seek(0)
            next(f)
            
            total_rows = sum(1 for _ in f)
            f.seek(0)
            next(f)  # Salta l'intestazione
            
            print(f"Importazione di {total_rows} righe...")
            
            corsi_creati = set()
            
            imported_rows = 0
            skipped_rows = 0
            
            for i, line in enumerate(f):
                try:
                    row = line.strip().split(delimiter)
                    row = [cell.strip() for cell in row]
                    
                    values = {}
                    for col, idx in column_indices.items():
                        if idx < len(row):
                            values[col] = row[idx] if row[idx] else None
                        else:
                            values[col] = None
                    
                    id_corso = values.get('id_corso')
                    if not id_corso:
                        print(f"⚠️ Riga {i+2}: ID corso mancante, riga saltata")
                        skipped_rows += 1
                        continue
                    
                    data = values.get('data')
                    if data and '/' in data:
                        try:
                            values['data'] = converti_data_formato(data, "%d/%m/%Y", "%Y-%m-%d")
                        except Exception:
                            try:
                                values['data'] = converti_data_formato(data, "%d-%m-%Y", "%Y-%m-%d")
                            except Exception:
                                pass
                    
                    if 'stato' not in values or not values['stato']:
                        if values.get('data'):
                            try:
                                data_lezione = datetime.strptime(values['data'], "%Y-%m-%d")
                                if data_lezione.date() < datetime.now().date():
                                    values['stato'] = 'Completato'
                                else:
                                    values['stato'] = 'Pianificato'
                            except Exception:
                                values['stato'] = 'Pianificato'
                        else:
                            values['stato'] = 'Pianificato'
                    
                    if 'fatturato' not in values or values['fatturato'] is None:
                        values['fatturato'] = 0
                    else:
                        try:
                            values['fatturato'] = int(values['fatturato'])
                        except Exception:
                            if values['fatturato'].lower() in ['sì', 'si', 'yes', 'true', '1']:
                                values['fatturato'] = 1
                            else:
                                values['fatturato'] = 0
                    
                    if 'ore_fatturate' not in values or not values['ore_fatturate']:
                        if values['fatturato'] == 1 and values.get('ora_inizio') and values.get('ora_fine'):
                            values['ore_fatturate'] = calcola_ore(values['ora_inizio'], values['ora_fine'])
                        else:
                            values['ore_fatturate'] = 0
                    else:
                        try:
                            values['ore_fatturate'] = float(values['ore_fatturate'].replace(',', '.'))
                        except Exception:
                            values['ore_fatturate'] = 0
                    
                    if id_corso not in corsi_creati:
                        cursor.execute("SELECT 1 FROM corsi WHERE id_corso = ?", (id_corso,))
                        corso_exists = cursor.fetchone()
                        
                        if not corso_exists:
                            cliente = values.get('cliente', '')
                            nome = f"Corso {id_corso}"
                            
                            cursor.execute("""
                                INSERT INTO corsi (id_corso, nome, cliente)
                                VALUES (?, ?, ?)
                            """, (id_corso, nome, cliente))
                            
                            corsi_creati.add(id_corso)
                            print(f"✅ Creato nuovo corso: {id_corso}")
                    
                    cursor.execute("""
                        INSERT INTO lezioni (
                            id_corso, materia, data, ora_inizio, ora_fine, 
                            luogo, compenso_orario, stato, fatturato, 
                            mese_fatturato, ore_fatturate
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        values.get('id_corso'),
                        values.get('materia'),
                        values.get('data'),
                        values.get('ora_inizio'),
                        values.get('ora_fine'),
                        values.get('luogo'),
                        values.get('compenso_orario', 0),
                        values.get('stato'),
                        values.get('fatturato', 0),
                        values.get('mese_fatturato'),
                        values.get('ore_fatturate', 0)
                    ))
                    
                    imported_rows += 1
                    
                    if (i+1) % 50 == 0 or i+1 == total_rows:
                        print(f"Importate {i+1}/{total_rows} righe...")
                
                except Exception as e:
                    print(f"❌ Errore alla riga {i+2}: {e}")
                    skipped_rows += 1
                    continue
            
            conn.commit()
            print(f"\n✅ Importazione completata:")
            print(f"  - Righe totali: {total_rows}")
            print(f"  - Righe importate: {imported_rows}")
            print(f"  - Righe saltate: {skipped_rows}")
            print(f"  - Corsi creati: {len(corsi_creati)}")
            
            return imported_rows > 0
            
    except Exception as e:
        conn.rollback()
        print(f"❌ Errore durante l'importazione del CSV: {e}")
        return False
    finally:
        conn.close()

def correggi_stato_lezioni():
    """Corregge lo stato delle lezioni in SQLite"""
    print("\n=== Correzione stato lezioni ===")
    
    conn = get_sqlite_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE lezioni
            SET stato = 'Completato'
            WHERE stato != 'Completato' AND date(data) < date('now')
        """)
        
        rows_updated = cursor.rowcount
        conn.commit()
        
        print(f"✅ Stato aggiornato per {rows_updated} lezioni con data passata")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Errore durante la correzione dello stato delle lezioni: {e}")
    
    conn.close()

def main():
    """Funzione principale"""
    print("=== Script di Importazione CSV in SQLite ===")
    
    try:
        conn = get_sqlite_connection()
        conn.close()
        print("✅ Connessione a SQLite riuscita!")
    except Exception as e:
        print(f"❌ Errore di connessione a SQLite: {e}")
        return
    
    while True:
        print("\nScegli un'operazione:")
        print("1. Importa da CSV")
        print("2. Correggi stato lezioni")
        print("3. Esegui entrambe le operazioni")
        print("0. Esci")
        
        scelta = input("Scelta: ")
        
        if scelta == "1":
            file_path = input("Percorso del file CSV: ")
            importa_csv(file_path)
        elif scelta == "2":
            correggi_stato_lezioni()
        elif scelta == "3":
            file_path = input("Percorso del file CSV: ")
            importa_csv(file_path)
            correggi_stato_lezioni()
        elif scelta == "0":
            print("Arrivederci!")
            break
        else:
            print("Scelta non valida!")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path):
            importa_csv(file_path)
            correggi_stato_lezioni()
        else:
            print(f"❌ File non trovato: {file_path}")
    else:
        main()
