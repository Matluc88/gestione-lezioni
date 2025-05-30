import os
import psycopg2
from psycopg2.extras import DictCursor
from contextlib import contextmanager
from flask_bcrypt import generate_password_hash
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("La variabile d'ambiente DATABASE_URL non è impostata")

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "fatture")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    """Crea una connessione al database PostgreSQL"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.cursor_factory = DictCursor
    return conn

@contextmanager
def db_connection():
    """Context manager per la connessione al database"""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Inizializza il database con le tabelle necessarie"""
    print("Inizializzazione del database PostgreSQL...")
    
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema_postgres.sql")
    with open(schema_path, 'r') as f:
        schema = f.read()
    
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(schema)
        
        cursor.execute("SELECT * FROM users WHERE username = %s", ("admin",))
        if cursor.fetchone() is None:
            username = "admin"
            password = "admin123"
            hashed_password = generate_password_hash(password).decode('utf-8')
            cursor.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (username, hashed_password)
            )
            print(f"✅ Utente di test creato: {username} / {password}")
        else:
            print("✅ L'utente 'admin' esiste già, nessuna modifica.")
        
        conn.commit()
    
    print("✅ Database PostgreSQL inizializzato con successo!")

def ensure_database():
    """Verifica e crea tutte le tabelle necessarie nel database"""
    with db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'lezioni'
            )
        """)
        
        if not cursor.fetchone()[0]:
            print("La tabella 'lezioni' non esiste. Inizializzazione del database completo...")
            init_db()
            return
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = 'lezioni' AND column_name = 'ore_fatturate'
            )
        """)
        
        if not cursor.fetchone()[0]:
            print("La colonna 'ore_fatturate' non esiste nella tabella 'lezioni'. Aggiunta in corso...")
            cursor.execute("ALTER TABLE lezioni ADD COLUMN ore_fatturate REAL DEFAULT 0")
            
            cursor.execute("""
                UPDATE lezioni 
                SET ore_fatturate = calcola_ore(ora_inizio, ora_fine)
                WHERE fatturato = 1
            """)
            
            print("✅ Colonna 'ore_fatturate' aggiunta con successo alla tabella 'lezioni'")
        
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = 'archiviate' AND column_name = 'ore_fatturate'
            )
        """)
        
        if not cursor.fetchone()[0]:
            print("La colonna 'ore_fatturate' non esiste nella tabella 'archiviate'. Aggiunta in corso...")
            cursor.execute("ALTER TABLE archiviate ADD COLUMN ore_fatturate REAL DEFAULT 0")
            
            cursor.execute("""
                UPDATE archiviate 
                SET ore_fatturate = calcola_ore(ora_inizio, ora_fine)
                WHERE fatturato = 1
            """)
            
            print("✅ Colonna 'ore_fatturate' aggiunta con successo alla tabella 'archiviate'")
        
        # Verifica e aggiunge la colonna numero_fattura alla tabella fatture
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = 'fatture' AND column_name = 'numero_fattura'
            )
        """)
        
        if not cursor.fetchone()[0]:
            print("La colonna 'numero_fattura' non esiste nella tabella 'fatture'. Aggiunta in corso...")
            cursor.execute("ALTER TABLE fatture ADD COLUMN numero_fattura TEXT")
            
            # Inizializza numero_fattura con id_fattura per le fatture esistenti
            cursor.execute("""
                UPDATE fatture 
                SET numero_fattura = id_fattura::TEXT
                WHERE numero_fattura IS NULL
            """)
            
            # Aggiunge il vincolo UNIQUE
            cursor.execute("ALTER TABLE fatture ADD CONSTRAINT numero_fattura_unique UNIQUE (numero_fattura)")
            
            print("✅ Colonna 'numero_fattura' aggiunta con successo alla tabella 'fatture'")
        
        conn.commit()
    
    print("✅ Database verificato e aggiornato con successo!")

if __name__ == "__main__":
    ensure_database()
