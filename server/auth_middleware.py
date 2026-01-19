"""
Authentication Middleware for MCP Server

Provides API key-based authentication via Authorization header.
Format: Authorization: Bearer <api_key>

Also extracts session and client identifiers for feedback system tracking.
"""

import logging
import hashlib
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

    def _extract_session_id(self, request: Request) -> str:
        """
        Extract or generate session ID from request.

        Session ID sources (in priority order):
        1. X-Session-Id header (if client provides)
        2. Connection ID from MCP transport
        3. Hash of client IP + User-Agent (fallback)
        4. Generate UUID (last resort)

        Returns stable session ID for tracking purposes.
        """
        # Check for explicit session header
        session_header = request.headers.get("x-session-id")
        if session_header:
            return session_header[:64]  # Truncate for safety

        # Try to extract from MCP connection context
        # MCP typically provides connection metadata
        connection_id = request.headers.get("x-connection-id")
        if connection_id:
            return connection_id[:64]

        # Fallback: Create stable session from client fingerprint
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")

        # Create deterministic session ID from IP + User-Agent
        fingerprint = f"{client_ip}:{user_agent}"
        session_hash = hashlib.sha256(fingerprint.encode()).hexdigest()[:32]

        return f"fp_{session_hash}"

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

        # Extract session ID for tracking
        session_id = self._extract_session_id(request)

        # Store authentication and tracking info in request.state
        request.state.client_name = client_name
        request.state.client_id = client_name  # Use client_name as client_id
        request.state.session_id = session_id

        # SUCCESS
        logger.info(f"[AUTH] ✅ Authenticated client: {client_name} | session: {session_id[:16]}... → {path}")

        return await call_next(request)
