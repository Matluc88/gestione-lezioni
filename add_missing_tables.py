import os
import sqlite3
from flask_bcrypt import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lezioni.db")

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "fatture")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
print(f"✅ Cartella per le fatture creata: {UPLOAD_FOLDER}")

def add_missing_tables():
    """Aggiunge solo le tabelle mancanti al database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fatture'")
    if cursor.fetchone():
        print("La tabella 'fatture' esiste già.")
    else:
        print("Creazione della tabella 'fatture'...")
        cursor.execute("""
        CREATE TABLE fatture (
            id_fattura INTEGER PRIMARY KEY AUTOINCREMENT,
            id_corso TEXT,
            data_fattura TEXT NOT NULL,
            importo REAL NOT NULL,
            tipo_fatturazione TEXT CHECK(tipo_fatturazione IN ('parziale', 'totale')) NOT NULL,
            file_pdf TEXT NOT NULL,
            note TEXT
        )
        """)
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fatture_lezioni'")
    if cursor.fetchone():
        print("La tabella 'fatture_lezioni' esiste già.")
    else:
        print("Creazione della tabella 'fatture_lezioni'...")
        cursor.execute("""
        CREATE TABLE fatture_lezioni (
            id_fattura INTEGER,
            id_lezione INTEGER,
            FOREIGN KEY (id_fattura) REFERENCES fatture (id_fattura),
            FOREIGN KEY (id_lezione) REFERENCES lezioni (id)
        )
        """)
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='corsi_archiviati'")
    if cursor.fetchone():
        print("La tabella 'corsi_archiviati' esiste già.")
    else:
        print("Creazione della tabella 'corsi_archiviati'...")
        cursor.execute("""
        CREATE TABLE corsi_archiviati (
            id_corso TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            cliente TEXT DEFAULT NULL,
            data_archiviazione TEXT NOT NULL
        )
        """)
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='corsi'")
    if cursor.fetchone():
        print("La tabella 'corsi' esiste già.")
    else:
        print("Creazione della tabella 'corsi'...")
        cursor.execute("""
        CREATE TABLE corsi (
            id_corso TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            cliente TEXT DEFAULT NULL
        )
        """)
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if not cursor.fetchone():
        print("Creazione della tabella 'users'...")
        cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
        """)
        
        username = "admin"
        password = "admin123"
        hashed_password = generate_password_hash(password).decode('utf-8')
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
        print(f"✅ Utente di test creato: {username} / {password}")
    else:
        print("La tabella 'users' esiste già.")
    
    conn.commit()
    conn.close()
    print(f"✅ Database aggiornato con successo: {DB_PATH}")
    print("✅ Tutte le tabelle necessarie sono state verificate o create.")

if __name__ == "__main__":
    add_missing_tables()
