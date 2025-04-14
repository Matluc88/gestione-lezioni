import os
import sqlite3
from contextlib import contextmanager
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lezioni.db")
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "fatture")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def db_connection():
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()

def aggiorna_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fatture'")
    if not cursor.fetchone():
        print("La tabella 'fatture' non esiste. Inizializzazione del database completo...")
        conn.close()
        init_db()
        return

    # Aggiunta colonne a lezioni
    try:
        cursor.execute("ALTER TABLE lezioni ADD COLUMN fatturato INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE lezioni ADD COLUMN mese_fatturato TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        print("Le colonne 'fatturato' e 'mese_fatturato' esistono già in 'lezioni'.")

    # Aggiunta colonne a archiviate
    try:
        cursor.execute("ALTER TABLE archiviate ADD COLUMN fatturato INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE archiviate ADD COLUMN mese_fatturato TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        print("Le colonne 'fatturato' e 'mese_fatturato' esistono già in 'archiviate'.")

    conn.commit()
    conn.close()
    print("Database aggiornato con successo!")

def init_db():
    """Inizializza il database con tutte le tabelle definite nello schema.sql"""
    with open(SCHEMA_PATH, 'r') as f:
        schema = f.read()
    
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(schema)
    
    # Inserisci utente admin di test (se non già presente)
    cursor = conn.cursor()
    username = "admin"
    password = "admin123"
    hashed_password = generate_password_hash(password)
    
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
        print(f"✅ Utente di test creato: {username} / {password}")
    else:
        print(f"✅ L'utente '{username}' esiste già, nessuna modifica.")
    
    conn.commit()
    conn.close()
    print(f"✅ Database inizializzato con successo: {DB_PATH}")
    print("✅ Tutte le tabelle sono state create secondo lo schema.sql")

# --- Avvio principale ---
if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"Il database non esiste. Creazione di un nuovo database: {DB_PATH}")
        init_db()
    else:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fatture'")
        if not cursor.fetchone():
            print("La tabella 'fatture' non esiste. Inizializzazione del database completo...")
            conn.close()
            init_db()
        else:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS lezioni (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_corso TEXT NOT NULL,
                materia TEXT NOT NULL,
                data TEXT NOT NULL,
                ora_inizio TEXT NOT NULL,
                ora_fine TEXT NOT NULL,
                luogo TEXT NOT NULL,
                compenso_orario REAL NOT NULL,
                stato TEXT NOT NULL,
                fatturato INTEGER DEFAULT 0,
                mese_fatturato TEXT DEFAULT NULL
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS archiviate (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                id_corso TEXT NOT NULL,
                materia TEXT NOT NULL,
                data TEXT NOT NULL,
                ora_inizio TEXT NOT NULL,
                ora_fine TEXT NOT NULL,
                luogo TEXT NOT NULL,
                compenso_orario REAL NOT NULL,
                stato TEXT NOT NULL,
                fatturato INTEGER DEFAULT 0,
                mese_fatturato TEXT DEFAULT NULL
            )
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
            """)

            # Inserisci utente admin di test (se non già presente)
            username = "admin"
            password = "admin123"
            hashed_password = generate_password_hash(password)

            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            if cursor.fetchone() is None:
                cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
                print(f"Utente di test creato: {username} / {password}")
            else:
                print(f"L'utente '{username}' esiste già, nessuna modifica.")

            conn.commit()
            conn.close()
            print("✅ Database pronto: tutte le tabelle verificate.")
