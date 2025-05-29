# models/user.py

from flask_login import UserMixin
from db_utils import db_connection, get_placeholder

class User(UserMixin):
    def __init__(self, id):
        self.id = id

def load_user_from_db(user_id):
    try:
        user_id_int = int(user_id)
        placeholder = get_placeholder()
        with db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM users WHERE id = {placeholder}", (user_id_int,))
            user = cursor.fetchone()
            if user:
                return User(id=user['id'])
    except Exception as e:
        print(f"Errore in load_user_from_db: {e}")
    return None
