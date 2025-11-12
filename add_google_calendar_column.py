#!/usr/bin/env python3
"""
Migration script to add google_calendar_event_id column to lezioni and archiviate tables
"""
import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

def migrate_sqlite():
    """Add google_calendar_event_id column to SQLite database"""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lezioni.db")
    
    if not os.path.exists(db_path):
        print(f"❌ Database SQLite non trovato: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE lezioni ADD COLUMN google_calendar_event_id TEXT DEFAULT NULL")
        print("✅ Colonna 'google_calendar_event_id' aggiunta alla tabella 'lezioni'")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("ℹ️  La colonna 'google_calendar_event_id' esiste già nella tabella 'lezioni'")
        else:
            print(f"❌ Errore durante l'aggiunta della colonna a 'lezioni': {e}")
            conn.close()
            return False
    
    try:
        cursor.execute("ALTER TABLE archiviate ADD COLUMN google_calendar_event_id TEXT DEFAULT NULL")
        print("✅ Colonna 'google_calendar_event_id' aggiunta alla tabella 'archiviate'")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("ℹ️  La colonna 'google_calendar_event_id' esiste già nella tabella 'archiviate'")
        else:
            print(f"❌ Errore durante l'aggiunta della colonna a 'archiviate': {e}")
            conn.close()
            return False
    
    conn.commit()
    conn.close()
    print("✅ Migrazione SQLite completata con successo!")
    return True

def migrate_postgres():
    """Add google_calendar_event_id column to PostgreSQL database"""
    try:
        import psycopg2
        from urllib.parse import urlparse
        
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            print("❌ DATABASE_URL non configurato per PostgreSQL")
            return False
        
        result = urlparse(database_url)
        conn = psycopg2.connect(
            database=result.path[1:],
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port
        )
        cursor = conn.cursor()
        
        try:
            cursor.execute("ALTER TABLE lezioni ADD COLUMN google_calendar_event_id TEXT DEFAULT NULL")
            print("✅ Colonna 'google_calendar_event_id' aggiunta alla tabella 'lezioni'")
        except psycopg2.errors.DuplicateColumn:
            conn.rollback()
            print("ℹ️  La colonna 'google_calendar_event_id' esiste già nella tabella 'lezioni'")
        
        try:
            cursor.execute("ALTER TABLE archiviate ADD COLUMN google_calendar_event_id TEXT DEFAULT NULL")
            print("✅ Colonna 'google_calendar_event_id' aggiunta alla tabella 'archiviate'")
        except psycopg2.errors.DuplicateColumn:
            conn.rollback()
            print("ℹ️  La colonna 'google_calendar_event_id' esiste già nella tabella 'archiviate'")
        
        conn.commit()
        conn.close()
        print("✅ Migrazione PostgreSQL completata con successo!")
        return True
        
    except ImportError:
        print("❌ psycopg2 non installato, impossibile migrare PostgreSQL")
        return False
    except Exception as e:
        print(f"❌ Errore durante la migrazione PostgreSQL: {e}")
        return False

if __name__ == "__main__":
    print("=== Migrazione Database: Aggiunta colonna google_calendar_event_id ===\n")
    
    database_url = os.environ.get("DATABASE_URL")
    
    if database_url and "postgresql" in database_url:
        print("Migrazione database PostgreSQL...")
        migrate_postgres()
    else:
        print("Migrazione database SQLite...")
        migrate_sqlite()
    
    print("\n=== Migrazione completata ===")
