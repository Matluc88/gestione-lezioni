import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lezioni.db")

def add_cliente_column():
    """Aggiunge la colonna 'cliente' alla tabella 'corsi' se non esiste già"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(corsi)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    
    if 'cliente' not in column_names:
        print("La colonna 'cliente' non esiste nella tabella 'corsi'. Aggiunta in corso...")
        cursor.execute("ALTER TABLE corsi ADD COLUMN cliente TEXT DEFAULT NULL")
        conn.commit()
        print("✅ Colonna 'cliente' aggiunta con successo alla tabella 'corsi'")
    else:
        print("La colonna 'cliente' esiste già nella tabella 'corsi'")
    
    conn.close()
    print(f"✅ Database aggiornato con successo: {DB_PATH}")

if __name__ == "__main__":
    add_cliente_column()
