import os
import sqlite3
from flask_bcrypt import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lezioni.db")

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "fatture")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
print(f"✅ Cartella per le fatture creata: {UPLOAD_FOLDER}")

def init_db():
    """Inizializza il database con tutte le tabelle definite nello schema.sql"""
    with open(SCHEMA_PATH, 'r') as f:
        schema = f.read()
    
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(schema)
    
    cursor = conn.cursor()
    username = os.environ.get("DEFAULT_ADMIN_USERNAME", "admin")
    password = os.environ.get("DEFAULT_ADMIN_PASSWORD", "changeme")
    hashed_password = generate_password_hash(password).decode('utf-8')
    
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

if __name__ == "__main__":
    init_db()
