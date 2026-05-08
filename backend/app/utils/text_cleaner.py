import re

def clean_text(text: str) -> str:
    """Removes extra whitespace and basic HTML tags."""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text
