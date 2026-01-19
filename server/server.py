"""
Performance MCP Server - Starlette Application
=============================================
MCP Performance server with authentication middleware, auto-discovery,
DB connectivity checks, and FastMCP HTTP transport.
"""

import os
import sys
import signal
import logging
import importlib
import pkgutil
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.requests import Request
import uvicorn

from config import config
from mcp_app import mcp
from auth_middleware import AuthMiddleware

import db_connector
from db_connector import oracle_connector

# -------------------------------------------------------------
# Logging
# -------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("server")

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("fastmcp").setLevel(logging.WARNING)

# -------------------------------------------------------------
# TEMP DEBUG: PRINT AUTH TOKENS (REMOVE LATER)
# -------------------------------------------------------------
if config.auth_enabled:
    logger.warning("🚨 DEBUG: AUTHENTICATION ENABLED — PRINTING TOKENS (REMOVE THIS LATER)")
    for token, name in config.api_keys.items():
        logger.warning("🔑 API KEY LOADED | name=%s | token=%s", name, token)
else:
    logger.warning("🔓 DEBUG: AUTHENTICATION DISABLED")

# -------------------------------------------------------------
# Graceful Shutdown
# -------------------------------------------------------------
def _graceful_shutdown(*_):
    logger.info("🛑 Received shutdown signal. Shutting down gracefully...")
    # Knowledge DB cleanup now handled by lifespan context manager
    logger.info("✅ Graceful shutdown complete")
    sys.exit(0)

for sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(sig, _graceful_shutdown)

# -------------------------------------------------------------
# Auto-discovery
# -------------------------------------------------------------
AUTO_DISCOVER = os.getenv("AUTO_DISCOVER", "true").lower() in ("1", "true", "yes", "on")

def import_submodules(pkg_name: str):
    try:
        pkg = __import__(pkg_name)
    except ModuleNotFoundError:
        logger.warning(f"⚠️ Package not found: {pkg_name}")
        return

    if not hasattr(pkg, "__path__"):
        logger.warning(f"⚠️ {pkg_name} is not a package")
        return

    for _, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
        if not ispkg:
            full_name = f"{pkg_name}.{modname}"
            importlib.import_module(full_name)
            logger.info(f"📦 Auto-imported: {full_name}")

def safe_import(name: str):
    module = __import__(name, fromlist=["*"])
    logger.info(f"✅ Imported: {name}")
    return module

# -------------------------------------------------------------
# Startup Banner
# -------------------------------------------------------------
print("=" * 70)
print(f"🚀 MCP Server Starting: {config.server_name}")
print("=" * 70)
print("📦 Loading Tools, Resources, Prompts...")

if AUTO_DISCOVER:
    logger.info("🧠 Auto-discovery enabled — scanning modules.")
    for pkg in ("tools", "resources", "prompts"):
        import_submodules(pkg)
else:
    logger.info("🧩 Auto-discovery disabled — using static imports.")
    for pkg in ("tools", "resources", "prompts"):
        safe_import(pkg)

print("=" * 70)

# -------------------------------------------------------------
# DB Connectivity Test (Optional) — PARALLEL with better visibility
# -------------------------------------------------------------
if getattr(config, 'check_db_connections', False):
    logger.info("🔍 Starting parallel DB connectivity tests...\n")

    oracle_dbs = []
    mysql_dbs = []
    other_dbs = []

    for preset_name, preset_config in config.database_presets.items():
        db_type = preset_config.get("type", "oracle").lower()
        if db_type == "oracle":
            oracle_dbs.append(preset_name)
        elif db_type in ("mysql", "mariadb"):
            mysql_dbs.append(preset_name)
        else:
            other_dbs.append(preset_name)

    all_dbs = oracle_dbs + mysql_dbs + other_dbs

    if not all_dbs:
        logger.info("ℹ️  No databases configured to test.")
    else:
        logger.info(f"Testing {len(all_dbs)} database preset(s) in parallel "
                    f"(max {min(8, len(all_dbs))} workers)")
        if oracle_dbs:
            logger.info(f"  Oracle: {', '.join(oracle_dbs)}")
        if mysql_dbs:
            logger.info(f"  MySQL:  {', '.join(mysql_dbs)}")
        if other_dbs:
            logger.info(f"  Other:  {', '.join(other_dbs)}")
        print("")
        success_count = 0
        failed = []
        def check_db(db_name: str):
            ok = db_connector.test_connection(db_name)
            return db_name, ok
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=min(8, len(all_dbs) or 1)) as pool:
            futures = {pool.submit(check_db, db): db for db in all_dbs}
            for future in as_completed(futures):
                db_name = futures[future]
                try:
                    db_name, ok = future.result()
                    if ok:
                        success_count += 1
                        logger.info(f"  ✅ {db_name:<24} Connected successfully")
                    else:
                        failed.append(db_name)
                        logger.warning(f"  ❌ {db_name:<24} Connection FAILED")
                except Exception as e:
                    failed.append(db_name)
                    logger.error(f"  💥 {db_name:<24} Check crashed → {e}")
        print("")
        total = len(all_dbs)
        logger.info("-" * 60)
        logger.info(f" Database connectivity summary:")
        logger.info(f"   Successful : {success_count:2d} / {total}")
        logger.info(f"   Failed     : {len(failed):2d} / {total}")
        if failed:
            logger.warning(f" Failed databases: {', '.join(failed)}")
        else:
            logger.info(" All databases connected successfully ✓")
        logger.info("-" * 60 + "\n")

# -------------------------------------------------------------
# Session Context Middleware
# -------------------------------------------------------------
class SessionContextMiddleware(BaseHTTPMiddleware):
    """
    Sets session and client context variables for feedback tracking.

    Only active when feedback system is enabled in settings.yaml.
    Reads from request.state (populated by AuthMiddleware) and sets
    context variables that are accessible throughout the request lifecycle.
    """

    async def dispatch(self, request: Request, call_next):
        # Only activate if feedback system is enabled
        if not config.is_feedback_enabled():
            return await call_next(request)

        # Import here to avoid circular dependency
        from tools.feedback_context import set_request_context
        import uuid

        # Extract IDs from request.state (set by AuthMiddleware)
        session_id = getattr(request.state, "session_id", None)
        client_id = getattr(request.state, "client_id", None)
        user_id = getattr(request.state, "client_name", None)

        # Fallback values if not set by auth middleware
        if not session_id:
            session_id = str(uuid.uuid4())
        if not client_id:
            client_id = "anonymous"

        # Always set context variables for this request
        set_request_context(
            session_id=session_id,
            user_id=user_id or client_id,
            client_id=client_id
        )

        logger.debug(f"📍 Session context set: client_id={client_id}, session_id={session_id[:16]}...")

        # Continue processing request
        response = await call_next(request)
        return response

# -------------------------------------------------------------
# Build ASGI app
# -------------------------------------------------------------
os.environ["PYTHONUNBUFFERED"] = "1"
warnings.filterwarnings("ignore", category=DeprecationWarning)

from contextlib import asynccontextmanager

# Knowledge DB initialization
async def init_knowledge_db():
    """Initialize knowledge DB connection (required for admin features)."""
    from knowledge_db import get_knowledge_db

    logger.info("🔗 Initializing MCP Knowledge DB...")
    db = get_knowledge_db()
    if db.config is None:
        logger.error("❌ MCP knowledge DB: Config loading failed")
        logger.warning("⚠️  Admin features (feedback dashboard, etc.) will not work!")
        return

    success = await db.init()
    if success and db.is_enabled:
        logger.info("✅ MCP knowledge DB connection: SUCCESS")
        # Get cache stats for diagnostic info
        try:
            stats = await db.get_cache_stats()
            logger.info(f"   📊 Cache stats: {stats.get('tables_cached', 0)} tables, {stats.get('relationships_cached', 0)} relationships")

            # Warm cache for better performance
            if stats.get('tables_cached', 0) > 0:
                logger.info("🔥 Warming cache with frequently accessed tables...")
                warm_stats = await db.warm_cache_on_startup(top_n=50)
                logger.info(f"   🔥 Cache warmed: {warm_stats.get('warmed', 0)} tables, {warm_stats.get('relationships_warmed', 0)} relationships")
                if warm_stats.get('top_domains'):
                    logger.info(f"   🏷️  Top domains: {', '.join(warm_stats['top_domains'][:5])}")
        except Exception as stats_error:
            logger.warning(f"   ⚠️  Could not get cache stats: {stats_error}")
    else:
        logger.error("❌ MCP knowledge DB connection: FAILED")
        logger.warning("⚠️  Admin features (feedback dashboard, etc.) will not work!")
        status = db.get_connection_status()
        logger.error(f"   Connection status: {status}")

@asynccontextmanager
async def lifespan(app):
    """Application lifespan manager - runs on startup and shutdown."""
    # Startup: Initialize Knowledge DB
    try:
        await init_knowledge_db()
    except Exception as e:
        logger.error(f"❌ MCP knowledge DB initialization failed: {e}", exc_info=True)
        logger.warning("⚠️  Admin features (feedback dashboard, etc.) will not work!")

    yield

    # Shutdown: Cleanup Knowledge DB
    try:
        from knowledge_db import cleanup_knowledge_db
        await cleanup_knowledge_db()
        logger.info("✅ Knowledge DB cleanup complete")
    except Exception as e:
        logger.error(f"⚠️  Error during Knowledge DB cleanup: {e}")

mcp_http_app = mcp.http_app(transport="streamable-http")

# Wrap the MCP lifespan with our own lifespan
@asynccontextmanager
async def combined_lifespan(app):
    """Combined lifespan for both MCP and Knowledge DB."""
    # Start our lifespan
    async with lifespan(app):
        # Start MCP lifespan
        async with mcp_http_app.lifespan(app):
            yield

app = Starlette(lifespan=combined_lifespan)

# -------------------------------------------------------------
# Simple Endpoints
# -------------------------------------------------------------
async def health(request):
    return PlainTextResponse("OK")

async def version(request):
    return JSONResponse({
        "server": config.server_name,
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "python": sys.version,
    })

async def deep_health(request):
    return JSONResponse({
        "status": "healthy",
        "checks": {
            "server": "ok",
            "mcp": {
                "tools": len(mcp.tools),
                "resources": len(mcp.resources),
                "prompts": len(mcp.prompts),
            }
        }
    })

# -------------------------------------------------------------
# Routes
# -------------------------------------------------------------
app.add_route("/health", health, methods=["GET"])
app.add_route("/healthz", health, methods=["GET"])
app.add_route("/health/deep", deep_health, methods=["GET"])
app.add_route("/version", version, methods=["GET"])

# -------------------------------------------------------------
# Middleware
# -------------------------------------------------------------
# IMPORTANT: Middleware executes in REVERSE order!
# Listed order: Session Context -> Auth -> CORS
# Execution order: CORS -> Auth -> Session Context
# This ensures Auth runs BEFORE Session Context can read request.state
app.add_middleware(SessionContextMiddleware)
app.add_middleware(AuthMiddleware, config=config)

if config.auth_enabled:
    logger.info(f"🔐 Authentication ENABLED — {len(config.api_keys)} API key(s) configured")
else:
    logger.info("🔓 Authentication DISABLED")

if config.is_feedback_enabled():
    logger.info("🔗 Session Context Middleware enabled (feedback system active)")
else:
    logger.info("🔇 Feedback system DISABLED (session context middleware inactive)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# Mount MCP
# -------------------------------------------------------------
app.mount("/", mcp_http_app)
logger.info("✅Avi FastMCP mounted at /mcp")

# -------------------------------------------------------------
# Run Server
# -------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.server_port,
        log_level="info",
    )
