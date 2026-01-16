# server/tools/oracle_business_context.py
"""
Oracle Business Context Collector

Collects metadata from Oracle databases to build business understanding:
- Table and column comments from ALL_TAB_COMMENTS / ALL_COL_COMMENTS
- Foreign key relationships from ALL_CONSTRAINTS
- Primary keys and unique constraints
- Row counts and table sizes

For MySQL databases, use mysql_business_context.py instead.
"""

import re
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger("oracle_business_context")


# ============================================================
# Oracle Metadata Queries
# ============================================================

def get_table_comments(cur, tables: List[Tuple[str, str]]) -> Dict[Tuple[str, str], str]:
    """
    Get table comments from ALL_TAB_COMMENTS.
    
    Args:
        cur: Oracle cursor
        tables: List of (owner, table_name) tuples
        
    Returns:
        Dict mapping (owner, table) to comment string
    """
    if not tables:
        return {}
    
    # Build OR conditions
    conditions = []
    binds = {}
    
    for i, (owner, table) in enumerate(tables, 1):
        conditions.append(f"(owner = :o{i} AND table_name = :t{i})")
        binds[f"o{i}"] = owner.upper()
        binds[f"t{i}"] = table.upper()
    
    query = f"""
        SELECT owner, table_name, comments
        FROM all_tab_comments
        WHERE ({' OR '.join(conditions)})
          AND comments IS NOT NULL
    """
    
    try:
        cur.execute(query, binds)
        result = {}
        for row in cur.fetchall():
            result[(row[0], row[1])] = row[2]
        logger.debug(f"📝 Got {len(result)} table comments")
        return result
    except Exception as e:
        logger.warning(f"⚠️ Failed to get table comments: {e}")
        return {}


def get_column_comments(cur, tables: List[Tuple[str, str]]) -> Dict[Tuple[str, str], Dict[str, str]]:
    """
    Get column comments from ALL_COL_COMMENTS.
    
    Args:
        cur: Oracle cursor
        tables: List of (owner, table_name) tuples
        
    Returns:
        Dict mapping (owner, table) to {column_name: comment}
    """
    if not tables:
        return {}
    
    # Build OR conditions
    conditions = []
    binds = {}
    
    for i, (owner, table) in enumerate(tables, 1):
        conditions.append(f"(owner = :o{i} AND table_name = :t{i})")
        binds[f"o{i}"] = owner.upper()
        binds[f"t{i}"] = table.upper()
    
    query = f"""
        SELECT owner, table_name, column_name, comments
        FROM all_col_comments
        WHERE ({' OR '.join(conditions)})
          AND comments IS NOT NULL
    """
    
    try:
        cur.execute(query, binds)
        result = defaultdict(dict)
        for row in cur.fetchall():
            result[(row[0], row[1])][row[2]] = row[3]
        logger.debug(f"📝 Got column comments for {len(result)} tables")
        return dict(result)
    except Exception as e:
        logger.warning(f"⚠️ Failed to get column comments: {e}")
        return {}


def get_column_details(cur, tables: List[Tuple[str, str]]) -> Dict[Tuple[str, str], List[Dict]]:
    """
    Get detailed column information from ALL_TAB_COLUMNS.
    
    Returns columns with: name, type, nullable, data_default, comments
    """
    if not tables:
        return {}
    
    # Build OR conditions
    conditions = []
    binds = {}
    
    for i, (owner, table) in enumerate(tables, 1):
        conditions.append(f"(c.owner = :o{i} AND c.table_name = :t{i})")
        binds[f"o{i}"] = owner.upper()
        binds[f"t{i}"] = table.upper()
    
    query = f"""
        SELECT 
            c.owner,
            c.table_name,
            c.column_name,
            c.data_type,
            c.data_length,
            c.data_precision,
            c.data_scale,
            c.nullable,
            c.data_default,
            c.column_id,
            cc.comments
        FROM all_tab_columns c
        LEFT JOIN all_col_comments cc 
            ON c.owner = cc.owner 
            AND c.table_name = cc.table_name 
            AND c.column_name = cc.column_name
        WHERE ({' OR '.join(conditions)})
        ORDER BY c.owner, c.table_name, c.column_id
    """
    
    try:
        cur.execute(query, binds)
        result = defaultdict(list)
        
        for row in cur.fetchall():
            owner, table = row[0], row[1]
            
            # Build data type string
            data_type = row[3]
            if row[4] and data_type in ('VARCHAR2', 'CHAR', 'NVARCHAR2', 'RAW'):
                data_type = f"{data_type}({row[4]})"
            elif row[5] is not None:
                if row[6]:
                    data_type = f"{data_type}({row[5]},{row[6]})"
                else:
                    data_type = f"{data_type}({row[5]})"
            
            result[(owner, table)].append({
                "name": row[2],
                "data_type": data_type,
                "nullable": row[7] == 'Y',
                "default": str(row[8])[:100] if row[8] else None,
                "position": row[9],
                "comment": row[10]
            })
        
        logger.debug(f"📊 Got column details for {len(result)} tables")
        return dict(result)
    except Exception as e:
        logger.warning(f"⚠️ Failed to get column details: {e}")
        return {}


def get_foreign_keys(cur, tables: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    """
    Get foreign key constraints from ALL_CONSTRAINTS.
    
    Returns FK details including referenced table and columns.
    """
    if not tables:
        return []
    
    # Build OR conditions for the FROM side (tables that HAVE foreign keys)
    conditions = []
    binds = {}
    
    for i, (owner, table) in enumerate(tables, 1):
        conditions.append(f"(c.owner = :o{i} AND c.table_name = :t{i})")
        binds[f"o{i}"] = owner.upper()
        binds[f"t{i}"] = table.upper()
    
    query = f"""
        SELECT 
            c.owner as from_owner,
            c.table_name as from_table,
            c.constraint_name,
            cc.column_name as from_column,
            cc.position,
            c.r_owner as to_owner,
            rc.table_name as to_table,
            rcc.column_name as to_column
        FROM all_constraints c
        JOIN all_cons_columns cc 
            ON c.owner = cc.owner AND c.constraint_name = cc.constraint_name
        JOIN all_constraints rc 
            ON c.r_owner = rc.owner AND c.r_constraint_name = rc.constraint_name
        JOIN all_cons_columns rcc 
            ON rc.owner = rcc.owner AND rc.constraint_name = rcc.constraint_name
            AND cc.position = rcc.position
        WHERE c.constraint_type = 'R'
          AND ({' OR '.join(conditions)})
        ORDER BY c.owner, c.table_name, c.constraint_name, cc.position
    """
    
    try:
        cur.execute(query, binds)
        
        # Group by constraint
        fks = defaultdict(lambda: {
            "from_owner": None,
            "from_table": None,
            "to_owner": None,
            "to_table": None,
            "constraint_name": None,
            "from_columns": [],
            "to_columns": []
        })
        
        for row in cur.fetchall():
            key = (row[0], row[1], row[2])  # from_owner, from_table, constraint_name
            fk = fks[key]
            fk["from_owner"] = row[0]
            fk["from_table"] = row[1]
            fk["constraint_name"] = row[2]
            fk["from_columns"].append(row[3])
            fk["to_owner"] = row[5]
            fk["to_table"] = row[6]
            fk["to_columns"].append(row[7])
        
        result = list(fks.values())
        logger.debug(f"🔗 Found {len(result)} foreign keys")
        return result
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to get foreign keys: {e}")
        return []


def get_incoming_foreign_keys(cur, tables: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    """
    Get foreign keys that REFERENCE these tables (incoming relationships).
    
    This helps understand what other tables depend on the given tables.
    """
    if not tables:
        return []
    
    # Build OR conditions for the TO side (tables that ARE REFERENCED)
    conditions = []
    binds = {}
    
    for i, (owner, table) in enumerate(tables, 1):
        conditions.append(f"(rc.owner = :o{i} AND rc.table_name = :t{i})")
        binds[f"o{i}"] = owner.upper()
        binds[f"t{i}"] = table.upper()
    
    query = f"""
        SELECT 
            c.owner as from_owner,
            c.table_name as from_table,
            c.constraint_name,
            cc.column_name as from_column,
            cc.position,
            rc.owner as to_owner,
            rc.table_name as to_table,
            rcc.column_name as to_column
        FROM all_constraints c
        JOIN all_cons_columns cc 
            ON c.owner = cc.owner AND c.constraint_name = cc.constraint_name
        JOIN all_constraints rc 
            ON c.r_owner = rc.owner AND c.r_constraint_name = rc.constraint_name
        JOIN all_cons_columns rcc 
            ON rc.owner = rcc.owner AND rc.constraint_name = rcc.constraint_name
            AND cc.position = rcc.position
        WHERE c.constraint_type = 'R'
          AND ({' OR '.join(conditions)})
        ORDER BY c.owner, c.table_name, c.constraint_name, cc.position
    """
    
    try:
        cur.execute(query, binds)
        
        # Group by constraint
        fks = defaultdict(lambda: {
            "from_owner": None,
            "from_table": None,
            "to_owner": None,
            "to_table": None,
            "constraint_name": None,
            "from_columns": [],
            "to_columns": []
        })
        
        for row in cur.fetchall():
            key = (row[0], row[1], row[2])
            fk = fks[key]
            fk["from_owner"] = row[0]
            fk["from_table"] = row[1]
            fk["constraint_name"] = row[2]
            fk["from_columns"].append(row[3])
            fk["to_owner"] = row[5]
            fk["to_table"] = row[6]
            fk["to_columns"].append(row[7])
        
        result = list(fks.values())
        logger.debug(f"🔗 Found {len(result)} incoming foreign keys")
        return result
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to get incoming foreign keys: {e}")
        return []


def get_primary_keys(cur, tables: List[Tuple[str, str]]) -> Dict[Tuple[str, str], List[str]]:
    """
    Get primary key columns for tables.
    """
    if not tables:
        return {}
    
    conditions = []
    binds = {}
    
    for i, (owner, table) in enumerate(tables, 1):
        conditions.append(f"(c.owner = :o{i} AND c.table_name = :t{i})")
        binds[f"o{i}"] = owner.upper()
        binds[f"t{i}"] = table.upper()
    
    query = f"""
        SELECT c.owner, c.table_name, cc.column_name, cc.position
        FROM all_constraints c
        JOIN all_cons_columns cc 
            ON c.owner = cc.owner AND c.constraint_name = cc.constraint_name
        WHERE c.constraint_type = 'P'
          AND ({' OR '.join(conditions)})
        ORDER BY c.owner, c.table_name, cc.position
    """
    
    try:
        cur.execute(query, binds)
        result = defaultdict(list)
        
        for row in cur.fetchall():
            result[(row[0], row[1])].append(row[2])
        
        logger.debug(f"🔑 Got primary keys for {len(result)} tables")
        return dict(result)
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to get primary keys: {e}")
        return {}


def get_unique_constraints(cur, tables: List[Tuple[str, str]]) -> Dict[Tuple[str, str], List[Dict]]:
    """
    Get unique constraints (potential business keys).
    """
    if not tables:
        return {}
    
    conditions = []
    binds = {}
    
    for i, (owner, table) in enumerate(tables, 1):
        conditions.append(f"(c.owner = :o{i} AND c.table_name = :t{i})")
        binds[f"o{i}"] = owner.upper()
        binds[f"t{i}"] = table.upper()
    
    query = f"""
        SELECT c.owner, c.table_name, c.constraint_name, cc.column_name, cc.position
        FROM all_constraints c
        JOIN all_cons_columns cc 
            ON c.owner = cc.owner AND c.constraint_name = cc.constraint_name
        WHERE c.constraint_type = 'U'
          AND ({' OR '.join(conditions)})
        ORDER BY c.owner, c.table_name, c.constraint_name, cc.position
    """
    
    try:
        cur.execute(query, binds)
        
        # Group by table then constraint
        temp = defaultdict(lambda: defaultdict(list))
        for row in cur.fetchall():
            temp[(row[0], row[1])][row[2]].append(row[3])
        
        result = {}
        for table_key, constraints in temp.items():
            result[table_key] = [
                {"name": name, "columns": cols}
                for name, cols in constraints.items()
            ]
        
        logger.debug(f"🔐 Got unique constraints for {len(result)} tables")
        return result
        
    except Exception as e:
        logger.warning(f"⚠️ Failed to get unique constraints: {e}")
        return {}


def get_table_row_counts(cur, tables: List[Tuple[str, str]]) -> Dict[Tuple[str, str], int]:
    """
    Get approximate row counts from ALL_TABLES.
    """
    if not tables:
        return {}
    
    conditions = []
    binds = {}
    
    for i, (owner, table) in enumerate(tables, 1):
        conditions.append(f"(owner = :o{i} AND table_name = :t{i})")
        binds[f"o{i}"] = owner.upper()
        binds[f"t{i}"] = table.upper()
    
    query = f"""
        SELECT owner, table_name, num_rows
        FROM all_tables
        WHERE ({' OR '.join(conditions)})
    """
    
    try:
        cur.execute(query, binds)
        result = {}
        for row in cur.fetchall():
            result[(row[0], row[1])] = row[2] or 0
        return result
    except Exception as e:
        logger.warning(f"⚠️ Failed to get row counts: {e}")
        return {}


def get_sample_column_values(
    cur, 
    owner: str, 
    table_name: str, 
    columns: List[str],
    limit: int = 10
) -> Dict[str, List[str]]:
    """
    Get sample distinct values for columns (useful for status codes, types, etc.)
    
    Only samples columns that look like codes/types (not IDs or large text).
    """
    if not columns:
        return {}
    
    # Filter to columns that are likely to be meaningful codes
    code_patterns = ['STATUS', 'TYPE', 'CODE', 'FLAG', 'STATE', 'CATEGORY', 'KIND', 'MODE']
    sample_columns = [
        c for c in columns 
        if any(p in c.upper() for p in code_patterns) or c.upper().endswith('_CD')
    ]
    
    if not sample_columns:
        return {}
    
    result = {}
    
    for col in sample_columns[:5]:  # Limit to 5 columns max
        try:
            # Safe query - column name is from metadata, not user input
            query = f"""
                SELECT DISTINCT "{col}"
                FROM "{owner}"."{table_name}"
                WHERE "{col}" IS NOT NULL
                  AND ROWNUM <= :lim
            """
            cur.execute(query, {"lim": limit})
            values = [str(row[0]) for row in cur.fetchall()]
            if values:
                result[col] = values
        except Exception as e:
            logger.debug(f"⚠️ Failed to sample {col}: {e}")
            continue
    
    return result


# ============================================================
# Business Context Inference
# ============================================================

def classify_table_type(owner: str, table_name: str) -> str:
    """
    Classify table as 'business', 'operational', 'system', or 'audit'.
    
    This helps filter out non-business tables from explanations.
    """
    name_upper = table_name.upper()
    owner_upper = owner.upper()
    
    # System/DBA tables - skip for business logic
    system_prefixes = ('V$', 'GV$', 'DBA_', 'ALL_', 'USER_', 'CDB_', 'V_$')
    if any(name_upper.startswith(p) for p in system_prefixes):
        return 'system'
    
    # System schemas
    system_schemas = ('SYS', 'SYSTEM', 'DBSNMP', 'OUTLN', 'APPQOSSYS', 
                      'WMSYS', 'EXFSYS', 'CTXSYS', 'XDB', 'ORDDATA')
    if owner_upper in system_schemas:
        return 'system'
    
    # Operational/monitoring tables
    operational_patterns = ['_LOG', '_HIST', '_ARCHIVE', '_BACKUP', '_TEMP', 
                           '_TMP', '_BAK', '_OLD', 'DEBUG_', 'TRACE_', 
                           'MONITOR_', 'METRIC_', 'STATS_']
    if any(p in name_upper for p in operational_patterns):
        return 'operational'
    
    # Audit tables
    audit_patterns = ['AUDIT', '_AUD', 'AUD_', 'CHANGE_LOG', 'ACTIVITY_LOG']
    if any(p in name_upper for p in audit_patterns):
        return 'audit'
    
    # Everything else is business
    return 'business'


def is_business_relevant(owner: str, table_name: str) -> bool:
    """
    Check if table should be included in business logic explanation.
    
    Returns False for system views, operational tables, etc.
    """
    table_type = classify_table_type(owner, table_name)
    return table_type in ('business', 'audit')  # Include audit for context


def infer_entity_type(table_name: str, columns: List[str]) -> Optional[str]:
    """
    Infer entity type from table name and columns.
    Priority matters - more specific patterns are checked first.
    """
    name_upper = table_name.upper()
    
    # Ordered patterns - more specific first to avoid false matches
    # e.g., CUSTOMER_ORDERS should match 'order' not 'customer'
    ordered_patterns = [
        # Very specific patterns first
        ('audit_log', ['AUDIT_LOG', 'AUDIT_TRAIL', 'CHANGE_LOG', 'HISTORY_LOG']),
        ('transaction', ['TRANSACTION', 'TRANS_', '_TXN', 'TXN_', 'PAYMENT', 'SETTLEMENT']),
        ('order', ['ORDER', 'ORD_', '_ORD', 'PURCHASE']),
        ('invoice', ['INVOICE', 'INV_', '_INV', 'BILL']),
        ('product', ['PRODUCT', 'PROD_', '_PROD', 'ITEM', 'SKU']),
        ('merchant', ['MERCHANT', 'SELLER', 'VENDOR', 'SHOP']),
        ('customer', ['CUSTOMER', 'CUST_', '_CUST', 'CLIENT', 'BUYER']),
        ('user', ['USER', 'ACCOUNT', 'MEMBER', 'PROFILE']),
        ('employee', ['EMPLOYEE', 'EMP_', '_EMP', 'STAFF', 'WORKER']),
        # Generic patterns last
        ('lookup', ['_TYPE', 'TYPE_', '_CODE', 'CODE_', '_STATUS', 'STATUS_', 'CATEGORY', 'CONFIG', 'LOOKUP']),
        ('audit_log', ['AUDIT', 'LOG', 'HISTORY', 'TRAIL']),
    ]
    
    for entity, patterns in ordered_patterns:
        for pattern in patterns:
            if pattern in name_upper:
                return entity
    
    # Infer from columns
    col_set = set(c.upper() for c in columns)
    
    if 'CARD_NUMBER' in col_set or 'PAN' in col_set:
        return 'payment_card'
    if 'EMAIL' in col_set and 'FIRST_NAME' in col_set:
        return 'person'
    if 'AMOUNT' in col_set and 'CURRENCY' in col_set:
        return 'financial_record'
    
    return None


def infer_domain(table_name: str, columns: List[str], fk_tables: List[str]) -> Optional[str]:
    """
    Infer business domain from table context.
    """
    all_text = ' '.join([table_name] + columns + fk_tables).upper()
    
    domain_indicators = {
        'payments': ['PAYMENT', 'TRANS', 'SETTLE', 'MERCHANT', 'CARD', 'ACQUIR', 'CHARGEBACK'],
        'ecommerce': ['ORDER', 'CART', 'PRODUCT', 'SHIPPING', 'CATALOG'],
        'crm': ['CUSTOMER', 'CONTACT', 'LEAD', 'OPPORTUNITY', 'CAMPAIGN'],
        'hr': ['EMPLOYEE', 'SALARY', 'DEPARTMENT', 'LEAVE', 'PAYROLL'],
        'inventory': ['STOCK', 'WAREHOUSE', 'INVENTORY', 'SUPPLY'],
        'finance': ['ACCOUNT', 'LEDGER', 'JOURNAL', 'BALANCE', 'CREDIT', 'DEBIT'],
        'audit': ['AUDIT', 'LOG', 'HISTORY', 'CHANGE', 'TRACK'],
    }
    
    scores = defaultdict(int)
    for domain, indicators in domain_indicators.items():
        for indicator in indicators:
            if indicator in all_text:
                scores[domain] += 1
    
    if scores:
        return max(scores, key=scores.get)
    return None


def is_lookup_table(row_count: Optional[int], column_count: int) -> bool:
    """
    Determine if a table is likely a lookup/reference table.
    
    Lookup tables typically have:
    - Small row count (< 1000) AND reasonable column count
    - OR very few columns (< 5) AND small-ish row count
    
    Large tables with few columns might be narrow fact tables, not lookups.
    """
    # If row count is unknown, be conservative
    if row_count is None:
        return column_count <= 5
    
    # Definitely not a lookup if millions of rows
    if row_count >= 100000:
        return False
    
    # Classic lookup: small row count
    if row_count < 1000:
        return True
    
    # Medium table with very few columns might be lookup
    if row_count < 10000 and column_count <= 5:
        return True
    
    return False


# ============================================================
# Main Collector Function
# ============================================================

def collect_oracle_business_context(
    cur,
    tables: List[Tuple[str, str]],
    follow_relationships: bool = True,
    max_depth: int = 2
) -> Dict[str, Any]:
    """
    Collect comprehensive business context for Oracle tables.
    
    Args:
        cur: Oracle cursor
        tables: List of (owner, table_name) tuples
        follow_relationships: Whether to follow FK relationships
        max_depth: How many levels deep to follow relationships
        
    Returns:
        Dict with table_context, relationships, and inferred_domains
    """
    start_time = datetime.now()
    oracle_queries = 0
    
    all_tables = set(tables)
    processed_tables = set()
    relationships = []
    
    # Iteratively discover related tables
    current_depth = 0
    tables_to_process = list(tables)
    
    while tables_to_process and current_depth < max_depth:
        # Get metadata for current batch
        batch = [t for t in tables_to_process if t not in processed_tables]
        if not batch:
            break
            
        logger.info(f"📊 Processing {len(batch)} tables at depth {current_depth}")
        
        # Collect foreign keys (outgoing)
        fks = get_foreign_keys(cur, batch)
        oracle_queries += 1
        
        for fk in fks:
            relationships.append({
                "from": (fk["from_owner"], fk["from_table"]),
                "to": (fk["to_owner"], fk["to_table"]),
                "from_columns": fk["from_columns"],
                "to_columns": fk["to_columns"],
                "constraint_name": fk["constraint_name"],
                "type": "FK"
            })
            
            # Add referenced table for next iteration
            ref_table = (fk["to_owner"], fk["to_table"])
            if ref_table not in all_tables and follow_relationships:
                all_tables.add(ref_table)
        
        # Mark as processed
        processed_tables.update(batch)
        
        # Prepare next batch (newly discovered tables)
        tables_to_process = [t for t in all_tables if t not in processed_tables]
        current_depth += 1
    
    # Now collect detailed metadata for ALL tables
    all_tables_list = list(all_tables)
    
    table_comments = get_table_comments(cur, all_tables_list)
    oracle_queries += 1
    
    column_details = get_column_details(cur, all_tables_list)
    oracle_queries += 1
    
    primary_keys = get_primary_keys(cur, all_tables_list)
    oracle_queries += 1
    
    unique_constraints = get_unique_constraints(cur, all_tables_list)
    oracle_queries += 1
    
    row_counts = get_table_row_counts(cur, all_tables_list)
    oracle_queries += 1
    
    # Build table context
    table_context = {}
    
    for owner, table in all_tables_list:
        key = (owner, table)
        columns = column_details.get(key, [])
        column_names = [c["name"] for c in columns]
        
        # Get related table names for domain inference
        related_tables = [
            r["to"][1] for r in relationships 
            if r["from"] == key
        ]
        
        row_count = row_counts.get(key)
        
        # Classify table type
        table_type = classify_table_type(owner, table)
        
        table_context[key] = {
            "owner": owner,
            "table_name": table,
            "comment": table_comments.get(key),
            "columns": columns,
            "primary_key": primary_keys.get(key, []),
            "unique_constraints": unique_constraints.get(key, []),
            "row_count": row_count,
            "is_lookup": is_lookup_table(row_count, len(columns)),
            "inferred_entity_type": infer_entity_type(table, column_names),
            "inferred_domain": infer_domain(table, column_names, related_tables),
            "is_core_table": key in tables,  # Was in original query
            "table_type": table_type,  # business, operational, system, audit
            "is_business_relevant": table_type in ('business', 'audit'),
        }
    
    # Filter out system tables from relationships for cleaner output
    business_relationships = [
        r for r in relationships
        if is_business_relevant(r["from"][0], r["from"][1]) 
        and is_business_relevant(r["to"][0], r["to"][1])
    ]
    
    # Calculate duration
    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
    
    # Count skipped tables
    system_tables = [
        f"{o}.{t}" for o, t in all_tables 
        if not is_business_relevant(o, t)
    ]
    
    return {
        "table_context": table_context,
        "relationships": business_relationships,
        "all_relationships": relationships,  # Include all for debugging
        "core_tables": [{"owner": o, "table": t} for o, t in tables],
        "discovered_tables": [
            {"owner": o, "table": t} 
            for o, t in all_tables 
            if (o, t) not in set(tables)
        ],
        "skipped_system_tables": system_tables,
        "stats": {
            "tables_analyzed": len(all_tables),
            "business_tables": len([t for t in all_tables if is_business_relevant(t[0], t[1])]),
            "system_tables_skipped": len(system_tables),
            "relationships_found": len(business_relationships),
            "oracle_queries": oracle_queries,
            "duration_ms": duration_ms,
            "max_depth_reached": current_depth
        }
    }
