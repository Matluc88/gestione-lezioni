import os
import sqlite3
from flask_bcrypt import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lezioni.db")
print(f"Percorso database: {DB_PATH}")

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "fatture")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
print(f"✅ Cartella per le fatture creata: {UPLOAD_FOLDER}")

def ensure_database():
    """Verifica e crea tutte le tabelle necessarie nel database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lezioni'")
    if not cursor.fetchone():
        print("Creazione della tabella 'lezioni'...")
        cursor.execute("""
        CREATE TABLE lezioni (
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
            mese_fatturato TEXT DEFAULT NULL,
            ore_fatturate REAL DEFAULT 0
        )
        """)
        print("✅ Tabella 'lezioni' creata con successo")
    else:
        print("✅ La tabella 'lezioni' esiste già")
        
        cursor.execute("PRAGMA table_info(lezioni)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        if 'ore_fatturate' not in column_names:
            print("La colonna 'ore_fatturate' non esiste nella tabella 'lezioni'. Aggiunta in corso...")
            cursor.execute("ALTER TABLE lezioni ADD COLUMN ore_fatturate REAL DEFAULT 0")
            
            cursor.execute("""
                UPDATE lezioni 
                SET ore_fatturate = (
                    (strftime('%s', '2000-01-01 ' || substr('0' || ora_fine, -5)) - 
                    strftime('%s', '2000-01-01 ' || substr('0' || ora_inizio, -5))
                ) / 3600.0
                WHERE fatturato = 1
            """)
            print("✅ Colonna 'ore_fatturate' aggiunta con successo alla tabella 'lezioni'")
        else:
            print("✅ La tabella 'lezioni' esiste già con la colonna 'ore_fatturate'")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='archiviate'")
    if not cursor.fetchone():
        print("Creazione della tabella 'archiviate'...")
        cursor.execute("""
        CREATE TABLE archiviate (
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
            mese_fatturato TEXT DEFAULT NULL,
            ore_fatturate REAL DEFAULT 0
        )
        """)
        print("✅ Tabella 'archiviate' creata con successo")
    else:
        print("✅ La tabella 'archiviate' esiste già")
        
        cursor.execute("PRAGMA table_info(archiviate)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        if 'ore_fatturate' not in column_names:
            print("La colonna 'ore_fatturate' non esiste nella tabella 'archiviate'. Aggiunta in corso...")
            cursor.execute("ALTER TABLE archiviate ADD COLUMN ore_fatturate REAL DEFAULT 0")
            
            cursor.execute("""
                UPDATE archiviate 
                SET ore_fatturate = (
                    (strftime('%s', '2000-01-01 ' || substr('0' || ora_fine, -5)) - 
                    strftime('%s', '2000-01-01 ' || substr('0' || ora_inizio, -5))
                ) / 3600.0
                WHERE fatturato = 1
            """)
            print("✅ Colonna 'ore_fatturate' aggiunta con successo alla tabella 'archiviate'")
        else:
            print("✅ La tabella 'archiviate' esiste già con la colonna 'ore_fatturate'")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fatture'")
    if not cursor.fetchone():
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
        print("✅ Tabella 'fatture' creata con successo")
    else:
        print("✅ La tabella 'fatture' esiste già")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fatture_lezioni'")
    if not cursor.fetchone():
        print("Creazione della tabella 'fatture_lezioni'...")
        cursor.execute("""
        CREATE TABLE fatture_lezioni (
            id_fattura INTEGER,
            id_lezione INTEGER,
            FOREIGN KEY (id_fattura) REFERENCES fatture (id_fattura),
            FOREIGN KEY (id_lezione) REFERENCES lezioni (id)
        )
        """)
        print("✅ Tabella 'fatture_lezioni' creata con successo")
    else:
        print("✅ La tabella 'fatture_lezioni' esiste già")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='corsi'")
    if not cursor.fetchone():
        print("Creazione della tabella 'corsi'...")
        cursor.execute("""
        CREATE TABLE corsi (
            id_corso TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            cliente TEXT DEFAULT NULL
        )
        """)
        print("✅ Tabella 'corsi' creata con successo")
    else:
        cursor.execute("PRAGMA table_info(corsi)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        if 'cliente' not in column_names:
            print("La colonna 'cliente' non esiste nella tabella 'corsi'. Aggiunta in corso...")
            cursor.execute("ALTER TABLE corsi ADD COLUMN cliente TEXT DEFAULT NULL")
            print("✅ Colonna 'cliente' aggiunta con successo alla tabella 'corsi'")
        else:
            print("✅ La tabella 'corsi' esiste già con la colonna 'cliente'")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='corsi_archiviati'")
    if not cursor.fetchone():
        print("Creazione della tabella 'corsi_archiviati'...")
        cursor.execute("""
        CREATE TABLE corsi_archiviati (
            id_corso TEXT PRIMARY KEY,
            nome TEXT NOT NULL,
            cliente TEXT DEFAULT NULL,
            data_archiviazione TEXT NOT NULL
        )
        """)
        print("✅ Tabella 'corsi_archiviati' creata con successo")
    else:
        cursor.execute("PRAGMA table_info(corsi_archiviati)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        if 'cliente' not in column_names:
            print("La colonna 'cliente' non esiste nella tabella 'corsi_archiviati'. Aggiunta in corso...")
            cursor.execute("ALTER TABLE corsi_archiviati ADD COLUMN cliente TEXT DEFAULT NULL")
            print("✅ Colonna 'cliente' aggiunta con successo alla tabella 'corsi_archiviati'")
        else:
            print("✅ La tabella 'corsi_archiviati' esiste già con la colonna 'cliente'")
    
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
        print("✅ Tabella 'users' creata con successo")
    else:
        print("✅ La tabella 'users' esiste già")
        
        cursor.execute("SELECT * FROM users WHERE username = ?", ("admin",))
        if not cursor.fetchone():
            username = "admin"
            password = "admin123"
            hashed_password = generate_password_hash(password)
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            print(f"✅ Utente di test creato: {username} / {password}")
    
    conn.commit()
    conn.close()
    print(f"✅ Database verificato e aggiornato con successo: {DB_PATH}")
    print("✅ Tutte le tabelle necessarie sono state verificate o create.")

if __name__ == "__main__":
    ensure_database()
