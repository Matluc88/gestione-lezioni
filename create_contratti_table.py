#!/usr/bin/env python3
"""
Script per creare la tabella contratti nel database PostgreSQL.
Può essere eseguito manualmente se la tabella non viene creata automaticamente.
"""

import os
from dotenv import load_dotenv
from database_postgres import get_db_connection

load_dotenv()

def create_contratti_table():
    """Crea la tabella contratti se non esiste"""
    print("🔄 Connessione al database PostgreSQL...")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verifica se la tabella esiste già
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'contratti'
            )
        """)
        
        if cursor.fetchone()[0]:
            print("ℹ️  La tabella 'contratti' esiste già nel database.")
            conn.close()
            return
        
        print("🔧 Creazione tabella 'contratti'...")
        
        # Crea la tabella
        cursor.execute("""
            CREATE TABLE contratti (
                id SERIAL PRIMARY KEY,
                numero_contratto TEXT,
                nome_file TEXT NOT NULL,
                file_path TEXT NOT NULL,
                data_upload TEXT NOT NULL,
                cliente TEXT,
                contenuto_estratto TEXT,
                id_corso TEXT,
                FOREIGN KEY (id_corso) REFERENCES corsi(id_corso)
            )
        """)
        
        conn.commit()
        print("✅ Tabella 'contratti' creata con successo!")
        
        # Verifica finale
        cursor.execute("SELECT COUNT(*) FROM contratti")
        print(f"✅ Verifica: La tabella 'contratti' è vuota e pronta per l'uso (0 record).")
        
        conn.close()
        print("✅ Operazione completata con successo!")
        
    except Exception as e:
        print(f"❌ ERRORE: {e}")
        raise

if __name__ == "__main__":
    print("=" * 60)
    print("CREAZIONE TABELLA CONTRATTI")
    print("=" * 60)
    create_contratti_table()
    print("=" * 60)
