# server/tools/oracle_analysis.py

import logging
import traceback
from mcp_app import mcp
from db_connector import oracle_connector
from tools.oracle_collector_impl import run_full_oracle_analysis as run_collector


logger = logging.getLogger("oracle_analysis")
logger.setLevel(logging.INFO)

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