import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

_EXEMPT_PREFIXES = ("/health", "/connect/start", "/connect/complete", "/docs", "/openapi.json")


class BearerAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str):
        super().__init__(app)
        self.token = token

    async def dispatch(self, request, call_next):
        if any(request.url.path.startswith(p) for p in _EXEMPT_PREFIXES):
            return await call_next(request)
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {self.token}":
            logger.warning("auth failed: %s %s from %s", request.method, request.url.path, request.client.host if request.client else "unknown")
            return JSONResponse({"detail": "invalid or missing bearer token"}, status_code=401)
        return await call_next(request)
