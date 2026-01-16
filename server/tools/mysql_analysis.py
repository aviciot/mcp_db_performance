"""
MySQL Query Analysis Tool - MCP Tool for MySQL performance analysis
Reuses historical tracking and validation from Oracle analysis
"""

import logging
import traceback
from mcp_app import mcp
import mysql_connector

logger = logging.getLogger(__name__)


@mcp.tool(
    name="analyze_mysql_query",
    description=(
        "🔍 [MYSQL ONLY] Analyze MySQL database query performance - Get execution plan, table stats, and index usage.\n\n"
        "⚠️ DATABASE TYPE: This tool is for MYSQL databases only.\n"
        "   For Oracle databases, use 'analyze_oracle_query' instead.\n\n"
        "⚠️ SECURITY RESTRICTIONS - This tool ONLY accepts:\n"
        "✅ SELECT queries (including WITH clauses/CTEs)\n"
        "✅ Read-only operations for analysis\n\n"
        "❌ BLOCKED OPERATIONS (will be rejected immediately):\n"
        "❌ Data modification: INSERT, UPDATE, DELETE, REPLACE\n"
        "❌ Schema changes: CREATE, DROP, ALTER, TRUNCATE, RENAME\n"
        "❌ Permissions: GRANT, REVOKE\n"
        "❌ Transactions: COMMIT, ROLLBACK, SAVEPOINT\n"
        "❌ System ops: SHUTDOWN, KILL, EXECUTE, CALL\n"
        "❌ Data loading: LOAD, IMPORT, HANDLER\n"
        "❌ INTO OUTFILE/DUMPFILE (data exfiltration)\n"
        "❌ Table locking: LOCK, UNLOCK\n\n"
        "📊 Returns: Execution plan (EXPLAIN FORMAT=JSON), table statistics, index recommendations, usage patterns.\n\n"
        "⚡ Usage: Provide MySQL database name and SELECT query to analyze."
    ),
)
def analyze_mysql_query(db_name: str, sql_text: str):
    """
    Analyze a MySQL SELECT query for performance issues.
    
    Args:
        db_name: Name of MySQL database from settings.yaml
        sql_text: SELECT query to analyze
    
    Returns:
        Dict with execution plan, table stats, indexes, and historical context
    """
    logger.info("="*70)
    logger.info("🔧 TOOL CALLED BY LLM: analyze_mysql_query")
    logger.info(f"   📊 Database: {db_name}")
    logger.info(f"   📝 SQL Length: {len(sql_text)} characters")
    logger.info(f"   💬 SQL Preview: {sql_text[:100]}")
    logger.info("="*70)
    
    try:
        conn = mysql_connector.connect(db_name)
        cur = conn.cursor()
        
        logger.info("📡 Connected to MySQL, collecting performance metadata…")
        
        # Import validation and collector
        from tools.mysql_collector_impl import validate_sql, run_collector
        
        # Validate SQL for safety
        logger.info("🔍 Validating SQL query (safety + syntax)...")
        is_valid, error_msg, is_dangerous = validate_sql(cur, sql_text)
        
        if is_dangerous:
            logger.error(f"🚨 DANGEROUS SQL BLOCKED: {error_msg}")
            return {
                "error": f"SECURITY BLOCK: {error_msg}",
                "facts": {},
                "prompt": (
                    f"The SQL query was BLOCKED for security reasons.\n\n"
                    f"Reason: {error_msg}\n\n"
                    f"This tool only accepts SELECT queries for read-only analysis.\n"
                    f"Please provide a SELECT query only."
                )
            }
        
        if not is_valid:
            logger.error(f"❌ SQL VALIDATION FAILED: {error_msg}")
            return {
                "error": f"Invalid SQL query: {error_msg}",
                "facts": {},
                "prompt": (
                    f"The SQL query is INVALID and cannot be analyzed.\n\n"
                    f"Error: {error_msg}\n\n"
                    f"Suggestions:\n"
                    f"1. Check that all table and column names are spelled correctly\n"
                    f"2. Verify table/database names exist\n"
                    f"3. Ensure all referenced columns exist in the tables\n"
                    f"4. Test the query in MySQL client first\n\n"
                    f"You can use: SHOW TABLES; or DESCRIBE table_name; to verify schema"
                )
            }
        
        logger.info("✅ SQL query is valid and safe")

        # Check historical executions
        from history_tracker import normalize_and_hash, store_history, get_recent_history, compare_with_history
        
        fingerprint = normalize_and_hash(sql_text)
        history = get_recent_history(fingerprint, db_name)

        # Call collector
        result = run_collector(cur, sql_text)
        
        facts = result.get("facts", {})
        plan_details = facts.get("plan_details", [])
        
        logger.info(f"📋 Collector returned {len(plan_details)} plan steps")
        
        # Add historical context
        if history:
            facts["historical_context"] = compare_with_history(history, facts)
            facts["history_count"] = len(history)
            logger.info(f"📊 Historical context: {facts['historical_context'].get('message', 'N/A')}")
            
            # Update the prompt field to emphasize historical context
            result["prompt"] = (
                f"🕒 IMPORTANT: This query pattern has been executed {len(history)} time(s) before. "
                f"START your response with the historical context section using facts['historical_context']. "
                f"{result.get('prompt', '')}"
            )
        else:
            facts["historical_context"] = {"status": "new_query", "message": "First execution - establishing baseline"}
            result["prompt"] = f"🆕 This is the first execution of this query pattern. {result.get('prompt', '')}"
        
        # Store current execution in history
        if plan_details:
            # MySQL doesn't have plan_hash, use first step's cost
            plan_hash = "mysql_plan"
            cost = plan_details[0].get("cost", 0) if plan_details else 0
            table_stats = {t["table_name"]: t["num_rows"] for t in facts.get("table_stats", [])}
            plan_operations = [
                f"{s.get('access_type', '')} {s.get('table', '')}".strip()
                for s in plan_details[:5]
            ]
            store_history(fingerprint, db_name, plan_hash, cost, table_stats, plan_operations)

        logger.info(f"✅ Analysis complete with {len(plan_details)} plan steps")
        return result

    except Exception as e:
        logger.exception("❌ Exception during MySQL analysis")
        return {
            "error": f"Internal error: {e}",
            "trace": traceback.format_exc(),
            "facts": {},
            "prompt": ""
        }
    finally:
        try:
            if 'conn' in locals():
                conn.close()
        except:
            pass


@mcp.tool(
    name="compare_mysql_query_plans",
    description=(
        "🔍 [MYSQL ONLY] Compares execution plans of two MySQL SELECT queries (original vs optimized).\n\n"
        "⚠️ DATABASE TYPE: This tool is for MYSQL databases only.\n"
        "   For Oracle databases, use 'compare_oracle_query_plans' instead.\n\n"
        "⚠️ SECURITY RESTRICTIONS - This tool ONLY accepts:\n"
        "✅ SELECT queries (including WITH clauses/CTEs)\n"
        "✅ Read-only operations for analysis\n\n"
        "❌ BLOCKED OPERATIONS: INSERT, UPDATE, DELETE, REPLACE, CREATE, DROP, ALTER, TRUNCATE, GRANT, REVOKE, and all other non-SELECT operations\n\n"
        "📊 Returns: Side-by-side cost comparison, operation differences, performance verdict.\n\n"
        "⚡ Usage: Provide MySQL database name and two valid SELECT queries to compare their execution plans."
    ),
)
def compare_mysql_query_plans(db_name: str, original_sql: str, optimized_sql: str):
    """
    Compare two MySQL query execution plans to validate optimization improvements.
    MySQL-specific implementation.
    """
    logger.info(f"🔍 compare_mysql_query_plans(db={db_name})")
    
    try:
        conn = mysql_connector.connect(db_name)
        cur = conn.cursor()
        
        # Import validation and collector
        from tools.mysql_collector_impl import validate_sql, run_collector
        
        # Validate BOTH queries for safety
        logger.info("🔍 Validating original query...")
        is_valid_orig, error_orig, is_dangerous_orig = validate_sql(cur, original_sql)
        
        if is_dangerous_orig:
            logger.error(f"🚨 Original query BLOCKED: {error_orig}")
            return {
                "error": f"SECURITY BLOCK (original query): {error_orig}",
                "comparison": None
            }
        
        if not is_valid_orig:
            logger.error(f"❌ Original query invalid: {error_orig}")
            return {
                "error": f"Invalid original query: {error_orig}",
                "comparison": None
            }
        
        logger.info("🔍 Validating optimized query...")
        is_valid_opt, error_opt, is_dangerous_opt = validate_sql(cur, optimized_sql)
        
        if is_dangerous_opt:
            logger.error(f"🚨 Optimized query BLOCKED: {error_opt}")
            return {
                "error": f"SECURITY BLOCK (optimized query): {error_opt}",
                "comparison": None
            }
        
        if not is_valid_opt:
            logger.error(f"❌ Optimized query invalid: {error_opt}")
            return {
                "error": f"Invalid optimized query: {error_opt}",
                "comparison": None
            }
        
        logger.info("✅ Both queries are valid and safe")
        
        # Analyze original query
        logger.info("📊 Analyzing original query...")
        original_result = run_collector(cur, original_sql)
        
        # Analyze optimized query
        logger.info("📊 Analyzing optimized query...")
        optimized_result = run_collector(cur, optimized_sql)
        
        # Extract facts from results
        original_facts = original_result.get("facts", {})
        optimized_facts = optimized_result.get("facts", {})
        
        # Extract key metrics from plan_details
        original_plan = original_facts.get("plan_details", [])
        optimized_plan = optimized_facts.get("plan_details", [])
        
        logger.info(f"   Original plan steps: {len(original_plan)}")
        logger.info(f"   Optimized plan steps: {len(optimized_plan)}")
        
        # Get cost from first step (root operation) of execution plan
        # MySQL EXPLAIN includes cost in query_block
        original_cost = original_plan[0].get("cost", 0) if original_plan else 0
        optimized_cost = optimized_plan[0].get("cost", 0) if optimized_plan else 0
        
        # Get rows examined
        original_rows = sum(step.get("rows", 0) for step in original_plan)
        optimized_rows = sum(step.get("rows", 0) for step in optimized_plan)
        
        improvement = 0
        if original_cost > 0:
            improvement = ((original_cost - optimized_cost) / original_cost) * 100
        
        rows_improvement = 0
        if original_rows > 0:
            rows_improvement = ((original_rows - optimized_rows) / original_rows) * 100
        
        comparison = {
            "original": {
                "cost": original_cost,
                "rows_examined": original_rows,
                "total_steps": len(original_plan),
                "tables_accessed": len([s for s in original_plan if s.get("table")]),
                "full_table_scans": len([s for s in original_plan if s.get("access_type") == "ALL"]),
                "index_scans": len([s for s in original_plan if s.get("access_type") in ["ref", "range", "index"]])
            },
            "optimized": {
                "cost": optimized_cost,
                "rows_examined": optimized_rows,
                "total_steps": len(optimized_plan),
                "tables_accessed": len([s for s in optimized_plan if s.get("table")]),
                "full_table_scans": len([s for s in optimized_plan if s.get("access_type") == "ALL"]),
                "index_scans": len([s for s in optimized_plan if s.get("access_type") in ["ref", "range", "index"]])
            },
            "comparison": {
                "cost_reduction": original_cost - optimized_cost,
                "cost_improvement_percentage": round(improvement, 2),
                "rows_reduction": original_rows - optimized_rows,
                "rows_improvement_percentage": round(rows_improvement, 2),
                "is_better": optimized_cost < original_cost or optimized_rows < original_rows,
                "steps_difference": len(original_plan) - len(optimized_plan),
                "scan_improvements": {
                    "fewer_full_scans": (len([s for s in original_plan if s.get("access_type") == "ALL"]) - 
                                        len([s for s in optimized_plan if s.get("access_type") == "ALL"])),
                    "more_index_usage": (len([s for s in optimized_plan if s.get("access_type") in ["ref", "range", "index"]]) - 
                                        len([s for s in original_plan if s.get("access_type") in ["ref", "range", "index"]]))
                }
            }
        }
        
        logger.info(f"✅ Comparison: {improvement:.1f}% cost improvement, {rows_improvement:.1f}% rows reduction")
        return comparison
        
    except Exception as e:
        logger.exception("❌ Exception during comparison")
        return {"error": str(e), "trace": traceback.format_exc()}
    finally:
        try:
            if 'conn' in locals():
                conn.close()
        except:
            pass
