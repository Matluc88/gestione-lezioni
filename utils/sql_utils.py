"""
Utility functions for SQL operations
"""

def sanitize_sql_identifier(identifier):
    """
    Sanitize a string to be used as a SQL identifier (table name, column name, savepoint name, etc.)
    
    Args:
        identifier (str): The identifier to sanitize
        
    Returns:
        str: A sanitized identifier safe to use in SQL statements
    """
    if not identifier:
        return "unknown"
        
    sanitized = identifier.replace(" ", "_")
    sanitized = sanitized.replace("-", "_")
    sanitized = sanitized.replace(".", "_")
    sanitized = sanitized.replace("'", "")
    sanitized = sanitized.replace('"', "")
    sanitized = sanitized.replace("(", "")
    sanitized = sanitized.replace(")", "")
    sanitized = sanitized.replace("/", "_")
    sanitized = sanitized.replace("\\", "_")
    sanitized = sanitized.replace(":", "_")
    sanitized = sanitized.replace(";", "_")
    sanitized = sanitized.replace(",", "_")
    sanitized = sanitized.replace("&", "_and_")
    sanitized = sanitized.replace("@", "_at_")
    sanitized = sanitized.replace("!", "_")
    sanitized = sanitized.replace("?", "_")
    sanitized = sanitized.replace("=", "_eq_")
    sanitized = sanitized.replace("+", "_plus_")
    sanitized = sanitized.replace("*", "_star_")
    sanitized = sanitized.replace("%", "_pct_")
    sanitized = sanitized.replace("#", "_num_")
    
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
        
    if sanitized and not (sanitized[0].isalpha() or sanitized[0] == '_'):
        sanitized = "id_" + sanitized
        
    return sanitized
