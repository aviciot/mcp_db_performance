# server/resources/hello_resource.py
from mcp_app import mcp

# Matches: demo://samples/anything-here
@mcp.resource("demo://samples/{name}")
async def sample_resource(name: str) -> str:
    # You can return plain str; FastMCP auto-wraps as text/plain
    return f"Hello from MCP demo! You asked for: {name}"

