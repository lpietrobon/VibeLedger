import os

import pytest

# Ensure required security settings exist before app import/startup in tests.
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
os.environ.setdefault("CONNECT_SIGNING_KEY", "test-connect-signing-key-32chars-min")

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

settings.token_encryption_key = os.environ["TOKEN_ENCRYPTION_KEY"]
settings.connect_signing_key = os.environ["CONNECT_SIGNING_KEY"]


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
