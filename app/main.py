import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import router
from app.core.auth import BearerAuthMiddleware
from app.core.config import settings, validate_security_settings
from app.db.base import Base
from app.db.schema_patches import apply_patches
from app.db.session import engine
from app.models import models  # noqa: F401
from app.services.scheduler import scheduled_sync_loop


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_security_settings()
    Base.metadata.create_all(bind=engine)
    apply_patches(engine)
    sync_task = asyncio.create_task(scheduled_sync_loop())
    yield
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


app = FastAPI(title="VibeLedger", lifespan=lifespan)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BearerAuthMiddleware, token=settings.api_token)
if settings.allowed_hosts:
    from starlette.middleware.trustedhost import TrustedHostMiddleware

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts.split(","))
app.include_router(router)

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"

if FRONTEND_INDEX.exists():
    app.mount(
        "/frontend/assets",
        StaticFiles(directory=FRONTEND_DIST / "assets"),
        name="frontend-assets",
    )

    @app.get("/frontend", include_in_schema=False)
    @app.get("/frontend/{_:path}", include_in_schema=False)
    def frontend_app() -> FileResponse:
        return FileResponse(FRONTEND_INDEX)
