from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.routes import router
from app.core.config import validate_security_settings
from app.db.base import Base
from app.db.session import engine
from app.models import models  # noqa: F401

@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_security_settings()
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="VibeLedger", lifespan=lifespan)
app.include_router(router)
