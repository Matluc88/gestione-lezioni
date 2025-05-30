import bleach
from typing import Optional

ALLOWED_TAGS = ['b', 'i', 'u', 'em', 'strong', 'p', 'br']
ALLOWED_ATTRIBUTES = {}

def sanitize_input(input_text: Optional[str]) -> str:
    """
    Sanitize user input to prevent XSS attacks
    """
    if not input_text:
        return ""
    return bleach.clean(input_text, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)

def sanitize_form_data(form_data: dict) -> dict:
    """
    Sanitize all string values in form data
    """
    sanitized = {}
    for key, value in form_data.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_input(value)
        else:
            sanitized[key] = value
    return sanitized
