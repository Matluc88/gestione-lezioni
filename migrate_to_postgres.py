import os
import sqlite3
import psycopg2
import csv
from datetime import datetime
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

load_dotenv()

SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lezioni.db")

PG_DATABASE_URL = os.environ.get("DATABASE_URL")

def export_sqlite_to_csv():
    """Esporta tutte le tabelle da SQLite a file CSV"""
    print("Esportazione dei dati da SQLite a CSV...")
    
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('sqlite_sequence')")
    tables = [row['name'] for row in cursor.fetchall()]
    
    os.makedirs("csv_export", exist_ok=True)
    
    for table in tables:
        print(f"Esportazione tabella: {table}")
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        
        if not rows:
            print(f"  Nessun dato trovato nella tabella {table}")
            continue
        
        csv_file = os.path.join("csv_export", f"{table}.csv")
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([column for column in rows[0].keys()])
            for row in rows:
                writer.writerow([row[column] for column in row.keys()])
        
        print(f"  Esportati {len(rows)} record nella tabella {table}")
    
    conn.close()
    print("Esportazione completata!")

def import_csv_to_postgres():
    """Importa i dati dai file CSV a PostgreSQL"""
    print("Importazione dei dati da CSV a PostgreSQL...")
    
    conn = psycopg2.connect(PG_DATABASE_URL)
    cursor = conn.cursor()
    
    csv_dir = "csv_export"
    csv_files = [f for f in os.listdir(csv_dir) if f.endswith('.csv')]
    
    for csv_file in csv_files:
        table_name = os.path.splitext(csv_file)[0]
        csv_path = os.path.join(csv_dir, csv_file)
        
        print(f"Importazione tabella: {table_name}")
        
        with open(csv_path, 'r', newline='') as f:
            reader = csv.reader(f)
            headers = next(reader)  # Leggi intestazioni
            
            if table_name in ['lezioni', 'archiviate'] and 'ore_fatturate' not in headers:
                headers.append('ore_fatturate')
            
            placeholders = ','.join(['%s'] * len(headers))
            columns = ','.join([f'"{col}"' for col in headers])
            
            cursor.execute("SET session_replication_role = 'replica';")
            
            count = 0
            for row in reader:
                try:
                    if table_name in ['lezioni', 'archiviate'] and len(row) < len(headers):
                        ora_inizio_idx = headers.index('ora_inizio')
                        ora_fine_idx = headers.index('ora_fine')
                        fatturato_idx = headers.index('fatturato')
                        
                        ora_inizio = row[ora_inizio_idx]
                        ora_fine = row[ora_fine_idx]
                        fatturato = int(row[fatturato_idx]) if row[fatturato_idx] else 0
                        
                        if fatturato == 1:
                            cursor.execute("SELECT calcola_ore(%s, %s)", (ora_inizio, ora_fine))
                            ore = cursor.fetchone()[0]
                            row.append(str(ore))
                        else:
                            row.append('0')
                    
                    cursor.execute(
                        f'INSERT INTO {table_name} ({columns}) VALUES ({placeholders})',
                        row
                    )
                    count += 1
                except Exception as e:
                    print(f"  Errore durante l'inserimento: {e}")
                    conn.rollback()
                    continue
            
            cursor.execute("SET session_replication_role = 'origin';")
            
            print(f"  Importati {count} record nella tabella {table_name}")
    
    cursor.execute("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE column_default LIKE 'nextval%'
    """)
    
    for table, column in cursor.fetchall():
        print(f"Aggiornamento sequenza per {table}.{column}")
        cursor.execute(f"""
            SELECT setval(
                pg_get_serial_sequence('{table}', '{column}'),
                COALESCE(MAX({column}), 0) + 1, false
            )
            FROM {table}
        """)
    
    conn.commit()
    conn.close()
    print("Importazione completata!")

def main():
    """Funzione principale per la migrazione"""
    print("Inizio migrazione da SQLite a PostgreSQL...")
    
    try:
        conn = psycopg2.connect(PG_DATABASE_URL)
        conn.close()
        print("✅ Connessione a PostgreSQL riuscita!")
    except Exception as e:
        print(f"❌ Errore di connessione a PostgreSQL: {e}")
        print("Assicurati che la variabile d'ambiente DATABASE_URL sia impostata correttamente.")
        return
    
    export_sqlite_to_csv()
    
    import_csv_to_postgres()
    
    print("✅ Migrazione completata con successo!")

if __name__ == "__main__":
    main()
