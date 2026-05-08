import hashlib
import hmac
import secrets


def generate_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    token_hash = hash_token(raw)
    return raw, token_hash


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), token_hash)


def masked_token(raw: str) -> str:
    if len(raw) <= 8:
        return "***"
    return f"{raw[:4]}...{raw[-4:]}"