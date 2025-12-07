# path: server/tools/oracle_collector_impl.py
# CLEAN & FIXED VERSION — Avi Cohen 2025

import re
from datetime import datetime
from collections import defaultdict

# ============================================================
# DEBUG HELPER
# ============================================================

def dbg(*msg):
    print("[ORACLE-COLLECTOR]", *msg)


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

def explain_plan(cur, sql_text: str, stmt_id: str):
    try:
        dbg("-> explain_plan START")
        cur.execute("DELETE FROM plan_table WHERE statement_id = :sid", sid=stmt_id)
        cur.connection.commit()

        clean = sql_text.strip()
        if clean.endswith(";"):
            clean = clean[:-1]

        stmt = f"EXPLAIN PLAN SET STATEMENT_ID = '{stmt_id}' FOR {clean}"
        dbg("Running:", stmt[:180], "...")

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
    
    where, binds = build_clause(tables, alias='s')
    
    # Try DBA_SEGMENTS first, fallback to USER_SEGMENTS
    queries = [
        # DBA_SEGMENTS (requires DBA privileges)
        f"""
            SELECT s.owner, s.segment_name, s.segment_type,
                   s.bytes, s.blocks, s.extents,
                   ROUND(s.bytes/1024/1024, 2) as size_mb,
                   ROUND(s.bytes/1024/1024/1024, 2) as size_gb
            FROM dba_segments s
            WHERE s.segment_type IN ('TABLE', 'TABLE PARTITION', 'INDEX', 'INDEX PARTITION')
              AND ({where})
            ORDER BY s.owner, s.segment_name
        """,
        # USER_SEGMENTS (fallback)
        f"""
            SELECT s.owner, s.segment_name, s.segment_type,
                   s.bytes, s.blocks, s.extents,
                   ROUND(s.bytes/1024/1024, 2) as size_mb,
                   ROUND(s.bytes/1024/1024/1024, 2) as size_gb
            FROM user_segments s
            WHERE s.segment_type IN ('TABLE', 'TABLE PARTITION', 'INDEX', 'INDEX PARTITION')
            ORDER BY s.owner, s.segment_name
        """
    ]
    
    for i, q in enumerate(queries):
        try:
            view_name = "DBA_SEGMENTS" if i == 0 else "USER_SEGMENTS"
            dbg(f"Trying {view_name}...")
            cur.execute(q, binds if i == 0 else {})
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


# ============================================================
# MAIN ENTRY CALLED BY MCP TOOL
# ============================================================

def run_full_oracle_analysis(cur, sql_text: str):
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

    table_stats = get_table_stats(cur, tables)
    index_stats = get_index_stats(cur, tables)
    index_cols = get_index_columns(cur, tables)
    part_tables, part_keys = get_partition_info(cur, tables)
    col_stats = get_column_stats(cur, tables, sql_cols)
    constraints = get_constraints(cur, tables)
    optimizer_params = get_optimizer_parameters(cur)
    segment_sizes = get_segment_sizes(cur, tables)
    partition_diagnostics = diagnose_partition_pruning(plan_details, part_tables, sql)

    # Cleanup
    try:
        cur.execute("DELETE FROM plan_table WHERE statement_id = :sid", sid=stmt_id)
        cur.connection.commit()
    except:
        pass

    return {
        "facts": {
            "sql_text": sql,
            "exec_plan": xplan,
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
            "summary": {
                "tables": len(tables),
                "indexes": len(index_stats),
                "columns": len(col_stats),
                "constraints": len(constraints),
                "partitioned_tables": len(part_tables),
                "partition_issues": len(partition_diagnostics)
            }
        },
        "prompt":
            f"Oracle analysis ready. SQL length={len(sql)}, tables={len(tables)}, "
            f"constraints={len(constraints)}, partition_issues={len(partition_diagnostics)}."
    }

    # Cleanup
    try:
        cur.execute("DELETE FROM plan_table WHERE statement_id = :sid", sid=stmt_id)
        cur.connection.commit()
    except:
        pass

    return {
        "facts": {
            "sql_text": sql,
            "exec_plan": xplan,
            "plan_details": plan_details,
            "table_stats": table_stats,
            "index_stats": index_stats,
            "index_columns": index_cols,
            "partition_tables": part_tables,
            "partition_keys": part_keys,
            "column_stats": col_stats,
            "constraints": constraints,
            "optimizer_parameters": optimizer_params,
            "summary": {
                "tables": len(tables),
                "indexes": len(index_stats),
                "columns": len(col_stats),
                "constraints": len(constraints)
            }
        },
        "prompt":
            f"Oracle analysis ready. SQL length={len(sql)}, tables={len(tables)}, constraints={len(constraints)}."
    }
