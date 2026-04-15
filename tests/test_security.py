"""Security regression tests for token encryption helpers."""

import pytest
from cryptography.fernet import Fernet

from app.core.config import settings
from app.services.security import decrypt_token, encrypt_token


def test_encrypt_decrypt_round_trip():
    token = "access-sandbox-123"

    encrypted = encrypt_token(token)

    assert encrypted != token
    assert decrypt_token(encrypted) == token


def test_decrypt_invalid_ciphertext_raises_value_error():
    with pytest.raises(ValueError, match="failed to decrypt token"):
        decrypt_token("not-a-valid-fernet-token")


def test_encrypt_requires_configured_key(monkeypatch):
    monkeypatch.setattr(settings, "token_encryption_key", None)

    with pytest.raises(ValueError, match="TOKEN_ENCRYPTION_KEY is required"):
        encrypt_token("abc")


def test_encrypt_rejects_malformed_key(monkeypatch):
    malformed_key = "short-and-invalid"
    monkeypatch.setattr(settings, "token_encryption_key", malformed_key)

    with pytest.raises(ValueError):
        encrypt_token("abc")


def test_encrypt_with_generated_key(monkeypatch):
    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(settings, "token_encryption_key", key)

    encrypted = encrypt_token("secret-token")

    assert decrypt_token(encrypted) == "secret-token"
