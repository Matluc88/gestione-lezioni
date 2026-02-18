#!/usr/bin/env python3
"""
Script per rimuovere il vincolo UNIQUE da numero_fattura in PostgreSQL
Permette di avere lo stesso numero fattura per anni diversi
"""

import os
import psycopg2

# Leggi DATABASE_URL dal file .env
database_url = None
try:
    with open('.env', 'r') as f:
        for line in f:
            if line.startswith('DATABASE_URL='):
                database_url = line.split('=', 1)[1].strip()
                break
except:
    pass

if not database_url:
    database_url = os.environ.get('DATABASE_URL')

def get_db_connection():
    return psycopg2.connect(database_url)

def main():
    print("=" * 60)
    print("🔧 Rimozione vincolo UNIQUE da numero_fattura")
    print("=" * 60)
    print()
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print("📋 Verifico vincoli esistenti...")
        cursor.execute("""
            SELECT conname, contype 
            FROM pg_constraint 
            WHERE conrelid = 'fatture'::regclass 
              AND contype = 'u'
        """)
        vincoli = cursor.fetchall()
        
        if vincoli:
            print(f"✅ Trovati {len(vincoli)} vincoli UNIQUE:")
            for vincolo in vincoli:
                print(f"   - {vincolo[0]}")
        else:
            print("ℹ️ Nessun vincolo UNIQUE trovato")
        
        print()
        print("🔨 Rimuovo vincolo UNIQUE da numero_fattura...")
        cursor.execute("ALTER TABLE fatture DROP CONSTRAINT IF EXISTS fatture_numero_fattura_key")
        
        print()
        print("📋 Verifico vincoli dopo la rimozione...")
        cursor.execute("""
            SELECT conname, contype 
            FROM pg_constraint 
            WHERE conrelid = 'fatture'::regclass 
              AND contype = 'u'
        """)
        vincoli_dopo = cursor.fetchall()
        
        if vincoli_dopo:
            print(f"⚠️ Ancora presenti {len(vincoli_dopo)} vincoli UNIQUE:")
            for vincolo in vincoli_dopo:
                print(f"   - {vincolo[0]}")
        else:
            print("✅ Nessun vincolo UNIQUE presente - rimozione completata!")
        
        conn.commit()
        
        print()
        print("=" * 60)
        print("✅ OPERAZIONE COMPLETATA CON SUCCESSO!")
        print("   Ora puoi creare fatture con lo stesso numero in anni diversi")
        print("=" * 60)
        
    except Exception as e:
        print()
        print(f"❌ ERRORE: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    main()
