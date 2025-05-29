#!/usr/bin/env python3
import os
import csv
import sqlite3
import psycopg2
import sys
from psycopg2.extras import DictCursor
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lezioni.db")
PG_DATABASE_URL = os.environ.get("DATABASE_URL")

USE_POSTGRES = PG_DATABASE_URL and "postgresql" in PG_DATABASE_URL

def get_sqlite_connection():
    """Crea una connessione al database SQLite"""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_pg_connection():
    """Crea una connessione al database PostgreSQL"""
    if not USE_POSTGRES:
        print("❌ Variabile d'ambiente DATABASE_URL non configurata o non valida")
        sys.exit(1)
    conn = psycopg2.connect(PG_DATABASE_URL)
    conn.cursor_factory = DictCursor
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

def verifica_integrità_database():
    """Verifica l'integrità tra i database SQLite e PostgreSQL"""
    print("\n=== Verifica integrità database ===")
    
    sqlite_conn = get_sqlite_connection()
    sqlite_cursor = sqlite_conn.cursor()
    
    pg_conn = get_pg_connection()
    pg_cursor = pg_conn.cursor()
    
    tabelle = ['corsi', 'lezioni', 'fatture']
    
    for tabella in tabelle:
        try:
            sqlite_cursor.execute(f"SELECT COUNT(*) FROM {tabella}")
            sqlite_count = sqlite_cursor.fetchone()[0]
            
            pg_cursor.execute(f"SELECT COUNT(*) FROM {tabella}")
            pg_count = pg_cursor.fetchone()[0]
            
            print(f"Tabella {tabella}: SQLite={sqlite_count}, PostgreSQL={pg_count}")
            
            if sqlite_count > pg_count:
                print(f"⚠️ Mancano {sqlite_count - pg_count} record in PostgreSQL per la tabella {tabella}")
            elif sqlite_count < pg_count:
                print(f"⚠️ Ci sono {pg_count - sqlite_count} record in più in PostgreSQL per la tabella {tabella}")
        except Exception as e:
            print(f"❌ Errore durante la verifica della tabella {tabella}: {e}")
    
    try:
        sqlite_cursor.execute("SELECT COUNT(*) FROM lezioni WHERE stato = 'Completato'")
        sqlite_completed = sqlite_cursor.fetchone()[0]
        
        pg_cursor.execute("SELECT COUNT(*) FROM lezioni WHERE stato = 'Completato'")
        pg_completed = pg_cursor.fetchone()[0]
        
        print(f"Lezioni completate: SQLite={sqlite_completed}, PostgreSQL={pg_completed}")
        
        if sqlite_completed > pg_completed:
            print(f"⚠️ Mancano {sqlite_completed - pg_completed} lezioni completate in PostgreSQL")
    except Exception as e:
        print(f"❌ Errore durante la verifica delle lezioni completate: {e}")
    
    sqlite_conn.close()
    pg_conn.close()

def correggi_stato_lezioni():
    """Corregge lo stato delle lezioni in PostgreSQL"""
    print("\n=== Correzione stato lezioni ===")
    
    pg_conn = get_pg_connection()
    pg_cursor = pg_conn.cursor()
    
    try:
        pg_cursor.execute("""
            UPDATE lezioni
            SET stato = 'Completato'
            WHERE stato != 'Completato' AND TO_DATE(data, 'YYYY-MM-DD') < CURRENT_DATE
        """)
        
        rows_updated = pg_cursor.rowcount
        pg_conn.commit()
        
        print(f"✅ Stato aggiornato per {rows_updated} lezioni con data passata")
        
    except Exception as e:
        pg_conn.rollback()
        print(f"❌ Errore durante la correzione dello stato delle lezioni: {e}")
    
    pg_conn.close()

def migra_corsi_mancanti():
    """Migra i corsi presenti in SQLite ma mancanti in PostgreSQL"""
    print("\n=== Migrazione corsi mancanti ===")
    
    sqlite_conn = get_sqlite_connection()
    sqlite_cursor = sqlite_conn.cursor()
    
    pg_conn = get_pg_connection()
    pg_cursor = pg_conn.cursor()
    
    try:
        sqlite_cursor.execute("SELECT id_corso, nome, cliente FROM corsi")
        corsi_sqlite = {row['id_corso']: dict(row) for row in sqlite_cursor.fetchall()}
        
        pg_cursor.execute("SELECT id_corso FROM corsi")
        corsi_pg = [row['id_corso'] for row in pg_cursor.fetchall()]
        
        corsi_mancanti = []
        for id_corso, corso in corsi_sqlite.items():
            if id_corso not in corsi_pg:
                corsi_mancanti.append(corso)
        
        print(f"Trovati {len(corsi_mancanti)} corsi mancanti")
        
        for corso in corsi_mancanti:
            try:
                id_corso = corso['id_corso']
                
                pg_cursor.execute("""
                    INSERT INTO corsi (id_corso, nome, cliente)
                    VALUES (%s, %s, %s)
                """, (id_corso, corso['nome'], corso.get('cliente')))
                
                sqlite_cursor.execute("SELECT * FROM lezioni WHERE id_corso = ?", (id_corso,))
                lezioni = sqlite_cursor.fetchall()
                
                print(f"Migrazione corso {id_corso} con {len(lezioni)} lezioni...")
                
                for lezione in lezioni:
                    ore_fatturate = 0
                    if lezione['fatturato'] == 1:
                        ore_fatturate = calcola_ore(lezione['ora_inizio'], lezione['ora_fine'])
                    
                    pg_cursor.execute("""
                        INSERT INTO lezioni (
                            id_corso, materia, data, ora_inizio, ora_fine, 
                            luogo, compenso_orario, stato, fatturato, 
                            mese_fatturato, ore_fatturate
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        lezione['id_corso'], lezione['materia'], lezione['data'],
                        lezione['ora_inizio'], lezione['ora_fine'], lezione['luogo'],
                        lezione['compenso_orario'], lezione['stato'], lezione['fatturato'],
                        lezione['mese_fatturato'], ore_fatturate
                    ))
                
                pg_conn.commit()
                print(f"✅ Corso {id_corso} migrato con successo")
                
            except Exception as e:
                pg_conn.rollback()
                print(f"❌ Errore durante la migrazione del corso {corso['id_corso']}: {e}")
        
    except Exception as e:
        print(f"❌ Errore durante la migrazione dei corsi: {e}")
    
    sqlite_conn.close()
    pg_conn.close()

def importa_csv(file_path, delimiter=';'):
    """Importa dati da un file CSV nel database PostgreSQL"""
    print(f"\n=== Importazione CSV: {file_path} ===")
    
    if not os.path.exists(file_path):
        print(f"❌ File non trovato: {file_path}")
        return False
    
    pg_conn = get_pg_connection()
    pg_cursor = pg_conn.cursor()
    
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
            
            reader = csv.DictReader(f, delimiter=delimiter)
            
            colonne_minime = ['id_corso', 'materia', 'data', 'ora_inizio', 'ora_fine']
            colonne_opzionali = ['luogo', 'compenso_orario', 'stato', 'fatturato', 'mese_fatturato', 'ore_fatturate', 'cliente']
            
            colonne_csv = reader.fieldnames
            colonne_mancanti = [col for col in colonne_minime if col not in colonne_csv]
            
            if colonne_mancanti:
                print(f"❌ Colonne essenziali mancanti nel CSV: {', '.join(colonne_mancanti)}")
                print("Colonne disponibili:", ", ".join(colonne_csv))
                return False
                
            print(f"Colonne trovate: {', '.join(colonne_csv)}")
            colonne_opzionali_mancanti = [col for col in colonne_opzionali if col not in colonne_csv]
            if colonne_opzionali_mancanti:
                print(f"ℹ️ Colonne opzionali mancanti (verranno usati valori predefiniti): {', '.join(colonne_opzionali_mancanti)}")
            
            print(f"Colonne trovate: {', '.join(colonne_csv)}")
            
            righe_totali = 0
            righe_importate = 0
            righe_saltate = 0
            corsi_creati = 0
            
            for row in reader:
                righe_totali += 1
                
                try:
                    id_corso = row['id_corso'].strip() if row.get('id_corso') else None
                    materia = row['materia'].strip() if row.get('materia') else None
                    data_str = row['data'].strip() if row.get('data') else None
                    ora_inizio = row['ora_inizio'].strip() if row.get('ora_inizio') else None
                    ora_fine = row['ora_fine'].strip() if row.get('ora_fine') else None
                    
                    luogo = row['luogo'].strip() if 'luogo' in colonne_csv and row.get('luogo') else None
                    compenso_orario = row['compenso_orario'].strip() if 'compenso_orario' in colonne_csv and row.get('compenso_orario') else "0"
                    stato = row['stato'].strip() if 'stato' in colonne_csv and row.get('stato') else "Pianificato"
                    fatturato = row['fatturato'].strip() if 'fatturato' in colonne_csv and row.get('fatturato') else "0"
                    mese_fatturato = row['mese_fatturato'].strip() if 'mese_fatturato' in colonne_csv and row.get('mese_fatturato') else None
                    cliente = row['cliente'].strip() if 'cliente' in colonne_csv and row.get('cliente') else None
                    
                    ore_lezione = calcola_ore(ora_inizio, ora_fine)
                    
                    ore_fatturate = str(ore_lezione) if fatturato == "1" else "0"
                    
                    if not id_corso or not materia or not data_str or not ora_inizio or not ora_fine:
                        print(f"⚠️ Riga {righe_totali}: Dati obbligatori mancanti, saltata")
                        righe_saltate += 1
                        continue
                    
                    if '/' in data_str:
                        data = converti_data_formato(data_str, "%d/%m/%Y", "%Y-%m-%d")
                    else:
                        data = data_str
                    
                    if not data:
                        print(f"⚠️ Riga {righe_totali}: Formato data non valido '{data_str}', saltata")
                        righe_saltate += 1
                        continue
                    
                    try:
                        compenso_orario = float(compenso_orario.replace(',', '.'))
                    except ValueError:
                        compenso_orario = 0.0
                    
                    try:
                        fatturato = int(fatturato)
                    except ValueError:
                        fatturato = 0
                    
                    try:
                        ore_fatturate = float(ore_fatturate.replace(',', '.'))
                    except ValueError:
                        ore_fatturate = 0.0
                    
                    pg_cursor.execute("SELECT id_corso FROM corsi WHERE id_corso = %s", (id_corso,))
                    corso_esistente = pg_cursor.fetchone()
                    
                    if not corso_esistente:
                        try:
                            pg_cursor.execute("""
                                INSERT INTO corsi (id_corso, nome, cliente)
                                VALUES (%s, %s, %s)
                            """, (id_corso, id_corso, cliente))
                            corsi_creati += 1
                            print(f"✅ Corso '{id_corso}' creato automaticamente")
                        except Exception as e:
                            print(f"❌ Errore durante la creazione del corso '{id_corso}': {e}")
                            pg_conn.rollback()
                            continue
                    
                    pg_cursor.execute("""
                        INSERT INTO lezioni (
                            id_corso, materia, data, ora_inizio, ora_fine, 
                            luogo, compenso_orario, stato, fatturato, 
                            mese_fatturato, ore_fatturate
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        id_corso, materia, data,
                        ora_inizio, ora_fine, luogo,
                        compenso_orario, stato, fatturato,
                        mese_fatturato, ore_fatturate
                    ))
                    
                    righe_importate += 1
                    
                except Exception as e:
                    print(f"❌ Errore durante l'importazione della riga {righe_totali}: {e}")
                    righe_saltate += 1
                    continue
            
            pg_conn.commit()
            print(f"\n✅ Importazione completata:")
            print(f"  - Righe totali: {righe_totali}")
            print(f"  - Righe importate: {righe_importate}")
            print(f"  - Righe saltate: {righe_saltate}")
            print(f"  - Corsi creati: {corsi_creati}")
            
            return righe_importate > 0
            
    except Exception as e:
        pg_conn.rollback()
        print(f"❌ Errore durante l'importazione del CSV: {e}")
        return False
    finally:
        pg_conn.close()

def main():
    """Funzione principale"""
    print("=== Script di Correzione e Importazione Database ===")
    
    try:
        sqlite_conn = get_sqlite_connection()
        sqlite_conn.close()
        print("✅ Connessione a SQLite riuscita!")
        
        pg_conn = get_pg_connection()
        pg_conn.close()
        print("✅ Connessione a PostgreSQL riuscita!")
    except Exception as e:
        print(f"❌ Errore di connessione: {e}")
        return
    
    while True:
        print("\nScegli un'operazione:")
        print("1. Verifica integrità database")
        print("2. Correggi stato lezioni")
        print("3. Migra corsi mancanti")
        print("4. Importa da CSV")
        print("5. Esegui tutte le operazioni")
        print("0. Esci")
        
        scelta = input("Scelta: ")
        
        if scelta == "1":
            verifica_integrità_database()
        elif scelta == "2":
            correggi_stato_lezioni()
        elif scelta == "3":
            migra_corsi_mancanti()
        elif scelta == "4":
            file_path = input("Percorso del file CSV: ")
            importa_csv(file_path)
        elif scelta == "5":
            verifica_integrità_database()
            correggi_stato_lezioni()
            migra_corsi_mancanti()
            file_path = input("Percorso del file CSV (lascia vuoto per saltare): ")
            if file_path:
                importa_csv(file_path)
        elif scelta == "0":
            print("Arrivederci!")
            break
        else:
            print("Scelta non valida!")

if __name__ == "__main__":
    main()
