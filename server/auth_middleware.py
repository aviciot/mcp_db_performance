"""
Authentication Middleware for MCP Server

Provides API key-based authentication via Authorization header.
Format: Authorization: Bearer <api_key>
"""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.requests import Request

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    API Key Authentication Middleware
    """

    def __init__(self, app, config):
        super().__init__(app)
        self.config = config

        # Prefix matching so /health, /healthz, /health/deep all work
        self.public_path_prefixes = (
            "/health",
            "/healthz",
            "/version",
            "/_info",
        )

        logger.info(
            "AuthMiddleware initialized | enabled=%s | api_keys=%d | public_prefixes=%s",
            self.config.auth_enabled,
            len(self.config.api_keys),
            self.public_path_prefixes,
        )

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Auth disabled
        if not self.config.auth_enabled:
            return await call_next(request)

        # Public endpoints
        if path.startswith(self.public_path_prefixes):
            return await call_next(request)

        # Authorization header
        auth_header = request.headers.get("authorization")
        if not auth_header:
            logger.warning(f"[AUTH] Missing Authorization header from {request.client.host} for path: {path}")
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Authentication required",
                    "message": "Missing Authorization header. Use: Authorization: Bearer <api_key>",
                },
            )

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            logger.warning(f"[AUTH] Invalid Authorization format from {request.client.host} for path: {path}")
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid Authorization format. Use: Authorization: Bearer <api_key>"},
            )

        api_key = parts[1]

        client_name = self.config.api_keys.get(api_key)
        if not client_name:
            logger.warning(f"[AUTH] Invalid API key from {request.client.host} for path: {path}")
            return JSONResponse(status_code=401, content={"error": "Invalid API key"})

        # SUCCESS
        logger.info(f"[AUTH] ✅ Authenticated client: {client_name} → {path}")
        request.state.client_name = client_name

        return await call_next(request)
