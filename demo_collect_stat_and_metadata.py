# -*- coding: utf-8 -*-
"""
Automated Oracle SQL Performance Analysis and LLM Prompt Generation 
This script is an automated Oracle SQL performance-analysis tool.
Its purpose is to take a SQL query, extract metadata from the database, and generate a rich, structured prompt for an LLM to produce a full tuning report.
It does NOT reveal any application data.
Avi Cohen - 2025 Nobember

"""

import json
import os
import re
import sys
from datetime import datetime
from collections import defaultdict
import oracledb

# === CONFIG ===
ORACLE_USER = "stg"
ORACLE_PASSWORD = "stg99"
ORACLE_DSN = "bidb02.prod.bos.credorax.com:1521/stgprod"

SQL_TEXT = r"""
SELECT /*+ NO_MERGE */ DISTINCT c.customer_name,
       (SELECT /*+ NO_UNNEST */ SUM(o.amount)
        FROM demo_orders_30NOV o
        WHERE o.customer_id = c.customer_id
          AND TO_CHAR(o.order_date,'YYYY-MM-DD') > '2024-01-01'
       ) AS total_amount
FROM demo_customers_30NOV c
WHERE UPPER(c.city) = 'TEL-AVIV';  
"""


OUTPUT_DIR = "./data"


# === UTILS ===
def dbg(step, msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {step}: {msg}")


def normalize_sql(s: str) -> str:
    s = (s or "").strip()
    if s.endswith(";"):
        s = s[:-1]
    return s


def extract_sql_objects(sql_text: str):
    """Extract table references from SQL (owner.table pattern)"""
    s = (sql_text or "").upper()
    # Match OWNER.TABLE pattern
    owner_tabs = re.findall(r'\b([A-Z0-9_]+)\.([A-Z0-9_]+)\b', s)
    # Deduplicate while preserving order
    seen = set()
    unique_objs = []
    for o, t in owner_tabs:
        key = (o, t)
        if key not in seen:
            seen.add(key)
            unique_objs.append(key)
    return unique_objs


def extract_columns_from_sql(sql_text: str):
    """Extract potential column names from SQL"""
    s = (sql_text or "").upper()
    # Get identifiers that look like columns (after dots or standalone)
    tokens = re.findall(r'\b[A-Z0-9_]{2,}\b', s)
    return sorted(set(tokens))


# === PLAN ANALYSIS ===
def explain_plan(cur, sql_text: str, stmt_id: str):
    """Execute EXPLAIN PLAN and return formatted output"""
    try:
        # Clean any leftovers
        cur.execute("DELETE FROM plan_table WHERE statement_id = :sid", sid=stmt_id)
        cur.connection.commit()
        
        # Oracle EXPLAIN PLAN doesn't support bind variables in SET STATEMENT_ID
        # Must use string concatenation, but stmt_id is generated internally so it's safe
        # Remove any trailing semicolon from SQL
        clean_sql = sql_text.strip()
        if clean_sql.endswith(';'):
            clean_sql = clean_sql[:-1]
        
        # Build the EXPLAIN PLAN statement
        explain_stmt = f"EXPLAIN PLAN SET STATEMENT_ID = '{stmt_id}' FOR {clean_sql}"
        
        dbg("PLAN", f"Executing EXPLAIN with stmt_id: {stmt_id}")
        cur.execute(explain_stmt)
        cur.connection.commit()
        
        # Fetch xplan with additional details
        cur.execute("""
            SELECT plan_table_output
            FROM TABLE(DBMS_XPLAN.DISPLAY(
                statement_id => :sid,
                format => 'TYPICAL +PREDICATE +COST +BYTES'))
        """, sid=stmt_id)
        
        lines = [r[0] for r in cur.fetchall()]
        return lines, None
        
    except Exception as e:
        dbg("ERROR", f"EXPLAIN PLAN failed: {e}")
        return [f"(EXPLAIN PLAN failed: {e})"], str(e)


def get_plan_objects(cur, stmt_id: str):
    """
    Get all objects from execution plan with their types.
    Returns: dict with 'tables' and 'indexes' lists
    """
    try:
        # Get objects with operation types to distinguish tables from indexes
        cur.execute("""
            SELECT DISTINCT 
                p.object_owner,
                p.object_name,
                p.object_type,
                p.operation,
                p.options,
                MIN(p.id) as first_access_step
            FROM plan_table p
            WHERE p.statement_id = :sid
                AND p.object_name IS NOT NULL
                AND p.object_owner IS NOT NULL
            GROUP BY p.object_owner, p.object_name, p.object_type, p.operation, p.options
            ORDER BY MIN(p.id)
        """, sid=stmt_id)
        
        rows = cur.fetchall()
        tables = set()
        indexes = set()
        
        for owner, obj_name, obj_type, operation, options, step_id in rows:
            obj_key = (owner, obj_name)
            
            # Classify based on operation or object_type
            if obj_type in ('INDEX', 'INDEX PARTITION', 'INDEX SUBPARTITION'):
                indexes.add(obj_key)
            elif 'INDEX' in (operation or ''):
                indexes.add(obj_key)
            else:
                tables.add(obj_key)
        
        dbg("PLAN_OBJECTS", f"Found {len(tables)} tables, {len(indexes)} indexes")
        return {
            'tables': sorted(list(tables)),
            'indexes': sorted(list(indexes))
        }
        
    except Exception as e:
        dbg("ERROR", f"Failed to get plan objects: {e}")
        return {'tables': [], 'indexes': []}


def get_plan_details(cur, stmt_id: str):
    """Get detailed plan information for analysis"""
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
        
        cols = [d[0].lower() for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
        
    except Exception as e:
        dbg("ERROR", f"Failed to get plan details: {e}")
        return []


# === METADATA COLLECTION ===
def build_in_clause(items, prefix=''):
    """Helper to build SQL IN clause with bind variables"""
    if not items:
        return "", {}
    
    conditions = []
    binds = {}
    
    for i, (owner, name) in enumerate(items, 1):
        if prefix:
            # Add table alias prefix
            conditions.append(f"({prefix}.table_owner = :o{i} AND {prefix}.table_name = :t{i})")
        else:
            conditions.append(f"(owner = :o{i} AND table_name = :t{i})")
        binds[f'o{i}'] = owner
        binds[f't{i}'] = name
    
    return ' OR '.join(conditions), binds


def get_table_stats(cur, tables):
    """Get table statistics"""
    if not tables:
        return []
    
    where_clause, binds = build_in_clause(tables)
    
    query = f"""
        SELECT 
            owner,
            table_name,
            num_rows,
            blocks,
            empty_blocks,
            avg_row_len,
            sample_size,
            TO_CHAR(last_analyzed, 'YYYY-MM-DD HH24:MI:SS') as last_analyzed,
            CASE WHEN partitioned = 'YES' THEN 'Y' ELSE 'N' END as is_partitioned,
            compression,
            degree as parallel_degree
        FROM all_tables
        WHERE {where_clause}
        ORDER BY owner, table_name
    """
    
    try:
        cur.execute(query, binds)
        cols = [d[0].lower() for d in cur.description]
        results = [dict(zip(cols, r)) for r in cur.fetchall()]
        dbg("METADATA", f"Retrieved stats for {len(results)} tables")
        return results
    except Exception as e:
        dbg("ERROR", f"Failed to get table stats: {e}")
        return []


def get_index_stats(cur, tables):
    """Get index statistics for tables"""
    if not tables:
        return []
    
    where_clause, binds = build_in_clause(tables)
    
    query = f"""
        SELECT 
            owner,
            index_name,
            table_name,
            index_type,
            uniqueness,
            status,
            visibility,
            blevel,
            leaf_blocks,
            distinct_keys,
            clustering_factor,
            num_rows,
            sample_size,
            TO_CHAR(last_analyzed, 'YYYY-MM-DD HH24:MI:SS') as last_analyzed,
            degree as parallel_degree,
            partitioned
        FROM all_indexes
        WHERE {where_clause}
        ORDER BY owner, table_name, index_name
    """
    
    try:
        cur.execute(query, binds)
        cols = [d[0].lower() for d in cur.description]
        results = [dict(zip(cols, r)) for r in cur.fetchall()]
        dbg("METADATA", f"Retrieved {len(results)} indexes")
        return results
    except Exception as e:
        dbg("ERROR", f"Failed to get index stats: {e}")
        return []


def get_index_columns(cur, tables):
    """Get index column definitions"""
    if not tables:
        return []
    
    where_clause, binds = build_in_clause(tables, prefix='ic')
    
    query = f"""
        SELECT 
            ic.table_owner,
            ic.table_name,
            ic.index_name,
            ic.column_name,
            ic.column_position,
            ic.descend
        FROM all_ind_columns ic
        WHERE {where_clause}
        ORDER BY ic.table_owner, ic.table_name, ic.index_name, ic.column_position
    """
    
    try:
        cur.execute(query, binds)
        cols = [d[0].lower() for d in cur.description]
        results = [dict(zip(cols, r)) for r in cur.fetchall()]
        
        # Group by index
        index_map = defaultdict(list)
        for row in results:
            key = (row['table_owner'], row['table_name'], row['index_name'])
            index_map[key].append(row['column_name'])
        
        # Create compact representation
        compact = []
        for (owner, table, index), cols in index_map.items():
            compact.append({
                'owner': owner,
                'table_name': table,
                'index_name': index,
                'columns': cols
            })
        
        dbg("METADATA", f"Retrieved columns for {len(compact)} indexes")
        return compact
        
    except Exception as e:
        dbg("ERROR", f"Failed to get index columns: {e}")
        dbg("DEBUG", f"Query was: {query[:200]}...")
        dbg("DEBUG", f"Binds: {binds}")
        return []


def get_partition_info(cur, tables):
    """Get partition metadata"""
    if not tables:
        return [], []
    
    where_clause, binds = build_in_clause(tables)
    
    # Partition tables info
    query1 = f"""
        SELECT 
            owner,
            table_name,
            partitioning_type,
            subpartitioning_type,
            partition_count,
            def_subpartition_count,
            CASE WHEN interval IS NOT NULL THEN 'Y' ELSE 'N' END as is_interval,
            interval
        FROM all_part_tables
        WHERE {where_clause}
        ORDER BY owner, table_name
    """
    
    # Partition key columns - build separate where clause for different column structure
    pk_conditions = []
    for i, (owner, name) in enumerate(tables, 1):
        pk_conditions.append(f"(pkc.owner = :o{i} AND pkc.name = :t{i})")
    pk_where = ' OR '.join(pk_conditions)
    
    query2 = f"""
        SELECT 
            pkc.owner,
            pkc.name as table_name,
            pkc.column_name,
            pkc.column_position,
            pkc.object_type
        FROM all_part_key_columns pkc
        WHERE {pk_where}
        ORDER BY pkc.owner, pkc.name, pkc.object_type, pkc.column_position
    """
    
    try:
        cur.execute(query1, binds)
        cols1 = [d[0].lower() for d in cur.description]
        part_tables = [dict(zip(cols1, r)) for r in cur.fetchall()]
        
        cur.execute(query2, binds)
        cols2 = [d[0].lower() for d in cur.description]
        part_keys = [dict(zip(cols2, r)) for r in cur.fetchall()]
        
        dbg("METADATA", f"Retrieved partition info for {len(part_tables)} tables")
        return part_tables, part_keys
        
    except Exception as e:
        dbg("ERROR", f"Failed to get partition info: {e}")
        return [], []


def get_column_stats(cur, tables, sql_columns):
    """Get column statistics for columns used in SQL"""
    if not tables or not sql_columns:
        return []
    
    where_clause, binds = build_in_clause(tables)
    
    # Add column name binds
    col_placeholders = ','.join([f':c{i}' for i in range(len(sql_columns))])
    for i, col in enumerate(sql_columns):
        binds[f'c{i}'] = col
    
    query = f"""
        SELECT 
            owner,
            table_name,
            column_name,
            num_distinct,
            num_nulls,
            density,
            num_buckets as histogram_buckets,
            TO_CHAR(last_analyzed, 'YYYY-MM-DD HH24:MI:SS') as last_analyzed,
            sample_size
        FROM all_tab_col_statistics
        WHERE ({where_clause})
            AND column_name IN ({col_placeholders})
        ORDER BY owner, table_name, column_name
    """
    
    try:
        cur.execute(query, binds)
        cols = [d[0].lower() for d in cur.description]
        results = [dict(zip(cols, r)) for r in cur.fetchall()]
        dbg("METADATA", f"Retrieved stats for {len(results)} columns")
        return results
    except Exception as e:
        dbg("ERROR", f"Failed to get column stats: {e}")
        return []


# === FORMATTING ===
def format_table_data(data, title="Data"):
    """Format list of dicts as readable table"""
    if not data:
        return f"{title}: (none)\n"
    
    if not isinstance(data, list):
        return f"{title}: {str(data)}\n"
    
    lines = [f"\n{title}:"]
    lines.append("-" * 80)
    
    # Header
    keys = list(data[0].keys())
    lines.append(" | ".join(str(k) for k in keys))
    lines.append("-" * 80)
    
    # Rows
    for row in data:
        values = [str(row.get(k, '')) for k in keys]
        lines.append(" | ".join(values))
    
    return "\n".join(lines) + "\n"


def format_partition_summary(part_tables, part_keys):
    """Format partition information"""
    if not part_tables:
        return "Partitioning: None\n"
    
    lines = ["\nPartitioning Summary:"]
    lines.append("-" * 80)
    
    key_map = defaultdict(list)
    for pk in part_keys:
        key = (pk['owner'], pk['table_name'])
        key_map[key].append((pk['column_position'], pk['column_name']))
    
    for pt in part_tables:
        key = (pt['owner'], pt['table_name'])
        keys = [col for _, col in sorted(key_map.get(key, []))]
        
        lines.append(f"\nTable: {pt['owner']}.{pt['table_name']}")
        lines.append(f"  Type: {pt['partitioning_type']}")
        if pt.get('subpartitioning_type'):
            lines.append(f"  Subpartition Type: {pt['subpartitioning_type']}")
        lines.append(f"  Count: {pt['partition_count']}")
        lines.append(f"  Interval: {pt['is_interval']}")
        lines.append(f"  Key Columns: {', '.join(keys)}")
    
    return "\n".join(lines) + "\n"


# === MAIN ===
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    dbg("INIT", "Connecting to Oracle...")
    try:
        conn = oracledb.connect(
            user=ORACLE_USER,
            password=ORACLE_PASSWORD,
            dsn=ORACLE_DSN
        )
        cur = conn.cursor()
        dbg("INIT", "Connected successfully")
    except Exception as e:
        print(f"ERROR: Database connection failed: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Normalize SQL
    sql = normalize_sql(SQL_TEXT)
    if not sql:
        print("ERROR: SQL_TEXT is empty", file=sys.stderr)
        sys.exit(2)
    
    dbg("SQL", f"Analyzing SQL ({len(sql)} characters)")
    
    # Extract objects and columns from SQL text
    sql_objects = extract_sql_objects(sql)
    sql_columns = extract_columns_from_sql(sql)
    dbg("PARSE", f"Found {len(sql_objects)} object references in SQL")
    
    # EXPLAIN PLAN
    stmt_id = f"LLM_{int(datetime.now().timestamp())}"
    dbg("PLAN", "Executing EXPLAIN PLAN...")
    
    xplan_lines, plan_error = explain_plan(cur, sql, stmt_id)
    
    try:
        # Get objects from plan
        plan_objs = get_plan_objects(cur, stmt_id)
        tables = plan_objs['tables']
        indexes_in_plan = plan_objs['indexes']
        
        # Combine with SQL-parsed objects
        all_tables = sorted(set(tables + sql_objects))
        
        dbg("ANALYSIS", f"Analyzing {len(all_tables)} tables")
        
        # Get detailed plan info
        plan_details = get_plan_details(cur, stmt_id)
        
        # Collect metadata
        dbg("METADATA", "Collecting table statistics...")
        table_stats = get_table_stats(cur, all_tables)
        
        dbg("METADATA", "Collecting index information...")
        index_stats = get_index_stats(cur, all_tables)
        index_columns = get_index_columns(cur, all_tables)
        
        dbg("METADATA", "Collecting partition information...")
        part_tables, part_keys = get_partition_info(cur, all_tables)
        
        dbg("METADATA", "Collecting column statistics...")
        column_stats = get_column_stats(cur, all_tables, sql_columns)
        
    finally:
        # Cleanup plan_table
        try:
            cur.execute("DELETE FROM plan_table WHERE statement_id = :sid", sid=stmt_id)
            conn.commit()
        except:
            pass
    
    # Build comprehensive prompt
    dbg("PROMPT", "Building LLM prompt...")
    
    prompt = f"""You are an expert Oracle Database Performance Tuning Specialist.

Analyze the following SQL query and execution plan. Provide detailed optimization recommendations.

==================== SQL QUERY ====================
{sql}

==================== EXECUTION PLAN ====================
{''.join(xplan_lines)}

{format_table_data(plan_details, "Detailed Plan Steps")}

==================== SCHEMA METADATA ====================

{format_table_data(table_stats, "Table Statistics")}

{format_table_data(index_stats, "Index Statistics")}

{format_table_data(index_columns, "Index Column Definitions")}

{format_partition_summary(part_tables, part_keys)}

{format_table_data(column_stats, "Column Statistics (for columns used in SQL)")}

==================== OBJECTS IN PLAN ====================
Tables: {', '.join([f'{o}.{t}' for o, t in tables]) if tables else '(none)'}
Indexes: {', '.join([f'{o}.{i}' for o, i in indexes_in_plan]) if indexes_in_plan else '(none)'}

==================== ANALYSIS REQUIREMENTS ====================

Please analyze this query and provide a detailed JSON response with the following structure:

{{
  "summary": "Brief overview of query purpose and main performance characteristics",
  
  "bottlenecks": [
    {{
      "plan_step": "Step ID or null if general",
      "issue": "Description of the bottleneck",
      "reason": "Why this is causing performance problems",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "evidence": "Data from plan/stats supporting this finding"
    }}
  ],
  
  "recommendations": {{
    "indexes": [
      {{
        "action": "create|drop|modify|rebuild",
        "table": "OWNER.TABLE_NAME",
        "columns": ["col1", "col2"],
        "index_type": "btree|bitmap|function_based",
        "reason": "Specific benefit this index would provide",
        "priority": "HIGH|MEDIUM|LOW"
      }}
    ],
    
    "query_rewrites": [
      {{
        "description": "What to change and why",
        "original_pattern": "Pattern in current SQL",
        "suggested_pattern": "Improved pattern",
        "expected_benefit": "What improvement this brings"
      }}
    ],
    
    "sql_rewrite": {{
      "should_rewrite": true|false,
      "rewritten_sql": "Complete rewritten SQL if should_rewrite is true, otherwise null",
      "changes_summary": "List of changes made"
    }},
    
    "join_optimization": [
      {{
        "suggestion": "Join order or method change",
        "current_approach": "What the plan shows now",
        "recommended_approach": "Better approach",
        "reason": "Why this is better"
      }}
    ],
    
    "hints": [
      {{
        "hint": "Specific hint syntax",
        "placement": "Where in the SQL to place it",
        "use_when": "Conditions when this hint is beneficial",
        "expected_impact": "What this hint should achieve"
      }}
    ],
    
    "statistics": [
      {{
        "target": "table|index|column",
        "object": "OWNER.OBJECT_NAME",
        "action": "gather|refresh|histogram|extended_stats",
        "reason": "Why statistics need attention",
        "command": "Example DBMS_STATS command"
      }}
    ],
    
    "partitioning": [
      {{
        "table": "OWNER.TABLE_NAME",
        "suggestion": "What to do with partitioning",
        "reason": "Why this helps",
        "consideration": "Any trade-offs or requirements"
      }}
    ]
  }},
  
  "performance_insights": {{
    "estimated_rows_processed": "Number or range",
    "main_cost_drivers": ["list", "of", "operations"],
    "parallel_execution": "Analysis of parallel hints and DOP",
    "join_method_analysis": "Discussion of hash/nested loop/merge joins used"
  }},
  
  "expected_improvement": {{
    "estimate": "e.g., 50% faster, 3x reduction in I/O",
    "basis": "What data/assumptions this is based on",
    "confidence": "HIGH|MEDIUM|LOW"
  }},
  
  "implementation_priority": [
    {{
      "recommendation": "Which recommendation",
      "priority": 1,
      "effort": "LOW|MEDIUM|HIGH",
      "impact": "Expected performance impact"
    }}
  ]
}}

CRITICAL INSTRUCTIONS:
1. Return ONLY valid JSON (no markdown, no code blocks, no comments)
2. Be specific - reference actual table names, column names, and plan steps
3. Base all recommendations on the actual data provided
4. If statistics are stale or missing, note this
5. Consider the UNION ALL structure and its impact
6. Pay attention to the LEFT JOINs and their predicates
7. Analyze the date range filtering on PROCESSING_TIME_T
8. Consider the parallel hints already present
9. Look for opportunities to eliminate redundant operations
10. Validate that recommended indexes would actually be used

Focus especially on:
- Full table scans on large tables
- Missing or suboptimal indexes
- Inefficient join orders or methods
- Stale or missing statistics
- Partition pruning opportunities
- Parallel execution issues
"""

    # Save all collected data
    ts = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    base = f"sql_analysis_{ts}"
    
    facts = {
        "collected_at": ts,
        "sql_text": sql,
        "sql_length": len(sql),
        "objects_from_sql": [{"owner": o, "table": t} for o, t in sql_objects],
        "objects_from_plan": {
            "tables": [{"owner": o, "table": t} for o, t in tables],
            "indexes": [{"owner": o, "index": i} for o, i in indexes_in_plan]
        },
        "plan_error": plan_error,
        "execution_plan": "\n".join(xplan_lines),
        "plan_details": plan_details,
        "table_statistics": table_stats,
        "index_statistics": index_stats,
        "index_columns": index_columns,
        "partition_tables": part_tables,
        "partition_keys": part_keys,
        "column_statistics": column_stats,
        "analysis_notes": {
            "total_tables": len(all_tables),
            "total_indexes": len(index_stats),
            "partitioned_tables": len(part_tables),
            "columns_analyzed": len(column_stats)
        }
    }
    
    # Save files
    facts_path = os.path.join(OUTPUT_DIR, f"{base}_facts.json")
    prompt_path = os.path.join(OUTPUT_DIR, f"{base}_prompt.txt")
    
    dbg("SAVE", f"Writing facts to {facts_path}")
    with open(facts_path, "w", encoding="utf-8") as f:
        json.dump(facts, f, indent=2, ensure_ascii=False, default=str)
    
    dbg("SAVE", f"Writing prompt to {prompt_path}")
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt)
    
    # Print summary and prompt
    print("\n" + "=" * 80)
    print("COLLECTION SUMMARY")
    print("=" * 80)
    print(f"Tables analyzed: {len(all_tables)}")
    print(f"Indexes found: {len(index_stats)}")
    print(f"Partitioned tables: {len(part_tables)}")
    print(f"Column stats collected: {len(column_stats)}")
    print(f"Plan steps: {len(plan_details)}")
    if plan_error:
        print(f"WARNING: Plan generation had issues: {plan_error}")
    
    print("\n" + "=" * 80)
    print("LLM PROMPT (Ready to send)")
    print("=" * 80)
    print(prompt)
    
    print("\n" + "=" * 80)
    print("FILES SAVED")
    print("=" * 80)
    print(f"Facts:  {facts_path}")
    print(f"Prompt: {prompt_path}")
    
    # Cleanup
    cur.close()
    conn.close()
    dbg("DONE", "Analysis complete!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)