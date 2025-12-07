# server/tools/oracle_analysis.py

import logging
import traceback
import json
from mcp_app import mcp
from db_connector import oracle_connector
from tools.oracle_collector_impl import run_full_oracle_analysis as run_collector
from config import config


logger = logging.getLogger("oracle_analysis")
# Set log level from config
log_level = getattr(logging, config.log_level, logging.INFO)
logger.setLevel(log_level)

@mcp.tool(
    name="analyze_full_sql_context",
    description=(
        "Collects Oracle SQL performance metadata (plan, stats, indexes, partitions, histograms) "
        "and returns JSON + an LLM-ready optimization prompt."
    ),
)
def analyze_full_sql_context(db_name: str, sql_text: str) -> dict:
    """
    MCP tool entrypoint.
    Opens DB connection and calls the real collector.
    """
    # Log tool invocation details if enabled
    if config.show_tool_calls:
        logger.info("=" * 80)
        logger.info("🔧 TOOL CALLED BY LLM: analyze_full_sql_context")
        logger.info(f"   📊 Database: {db_name}")
        logger.info(f"   📝 SQL Length: {len(sql_text)} characters")
        if logger.isEnabledFor(logging.DEBUG):
            # Only show full SQL in DEBUG mode
            logger.debug(f"   💬 Full SQL:\n{sql_text}")
        else:
            # Show truncated version in INFO
            sql_preview = sql_text[:200] + "..." if len(sql_text) > 200 else sql_text
            logger.info(f"   💬 SQL Preview: {sql_preview}")
        logger.info("=" * 80)
    else:
        logger.info(f"🔍 analyze_full_sql_context(db={db_name}) called")

    if not sql_text or not sql_text.strip():
        return {"error": "sql_text is empty", "facts": {}, "prompt": ""}

    try:
        # Open DB connection
        conn = oracle_connector.connect(db_name)
        cur = conn.cursor()

        logger.info("📡 Connected to Oracle, collecting performance metadata…")

        # Call real collector
        result = run_collector(cur, sql_text)

        logger.info("✅ Analysis finished")
        return result

    except Exception as e:
        logger.exception("❌ Exception during analysis")
        return {
            "error": f"Internal error: {e}",
            "trace": traceback.format_exc(),
            "facts": {},
            "prompt": ""
        }
    finally:
        try:
            cur.close()
            conn.close()
        except:
            pass
        