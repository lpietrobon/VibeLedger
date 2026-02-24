from pydantic import BaseModel
import os


class Settings(BaseModel):
    app_name: str = "VibeLedger"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./vibeledger.db")

    plaid_client_id: str | None = os.getenv("PLAID_CLIENT_ID")
    plaid_secret: str | None = os.getenv("PLAID_SECRET")
    plaid_env: str = os.getenv("PLAID_ENV", "sandbox")


settings = Settings()
