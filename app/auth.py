import hashlib
import secrets
from datetime import datetime, timedelta, timezone


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000).hex()
    return f"{salt}:{h}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":", 1)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000).hex()
    return secrets.compare_digest(candidate, h)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def session_expires_at() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
