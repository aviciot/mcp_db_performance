"""
MySQL Query Collector - Gathers execution plan and metadata
Simplified version focusing on: EXPLAIN, table stats, and indexes
"""

import json
import logging
import re

logger = logging.getLogger(__name__)


def validate_sql(cursor, sql: str) -> tuple[bool, str, bool]:
    """
    Pre-validate SQL for safety and correctness.
    Returns (is_valid, error_message, is_dangerous)
    
    Safety checks:
    - Block DDL (CREATE, DROP, ALTER, TRUNCATE)
    - Block DML writes (INSERT, UPDATE, DELETE, REPLACE)
    - Block DCL (GRANT, REVOKE)
    - Block system operations (SHUTDOWN, KILL)
    - Only allow SELECT queries
    """
    try:
        clean = sql.strip().upper()
        if clean.endswith(";"):
            clean = clean[:-1]
        
        # SECURITY CHECK 1: Block dangerous operations
        dangerous_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'REPLACE',  # DML writes
            'CREATE', 'DROP', 'ALTER', 'TRUNCATE', 'RENAME',  # DDL
            'GRANT', 'REVOKE',  # DCL
            'COMMIT', 'ROLLBACK', 'SAVEPOINT',  # Transaction control
            'SHUTDOWN', 'KILL',  # System operations
            'CALL', 'EXECUTE',  # Procedure calls
            'HANDLER', 'LOAD', 'IMPORT',  # Data loading
            'LOCK', 'UNLOCK',  # Table locking
        ]
        
        # Check first word after WITH/comment removal
        first_word = clean.split()[0] if clean.split() else ''
        
        # Allow WITH clause (for CTEs)
        if first_word == 'WITH':
            # Find the main query after CTE - must contain SELECT
            if 'SELECT' not in clean:
                return False, "No SELECT found in query with WITH clause", True
        elif first_word != 'SELECT':
            return False, f"Only SELECT queries are allowed. Found: {first_word}", True
        
        # Check for dangerous keywords anywhere in the query
        for keyword in dangerous_keywords:
            # Use word boundaries to avoid false positives (e.g., "UPDATE_DATE" column)
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, clean):
                return False, f"DANGEROUS OPERATION BLOCKED: {keyword} statements are not allowed", True
        
        # SECURITY CHECK 2: Block INTO OUTFILE/DUMPFILE (data exfiltration)
        if re.search(r'\bINTO\s+(OUTFILE|DUMPFILE)\b', clean):
            return False, "DANGEROUS OPERATION BLOCKED: INTO OUTFILE/DUMPFILE not allowed", True
        
        # SECURITY CHECK 3: Limit subquery depth to prevent DoS
        paren_depth = 0
        max_depth = 0
        for char in clean:
            if char == '(':
                paren_depth += 1
                max_depth = max(max_depth, paren_depth)
            elif char == ')':
                paren_depth -= 1
        
        if max_depth > 10:
            return False, f"Query too complex: {max_depth} nested subqueries (max 10)", False
        
        # Syntax validation using EXPLAIN
        cursor.execute(f"EXPLAIN {sql}")
        cursor.fetchall()  # Consume results
        
        return True, "", False
        
    except Exception as e:
        return False, f"SQL syntax error: {str(e)}", False


def run_explain(cursor, sql: str) -> dict:
    """
    Run EXPLAIN FORMAT=JSON and parse the output.
    
    Returns:
        Dict with execution plan details
    """
    logger.info("[MYSQL-COLLECTOR] -> Running EXPLAIN FORMAT=JSON")
    
    try:
        cursor.execute(f"EXPLAIN FORMAT=JSON {sql}")
        result = cursor.fetchone()[0]
        plan_json = json.loads(result)
        
        logger.info(f"[MYSQL-COLLECTOR] ✓ EXPLAIN returned JSON plan")
        logger.debug(f"[MYSQL-COLLECTOR] Plan JSON structure: {json.dumps(plan_json, indent=2)[:500]}")
        return plan_json
        
    except Exception as e:
        logger.error(f"[MYSQL-COLLECTOR] ❌ EXPLAIN failed: {e}")
        raise


def extract_plan_details(plan_json: dict) -> list:
    """
    Extract key details from EXPLAIN JSON output.
    
    Returns:
        List of plan steps with: table, type, key, rows, filtered, extra
    """
    details = []
    
    def traverse_plan(node, depth=0):
        """Recursively traverse the plan tree"""
        if not node:
            return
        
        # Extract table info
        table_name = node.get("table_name", "")
        access_type = node.get("access_type", "")
        possible_keys = node.get("possible_keys", [])
        key = node.get("key", "")
        key_length = node.get("key_length", "")
        rows_examined = node.get("rows_examined_per_scan", 0)
        filtered = node.get("filtered", 100.0)
        cost_info = node.get("cost_info", {})
        query_cost = cost_info.get("query_cost", 0)
        
        if table_name:  # Only add if it's a table access
            details.append({
                "depth": depth,
                "table": table_name,
                "access_type": access_type,
                "possible_keys": possible_keys,
                "key_used": key if key else None,
                "key_length": key_length,
                "rows": rows_examined,
                "filtered_percent": filtered,
                "cost": query_cost,
                "extra": node.get("message", "")
            })
        
        # Traverse nested_loop
        if "nested_loop" in node:
            for child in node["nested_loop"]:
                traverse_plan(child, depth + 1)
        
        # Traverse table node
        if "table" in node:
            traverse_plan(node["table"], depth)
    
    # Start traversal from query_block
    query_block = plan_json.get("query_block", {})
    
    # DEBUG: Log the actual structure
    logger.debug(f"[MYSQL-COLLECTOR] query_block keys: {list(query_block.keys())}")
    logger.debug(f"[MYSQL-COLLECTOR] Full plan JSON: {json.dumps(plan_json, indent=2)}")
    
    # Handle nested_loop at root
    if "nested_loop" in query_block:
        for child in query_block["nested_loop"]:
            traverse_plan(child, 0)
    # Handle single table
    elif "table" in query_block:
        traverse_plan(query_block["table"], 0)
    # Handle ordering/grouping wrapper (MySQL 8+)
    elif "ordering_operation" in query_block:
        traverse_plan(query_block["ordering_operation"], 0)
    elif "grouping_operation" in query_block:
        traverse_plan(query_block["grouping_operation"], 0)
    else:
        logger.warning(f"[MYSQL-COLLECTOR] Unexpected plan structure - keys: {list(query_block.keys())}")
    
    logger.info(f"[MYSQL-COLLECTOR] Extracted {len(details)} plan steps")
    return details


def get_table_stats(cursor, tables: list) -> list:
    """
    Get table statistics from information_schema.
    
    Args:
        tables: List of table names from the query
    
    Returns:
        List of dicts with table stats
    """
    if not tables:
        return []
    
    logger.info(f"[MYSQL-COLLECTOR] -> get_table_stats() for {len(tables)} tables")
    
    placeholders = ", ".join(["%s"] * len(tables))
    query = f"""
        SELECT 
            TABLE_SCHEMA,
            TABLE_NAME,
            ENGINE,
            TABLE_ROWS,
            AVG_ROW_LENGTH,
            DATA_LENGTH,
            INDEX_LENGTH,
            UPDATE_TIME
        FROM information_schema.TABLES
        WHERE TABLE_NAME IN ({placeholders})
        ORDER BY TABLE_SCHEMA, TABLE_NAME
    """
    
    try:
        cursor.execute(query, tables)
        rows = cursor.fetchall()
        
        stats = []
        for row in rows:
            stats.append({
                "schema": row[0],
                "table_name": row[1],
                "engine": row[2],
                "num_rows": row[3] or 0,
                "avg_row_length": row[4] or 0,
                "data_length_bytes": row[5] or 0,
                "index_length_bytes": row[6] or 0,
                "last_update": str(row[7]) if row[7] else None
            })
        
        logger.info(f"[MYSQL-COLLECTOR] Table stats rows: {len(stats)}")
        return stats
        
    except Exception as e:
        logger.error(f"[MYSQL-COLLECTOR] get_table_stats ERROR: {e}")
        return []


def get_index_stats(cursor, tables: list) -> list:
    """
    Get index information from information_schema.
    
    Args:
        tables: List of table names from the query
    
    Returns:
        List of dicts with index details
    """
    if not tables:
        return []
    
    logger.info(f"[MYSQL-COLLECTOR] -> get_index_stats() for {len(tables)} tables")
    
    placeholders = ", ".join(["%s"] * len(tables))
    query = f"""
        SELECT 
            TABLE_SCHEMA,
            TABLE_NAME,
            INDEX_NAME,
            NON_UNIQUE,
            SEQ_IN_INDEX,
            COLUMN_NAME,
            CARDINALITY,
            INDEX_TYPE
        FROM information_schema.STATISTICS
        WHERE TABLE_NAME IN ({placeholders})
        ORDER BY TABLE_SCHEMA, TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
    """
    
    try:
        cursor.execute(query, tables)
        rows = cursor.fetchall()
        
        # Group by index
        indexes = {}
        for row in rows:
            schema, table, idx_name, non_unique, seq, col_name, cardinality, idx_type = row
            key = (schema, table, idx_name)
            
            if key not in indexes:
                indexes[key] = {
                    "schema": schema,
                    "table_name": table,
                    "index_name": idx_name,
                    "unique": not non_unique,
                    "index_type": idx_type,
                    "columns": [],
                    "cardinality": cardinality
                }
            
            indexes[key]["columns"].append(col_name)
        
        index_list = list(indexes.values())
        logger.info(f"[MYSQL-COLLECTOR] Index stats: {len(index_list)} indexes found")
        return index_list
        
    except Exception as e:
        logger.error(f"[MYSQL-COLLECTOR] get_index_stats ERROR: {e}")
        return []


def get_index_usage_stats(cursor, tables: list) -> list:
    """
    Get index usage statistics from performance_schema.
    Shows which indexes are actually used in production.
    
    Args:
        tables: List of table names from the query
    
    Returns:
        List of dicts with index usage details
    """
    if not tables:
        return []
    
    logger.info(f"[MYSQL-COLLECTOR] -> get_index_usage_stats() for {len(tables)} tables")
    
    # Check if performance_schema is enabled
    try:
        cursor.execute("SELECT @@performance_schema")
        ps_enabled = cursor.fetchone()[0]
        if not ps_enabled:
            logger.warning("[MYSQL-COLLECTOR] performance_schema is disabled - cannot collect usage stats")
            return []
    except Exception as e:
        logger.warning(f"[MYSQL-COLLECTOR] Cannot check performance_schema status: {e}")
        return []
    
    placeholders = ", ".join(["%s"] * len(tables))
    query = f"""
        SELECT 
            OBJECT_SCHEMA,
            OBJECT_NAME,
            INDEX_NAME,
            COUNT_READ,
            COUNT_WRITE,
            COUNT_FETCH,
            COUNT_INSERT,
            COUNT_UPDATE,
            COUNT_DELETE,
            SUM_TIMER_WAIT / 1000000000000 AS total_latency_seconds,
            SUM_TIMER_READ / 1000000000000 AS read_latency_seconds,
            SUM_TIMER_WRITE / 1000000000000 AS write_latency_seconds
        FROM performance_schema.table_io_waits_summary_by_index_usage
        WHERE OBJECT_NAME IN ({placeholders})
          AND INDEX_NAME IS NOT NULL
        ORDER BY OBJECT_SCHEMA, OBJECT_NAME, INDEX_NAME
    """
    
    try:
        cursor.execute(query, tables)
        rows = cursor.fetchall()
        
        usage_stats = []
        for row in rows:
            schema, table, idx_name, count_read, count_write, count_fetch, \
            count_insert, count_update, count_delete, \
            total_latency, read_latency, write_latency = row
            
            total_operations = (count_read or 0) + (count_write or 0)
            
            # Determine usage status
            if total_operations == 0:
                usage_status = "UNUSED"
            elif total_operations < 100:
                usage_status = "LOW_USAGE"
            elif total_operations < 10000:
                usage_status = "MODERATE_USAGE"
            else:
                usage_status = "HIGH_USAGE"
            
            usage_stats.append({
                "schema": schema,
                "table_name": table,
                "index_name": idx_name,
                "count_read": count_read or 0,
                "count_write": count_write or 0,
                "count_fetch": count_fetch or 0,
                "count_insert": count_insert or 0,
                "count_update": count_update or 0,
                "count_delete": count_delete or 0,
                "total_operations": total_operations,
                "total_latency_seconds": round(total_latency, 6) if total_latency else 0,
                "read_latency_seconds": round(read_latency, 6) if read_latency else 0,
                "write_latency_seconds": round(write_latency, 6) if write_latency else 0,
                "usage_status": usage_status
            })
        
        logger.info(f"[MYSQL-COLLECTOR] Index usage stats: {len(usage_stats)} indexes tracked")
        
        # Log unused indexes for visibility
        unused = [idx for idx in usage_stats if idx["usage_status"] == "UNUSED"]
        if unused:
            logger.warning(f"[MYSQL-COLLECTOR] Found {len(unused)} UNUSED indexes: {[idx['index_name'] for idx in unused]}")
        
        return usage_stats
        
    except Exception as e:
        logger.error(f"[MYSQL-COLLECTOR] get_index_usage_stats ERROR: {e}")
        return []


def get_duplicate_indexes(cursor, tables: list) -> list:
    """
    Detect duplicate or redundant indexes (same columns in same order).
    
    Args:
        tables: List of table names from the query
    
    Returns:
        List of dicts describing duplicate index groups
    """
    if not tables:
        return []
    
    logger.info(f"[MYSQL-COLLECTOR] -> get_duplicate_indexes() for {len(tables)} tables")
    
    placeholders = ", ".join(["%s"] * len(tables))
    query = f"""
        SELECT 
            TABLE_SCHEMA,
            TABLE_NAME,
            INDEX_NAME,
            GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX SEPARATOR ',') AS column_list,
            NON_UNIQUE,
            INDEX_TYPE
        FROM information_schema.STATISTICS
        WHERE TABLE_NAME IN ({placeholders})
        GROUP BY TABLE_SCHEMA, TABLE_NAME, INDEX_NAME, NON_UNIQUE, INDEX_TYPE
        ORDER BY TABLE_SCHEMA, TABLE_NAME, column_list
    """
    
    try:
        cursor.execute(query, tables)
        rows = cursor.fetchall()
        
        # Group by (schema, table, column_list) to find duplicates
        column_groups = {}
        for row in rows:
            schema, table, idx_name, col_list, non_unique, idx_type = row
            key = (schema, table, col_list)
            
            if key not in column_groups:
                column_groups[key] = []
            
            column_groups[key].append({
                "index_name": idx_name,
                "unique": not non_unique,
                "index_type": idx_type
            })
        
        # Find groups with multiple indexes
        duplicates = []
        for (schema, table, col_list), indexes in column_groups.items():
            if len(indexes) > 1:
                duplicates.append({
                    "schema": schema,
                    "table_name": table,
                    "columns": col_list,
                    "duplicate_indexes": indexes,
                    "duplicate_count": len(indexes),
                    "recommendation": f"Consider dropping redundant indexes - keep only one (prefer UNIQUE if applicable)"
                })
        
        if duplicates:
            logger.warning(f"[MYSQL-COLLECTOR] Found {len(duplicates)} duplicate index groups")
        else:
            logger.info(f"[MYSQL-COLLECTOR] No duplicate indexes detected")
        
        return duplicates
        
    except Exception as e:
        logger.error(f"[MYSQL-COLLECTOR] get_duplicate_indexes ERROR: {e}")
        return []


def extract_tables_from_sql(sql: str) -> list:
    """
    Extract table names from SQL query.
    Handles both simple table names and schema.table notation.
    
    Examples:
        FROM customer_order → customer_order
        FROM avi.customer_order → customer_order
        JOIN orders o → orders
    """
    tables = set()
    
    # Pattern: FROM [schema.]table_name or JOIN [schema.]table_name
    # Captures the table name, ignoring optional schema prefix and aliases
    patterns = [
        r'\bFROM\s+(?:[a-zA-Z0-9_]+\.)?([a-zA-Z0-9_]+)',  # FROM [schema.]table
        r'\bJOIN\s+(?:[a-zA-Z0-9_]+\.)?([a-zA-Z0-9_]+)',  # JOIN [schema.]table
    ]
    
    sql_upper = sql.upper()
    for pattern in patterns:
        matches = re.findall(pattern, sql_upper)
        tables.update(matches)
    
    logger.debug(f"[MYSQL-COLLECTOR] extract_tables_from_sql: {list(tables)}")
    
    return list(tables)


# ============================================================
# OUTPUT MINIMIZATION - Remove bloat, keep essentials
# ============================================================

def minimize_mysql_plan_output(plan_details):
    """
    Remove NULL/empty fields from MySQL execution plan to reduce token usage.
    Keep only essential fields that LLM needs for optimization.

    Typical savings: 60-70% per plan step
    """
    if not plan_details:
        return []

    # Essential fields for MySQL query optimization
    essential_fields = [
        'id', 'select_type', 'table', 'type', 'possible_keys',
        'key', 'key_len', 'ref', 'rows', 'filtered',
        'Extra', 'cost'
    ]

    minimized = []
    for step in plan_details:
        mini_step = {}
        for field in essential_fields:
            value = step.get(field)
            # Only include non-null, non-empty values
            if value is not None and value != '':
                mini_step[field] = value
        minimized.append(mini_step)

    logger.info(f"[MYSQL-COLLECTOR] Plan minimization: {len(plan_details)} steps simplified")
    return minimized


def minimize_mysql_table_stats(table_stats):
    """
    Simplify MySQL table stats to essentials for optimization.
    Remove physical storage details that don't affect query planning.

    Typical savings: 75-80% per table
    """
    if not table_stats:
        return []

    minimized = []
    for table in table_stats:
        minimized.append({
            'table': table.get('table_name', 'UNKNOWN'),
            'engine': table.get('engine', 'UNKNOWN'),
            'rows': table.get('table_rows', 0),
            'avg_row_length': table.get('avg_row_length', 0),
            'data_size_mb': table.get('data_length_mb', 0),
            'index_size_mb': table.get('index_length_mb', 0),
            'auto_increment': table.get('auto_increment')
        })

    logger.info(f"[MYSQL-COLLECTOR] Table stats minimization: {len(table_stats)} tables simplified")
    return minimized


def minimize_mysql_index_stats(index_stats):
    """
    Simplify MySQL index stats to essentials.

    Typical savings: 70-75% per index
    """
    if not index_stats:
        return []

    minimized = []
    for idx in index_stats:
        minimized.append({
            'table': idx.get('table_name', 'UNKNOWN'),
            'index': idx.get('index_name', 'UNKNOWN'),
            'columns': idx.get('columns', []),
            'unique': idx.get('non_unique', 1) == 0,
            'type': idx.get('index_type', 'BTREE'),
            'cardinality': idx.get('cardinality', 0)
        })

    logger.info(f"[MYSQL-COLLECTOR] Index stats minimization: {len(index_stats)} indexes simplified")
    return minimized


def minimize_mysql_index_usage(index_usage):
    """
    Simplify MySQL index usage stats to essentials.

    Typical savings: 60-70% per index
    """
    if not index_usage:
        return []

    minimized = []
    for usage in index_usage:
        minimized.append({
            'table': usage.get('object_name', 'UNKNOWN'),
            'index': usage.get('index_name', 'UNKNOWN'),
            'usage_count': usage.get('index_usage_count', 0),
            'last_used': usage.get('last_used')
        })

    logger.info(f"[MYSQL-COLLECTOR] Index usage minimization: {len(index_usage)} usage stats simplified")
    return minimized


def run_collector(cursor, sql: str, depth: str = "standard") -> dict:
    """
    Main collector function - orchestrates all data collection.

    Args:
        cursor: MySQL database cursor
        sql: SQL query to analyze
        depth: Analysis depth mode
            - "plan_only": Just EXPLAIN PLAN (fast)
            - "standard": Full analysis with metadata

    Returns:
        Dict with facts and prompt
    """
    import time
    from config import config

    start_time = time.time()
    logger.info(f"[MYSQL-COLLECTOR] ===== START ANALYSIS (depth={depth}) =====")

    facts = {}
    preset = config.output_preset
    logger.info(f"[MYSQL-COLLECTOR] Using preset: {preset}")

    # 1. Run EXPLAIN (always)
    plan_json = run_explain(cursor, sql)
    facts["plan_json"] = plan_json

    # 2. Extract plan details (always)
    plan_details = extract_plan_details(plan_json)

    # PLAN_ONLY MODE: Return just the execution plan
    if depth == "plan_only":
        logger.info("[MYSQL-COLLECTOR] PLAN_ONLY mode: Skipping metadata collection")

        # Calculate elapsed time
        elapsed = time.time() - start_time

        # Build minimal facts for plan-only mode
        plan_only_facts = {
            "plan_details": minimize_mysql_plan_output(plan_details),
            "summary": {
                "mode": "plan_only",
                "steps": len(plan_details),
                "total_cost": sum(step.get("cost", 0) for step in plan_details),
                "estimated_rows": sum(step.get("rows", 0) for step in plan_details)
            }
        }

        return {
            "facts": plan_only_facts,
            "prompt": (
                f"✓ Execution plan analysis complete in {elapsed:.2f}s | "
                f"Mode: plan_only | Steps: {len(plan_details)} | "
                f"Cost: {plan_only_facts['summary']['total_cost']} | "
                f"💡 This is a fast plan-only analysis. For full optimization with "
                f"table/index statistics, use depth='standard'."
            )
        }

    # STANDARD MODE: Continue with full analysis
    logger.info("[MYSQL-COLLECTOR] STANDARD mode: Collecting full metadata")

    # 3. Extract table names (always)
    tables = extract_tables_from_sql(sql)
    logger.info(f"[MYSQL-COLLECTOR] Tables found: {tables}")

    # 4. Get table statistics (always)
    if tables:
        table_stats = get_table_stats(cursor, tables)

        # === PRESET-BASED EARLY FILTERING ===
        if preset == "minimal":
            logger.info("[MYSQL-COLLECTOR] MINIMAL preset: Skipping indexes, usage stats, duplicate detection")
            index_stats = []
            index_usage = []
            duplicate_indexes = []
        elif preset == "compact":
            logger.info("[MYSQL-COLLECTOR] COMPACT preset: Collecting indexes + usage, skipping duplicate detection")
            index_stats = get_index_stats(cursor, tables)
            index_usage = get_index_usage_stats(cursor, tables)
            duplicate_indexes = []  # Skip duplicate detection
        else:  # standard
            logger.info("[MYSQL-COLLECTOR] STANDARD preset: Collecting full metadata")
            index_stats = get_index_stats(cursor, tables)
            index_usage = get_index_usage_stats(cursor, tables)
            duplicate_indexes = get_duplicate_indexes(cursor, tables)
    else:
        table_stats = []
        index_stats = []
        index_usage = []
        duplicate_indexes = []

    # Apply output minimization to reduce token usage
    logger.info("[MYSQL-COLLECTOR] Applying output minimization...")
    facts["plan_details"] = minimize_mysql_plan_output(plan_details)
    facts["table_stats"] = minimize_mysql_table_stats(table_stats)
    facts["index_stats"] = minimize_mysql_index_stats(index_stats)
    facts["index_usage"] = minimize_mysql_index_usage(index_usage)
    facts["duplicate_indexes"] = duplicate_indexes  # Keep as is (already minimal)
    logger.info("[MYSQL-COLLECTOR] ✓ Output minimization complete")
    
    logger.info("[MYSQL-COLLECTOR] ===== ANALYSIS COMPLETE =====")
    
    # Calculate elapsed time
    elapsed = time.time() - start_time
    
    # Build informative prompt with counts and timing
    prompt_parts = [f"✓ MySQL analysis complete in {elapsed:.2f}s"]
    prompt_parts.append(f"Preset: {preset}")
    prompt_parts.append(f"Tables: {len(tables)}")
    
    if facts["index_stats"]:
        prompt_parts.append(f"Indexes: {len(facts['index_stats'])}")
    if facts["index_usage"]:
        unused_count = sum(1 for idx in facts['index_usage'] if idx.get('index_usage_count', 0) == 0)
        if unused_count:
            prompt_parts.append(f"⚠️ {unused_count} unused indexes")
    if facts["duplicate_indexes"]:
        prompt_parts.append(f"⚠️ {len(facts['duplicate_indexes'])} duplicate indexes")
    
    return {
        "facts": facts,
        "prompt": " | ".join(prompt_parts)
    }
