import os
import tempfile

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()

os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp.name}")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
os.environ.setdefault("PLAID_USE_MOCK", "true")
os.environ.setdefault("VIBELEDGER_API_TOKEN", "test-token")

import pytest

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

settings.token_encryption_key = os.environ["TOKEN_ENCRYPTION_KEY"]
settings.plaid_use_mock = True
settings.api_token = os.environ["VIBELEDGER_API_TOKEN"]


AUTH_HEADERS = {"Authorization": f"Bearer {os.environ['VIBELEDGER_API_TOKEN']}"}


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
