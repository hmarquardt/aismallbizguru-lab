from argon2 import hash_password as _hash_password, verify_password as _verify_password


def hash_password(password: str) -> str:
    return _hash_password(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _verify_password(password, password_hash)
        return True
    except Exception:
        return False