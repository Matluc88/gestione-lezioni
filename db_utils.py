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
