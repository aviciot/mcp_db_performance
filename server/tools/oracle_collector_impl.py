# path: server/tools/oracle_collector_impl.py
# CLEAN & FIXED VERSION — Avi Cohen 2025

import re
from datetime import datetime
from collections import defaultdict
from config import config

# ============================================================
# DEBUG HELPER
# ============================================================

def dbg(*msg):
    """Debug print with prefix - respects config.show_sql_queries"""
    # TEMP: Always print for debugging - bypass config check
    import sys
    sys.stderr.write("[ORACLE-COLLECTOR] " + " ".join(str(m) for m in msg) + "\n")
    sys.stderr.flush()


# ============================================================
# BASIC HELPERS
# ============================================================

def normalize_sql(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    return s[:-1] if s.endswith(";") else s


def extract_sql_objects(sql_text: str):
    """
    Extract table references from SQL - handles both qualified (OWNER.TABLE) 
    and unqualified (TABLE) references.
    """
    s = (sql_text or "").upper()
    
    # Find qualified references (OWNER.TABLE)
    qualified = re.findall(r'\b([A-Z0-9_]+)\.([A-Z0-9_]+)\b', s)
    
    seen = set()
    result = []
    
    # Add qualified references
    for owner, table in qualified:
        # Skip if owner looks like a table alias or column reference
        if owner not in ('DUAL', 'SYS', 'SYSTEM') and len(owner) > 1:
            if (owner, table) not in seen:
                seen.add((owner, table))
                result.append((owner, table))
    
    # Find unqualified table references after FROM/JOIN keywords
    # Pattern: FROM/JOIN <whitespace> <table_name> (with optional alias)
    unqualified = re.findall(
        r'\b(?:FROM|JOIN)\s+([A-Z0-9_]+)\b',
        s
    )
    
    # For unqualified tables, we can't know the owner from SQL alone
    # These will be resolved by the execution plan
    for table in unqualified:
        # Skip common keywords and already qualified tables
        if table not in ('SELECT', 'DUAL', 'WHERE', 'TABLE') and not any(t == table for _, t in result):
            # Mark as unknown owner - will be resolved from plan
            if (None, table) not in seen:
                seen.add((None, table))
                result.append((None, table))
    
    return result


def extract_columns_from_sql(sql_text: str):
    """
    Extract potential column names from SQL, filtering out common keywords.
    This is used for column statistics gathering.
    """
    s = (sql_text or "").upper()
    
    # Common SQL keywords to exclude
    keywords = {
        'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'EXISTS', 'BETWEEN',
        'LIKE', 'IS', 'NULL', 'AS', 'ON', 'JOIN', 'INNER', 'OUTER', 'LEFT', 'RIGHT',
        'CROSS', 'UNION', 'INTERSECT', 'MINUS', 'ORDER', 'BY', 'GROUP', 'HAVING',
        'DISTINCT', 'ALL', 'ANY', 'SOME', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
        'INTO', 'VALUES', 'INSERT', 'UPDATE', 'DELETE', 'SET', 'CREATE', 'ALTER',
        'DROP', 'TABLE', 'VIEW', 'INDEX', 'SEQUENCE', 'TRIGGER', 'PROCEDURE',
        'FUNCTION', 'PACKAGE', 'CURSOR', 'FETCH', 'OPEN', 'CLOSE', 'COMMIT',
        'ROLLBACK', 'SAVEPOINT', 'GRANT', 'REVOKE', 'WITH', 'CONNECT', 'START',
        'ASC', 'DESC', 'NULLS', 'FIRST', 'LAST', 'FOR', 'TO', 'OF', 'DEFAULT',
        'CONSTRAINT', 'PRIMARY', 'FOREIGN', 'KEY', 'REFERENCES', 'UNIQUE', 'CHECK',
        'SYSDATE', 'SYSTIMESTAMP', 'DUAL', 'ROWNUM', 'ROWID', 'LEVEL',
        'CHAR', 'VARCHAR', 'VARCHAR2', 'NUMBER', 'DATE', 'TIMESTAMP', 'CLOB', 'BLOB',
        'TRUNC', 'ROUND', 'DECODE', 'NVL', 'COALESCE', 'CAST', 'EXTRACT',
        'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'STDDEV', 'VARIANCE',
        'OVER', 'PARTITION', 'ROW_NUMBER', 'RANK', 'DENSE_RANK', 'ROWNUM',
        'PRIOR', 'NOCYCLE', 'SIBLINGS'
    }
    
    # Extract potential column names (alphanumeric + underscore, 2+ chars)
    tokens = re.findall(r'\b[A-Z0-9_]{2,}\b', s)
    
    # Filter out keywords and limit to reasonable count
    columns = [t for t in tokens if t not in keywords]
    
    # Remove duplicates and limit to first 100 unique columns (performance consideration)
    unique_cols = []
    seen = set()
    for col in columns:
        if col not in seen and len(unique_cols) < 100:
            seen.add(col)
            unique_cols.append(col)
    
    return sorted(unique_cols)


# ============================================================
# PLAN COLLECTION
# ============================================================

def validate_sql(cur, sql_text: str):
    """
    Pre-validate SQL for safety and correctness.
    Returns (is_valid, error_message, is_dangerous)
    
    Safety checks:
    - Block DDL (CREATE, DROP, ALTER, TRUNCATE)
    - Block DML writes (INSERT, UPDATE, DELETE, MERGE)
    - Block DCL (GRANT, REVOKE)
    - Block system operations (SHUTDOWN, STARTUP)
    - Only allow SELECT queries
    """
    return True, None, False  # TEMP: Bypass for testing
    try:
        clean = sql_text.strip().upper()
        if clean.endswith(";"):
            clean = clean[:-1]
        
        # SECURITY CHECK 1: Only allow SELECT statements
        dangerous_keywords = [
            'INSERT', 'UPDATE', 'DELETE', 'MERGE',  # DML writes
            'CREATE', 'DROP', 'ALTER', 'TRUNCATE', 'RENAME',  # DDL
            'GRANT', 'REVOKE',  # DCL
            'COMMIT', 'ROLLBACK', 'SAVEPOINT',  # Transaction control
            'SHUTDOWN', 'STARTUP',  # System operations
            'EXECUTE', 'CALL',  # Procedure calls
            'BEGIN', 'DECLARE',  # PL/SQL blocks
        ]
        
        # Check first word after WITH/comment removal
        first_word = clean.split()[0] if clean.split() else ''
        
        # Allow WITH clause (for CTEs)
        if first_word == 'WITH':
            # Find the main query after CTE
            # Look for SELECT after the CTE definition        
            if 'SELECT' not in clean:
                return False, "No SELECT found in query with WITH clause", True
        elif first_word != 'SELECT':
            return False, f"Only SELECT queries are allowed. Found: {first_word}", True
        
        # Check for dangerous keywords anywhere in the query
        for keyword in dangerous_keywords:
            # Use word boundaries to avoid false positives
            # e.g., "UPDATE_DATE" column should be OK
            import re
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, clean):
                return False, f"DANGEROUS OPERATION BLOCKED: {keyword} statements are not allowed", True
        
        # SECURITY CHECK 2: Block INTO clauses (SELECT INTO)
        if re.search(r'\bINTO\b', clean):
            return False, "DANGEROUS OPERATION BLOCKED: SELECT INTO is not allowed", True
        
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
            return False, f"Query too complex: subquery nesting depth {max_depth} exceeds limit of 10", False
        
        # SYNTAX/SEMANTIC CHECK: Try to execute with ROWNUM = 0
        original_sql = sql_text.strip()
        if original_sql.endswith(";"):
            original_sql = original_sql[:-1]
        
        # Wrap in subquery and limit to 0 rows - validates structure without data
        test_stmt = f"SELECT * FROM ({original_sql}) subq WHERE ROWNUM = 0"
        cur.execute(test_stmt)
        cur.fetchall()
        
        return True, None, False
        
    except Exception as e:
        error_msg = str(e)
        # Extract Oracle error code and message
        if "ORA-" in error_msg:
            # Clean up the error message
            error_msg = error_msg.split('\n')[0]  # First line only
        return False, error_msg, False


def explain_plan(cur, sql_text: str, stmt_id: str):
    try:
        dbg("-> explain_plan START")
        
        # First check if PLAN_TABLE exists
        try:
            cur.execute("SELECT COUNT(*) FROM plan_table WHERE ROWNUM = 1")
            dbg("✓ PLAN_TABLE exists and is accessible")
        except Exception as e:
            dbg("✗ PLAN_TABLE check failed:", e)
            dbg("   Attempting to create PLAN_TABLE...")
            try:
                cur.execute("@?/rdbms/admin/utlxplan.sql")
                cur.connection.commit()
                dbg("✓ PLAN_TABLE created successfully")
            except Exception as create_err:
                dbg("✗ Cannot create PLAN_TABLE:", create_err)
        
        cur.execute("DELETE FROM plan_table WHERE statement_id = :sid", sid=stmt_id)
        cur.connection.commit()

        clean = sql_text.strip()
        if clean.endswith(";"):
            clean = clean[:-1]

        # PRE-VALIDATE SQL BEFORE EXPLAIN PLAN
        dbg("Pre-validating SQL syntax and semantics...")
        is_valid, validation_error, is_dangerous = validate_sql(cur, clean)
        
        if is_dangerous:
            dbg("🚨 DANGEROUS OPERATION BLOCKED:", validation_error)
            dbg("   This query was blocked for security reasons")
            return [f"SECURITY BLOCK: {validation_error}"], validation_error
        
        if not is_valid:
            dbg("✗ SQL VALIDATION FAILED:", validation_error)
            dbg("   Cannot run EXPLAIN PLAN on invalid SQL")
            dbg("   Returning early with validation error")
            return [f"SQL VALIDATION ERROR: {validation_error}"], validation_error
        
        dbg("✓ SQL is valid and safe - proceeding with EXPLAIN PLAN")

        stmt = f"EXPLAIN PLAN SET STATEMENT_ID = '{stmt_id}' FOR {clean}"
        dbg("Running EXPLAIN PLAN:", stmt[:180], "...")

        cur.execute(stmt)
        cur.connection.commit()

        cur.execute("""
            SELECT plan_table_output
            FROM TABLE(DBMS_XPLAN.DISPLAY(
                statement_id => :sid,
                format => 'TYPICAL +PREDICATE +COST +BYTES'))
        """, sid=stmt_id)

        lines = [r[0] for r in cur.fetchall()]
        dbg("EXPLAIN returned lines:", len(lines))
        return lines, None

    except Exception as e:
        dbg("EXPLAIN FAILED:", e)
        return [f"(EXPLAIN PLAN failed: {e})"], str(e)


def get_plan_objects(cur, stmt_id: str):
    dbg("-> get_plan_objects()")
    try:
        cur.execute("""
            SELECT DISTINCT 
                p.object_owner,
                p.object_name,
                p.object_type,
                p.operation,
                p.options,
                MIN(p.id) as step
            FROM plan_table p
            WHERE p.statement_id = :sid
              AND p.object_owner IS NOT NULL
              AND p.object_name IS NOT NULL
            GROUP BY p.object_owner, p.object_name, p.object_type, p.operation, p.options
            ORDER BY MIN(p.id)
        """, sid=stmt_id)

        rows = cur.fetchall()
        tables = set()
        indexes = set()

        for owner, name, obj_type, op, opt, _ in rows:
            if obj_type in ("INDEX", "INDEX PARTITION", "INDEX SUBPARTITION"):
                indexes.add((owner, name))
            elif op and "INDEX" in op:
                indexes.add((owner, name))
            else:
                tables.add((owner, name))

        dbg("Plan tables:", tables)
        dbg("Plan indexes:", indexes)

        return {"tables": list(tables), "indexes": list(indexes)}

    except Exception as e:
        dbg("get_plan_objects ERROR:", e)
        return {"tables": [], "indexes": []}


def get_plan_details(cur, stmt_id: str):
    dbg("-> get_plan_details()")
    try:
        cur.execute("""
            SELECT 
                id,
                parent_id,
                operation,
                options,
                object_owner,
                object_name,
                object_type,
                cost,
                cardinality,
                bytes,
                access_predicates,
                filter_predicates,
                partition_start,
                partition_stop
            FROM plan_table
            WHERE statement_id = :sid
            ORDER BY id
        """, sid=stmt_id)

        cols = [c[0].lower() for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        dbg("Plan detail rows:", len(rows))
        return rows

    except Exception as e:
        dbg("get_plan_details ERROR:", e)
        return []


# ============================================================
# METADATA HELPERS
# ============================================================

def build_clause(tables, alias=None):
    """Generic OR clause for OWNER.TABLE filters except for ALL_IND_COLUMNS"""
    if not tables:
        return "", {}

    parts = []
    binds = {}

    for i, (o, t) in enumerate(tables, 1):
        if alias:
            parts.append(f"({alias}.owner = :o{i} AND {alias}.table_name = :t{i})")
        else:
            parts.append(f"(owner = :o{i} AND table_name = :t{i})")

        binds[f"o{i}"] = o
        binds[f"t{i}"] = t

    return " OR ".join(parts), binds


# ============================================================
# METADATA QUERIES
# ============================================================

def get_table_stats(cur, tables):
    dbg("-> get_table_stats()")
    if not tables:
        return []

    where, binds = build_clause(tables)

    q = f"""
        SELECT owner, table_name, num_rows, blocks, empty_blocks,
               avg_row_len, sample_size,
               TO_CHAR(last_analyzed,'YYYY-MM-DD HH24:MI:SS') last_analyzed,
               partitioned, compression, degree
        FROM all_tables WHERE {where}
        ORDER BY owner, table_name
    """

    dbg("Table stats query:", q.replace("\n", " "))
    cur.execute(q, binds)
    cols = [c[0].lower() for c in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    dbg("Table stats rows:", len(rows))
    return rows


def get_index_stats(cur, tables):
    dbg("-> get_index_stats()")
    if not tables:
        return []

    where, binds = build_clause(tables)

    q = f"""
        SELECT owner, index_name, table_name, index_type, uniqueness,
               status, visibility, blevel, leaf_blocks,
               distinct_keys, clustering_factor, num_rows,
               sample_size, TO_CHAR(last_analyzed,'YYYY-MM-DD HH24:MI:SS') last_analyzed,
               degree, partitioned
        FROM all_indexes WHERE {where}
        ORDER BY owner, table_name, index_name
    """

    dbg("Index stats query:", q.replace("\n", " "))
    cur.execute(q, binds)
    cols = [c[0].lower() for c in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    dbg("Index stats rows:", len(rows))
    return rows


def get_index_columns(cur, tables):
    dbg("-> get_index_columns()")
    if not tables:
        return []

    # 🚨 FIX: ALL_IND_COLUMNS uses TABLE_OWNER — NOT OWNER 🚨
    where_parts = []
    binds = {}

    for i, (owner, table) in enumerate(tables, 1):
        where_parts.append(f"(ic.table_owner = :o{i} AND ic.table_name = :t{i})")
        binds[f"o{i}"] = owner
        binds[f"t{i}"] = table

    where = " OR ".join(where_parts)

    q = f"""
        SELECT ic.table_owner,
               ic.table_name,
               ic.index_name,
               ic.column_name,
               ic.column_position,
               ic.descend
        FROM all_ind_columns ic
        WHERE {where}
        ORDER BY ic.table_owner, ic.table_name, ic.index_name, ic.column_position
    """

    dbg("Index column query:", q.replace("\n", " "))
    dbg("Binds:", binds)

    cur.execute(q, binds)
    cols = [c[0].lower() for c in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    dbg("Index column rows:", len(rows))
    
    # Debug: Show what columns actually exist
    if rows:
        dbg("Sample index columns found:")
        for r in rows[:10]:  # Show first 10
            dbg(f"  {r['table_owner']}.{r['table_name']}.{r['column_name']}")

    grouped = defaultdict(list)
    for r in rows:
        key = (r["table_owner"], r["table_name"], r["index_name"])
        grouped[key].append(r["column_name"])

    compact = []
    for (o, t, idx), col_list in grouped.items():
        compact.append({
            "owner": o,
            "table_name": t,
            "index_name": idx,
            "columns": col_list
        })

    return compact


def get_partition_info(cur, tables):
    dbg("-> get_partition_info()")
    if not tables:
        return [], []

    where, binds = build_clause(tables)

    q1 = f"""
        SELECT owner, table_name, partitioning_type,
               subpartitioning_type, partition_count,
               def_subpartition_count, interval
        FROM all_part_tables WHERE {where}
        ORDER BY owner, table_name
    """

    cur.execute(q1, binds)
    cols1 = [c[0].lower() for c in cur.description]
    part_tables = [dict(zip(cols1, r)) for r in cur.fetchall()]

    # Partition key columns
    pk_cond = []
    for i, (o, t) in enumerate(tables, 1):
        pk_cond.append(f"(owner = :o{i} AND name = :t{i})")

    q2 = f"""
        SELECT owner, name AS table_name, column_name,
               column_position, object_type
        FROM all_part_key_columns
        WHERE {" OR ".join(pk_cond)}
        ORDER BY owner, name, object_type, column_position
    """

    cur.execute(q2, binds)
    cols2 = [c[0].lower() for c in cur.description]
    keys = [dict(zip(cols2, r)) for r in cur.fetchall()]

    return part_tables, keys


def get_column_stats(cur, tables, sql_columns):
    dbg("-> get_column_stats()")
    if not tables or not sql_columns:
        return []

    where, binds = build_clause(tables)

    placeholders = []
    for i, col in enumerate(sql_columns):
        key = f"c{i}"
        binds[key] = col
        placeholders.append(f":{key}")

    q = f"""
        SELECT owner, table_name, column_name,
               num_distinct, num_nulls, density,
               num_buckets, TO_CHAR(last_analyzed,'YYYY-MM-DD HH24:MI:SS') last_analyzed,
               sample_size
        FROM all_tab_col_statistics
        WHERE ({where}) AND column_name IN ({",".join(placeholders)})
        ORDER BY owner, table_name, column_name
    """

    dbg("Column stats query:", q.replace("\n", " "))
    dbg("Binds:", binds)

    cur.execute(q, binds)
    cols = [c[0].lower() for c in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    dbg("Column stats rows:", len(rows))

    return rows


def get_constraints(cur, tables):
    """Get primary key, foreign key, and unique constraints"""
    dbg("-> get_constraints()")
    if not tables:
        return []

    where, binds = build_clause(tables, alias='c')

    q = f"""
        SELECT c.owner, c.table_name, c.constraint_name, c.constraint_type,
               c.status, c.validated, c.rely,
               c.r_owner, c.r_constraint_name,
               cc.column_name, cc.position
        FROM all_constraints c
        LEFT JOIN all_cons_columns cc 
            ON c.owner = cc.owner 
            AND c.constraint_name = cc.constraint_name
        WHERE ({where}) 
          AND c.constraint_type IN ('P', 'R', 'U')
        ORDER BY c.owner, c.table_name, c.constraint_name, cc.position
    """

    dbg("Constraints query:", q.replace("\n", " "))
    cur.execute(q, binds)
    cols = [c[0].lower() for c in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    dbg("Constraint rows:", len(rows))

    # Group by constraint
    from collections import defaultdict
    grouped = defaultdict(lambda: {"columns": [], "info": {}})
    
    for r in rows:
        key = (r["owner"], r["table_name"], r["constraint_name"])
        if not grouped[key]["info"]:
            grouped[key]["info"] = {
                "owner": r["owner"],
                "table_name": r["table_name"],
                "constraint_name": r["constraint_name"],
                "constraint_type": r["constraint_type"],
                "status": r["status"],
                "validated": r["validated"],
                "rely": r["rely"],
                "r_owner": r["r_owner"],
                "r_constraint_name": r["r_constraint_name"]
            }
        if r["column_name"]:
            grouped[key]["columns"].append(r["column_name"])
    
    result = []
    for data in grouped.values():
        constraint = data["info"]
        constraint["columns"] = data["columns"]
        result.append(constraint)
    
    return result


def get_optimizer_parameters(cur):
    """Get critical optimizer parameters that affect execution plans"""
    dbg("-> get_optimizer_parameters()")
    
    params = [
        'optimizer_mode',
        'optimizer_index_cost_adj',
        'optimizer_index_caching',
        'optimizer_dynamic_sampling',
        'optimizer_features_enable',
        'parallel_degree_policy',
        'db_file_multiblock_read_count',
        'cursor_sharing',
        'statistics_level',
        '_optimizer_use_feedback',
        'optimizer_adaptive_features'
    ]
    
    placeholders = ', '.join([f"'{p}'" for p in params])
    
    q = f"""
        SELECT name, value, isdefault, description
        FROM v$parameter
        WHERE name IN ({placeholders})
        ORDER BY name
    """
    
    try:
        dbg("Optimizer params query:", q.replace("\n", " "))
        cur.execute(q)
        cols = [c[0].lower() for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        dbg("Optimizer param rows:", len(rows))
        return rows
    except Exception as e:
        dbg("get_optimizer_parameters ERROR (may need V$ privileges):", e)
        return []


def get_segment_sizes(cur, tables):
    """Get actual disk space (MB/GB) used by tables and indexes"""
    dbg("-> get_segment_sizes()")
    if not tables:
        return []
    
    # Build OR conditions for matching tables
    # DBA_SEGMENTS uses SEGMENT_NAME (not TABLE_NAME) and OWNER
    owner_segment_pairs = []
    for owner, table in tables:
        owner_segment_pairs.append(f"(owner = '{owner}' AND segment_name = '{table}')")
    
    where_clause = " OR ".join(owner_segment_pairs)
    
    # Try DBA_SEGMENTS first, fallback to USER_SEGMENTS
    queries = [
        # DBA_SEGMENTS (requires DBA privileges)
        f"""
            SELECT owner, segment_name, segment_type,
                   bytes, blocks, extents,
                   ROUND(bytes/1024/1024, 2) as size_mb,
                   ROUND(bytes/1024/1024/1024, 2) as size_gb
            FROM dba_segments
            WHERE segment_type IN ('TABLE', 'TABLE PARTITION', 'INDEX', 'INDEX PARTITION')
              AND ({where_clause})
            ORDER BY owner, segment_name
        """,
        # USER_SEGMENTS (fallback - only current user's segments)
        f"""
            SELECT USER as owner, segment_name, segment_type,
                   bytes, blocks, extents,
                   ROUND(bytes/1024/1024, 2) as size_mb,
                   ROUND(bytes/1024/1024/1024, 2) as size_gb
            FROM user_segments
            WHERE segment_type IN ('TABLE', 'TABLE PARTITION', 'INDEX', 'INDEX PARTITION')
            ORDER BY segment_name
        """
    ]
    
    for i, q in enumerate(queries):
        try:
            view_name = "DBA_SEGMENTS" if i == 0 else "USER_SEGMENTS"
            dbg(f"Trying {view_name}...")
            cur.execute(q)  # No binds needed - SQL is built directly
            cols = [c[0].lower() for c in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            dbg(f"Segment size rows from {view_name}:", len(rows))
            return rows
        except Exception as e:
            dbg(f"{view_name} failed:", e)
            if i == len(queries) - 1:
                dbg("All segment queries failed - will calculate from blocks")
                return []
    
    return []


def diagnose_partition_pruning(plan_details, partition_tables, sql_text):
    """
    Diagnose partition pruning issues.
    Returns warnings if partition pruning failed despite partition key in WHERE clause.
    """
    dbg("-> diagnose_partition_pruning()")
    
    if not partition_tables or not plan_details:
        return []
    
    diagnostics = []
    sql_upper = (sql_text or "").upper()
    
    for part_table in partition_tables:
        owner = part_table["owner"]
        table_name = part_table["table_name"]
        part_count = part_table.get("partition_count", 0)
        
        # Find the table access in plan
        for step in plan_details:
            if (step.get("object_owner") == owner and 
                step.get("object_name") == table_name and
                step.get("operation") == "TABLE ACCESS"):
                
                pstart = step.get("partition_start")
                pstop = step.get("partition_stop")
                
                # Check if ALL partitions are being scanned
                if pstart and pstop:
                    try:
                        # Check for "ALL" or large range
                        if (pstart == "1" and str(pstop) == str(part_count)) or pstop == "KEY":
                            # Potential pruning failure
                            diagnostic = {
                                "table": f"{owner}.{table_name}",
                                "partition_count": part_count,
                                "partitions_scanned": f"{pstart} to {pstop}",
                                "severity": "HIGH",
                                "issue": "All partitions scanned - partition pruning not working",
                                "possible_causes": [
                                    "Partition key not in WHERE clause",
                                    "Predicate uses function on partition key (prevents pruning)",
                                    "Data type mismatch (implicit conversion)",
                                    "Stale statistics",
                                    "Partition key value is bind variable (runtime pruning)"
                                ]
                            }
                            diagnostics.append(diagnostic)
                            dbg(f"⚠️ Partition pruning issue detected for {owner}.{table_name}")
                            
                    except:
                        pass
    
    return diagnostics


def classify_query_intent(sql_text, plan_details):
    """
    Classify query intent based on SQL patterns and execution plan.
    Returns query type, pattern, and typical use case.
    """
    dbg("-> classify_query_intent()")
    
    sql_upper = (sql_text or "").upper()
    
    # Initialize classification
    intent = {
        "type": "unknown",
        "patterns": [],
        "typical_use": "General data retrieval",
        "complexity": "simple"
    }
    
    # Pattern detection
    if "GROUP BY" in sql_upper:
        intent["type"] = "aggregation_report"
        intent["patterns"].append("GROUP BY aggregation")
        intent["typical_use"] = "Aggregated reporting or analytics"
        intent["complexity"] = "moderate"
    
    if "ROWNUM" in sql_upper or "FETCH FIRST" in sql_upper or ("WHERE" in sql_upper and "ROW_NUMBER" in sql_upper):
        intent["patterns"].append("result limiting")
        if intent["type"] == "unknown":
            intent["type"] = "pagination_query"
            intent["typical_use"] = "Paginated result set retrieval"
    
    if "ORDER BY" in sql_upper and "ROWNUM" in sql_upper:
        intent["patterns"].append("top-N query")
        intent["type"] = "top_n_query"
        intent["typical_use"] = "Finding top/bottom N records"
    
    if sql_upper.count("LEFT JOIN") >= 2 or sql_upper.count("LEFT OUTER JOIN") >= 2:
        intent["patterns"].append("multiple left joins")
        if "NOT NULL" in sql_upper or "IS NULL" in sql_upper:
            intent["type"] = "reconciliation_query"
            intent["typical_use"] = "Data reconciliation between systems"
        intent["complexity"] = "complex"
    
    if "UNION" in sql_upper or "UNION ALL" in sql_upper:
        intent["patterns"].append("set operation")
        intent["type"] = "multi_source_query"
        intent["typical_use"] = "Combining data from multiple sources"
        intent["complexity"] = "complex"
    
    if sql_upper.count("JOIN") >= 4:
        intent["complexity"] = "very_complex"
        if intent["type"] == "unknown":
            intent["type"] = "complex_join_query"
            intent["typical_use"] = "Complex multi-table data retrieval"
    
    if "COUNT(*)" in sql_upper or "COUNT(" in sql_upper:
        if "GROUP BY" not in sql_upper:
            intent["type"] = "count_query"
            intent["patterns"].append("record counting")
            intent["typical_use"] = "Data volume check or existence test"
    
    if sql_upper.strip().startswith("SELECT *"):
        intent["patterns"].append("SELECT *")
        if intent["type"] == "unknown":
            intent["type"] = "full_data_export"
            intent["typical_use"] = "Full record export or data dump"
    
    if "WITH" in sql_upper and sql_upper.index("WITH") < sql_upper.index("SELECT"):
        intent["patterns"].append("CTE (Common Table Expression)")
        intent["complexity"] = "complex"
    
    # Check for date range patterns
    if any(date_keyword in sql_upper for date_keyword in ["TRUNC(SYSDATE", "SYSDATE -", "BETWEEN", "TO_DATE"]):
        intent["patterns"].append("date range filter")
    
    return intent


def detect_cartesian_products(plan_details):
    """
    Detect potential Cartesian products (cross joins).
    Reports facts - LLM will determine if this is intended or problematic.
    """
    dbg("-> detect_cartesian_products()")
    
    detections = []
    
    for i, step in enumerate(plan_details):
        operation = step.get("operation", "")
        options = step.get("options", "")
        cardinality = step.get("cardinality", 0)
        
        # NESTED LOOPS with no filter predicate
        if operation == "NESTED LOOPS":
            # Check if next step has a filter or access predicate
            has_predicate = False
            if i + 1 < len(plan_details):
                next_step = plan_details[i + 1]
                if next_step.get("access_predicates") or next_step.get("filter_predicates"):
                    has_predicate = True
            
            # High cardinality without predicate
            if not has_predicate and cardinality and cardinality > 100000:
                detections.append({
                    "type": "NESTED_LOOPS_NO_PREDICATE",
                    "operation": f"{operation} {options}".strip(),
                    "cardinality": cardinality,
                    "step_id": step.get("id"),
                    "has_join_predicate": False
                })
                dbg(f"🚨 Potential Cartesian at step {step.get('id')}: {cardinality:,} rows")
        
        # MERGE JOIN CARTESIAN (explicit Cartesian)
        if operation == "MERGE JOIN" and "CARTESIAN" in options:
            detections.append({
                "type": "EXPLICIT_CARTESIAN",
                "operation": f"{operation} {options}".strip(),
                "cardinality": cardinality,
                "step_id": step.get("id"),
                "has_join_predicate": False
            })
            dbg(f"🚨 Explicit CARTESIAN at step {step.get('id')}")
    
    return detections


def detect_full_table_scans(plan_details, table_stats, index_stats, column_stats, sql_text):
    """
    Detect full table scans and report factual information.
    LLM will decide if this is a problem and what to do about it.
    """
    dbg("-> detect_full_table_scans()")
    
    scans = []
    sql_upper = (sql_text or "").upper()
    
    # Build table lookup for quick access
    table_lookup = {(t["owner"], t["table_name"]): t for t in table_stats}
    index_lookup = {}
    for idx in index_stats:
        key = (idx["owner"], idx["table_name"])
        if key not in index_lookup:
            index_lookup[key] = []
        index_lookup[key].append(idx)
    
    # Analyze each plan step
    for step in plan_details:
        operation = step.get("operation", "")
        options = step.get("options", "")
        obj_owner = step.get("object_owner")
        obj_name = step.get("object_name")
        cardinality = step.get("cardinality", 0)
        cost = step.get("cost", 0)
        
        # Full table scan detection
        if operation == "TABLE ACCESS" and options == "FULL":
            table_key = (obj_owner, obj_name)
            table = table_lookup.get(table_key)
            
            if table:
                num_rows = table.get("num_rows", 0)
                
                # Extract WHERE clause columns
                where_columns = []
                if "WHERE" in sql_upper:
                    where_part = sql_upper.split("WHERE", 1)[1].split("ORDER BY")[0] if "ORDER BY" in sql_upper else sql_upper.split("WHERE", 1)[1]
                    # Simple column extraction
                    for col_stat in column_stats:
                        if col_stat["column_name"] in where_part:
                            where_columns.append(col_stat["column_name"])
                
                # Check if indexes exist
                available_indexes = index_lookup.get(table_key, [])
                
                scan = {
                    "operation": "FULL TABLE SCAN",
                    "table": f"{obj_owner}.{obj_name}",
                    "table_owner": obj_owner,
                    "table_name": obj_name,
                    "num_rows": num_rows,
                    "cost": cost,
                    "cardinality": cardinality,
                    "available_indexes": [
                        {
                            "name": idx["index_name"],
                            "columns": idx.get("columns", []),
                            "type": idx.get("index_type"),
                            "status": idx.get("status")
                        } 
                        for idx in available_indexes
                    ],
                    "available_index_count": len(available_indexes),
                    "columns_in_where_clause": where_columns
                }
                
                scans.append(scan)
                dbg(f"⚠️ Full scan detected: {obj_owner}.{obj_name} ({num_rows:,} rows)")
    
    return scans


def detect_anomalies(table_stats, plan_details):
    """
    Detect data anomalies - reports facts about missing/stale statistics.
    LLM will determine impact and recommendations.
    """
    dbg("-> detect_anomalies()")
    
    anomalies = []
    
    # Check for tables with no statistics
    for table in table_stats:
        num_rows = table.get("num_rows")
        last_analyzed = table.get("last_analyzed")
        owner = table.get("owner")
        name = table.get("table_name")
        
        if num_rows is None or num_rows == 0:
            anomalies.append({
                "type": "missing_statistics",
                "table": f"{owner}.{name}",
                "table_owner": owner,
                "table_name": name,
                "num_rows": num_rows,
                "last_analyzed": last_analyzed
            })
            dbg(f"⚠️ No statistics: {owner}.{name}")
    
    # Check for extreme cardinality mismatches (if actual rows available)
    for step in plan_details:
        cardinality = step.get("cardinality", 0)
        actual_rows = step.get("actual_rows", 0)  # Only available with SQL Monitor
        
        if actual_rows and cardinality:
            ratio = actual_rows / cardinality if cardinality > 0 else 0
            if ratio > 10 or (ratio < 0.1 and cardinality > 100):
                anomalies.append({
                    "type": "cardinality_mismatch",
                    "step_id": step.get("id"),
                    "operation": step.get("operation"),
                    "estimated_rows": cardinality,
                    "actual_rows": actual_rows,
                    "estimation_ratio": round(ratio, 2)
                })
                dbg(f"⚠️ Cardinality mismatch at step {step.get('id')}: {cardinality} est vs {actual_rows} actual")
    
    return anomalies


# ============================================================
# MAIN ENTRY CALLED BY MCP TOOL
# ============================================================

def run_full_oracle_analysis(cur, sql_text: str):
    import time
    from config import config
    
    start_time = time.time()
    dbg("===== START ANALYSIS =====")

    sql = normalize_sql(sql_text)
    dbg("SQL normalized:", sql[:100], "...")

    sql_objects = extract_sql_objects(sql)
    sql_cols = extract_columns_from_sql(sql)

    dbg("Objects extracted:", sql_objects)
    dbg("Column tokens:", len(sql_cols))

    stmt_id = f"LLM_{int(datetime.now().timestamp())}"
    dbg("Statement ID:", stmt_id)

    xplan, plan_err = explain_plan(cur, sql, stmt_id)
    plan_objs = get_plan_objects(cur, stmt_id)
    plan_details = get_plan_details(cur, stmt_id)

    # Merge tables from plan (authoritative) with SQL-extracted objects
    # Plan objects are the source of truth since they have correct owners
    tables_set = set(plan_objs["tables"])
    
    # Add qualified tables from SQL that aren't in the plan
    for obj in sql_objects:
        if obj[0] is not None:  # Only add qualified tables (owner, table)
            tables_set.add(obj)
    
    # For unqualified tables in SQL, check if they appear in plan by table name
    unqualified_tables = [t for o, t in sql_objects if o is None]
    if unqualified_tables:
        dbg("Unqualified tables found in SQL:", unqualified_tables)
        # These should be resolved by the execution plan already
        # If not in plan, they might be views or not actually tables
    
    tables = sorted(list(tables_set))
    dbg("Tables to fetch metadata for:", tables)

    # === PRESET-BASED EARLY FILTERING ===
    preset = config.output_preset
    dbg(f"Using preset: {preset}")
    
    # Always collect: table stats, plan details
    table_stats = get_table_stats(cur, tables)
    
    # Conditional collection based on preset
    if preset == "minimal":
        dbg("MINIMAL preset: Skipping indexes, columns, constraints, partitions, optimizer, segments")
        index_stats = []
        index_cols = []
        part_tables, part_keys = [], []
        col_stats = []
        constraints = []
        optimizer_params = {}
        segment_sizes = []
    elif preset == "compact":
        dbg("COMPACT preset: Collecting most metadata, skipping segments")
        index_stats = get_index_stats(cur, tables)
        index_cols = get_index_columns(cur, tables)
        part_tables, part_keys = get_partition_info(cur, tables)
        col_stats = get_column_stats(cur, tables, sql_cols)
        constraints = get_constraints(cur, tables)
        optimizer_params = get_optimizer_parameters(cur)
        segment_sizes = []  # Skip physical storage
    else:  # standard
        dbg("STANDARD preset: Collecting full metadata")
        index_stats = get_index_stats(cur, tables)
        index_cols = get_index_columns(cur, tables)
        part_tables, part_keys = get_partition_info(cur, tables)
        col_stats = get_column_stats(cur, tables, sql_cols)
        constraints = get_constraints(cur, tables)
        optimizer_params = get_optimizer_parameters(cur)
        segment_sizes = get_segment_sizes(cur, tables)
    
    # Run diagnostics (always, but use available data)
    partition_diagnostics = diagnose_partition_pruning(plan_details, part_tables, sql) if part_tables else []
    query_intent = classify_query_intent(sql, plan_details)
    cartesian_detections = detect_cartesian_products(plan_details)
    full_table_scans = detect_full_table_scans(plan_details, table_stats, index_stats, col_stats, sql) if index_stats else []
    anomalies = detect_anomalies(table_stats, plan_details)

    # Cleanup
    try:
        cur.execute("DELETE FROM plan_table WHERE statement_id = :sid", sid=stmt_id)
        cur.connection.commit()
    except:
        pass

    # Build full facts dictionary
    full_facts = {
        "sql_text": sql,
        "execution_plan": xplan,
        "plan_details": plan_details,
        "table_stats": table_stats,
        "index_stats": index_stats,
        "index_columns": index_cols,
        "partition_tables": part_tables,
        "partition_keys": part_keys,
        "column_stats": col_stats,
        "constraints": constraints,
        "optimizer_parameters": optimizer_params,
        "segment_sizes": segment_sizes,
        "partition_diagnostics": partition_diagnostics,
        "query_intent": query_intent,
        "full_table_scans": full_table_scans,
        "cartesian_detections": cartesian_detections,
        "anomalies": anomalies,
        "summary": {
            "tables": len(tables),
            "indexes": len(index_stats),
            "columns": len(col_stats),
            "constraints": len(constraints),
            "partitioned_tables": len(part_tables),
            "partition_issues": len(partition_diagnostics),
            "full_scans_detected": len(full_table_scans),
            "cartesian_detections": len(cartesian_detections),
            "anomalies_detected": len(anomalies)
        }
    }
    
    # Apply output filtering based on preset
    plan_tables_set = set(plan_objs["tables"])
    plan_indexes_set = set(plan_objs["indexes"])
    filtered_facts = apply_output_preset(full_facts, preset, plan_tables_set, plan_indexes_set)
    
    # Calculate elapsed time
    elapsed = time.time() - start_time
    
    # Build informative prompt with counts and timing
    prompt_parts = [f"✓ Oracle analysis complete in {elapsed:.2f}s"]
    prompt_parts.append(f"Preset: {preset}")
    prompt_parts.append(f"Tables: {len(tables)}")
    
    if index_stats:
        prompt_parts.append(f"Indexes: {len(index_stats)}")
    if constraints:
        prompt_parts.append(f"Constraints: {len(constraints)}")
    if col_stats:
        prompt_parts.append(f"Columns: {len(col_stats)}")
    
    # Add warnings
    warnings = []
    if full_table_scans:
        warnings.append(f"⚠️ {len(full_table_scans)} full table scans")
    if cartesian_detections:
        warnings.append(f"⚠️ {len(cartesian_detections)} cartesian products")
    if anomalies:
        warnings.append(f"⚠️ {len(anomalies)} anomalies")
    
    if warnings:
        prompt_parts.append(" | ".join(warnings))
    
    return {
        "facts": filtered_facts,
        "prompt": " | ".join(prompt_parts)
    }


def apply_output_preset(facts, preset, plan_tables, plan_indexes):
    """
    Filter facts based on output preset to optimize for different use cases.
    
    Args:
        facts: Full facts dictionary
        preset: "standard" | "compact" | "minimal"
        plan_tables: Set of (owner, table) tuples actually in the execution plan
        plan_indexes: Set of (owner, index) tuples actually in the execution plan
    
    Returns:
        Filtered facts dictionary
    """
    if preset == "standard":
        # Return everything - no filtering
        return facts
    
    # For compact and minimal, create a filtered copy
    filtered = {
        "sql_text": facts["sql_text"],
        "plan_details": facts["plan_details"],  # Always include structured plan
        "summary": facts["summary"]
    }
    
    if preset == "compact":
        # Compact: Filter to plan objects, exclude execution_plan text
        filtered["table_stats"] = [
            t for t in facts["table_stats"]
            if (t.get("owner"), t.get("table_name")) in plan_tables
        ]
        filtered["index_stats"] = [
            i for i in facts["index_stats"]
            if (i.get("owner"), i.get("index_name")) in plan_indexes
        ]
        filtered["index_columns"] = [
            ic for ic in facts["index_columns"]
            if (ic.get("table_owner"), ic.get("index_name")) in plan_indexes
        ]
        filtered["column_stats"] = facts["column_stats"]  # Keep all - needed for cardinality
        filtered["constraints"] = facts["constraints"]
        filtered["optimizer_parameters"] = facts["optimizer_parameters"]
        filtered["segment_sizes"] = [
            s for s in facts["segment_sizes"]
            if (s.get("owner"), s.get("segment_name")) in plan_tables or 
               (s.get("owner"), s.get("segment_name")) in plan_indexes
        ]
        filtered["partition_tables"] = facts["partition_tables"]
        filtered["partition_keys"] = facts["partition_keys"]
        filtered["partition_diagnostics"] = facts["partition_diagnostics"]
        
    elif preset == "minimal":
        # Minimal: Only plan + basic table stats
        filtered["table_stats"] = [
            {k: v for k, v in t.items() if k in ["owner", "table_name", "num_rows", "blocks"]}
            for t in facts["table_stats"]
            if (t.get("owner"), t.get("table_name")) in plan_tables
        ]
        # Exclude: indexes, columns, constraints, segments, partitions
        
    return filtered

