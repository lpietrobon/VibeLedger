from fastapi import FastAPI
from app.api.routes import router
from app.core.config import validate_security_settings
from app.db.base import Base
from app.db.session import engine
from app.models import models  # noqa: F401

app = FastAPI(title="VibeLedger")
app.include_router(router)


@app.on_event("startup")
def startup():
    validate_security_settings()
    Base.metadata.create_all(bind=engine)
