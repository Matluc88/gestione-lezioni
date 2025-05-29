import os
from dotenv import load_dotenv
from database_postgres import db_connection, init_db, ensure_database

load_dotenv()

def ensure_postgres_database():
    """Verifica e crea tutte le tabelle necessarie nel database PostgreSQL"""
    print("Verifica e inizializzazione del database PostgreSQL...")
    
    if not os.environ.get("DATABASE_URL"):
        raise ValueError("La variabile d'ambiente DATABASE_URL non è impostata")
    
    ensure_database()
    
    print("✅ Database PostgreSQL verificato e aggiornato con successo!")

if __name__ == "__main__":
    ensure_postgres_database()
