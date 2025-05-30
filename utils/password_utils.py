from werkzeug.security import check_password_hash as werkzeug_check_password_hash
from flask_bcrypt import check_password_hash as bcrypt_check_password_hash, generate_password_hash

def hybrid_check_password_hash(pw_hash, password):
    """
    Check password hash using either Werkzeug or Bcrypt based on hash format.
    Also handles migration from Werkzeug to Bcrypt format.
    
    Args:
        pw_hash: The stored password hash
        password: The plaintext password to verify
        
    Returns:
        bool: True if password matches, False otherwise
    """
    if pw_hash.startswith('pbkdf2:sha256:') or pw_hash.startswith('scrypt:'):
        return werkzeug_check_password_hash(pw_hash, password)
    else:
        try:
            return bcrypt_check_password_hash(pw_hash, password)
        except ValueError:
            return False

def rehash_password_if_needed(user_id, current_hash, password):
    """
    Rehash password using Bcrypt if it's currently in Werkzeug format
    
    Args:
        user_id: The user ID
        current_hash: The current password hash
        password: The plaintext password (only used if rehashing is needed)
        
    Returns:
        bool: True if password was rehashed, False otherwise
    """
    if current_hash.startswith('pbkdf2:sha256:') or current_hash.startswith('scrypt:'):
        from db_utils import db_connection, get_placeholder
        
        new_hash = generate_password_hash(password).decode('utf-8')
        
        with db_connection() as conn:
            cursor = conn.cursor()
            placeholder = get_placeholder()
            cursor.execute(
                f"UPDATE users SET password = {placeholder} WHERE id = {placeholder}",
                (new_hash, user_id)
            )
            conn.commit()
        
        print(f"✅ Password rehashed for user ID {user_id} from Werkzeug to Bcrypt format")
        return True
    
    return False
