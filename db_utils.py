import os
from dotenv import load_dotenv

load_dotenv()

USE_POSTGRES = os.environ.get("DATABASE_URL") and "postgresql" in os.environ.get("DATABASE_URL")

if USE_POSTGRES:
    from database_postgres import db_connection, get_db_connection
else:
    from database import db_connection, get_db_connection

def get_placeholder():
    """Restituisce il placeholder corretto per il database in uso (%s per PostgreSQL, ? per SQLite)"""
    return "%s" if USE_POSTGRES else "?"

def get_group_concat_function():
    """Restituisce la funzione di concatenazione di gruppo corretta per il database in uso (string_agg per PostgreSQL, GROUP_CONCAT per SQLite)"""
    return "string_agg" if USE_POSTGRES else "GROUP_CONCAT"
