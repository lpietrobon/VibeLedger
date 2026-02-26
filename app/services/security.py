from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings


def _get_fernet() -> Fernet:
    key = settings.token_encryption_key
    if not key:
        raise ValueError("TOKEN_ENCRYPTION_KEY is required")
    return Fernet(key.encode("utf-8"))


def encrypt_token(token: str) -> str:
    f = _get_fernet()
    return f.encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(token_encrypted: str) -> str:
    f = _get_fernet()
    try:
        return f.decrypt(token_encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        raise ValueError("failed to decrypt token") from e
