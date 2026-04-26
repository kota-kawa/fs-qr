import hmac

from werkzeug.security import check_password_hash, generate_password_hash

_HASH_PREFIXES = ("scrypt:", "pbkdf2:", "argon2:", "bcrypt:")


def hash_password(password: str) -> str:
    return generate_password_hash(password, method="scrypt")


def is_password_hashed(stored_password: str | None) -> bool:
    if not isinstance(stored_password, str):
        return False
    return stored_password.startswith(_HASH_PREFIXES)


def verify_password(stored_password: str | None, provided_password: str | None) -> bool:
    if not isinstance(stored_password, str) or not isinstance(provided_password, str):
        return False
    if is_password_hashed(stored_password):
        try:
            return check_password_hash(stored_password, provided_password)
        except ValueError:
            return False
    return hmac.compare_digest(stored_password, provided_password)


def needs_hash_upgrade(stored_password: str | None) -> bool:
    return isinstance(stored_password, str) and not is_password_hashed(stored_password)
