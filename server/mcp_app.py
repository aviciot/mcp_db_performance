#path: server/mcp_app.py

from fastmcp import FastMCP
from config import config


# Single shared instance – everything else will import this
mcp = FastMCP(config.server_name)
