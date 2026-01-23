# server/tools/oracle_analysis.py

import logging
import traceback
import json
import asyncio
from mcp_app import mcp
from db_connector import oracle_connector
from tools.oracle_collector_impl import run_full_oracle_analysis as run_collector
from tools.plan_visualizer import build_visual_plan, get_plan_summary
from history_tracker import normalize_and_hash, store_history, get_recent_history, compare_with_history
from config import config

# Business logic imports
from tools.oracle_explain_logic import explain_oracle_query_logic
from tools.oracle_business_context import collect_oracle_business_context
from knowledge_db import get_knowledge_db


logger = logging.getLogger("oracle_analysis")
# Set log level from config
log_level = getattr(logging, config.log_level, logging.INFO)
logger.setLevel(log_level)

@mcp.tool(
    name="analyze_oracle_query",
    description=(
        "🔍 [ORACLE ONLY] Analyzes Oracle database SQL SELECT queries for performance optimization.\n\n"
        "⚠️ DATABASE TYPE: This tool is for ORACLE databases only.\n"
        "   For MySQL databases, use 'analyze_mysql_query' instead.\n\n"
        "⚠️ SECURITY RESTRICTIONS - This tool ONLY accepts:\n"
        "✅ SELECT queries (including WITH clauses/CTEs)\n"
        "✅ Read-only operations for analysis\n\n"
        "❌ BLOCKED OPERATIONS (will be rejected immediately):\n"
        "❌ Data modification: INSERT, UPDATE, DELETE, MERGE\n"
        "❌ Schema changes: CREATE, DROP, ALTER, TRUNCATE, RENAME\n"
        "❌ Permissions: GRANT, REVOKE\n"
        "❌ Transactions: COMMIT, ROLLBACK, SAVEPOINT\n"
        "❌ System ops: SHUTDOWN, STARTUP, EXECUTE, CALL\n"
        "❌ PL/SQL blocks: BEGIN, DECLARE\n"
        "❌ SELECT INTO (data insertion)\n\n"
        "📊 DEPTH MODES:\n"
        "• depth='plan_only' - Fast execution plan analysis only (0.3s, educational)\n"
        "• depth='standard' - Full analysis with metadata (default, for optimization)\n\n"
        "💡 Use 'plan_only' to understand query execution without optimization.\n"
        "   Use 'standard' (default) when you need to optimize the query.\n\n"
        "⚡ Usage: Only call this tool with valid SELECT queries that you want to analyze."
    ),
)
async def analyze_oracle_query(db_name: str, sql_text: str, depth: str = "standard"):
    """
    MCP tool entrypoint for Oracle query analysis.
    Opens Oracle DB connection and calls the real collector.

    Args:
        db_name: Oracle database preset name from settings.yaml
        sql_text: SQL SELECT query to analyze
        depth: Analysis depth mode
            - "plan_only": Fast execution plan only (no metadata collection)
            - "standard": Full analysis with all metadata (default)
    """
    # Validate depth parameter
    if depth not in ["plan_only", "standard"]:
        return {
            "error": f"Invalid depth parameter: '{depth}'",
            "facts": {},
            "prompt": "depth must be 'plan_only' or 'standard'"
        }

    # Log tool invocation details if enabled
    if config.show_tool_calls:
        logger.info("=" * 80)
        logger.info("🔧 TOOL CALLED BY LLM: analyze_oracle_query")
        logger.info(f"   📊 Database: {db_name}")
        logger.info(f"   📊 Depth: {depth}")
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
        logger.info(f"🔍 analyze_oracle_query(db={db_name}, depth={depth}) called")

    if not sql_text or not sql_text.strip():
        return {"error": "sql_text is empty", "facts": {}, "prompt": ""}

    try:
        # Open DB connection
        conn = oracle_connector.connect(db_name)
        cur = conn.cursor()

        logger.info("📡 Connected to Oracle, collecting performance metadata…")

        # PRE-VALIDATE SQL before expensive metadata collection
        logger.info("🔍 Validating SQL query (safety + syntax)...")
        
        # Import validation function
        from tools.oracle_collector_impl import validate_sql
        
        is_valid, error_msg, is_dangerous = validate_sql(cur, sql_text)
        
        if is_dangerous:
            logger.error(f"🚨 DANGEROUS OPERATION BLOCKED: {error_msg}")
            logger.error("   This query was blocked for SECURITY reasons")
            return {
                "error": f"SECURITY BLOCK: {error_msg}",
                "facts": {},
                "prompt": (
                    f"🚨 SECURITY: This query was BLOCKED for safety reasons.\n\n"
                    f"Reason: {error_msg}\n\n"
                    f"This tool only allows SELECT queries for analysis.\n"
                    f"The following operations are PROHIBITED:\n"
                    f"- Data modification (INSERT, UPDATE, DELETE, MERGE)\n"
                    f"- Schema changes (CREATE, DROP, ALTER, TRUNCATE)\n"
                    f"- Permission changes (GRANT, REVOKE)\n"
                    f"- System operations (SHUTDOWN, STARTUP)\n"
                    f"- Procedure execution (EXECUTE, CALL)\n"
                    f"- PL/SQL blocks (BEGIN, DECLARE)\n\n"
                    f"Please provide a SELECT query only."
                )
            }
        
        if not is_valid:
            logger.error(f"❌ SQL VALIDATION FAILED: {error_msg}")
            logger.error("   Cannot analyze invalid SQL - returning error to user")
            return {
                "error": f"Invalid SQL query: {error_msg}",
                "facts": {},
                "prompt": (
                    f"The SQL query is INVALID and cannot be analyzed.\n\n"
                    f"Error: {error_msg}\n\n"
                    f"Suggestions:\n"
                    f"1. Check that all table and column names are spelled correctly\n"
                    f"2. Verify table aliases match the table names\n"
                    f"3. Ensure all referenced columns exist in the tables\n"
                    f"4. Test the query in SQL*Plus or another SQL client first\n\n"
                    f"You can use this query to find correct column names:\n"
                    f"SELECT column_name FROM all_tab_columns WHERE owner='SCHEMA' AND table_name='TABLE';"
                )
            }
        
        logger.info("✅ SQL query is valid and safe")

        # AUTO-ADJUST PRESET FOR LARGE QUERIES
        # Save original preset and determine if adjustment needed
        original_preset = config.output_preset
        adjusted_preset = original_preset  # Track what we adjusted to
        preset_adjusted = False
        query_length = len(sql_text)

        if query_length >= 50000:
            # Very large query - use minimal preset
            config.output_preset = "minimal"
            adjusted_preset = "minimal"
            preset_adjusted = True
            logger.warning(f"⚠️ Large query detected ({query_length:,} chars). Auto-switching to 'minimal' preset.")
        elif query_length >= 10000:
            # Large query - use compact preset (unless already minimal)
            if original_preset == "standard":
                config.output_preset = "compact"
                adjusted_preset = "compact"
                preset_adjusted = True
                logger.info(f"📊 Query length {query_length:,} chars. Auto-switching to 'compact' preset.")

        try:
            # Check historical executions (skip for plan_only mode)
            if depth == "standard":
                fingerprint = normalize_and_hash(sql_text)
                history = await get_recent_history(fingerprint, db_name)
            else:
                history = None

            # Call real collector with depth parameter
            result = run_collector(cur, sql_text, depth=depth)
        finally:
            # Always restore original preset
            config.output_preset = original_preset
        
        facts = result.get("facts", {})
        plan_details = facts.get("plan_details", [])
        
        logger.info(f"📋 Collector returned {len(plan_details)} plan steps")
        if not plan_details:
            logger.warning("⚠️  EXPLAIN PLAN returned no steps - check if query is valid")

        # Add visual plan
        if plan_details:
            facts["visual_plan"] = build_visual_plan(plan_details)
            facts["plan_summary"] = get_plan_summary(plan_details)
        
        # Add historical context
        if history:
            facts["historical_context"] = await compare_with_history(history, facts)
            facts["history_count"] = len(history)  # Add count for LLM
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
        
        # Add factual summary for LLM context
        query_intent = facts.get("query_intent", {})
        full_table_scans = facts.get("full_table_scans", [])
        cartesian_detections = facts.get("cartesian_detections", [])
        
        # Build informational prompt (no recommendations)
        prompt_parts = [result.get("prompt", "")]

        # Add depth mode notification
        if depth == "plan_only":
            prompt_parts.append(
                f"\n📖 PLAN-ONLY MODE: This is a fast execution plan analysis without metadata collection. "
                f"Use depth='standard' for full optimization analysis with table/index/column statistics."
            )

        # Add preset adjustment notification if it occurred
        if preset_adjusted:
            prompt_parts.append(
                f"\n⚙️ NOTE: Large query detected ({query_length:,} characters). "
                f"Analysis preset automatically adjusted to '{adjusted_preset}' "
                f"(from '{original_preset}') to optimize token usage. "
                f"Full SQL preserved for accurate optimization recommendations."
            )

        # Add query pattern info
        if query_intent:
            prompt_parts.append(
                f"\n📋 Query Pattern: '{query_intent.get('type', 'unknown')}' "
                f"(complexity: {query_intent.get('complexity', 'unknown')}). "
            )
        
        # Add detection summary
        if full_table_scans:
            prompt_parts.append(
                f"\n🔍 Detected: {len(full_table_scans)} full table scan(s). "
                f"See facts['full_table_scans'] for details."
            )
        
        if cartesian_detections:
            prompt_parts.append(
                f"\n🔍 Detected: {len(cartesian_detections)} potential Cartesian product(s). "
                f"See facts['cartesian_detections'] for details."
            )
        
        # Inform about business logic tool availability
        tables_count = facts.get("summary", {}).get("tables", 0)
        if tables_count > 1:
            prompt_parts.append(
                f"\n💡 Note: For business context analysis, the 'explain_business_logic' tool "
                f"can analyze table relationships and infer business domains."
            )
        
        result["prompt"] = "".join(prompt_parts)

        # Store current execution in history (only for standard mode)
        if depth == "standard" and plan_details:
            plan_hash = plan_details[0].get("plan_hash_value", "unknown")
            cost = plan_details[0].get("cost", 0)
            table_stats = {t["table_name"]: t["num_rows"] for t in facts.get("table_stats", [])}
            plan_operations = [
                f"{s.get('operation', '')} {s.get('options', '')}".strip()
                for s in plan_details[:5]  # Top 5 operations
            ]
            await store_history(fingerprint, db_name, plan_hash, cost, table_stats, plan_operations)

        logger.info(f"✅ Analysis complete with {len(plan_details)} plan steps")
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
            if 'conn' in locals():
                conn.close()
        except:
            pass


@mcp.tool(
    name="compare_oracle_query_plans",
    description=(
        "🔍 [ORACLE ONLY] Compares execution plans of two Oracle SELECT queries (original vs optimized).\n\n"
        "⚠️ DATABASE TYPE: This tool is for ORACLE databases only.\n"
        "   For MySQL databases, use 'compare_mysql_query_plans' instead.\n\n"
        "⚠️ SECURITY RESTRICTIONS - This tool ONLY accepts:\n"
        "✅ SELECT queries (including WITH clauses/CTEs)\n"
        "✅ Read-only operations for analysis\n\n"
        "❌ BLOCKED: All data modification, schema changes, and system operations\n\n"
        "📊 Returns: Side-by-side cost comparison, operation differences, performance verdict.\n\n"
        "⚡ Usage: Provide Oracle database name and two valid SELECT queries to compare their execution plans."
    ),
)
async def compare_oracle_query_plans(db_name: str, original_sql: str, optimized_sql: str):
    """
    Compare two Oracle query execution plans to validate optimization improvements.
    Oracle-specific implementation.
    """
    logger.info(f"🔍 compare_oracle_query_plans(db={db_name})")
    
    try:
        conn = oracle_connector.connect(db_name)
        cur = conn.cursor()
        
        # Import Oracle validation function
        from tools.oracle_collector_impl import validate_sql
        
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
        
        # Debug: Log what we got
        logger.info(f"   Original result keys: {list(original_result.keys())}")
        logger.info(f"   Optimized result keys: {list(optimized_result.keys())}")
        
        # Extract facts from results
        original_facts = original_result.get("facts", {})
        optimized_facts = optimized_result.get("facts", {})
        
        logger.info(f"   Original facts keys: {list(original_facts.keys())}")
        logger.info(f"   Optimized facts keys: {list(optimized_facts.keys())}")
        
        # Extract key metrics from plan_details
        original_plan = original_facts.get("plan_details", [])
        optimized_plan = optimized_facts.get("plan_details", [])
        
        logger.info(f"   Original plan steps: {len(original_plan)}")
        logger.info(f"   Optimized plan steps: {len(optimized_plan)}")
        
        if original_plan:
            logger.info(f"   Original plan[0] keys: {list(original_plan[0].keys())}")
            logger.info(f"   Original plan[0] cost: {original_plan[0].get('cost', 'N/A')}")
        
        # Get cost from first step (root operation) of execution plan
        original_cost = original_plan[0].get("cost", 0) if original_plan else 0
        optimized_cost = optimized_plan[0].get("cost", 0) if optimized_plan else 0
        
        improvement = 0
        if original_cost > 0:
            improvement = ((original_cost - optimized_cost) / original_cost) * 100
        
        comparison = {
            "original": {
                "cost": original_cost,
                "plan_summary": original_facts.get("summary", {}),
                "total_steps": len(original_plan),
                "tables": original_facts.get("summary", {}).get("tables", 0),
                "indexes": original_facts.get("summary", {}).get("indexes", 0)
            },
            "optimized": {
                "cost": optimized_cost,
                "plan_summary": optimized_facts.get("summary", {}),
                "total_steps": len(optimized_plan),
                "tables": optimized_facts.get("summary", {}).get("tables", 0),
                "indexes": optimized_facts.get("summary", {}).get("indexes", 0)
            },
            "comparison": {
                "cost_reduction": original_cost - optimized_cost,
                "improvement_percentage": round(improvement, 2),
                "is_better": optimized_cost < original_cost,
                "steps_difference": len(original_plan) - len(optimized_plan)
            }
        }
        
        logger.info(f"✅ Comparison: {improvement:.1f}% improvement")
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


@mcp.tool(
    name="explain_business_logic",
    description=(
        "📖 [ORACLE ONLY] Explains the business logic behind an Oracle SQL query.\n\n"
        "⚠️ DATABASE TYPE: This tool is for ORACLE databases only.\n\n"
        "This tool analyzes SQL queries and provides:\n"
        "✅ Business-focused explanation of what the query does\n"
        "✅ Table relationships and entity descriptions\n"
        "✅ Column meanings from database comments\n"
        "✅ Inferred business domain and entity types\n\n"
        "📊 Returns: Structured context and a prompt for generating business explanation.\n\n"
        "💡 Use this when you need to understand WHAT a query does from a business perspective,\n"
        "   not just HOW it performs (use analyze_oracle_query for performance analysis).\n\n"
        "🔄 Results are cached in PostgreSQL for faster future lookups.\n"
        "   First run may take longer as it queries Oracle metadata."
    ),
)
async def explain_business_logic(
    db_name: str, 
    sql_text: str, 
    follow_relationships: bool = True,
    max_depth: int = 2
):
    """
    MCP tool to explain the business logic of a SQL query.
    
    Args:
        db_name: Oracle database preset name
        sql_text: SQL query to explain
        follow_relationships: Whether to follow FK relationships (default True)
        max_depth: How deep to follow relationships (default 2)
    """
    # Log tool invocation
    if config.show_tool_calls:
        logger.info("=" * 80)
        logger.info("🔧 TOOL CALLED BY LLM: explain_business_logic")
        logger.info(f"   📊 Database: {db_name}")
        logger.info(f"   📝 SQL Length: {len(sql_text)} characters")
        logger.info(f"   🔗 Follow Relationships: {follow_relationships}")
        logger.info(f"   📏 Max Depth: {max_depth}")
        logger.info("=" * 80)
    else:
        logger.info(f"📖 explain_business_logic(db={db_name}) called")
    
    if not sql_text or not sql_text.strip():
        return {"error": "sql_text is empty", "context": {}, "prompt": ""}
    
    try:
        # Connect to Oracle
        conn = oracle_connector.connect(db_name)
        cur = conn.cursor()
        
        logger.info("📡 Connected to Oracle, collecting business context…")
        
        # Get knowledge DB for caching (optional - works without it)
        try:
            knowledge_db = get_knowledge_db()
            if knowledge_db and not knowledge_db.is_enabled:
                await knowledge_db.connect()
            logger.info("📦 Knowledge DB connected for caching")
        except Exception as e:
            logger.warning(f"⚠️ Knowledge DB not available: {e}")
            knowledge_db = None
        
        # Get default schema from connection
        try:
            cur.execute("SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM DUAL")
            default_schema = cur.fetchone()[0]
            logger.info(f"📋 Default schema: {default_schema}")
        except:
            default_schema = None
        
        # Run the async explanation function
        result = await explain_oracle_query_logic(
            sql=sql_text,
            oracle_cursor=cur,
            db_name=db_name,
            knowledge_db=knowledge_db,
            default_schema=default_schema,
            follow_relationships=follow_relationships,
            max_depth=max_depth,
            use_cache=True
        )
        
        if "error" in result:
            logger.error(f"❌ Explanation failed: {result['error']}")
            return result
        
        # Format the response
        stats = result.get("stats", {})
        logger.info(f"✅ Business context collected: {stats.get('tables_analyzed', 0)} tables, "
                   f"{stats.get('relationships_found', 0)} relationships")
        logger.info(f"   Cache: {stats.get('cache_hits', 0)} hits, {stats.get('cache_misses', 0)} misses")
        logger.info(f"   Duration: {stats.get('duration_ms', 0)}ms")
        
        return {
            "context": result.get("formatted_context", ""),
            "explanation_prompt": result.get("explanation_prompt", ""),
            "tables": result.get("table_context", {}),
            "relationships": result.get("relationships", []),
            "stats": stats,
            "prompt": (
                "Use the 'explanation_prompt' field to generate a business-focused explanation. "
                "The context includes table descriptions, column meanings, and relationships. "
                "Focus on explaining WHAT the query does in business terms, not technical SQL details."
            )
        }
        
    except Exception as e:
        logger.exception("❌ Exception during business logic explanation")
        return {
            "error": f"Internal error: {e}",
            "trace": traceback.format_exc(),
            "context": {},
            "prompt": ""
        }
    finally:
        try:
            if 'conn' in locals():
                conn.close()
        except:
            pass


@mcp.tool(
    name="get_table_business_context",
    description=(
        "📋 [ORACLE ONLY] Gets business context for specific tables (comments, columns, relationships).\n\n"
        "⚠️ DATABASE TYPE: This tool is for ORACLE databases only.\n\n"
        "Use this tool when you want to understand a table's purpose without a full query.\n\n"
        "✅ Returns: Table comments, column descriptions, foreign key relationships\n"
        "✅ Follows FK relationships to discover related tables\n"
        "✅ Results are cached for fast future lookups\n\n"
        "💡 Provide table names as comma-separated values: 'SCHEMA.TABLE1, SCHEMA.TABLE2'"
    ),
)
async def get_table_business_context(
    db_name: str,
    table_names: str,
    follow_relationships: bool = True,
    max_depth: int = 1
):
    """
    MCP tool to get business context for specific tables.
    
    Args:
        db_name: Oracle database preset name  
        table_names: Comma-separated table names (e.g., "OWNER.TABLE1, OWNER.TABLE2")
        follow_relationships: Whether to follow FK relationships
        max_depth: How deep to follow relationships
    """
    logger.info(f"📋 get_table_business_context(db={db_name}, tables={table_names})")
    
    if not table_names or not table_names.strip():
        return {"error": "table_names is empty"}
    
    # Parse table names
    tables = []
    for part in table_names.split(","):
        part = part.strip()
        if "." in part:
            schema, table = part.split(".", 1)
            tables.append((schema.upper().strip(), table.upper().strip()))
        else:
            tables.append((None, part.upper()))
    
    if not tables:
        return {"error": "No valid table names provided"}
    
    try:
        conn = oracle_connector.connect(db_name)
        cur = conn.cursor()
        
        # Resolve schemas for tables without schema prefix
        try:
            cur.execute("SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM DUAL")
            default_schema = cur.fetchone()[0]
        except:
            default_schema = None
        
        resolved_tables = []
        for schema, table in tables:
            if schema:
                resolved_tables.append((schema, table))
            elif default_schema:
                resolved_tables.append((default_schema, table))
            else:
                # Try to find the table
                cur.execute(
                    "SELECT owner FROM all_tables WHERE table_name = :t AND ROWNUM = 1",
                    {"t": table}
                )
                row = cur.fetchone()
                if row:
                    resolved_tables.append((row[0], table))
                else:
                    logger.warning(f"⚠️ Could not find table: {table}")
        
        if not resolved_tables:
            return {"error": "Could not resolve any table names"}
        
                # Get knowledge DB for caching
        try:
            knowledge_db = get_knowledge_db()
            if knowledge_db and not knowledge_db.is_enabled:
                logger.debug(f"[DEBUG] About to call await knowledge_db.connect() (enabled={knowledge_db.is_enabled}, attempts={getattr(knowledge_db, '_connection_attempts', None)})")
                await knowledge_db.connect()
                logger.debug(f"[DEBUG] After connect: enabled={knowledge_db.is_enabled}, pool={knowledge_db.pool is not None}, attempts={getattr(knowledge_db, '_connection_attempts', None)}")
        except Exception as e:
            logger.warning(f"⚠️ Knowledge DB not available: {e}")
            knowledge_db = None
        
        # Collect business context (sync function - no await)
        context = collect_oracle_business_context(
            cur,
            resolved_tables,
            follow_relationships=follow_relationships,
            max_depth=max_depth
        )
        
        # Cache results if possible
        if knowledge_db:
            from tools.oracle_explain_logic import cache_collected_context
            await cache_collected_context(knowledge_db, context)
        
        # Format response
        return {
            "tables": {
                f"{k[0]}.{k[1]}": v
                for k, v in context.get("table_context", {}).items()
            },
            "relationships": [
                {
                    "from": f"{r['from'][0]}.{r['from'][1]}",
                    "to": f"{r['to'][0]}.{r['to'][1]}",
                    "from_columns": r["from_columns"],
                    "to_columns": r["to_columns"]
                }
                for r in context.get("relationships", [])
            ],
            "discovered_tables": context.get("discovered_tables", []),
            "stats": context.get("stats", {}),
            "prompt": (
                "This response contains business context for the requested tables. "
                "Use table comments and column descriptions to understand their business purpose. "
                "Follow relationships to understand how tables connect to each other."
            )
        }
        
    except Exception as e:
        logger.exception("❌ Exception during table context retrieval")
        return {"error": str(e), "trace": traceback.format_exc()}
    finally:
        try:
            if 'conn' in locals():
                conn.close()
        except:
            pass
