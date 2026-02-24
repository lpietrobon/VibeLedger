import base64


def encrypt_token(token: str) -> str:
    return base64.b64encode(token.encode("utf-8")).decode("utf-8")


def decrypt_token(token_encrypted: str) -> str:
    return base64.b64decode(token_encrypted.encode("utf-8")).decode("utf-8")
