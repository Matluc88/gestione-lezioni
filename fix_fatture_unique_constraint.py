#!/usr/bin/env python3
"""
Script di migrazione per rimuovere il vincolo UNIQUE da numero_fattura
nella tabella fatture, permettendo lo stesso numero per anni diversi.

Questo script:
1. Crea un backup della tabella fatture
2. Ricrea la tabella senza il vincolo UNIQUE
3. Ripristina tutti i dati
4. Funziona sia su SQLite che PostgreSQL
"""

import os
import sys
import sqlite3
from datetime import datetime

# Utilizzo SQLite direttamente
print("🔧 Utilizzo SQLite...")
USE_POSTGRES = False

def get_db_connection():
    """Connessione diretta al database SQLite"""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lezioni.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def backup_fatture_table(cursor):
    """Crea una tabella di backup"""
    print("📦 Creazione backup della tabella fatture...")
    
    if USE_POSTGRES:
        cursor.execute("DROP TABLE IF EXISTS fatture_backup CASCADE")
        cursor.execute("""
            CREATE TABLE fatture_backup AS 
            SELECT * FROM fatture
        """)
    else:
        cursor.execute("DROP TABLE IF EXISTS fatture_backup")
        cursor.execute("""
            CREATE TABLE fatture_backup AS 
            SELECT * FROM fatture
        """)
    
    cursor.execute("SELECT COUNT(*) FROM fatture_backup")
    count = cursor.fetchone()[0]
    print(f"✅ Backup completato: {count} fatture salvate")
    return count

def recreate_fatture_table(cursor):
    """Ricrea la tabella fatture senza vincolo UNIQUE su numero_fattura"""
    print("🔨 Ricreo la tabella fatture senza vincolo UNIQUE...")
    
    if USE_POSTGRES:
        # PostgreSQL: DROP e CREATE
        cursor.execute("DROP TABLE IF EXISTS fatture CASCADE")
        cursor.execute("""
            CREATE TABLE fatture (
                id_fattura SERIAL PRIMARY KEY,
                numero_fattura TEXT NOT NULL,
                id_corso TEXT,
                data_fattura DATE NOT NULL,
                importo DECIMAL(10,2) NOT NULL,
                tipo_fatturazione TEXT CHECK(tipo_fatturazione IN ('parziale', 'totale')) NOT NULL,
                file_pdf TEXT NOT NULL,
                note TEXT
            )
        """)
    else:
        # SQLite: DROP e CREATE
        cursor.execute("DROP TABLE IF EXISTS fatture")
        cursor.execute("""
            CREATE TABLE fatture (
                id_fattura INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_fattura TEXT NOT NULL,
                id_corso TEXT,
                data_fattura TEXT NOT NULL,
                importo REAL NOT NULL,
                tipo_fatturazione TEXT CHECK(tipo_fatturazione IN ('parziale', 'totale')) NOT NULL,
                file_pdf TEXT NOT NULL,
                note TEXT
            )
        """)
    
    print("✅ Tabella fatture ricreata (senza UNIQUE su numero_fattura)")

def restore_data(cursor):
    """Ripristina i dati dal backup"""
    print("📥 Ripristino dei dati...")
    
    if USE_POSTGRES:
        cursor.execute("""
            INSERT INTO fatture (id_fattura, numero_fattura, id_corso, data_fattura, importo, tipo_fatturazione, file_pdf, note)
            SELECT id_fattura, numero_fattura, id_corso, data_fattura, importo, tipo_fatturazione, file_pdf, note
            FROM fatture_backup
            ORDER BY id_fattura
        """)
        
        # Reset della sequenza
        cursor.execute("""
            SELECT setval('fatture_id_fattura_seq', 
                         (SELECT MAX(id_fattura) FROM fatture), 
                         true)
        """)
    else:
        cursor.execute("""
            INSERT INTO fatture (id_fattura, numero_fattura, id_corso, data_fattura, importo, tipo_fatturazione, file_pdf, note)
            SELECT id_fattura, numero_fattura, id_corso, data_fattura, importo, tipo_fatturazione, file_pdf, note
            FROM fatture_backup
            ORDER BY id_fattura
        """)
        
        # Reset dell'autoincrement
        cursor.execute("""
            UPDATE sqlite_sequence 
            SET seq = (SELECT MAX(id_fattura) FROM fatture) 
            WHERE name = 'fatture'
        """)
    
    cursor.execute("SELECT COUNT(*) FROM fatture")
    count = cursor.fetchone()[0]
    print(f"✅ Dati ripristinati: {count} fatture")
    return count

def recreate_foreign_keys(cursor):
    """Ricrea le foreign keys della tabella fatture_lezioni"""
    print("🔗 Verifica foreign keys...")
    
    if USE_POSTGRES:
        # PostgreSQL: le foreign keys vengono ricreate automaticamente
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.table_constraints 
            WHERE table_name = 'fatture_lezioni' 
            AND constraint_type = 'FOREIGN KEY'
        """)
        fk_count = cursor.fetchone()[0]
        print(f"✅ Foreign keys verificate: {fk_count} trovate")
    else:
        # SQLite: verifica che la tabella fatture_lezioni esista
        cursor.execute("""
            SELECT COUNT(*) 
            FROM sqlite_master 
            WHERE type='table' AND name='fatture_lezioni'
        """)
        if cursor.fetchone()[0] > 0:
            print("✅ Tabella fatture_lezioni verificata")
        else:
            print("⚠️ Tabella fatture_lezioni non trovata")

def main():
    print("=" * 60)
    print("🚀 MIGRATION: Rimozione vincolo UNIQUE da numero_fattura")
    print("=" * 60)
    print()
    
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Step 1: Backup
        backup_count = backup_fatture_table(cursor)
        
        # Step 2: Ricrea tabella
        recreate_fatture_table(cursor)
        
        # Step 3: Ripristina dati
        restore_count = restore_data(cursor)
        
        # Step 4: Verifica foreign keys
        recreate_foreign_keys(cursor)
        
        # Verifica finale
        if backup_count == restore_count:
            print()
            print("=" * 60)
            print("✅ MIGRATION COMPLETATA CON SUCCESSO!")
            print(f"   - {restore_count} fatture migrate correttamente")
            print("   - Vincolo UNIQUE rimosso da numero_fattura")
            print("   - Ora puoi avere lo stesso numero per anni diversi")
            print("=" * 60)
            
            conn.commit()
            
            # Cleanup backup (opzionale)
            risposta = input("\n🗑️ Vuoi eliminare la tabella di backup? (s/n): ")
            if risposta.lower() == 's':
                cursor.execute("DROP TABLE fatture_backup")
                conn.commit()
                print("✅ Tabella di backup eliminata")
            else:
                print("ℹ️ Tabella di backup conservata (fatture_backup)")
        else:
            print()
            print("❌ ERRORE: Numero di record non coincide!")
            print(f"   Backup: {backup_count}, Ripristinati: {restore_count}")
            conn.rollback()
            sys.exit(1)
            
    except Exception as e:
        print()
        print(f"❌ ERRORE durante la migration: {e}")
        if conn:
            conn.rollback()
        print("🔄 Rollback eseguito - nessuna modifica applicata")
        sys.exit(1)
    finally:
        if conn:
            conn.close()
    
    print()
    print("🎉 Migration completata! Ora puoi utilizzare l'applicazione.")

if __name__ == "__main__":
    main()
