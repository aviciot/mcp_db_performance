# server/resources/server_info.py
from mcp_app import mcp
from datetime import datetime
from config import config

@mcp.resource("data://statistics/summary")
def get_statistics() -> dict:
    """
    Dynamic statistics resource.
    """
    return {
        "server_name": config.server_name,
        "uptime_hours": 42,  # Placeholder; implement actual uptime tracking
        "total_requests": 1337,  # Placeholder
        "active_tools": len(mcp.tools),
        "active_resources": len(mcp.resources),
        "active_prompts": len(mcp.prompts),
        "generated_at": datetime.now().isoformat()
    }

@mcp.resource("config://server/settings")
def get_server_config() -> dict:
    """
    Server configuration resource.
    """
    return {
        "server_version": "1.0.0",
        "api_version": "mcp-1.0",
        "features": ["tools", "resources", "prompts"],
        "rate_limits": {
            "requests_per_minute": 60,
            "max_concurrent": 10
        },
        "supported_models": [config.groq_model]
    }
