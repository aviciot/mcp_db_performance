# server/server.py
import os
import sys
import signal
import logging
import importlib
import pkgutil
import warnings

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse, PlainTextResponse
import uvicorn

from config import config
from mcp_app import mcp
from db_connector import oracle_connector


# -------------------------------------------------------------
# Logging
# -------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("server")

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("fastmcp").setLevel(logging.WARNING)

# Optional JSON log mode
if os.getenv("LOG_JSON") == "1":
    import json
    class JSONHandler(logging.StreamHandler):
        def emit(self, record):
            sys.stdout.write(json.dumps({
                "level": record.levelname,
                "msg": record.getMessage()
            }) + "\n")
    logger.handlers = [JSONHandler()]


AUTO_DISCOVER = os.getenv("AUTO_DISCOVER", "true").lower() in ("1", "true", "yes", "on")


# -------------------------------------------------------------
# Graceful Shutdown
# -------------------------------------------------------------
def _graceful(*_):
    logger.info("🛑 Received shutdown signal. Shutting down gracefully.")
    sys.exit(0)

for sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(sig, _graceful)


# -------------------------------------------------------------
# Module Auto-discovery
# -------------------------------------------------------------
def import_submodules(pkg_name: str):
    """Auto-import all modules inside a package."""
    try:
        pkg = __import__(pkg_name)
    except ModuleNotFoundError:
        logger.warning(f"⚠ Package not found: {pkg_name}")
        return

    for _, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
        if not ispkg:
            full_name = f"{pkg_name}.{modname}"
            importlib.import_module(full_name)
            logger.info(f"📦 Auto-imported: {full_name}")


def safe_import(name: str):
    try:
        module = __import__(name, fromlist=["*"])
        logger.info(f"✅ Imported: {name}")
        return module
    except Exception as e:
        logger.exception(f"❌ Failed to import: {name}: {e}")
        raise


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


# -------------------------------------------------------------
# DB Connectivity Test (Init Step)
# -------------------------------------------------------------
logger.info("🔍 Performing initial DB connectivity tests...")

for preset_name in config.database_presets.keys():
    oracle_connector.test_connection(preset_name)


print(f"🌐 Listening on port: {config.server_port}")

print("=" * 70)


# -------------------------------------------------------------
# Build ASGI app
# -------------------------------------------------------------
os.environ["PYTHONUNBUFFERED"] = "1"
warnings.filterwarnings("ignore", category=DeprecationWarning)

mcp_http_app = mcp.http_app()
app = Starlette(lifespan=mcp_http_app.lifespan)


# ---- Simple Endpoints ----
async def health(request):
    return PlainTextResponse("ok")


async def info(request):
    return JSONResponse({
        "name": config.server_name,
        "tools": [t.name for t in mcp.tools],
    })


async def version(request):
    return JSONResponse({
        "server": config.server_name,
        "version": os.getenv("APP_VERSION", "1.0.0"),
        "python": sys.version,
    })


# ---- Routes ----
app.add_route("/version", version, methods=["GET"])
app.add_route("/healthz", health, methods=["GET"])
app.add_route("/_info", info, methods=["GET"])


# ---- CORS ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=getattr(config, "cors_origins", ["*"]),
    allow_methods=getattr(config, "cors_methods", ["*"]),
    allow_headers=getattr(config, "cors_headers", ["*"]),
)

# Mount FastMCP HTTP app
app.mount("/", mcp_http_app)



# -------------------------------------------------------------
# Run Server
# -------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=config.server_port,
        reload=True,
        reload_dirs=["/app"],
        log_level="debug",
    )