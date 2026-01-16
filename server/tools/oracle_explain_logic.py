# server/tools/oracle_explain_logic.py
"""
Oracle Business Logic Explanation Tool

This tool explains the business logic behind Oracle SQL queries by:
1. Extracting tables from the query
2. Collecting metadata from Oracle (with PostgreSQL caching)
3. Following relationships to understand the full context
4. Generating a graph-friendly output for relationship visualization
5. Creating LLM prompts for business explanation

For MySQL databases, use mysql_explain_logic.py instead.
"""

import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

# Import from sibling modules
from .oracle_business_context import collect_oracle_business_context

logger = logging.getLogger("explain_query_logic")
logger.setLevel(logging.DEBUG)


# ============================================================
# SQL Parsing
# ============================================================

def extract_tables_from_sql(sql: str) -> List[Tuple[Optional[str], str]]:
    """
    Extract table references from SQL.
    
    Returns list of (schema, table_name) tuples.
    Schema may be None if not specified.
    """
    # Normalize whitespace
    sql = ' '.join(sql.split())
    
    # Remove comments
    sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
    sql = re.sub(r'--[^\n]*', ' ', sql)
    
    # Patterns to find table names
    # Matches: FROM table, JOIN table, INTO table, UPDATE table
    table_pattern = r'''
        (?:FROM|JOIN|INTO|UPDATE)\s+
        (?:
            (?:"?(\w+)"?\s*\.\s*"?(\w+)"?)  # schema.table
            |
            (?:"?(\w+)"?)                    # just table
        )
        (?:\s+(?:AS\s+)?(?:\w+))?            # optional alias
    '''
    
    matches = re.findall(table_pattern, sql, re.IGNORECASE | re.VERBOSE)
    
    tables = set()
    for match in matches:
        schema1, table1, table_only = match
        if schema1 and table1:
            # schema.table format
            tables.add((schema1.upper(), table1.upper()))
        elif table_only:
            # Just table name
            tables.add((None, table_only.upper()))
    
    logger.debug(f"📋 Extracted {len(tables)} table references from SQL")
    return list(tables)


def resolve_table_schemas(
    cur, 
    tables: List[Tuple[Optional[str], str]], 
    default_schema: Optional[str] = None
) -> List[Tuple[str, str]]:
    """
    Resolve schema names for tables where schema wasn't specified.
    
    Args:
        cur: Oracle cursor
        tables: List of (schema, table) where schema may be None
        default_schema: Schema to use when none specified
        
    Returns:
        List of (schema, table) with all schemas resolved
    """
    resolved = []
    unresolved = []
    
    for schema, table in tables:
        if schema:
            resolved.append((schema, table))
        else:
            unresolved.append(table)
    
    if not unresolved:
        return resolved
    
    # Try to find schemas from database
    if default_schema:
        # Check if tables exist in default schema
        placeholders = ','.join([f':t{i}' for i in range(len(unresolved))])
        query = f"""
            SELECT table_name 
            FROM all_tables 
            WHERE owner = :schema AND table_name IN ({placeholders})
        """
        binds = {"schema": default_schema.upper()}
        binds.update({f"t{i}": t for i, t in enumerate(unresolved)})
        
        try:
            cur.execute(query, binds)
            found = {row[0] for row in cur.fetchall()}
            
            for table in unresolved:
                if table in found:
                    resolved.append((default_schema.upper(), table))
                else:
                    # Try to find in any schema
                    cur.execute(
                        "SELECT owner FROM all_tables WHERE table_name = :t AND ROWNUM = 1",
                        {"t": table}
                    )
                    row = cur.fetchone()
                    if row:
                        resolved.append((row[0], table))
                    else:
                        logger.warning(f"⚠️ Could not resolve schema for table: {table}")
                        
        except Exception as e:
            logger.warning(f"⚠️ Error resolving schemas: {e}")
            # Fallback: assume default schema
            for table in unresolved:
                resolved.append((default_schema.upper() if default_schema else "UNKNOWN", table))
    else:
        # No default schema - try to find each table
        for table in unresolved:
            try:
                cur.execute(
                    "SELECT owner FROM all_tables WHERE table_name = :t AND ROWNUM = 1",
                    {"t": table}
                )
                row = cur.fetchone()
                if row:
                    resolved.append((row[0], table))
                else:
                    logger.warning(f"⚠️ Could not resolve schema for table: {table}")
            except Exception as e:
                logger.warning(f"⚠️ Error finding table {table}: {e}")
    
    return resolved


# ============================================================
# Cache Integration
# ============================================================

async def get_cached_context(
    knowledge_db,
    db_name: str,
    tables: List[Tuple[str, str]]
) -> Tuple[Dict[Tuple[str, str], Dict], List[Tuple[str, str]]]:
    """
    Check PostgreSQL cache for existing table knowledge.
    Returns:
        - Dict of cached table context
        - List of tables that need to be fetched from Oracle
    """
    cached = {}
    uncached = []
    
    logger.info(f"🔍 Checking PostgreSQL cache for {len(tables)} tables...")
    
    for owner, table in tables:
        logger.debug(f"🔎 Attempting cache lookup: db={db_name}, schema={owner}, table={table}")
        try:
            knowledge = await knowledge_db.get_table_knowledge(db_name, owner, table)
            logger.debug(f"🔎 Cache lookup result for db={db_name}, schema={owner}, table={table}: {knowledge}")
            if knowledge:
                # Convert to context format
                cached[(owner, table)] = {
                    "owner": owner,
                    "table_name": table,
                    "comment": knowledge.get("oracle_comment"),
                    "columns": knowledge.get("columns", []),
                    "primary_key": knowledge.get("primary_key_columns", []),
                    "row_count": knowledge.get("num_rows"),
                    "is_lookup": knowledge.get("is_lookup_table", False),
                    "inferred_entity_type": knowledge.get("inferred_entity_type"),
                    "inferred_domain": knowledge.get("inferred_domain"),
                    "business_description": knowledge.get("business_description"),  # Admin docs
                    "cached": True
                }
                logger.info(f"📦 CACHE HIT: db={db_name}, schema={owner}, table={table} (from PostgreSQL)")
            else:
                uncached.append((owner, table))
                logger.info(f"📭 CACHE MISS: db={db_name}, schema={owner}, table={table} (will query Oracle)")
        except Exception as e:
            logger.error(f"❌ Exception during cache lookup for db={db_name}, schema={owner}, table={table}: {e}", exc_info=True)
    
    if cached:
        logger.info(f"✅ Found {len(cached)} tables in cache, {len(uncached)} need Oracle lookup")
    else:
        logger.info(f"📭 No cached data found, will fetch all {len(uncached)} tables from Oracle")
    
    return cached, uncached


async def cache_collected_context(knowledge_db, db_name: str, context: Dict[str, Any]):
    """
    Save collected context to PostgreSQL cache.
    """
    for key, table_ctx in context.get("table_context", {}).items():
        owner, table = key
        logger.debug(f"💾 [CACHE SAVE] Attempting to save to cache: db={db_name}, schema={owner}, table={table}")
        logger.debug(f"💾 [CACHE SAVE] Data keys: {list(table_ctx.keys())}")
        try:
            success = await knowledge_db.save_table_knowledge(
                db_name=db_name,
                owner=owner,
                table_name=table,
                oracle_comment=table_ctx.get("comment"),
                columns=[
                    {
                        "name": c.get("name"),
                        "data_type": c.get("data_type"),
                        "comment": c.get("comment"),
                        "nullable": c.get("nullable"),
                        "position": c.get("position")
                    }
                    for c in table_ctx.get("columns", [])
                ],
                primary_key_columns=table_ctx.get("primary_key", []),
                num_rows=table_ctx.get("row_count"),
                inferred_entity_type=table_ctx.get("inferred_entity_type"),
                inferred_domain=table_ctx.get("inferred_domain")
            )
            if success:
                logger.info(f"✅ [CACHE SAVE] Successfully saved to cache: db={db_name}, schema={owner}, table={table}")
            else:
                logger.error(f"❌ [CACHE SAVE] Save returned False for: db={db_name}, schema={owner}, table={table}")
        except Exception as e:
            logger.error(f"❌ [CACHE SAVE] Exception during save for db={db_name}, schema={owner}, table={table}: {e}", exc_info=True)
    # Cache relationships
    for rel in context.get("relationships", []):
        from_owner, from_table = rel["from"]
        to_owner, to_table = rel["to"]
        logger.debug(f"💾 Attempting to save relationship to cache: db={db_name}, from={from_owner}.{from_table}, to={to_owner}.{to_table}, rel={rel}")
        try:
            await knowledge_db.save_relationship(
                db_name=db_name,
                from_owner=from_owner,
                from_table=from_table,
                from_columns=rel["from_columns"],
                to_owner=to_owner,
                to_table=to_table,
                to_columns=rel["to_columns"],
                relationship_type="FK",
                constraint_name=rel.get("constraint_name")
            )
            logger.debug(f"💾 Successfully saved relationship to cache: db={db_name}, from={from_owner}.{from_table}, to={to_owner}.{to_table}")
        except Exception as e:
            logger.error(f"❌ Exception during cache save for relationship db={db_name}, from={from_owner}.{from_table}, to={to_owner}.{to_table}: {e}", exc_info=True)
    logger.info(f"💾 Cached {len(context.get('table_context', {}))} tables and {len(context.get('relationships', []))} relationships")


# ============================================================
# Explanation Generation
# ============================================================

def format_context_for_explanation(context: Dict[str, Any], sql: str) -> str:
    """
    Format collected context into a prompt for the LLM.
    """
    parts = []
    
    parts.append("## SQL Query to Explain\n")
    parts.append(f"```sql\n{sql}\n```\n")
    
    parts.append("\n## Tables in Query\n")
    
    for key, table_ctx in context.get("table_context", {}).items():
        owner, table = key
        
        parts.append(f"\n### {owner}.{table}")
        
        if table_ctx.get("is_core_table"):
            parts.append(" ⭐ (directly in query)")
        parts.append("\n")
        
        if table_ctx.get("comment"):
            parts.append(f"**Description:** {table_ctx['comment']}\n")
        
        if table_ctx.get("inferred_entity_type"):
            parts.append(f"**Entity Type:** {table_ctx['inferred_entity_type']}\n")
        
        if table_ctx.get("inferred_domain"):
            parts.append(f"**Domain:** {table_ctx['inferred_domain']}\n")
        
        if table_ctx.get("is_lookup"):
            parts.append("**Type:** Lookup/Reference table\n")
        
        if table_ctx.get("row_count") is not None:
            parts.append(f"**Row Count:** {table_ctx['row_count']:,}\n")
        
        if table_ctx.get("primary_key"):
            parts.append(f"**Primary Key:** {', '.join(table_ctx['primary_key'])}\n")
        
        # Columns
        columns = table_ctx.get("columns", [])
        if columns:
            parts.append("\n**Columns:**\n")
            for col in columns[:20]:  # Limit columns shown
                col_desc = f"- `{col['name']}` ({col.get('data_type', 'unknown')})"
                if col.get("comment"):
                    col_desc += f" - {col['comment']}"
                parts.append(col_desc + "\n")
            
            if len(columns) > 20:
                parts.append(f"  ... and {len(columns) - 20} more columns\n")
    
    # Relationships
    relationships = context.get("relationships", [])
    if relationships:
        parts.append("\n## Table Relationships\n")
        
        for rel in relationships:
            from_owner, from_table = rel["from"]
            to_owner, to_table = rel["to"]
            from_cols = ", ".join(rel["from_columns"])
            to_cols = ", ".join(rel["to_columns"])
            
            parts.append(
                f"- **{from_owner}.{from_table}** ({from_cols}) → "
                f"**{to_owner}.{to_table}** ({to_cols})\n"
            )
    
    return "".join(parts)


def generate_business_explanation_prompt(formatted_context: str, mermaid_diagram: str) -> str:
    """
    Generate the prompt for the LLM to explain business logic and create visualization.
    """
    return f"""You are a senior data analyst explaining database queries to business stakeholders.

Analyze this SQL query and provide:

1. **Business Purpose** - What business question does this answer?
2. **Data Flow** - How data flows through the tables (plain English)
3. **Entity Summary** - One sentence per table explaining its business role
4. **Key Relationships** - How entities connect (customer has orders, etc.)

Then, generate a **Mermaid ER diagram** showing the relationships. Use this as your starting point and enhance it:

```mermaid
{mermaid_diagram}
```

Improve the diagram by:
- Adding key columns to each entity
- Using proper cardinality (||--o{{ for one-to-many, etc.)
- Adding meaningful relationship labels

---

{formatted_context}

---

Provide your explanation, then the enhanced Mermaid diagram:"""


# ============================================================
# Graph Generation for Visualization
# ============================================================

def build_relationship_graph(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a graph structure that LLM can use to generate visual diagrams.
    
    Output format is optimized for Mermaid diagram generation:
    - nodes: tables with their type/domain info
    - edges: relationships between tables
    - mermaid: ready-to-use Mermaid diagram code
    """
    nodes = []
    edges = []
    
    # Build nodes from table context
    for key, table_ctx in context.get("table_context", {}).items():
        owner, table = key
        
        # Determine node style based on table type
        node_type = "entity"
        if table_ctx.get("is_lookup"):
            node_type = "lookup"
        elif table_ctx.get("is_core_table"):
            node_type = "core"
        
        nodes.append({
            "id": f"{owner}.{table}",
            "label": table,
            "schema": owner,
            "type": node_type,
            "entity": table_ctx.get("inferred_entity_type"),
            "domain": table_ctx.get("inferred_domain"),
            "row_count": table_ctx.get("row_count"),
            "description": table_ctx.get("comment")
        })
    
    # Build edges from relationships
    for rel in context.get("relationships", []):
        from_owner, from_table = rel["from"]
        to_owner, to_table = rel["to"]
        
        edges.append({
            "from": f"{from_owner}.{from_table}",
            "to": f"{to_owner}.{to_table}",
            "from_column": ", ".join(rel["from_columns"]),
            "to_column": ", ".join(rel["to_columns"]),
            "label": f"{rel['from_columns'][0]} → {rel['to_columns'][0]}" if rel["from_columns"] else "FK"
        })
    
    # Generate Mermaid diagram
    mermaid_lines = ["erDiagram"]
    
    # Add relationships as Mermaid ER notation
    for edge in edges:
        from_short = edge["from"].split(".")[-1]
        to_short = edge["to"].split(".")[-1]
        mermaid_lines.append(f"    {from_short} }}|--|| {to_short} : \"{edge['label']}\"")
    
    # Add standalone nodes (tables with no relationships shown)
    connected = set()
    for edge in edges:
        connected.add(edge["from"])
        connected.add(edge["to"])
    
    for node in nodes:
        if node["id"] not in connected:
            mermaid_lines.append(f"    {node['label']} {{")
            mermaid_lines.append(f"    }}")
    
    return {
        "nodes": nodes,
        "edges": edges,
        "mermaid": "\n".join(mermaid_lines)
    }


# ============================================================
# Main Tool Function
# ============================================================

async def explain_oracle_query_logic(
    sql: str,
    oracle_cursor,
    db_name: str = "unknown",
    knowledge_db = None,
    default_schema: Optional[str] = None,
    follow_relationships: bool = True,
    max_depth: int = 2,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Main entry point: Explain the business logic of an Oracle SQL query.
    
    Args:
        sql: The SQL query to explain
        oracle_cursor: Active Oracle cursor
        db_name: Database name (for caching)
        knowledge_db: Optional KnowledgeDB instance for caching
        default_schema: Default schema if tables don't specify one
        follow_relationships: Whether to follow FK relationships
        max_depth: How deep to follow relationships
        use_cache: Whether to use PostgreSQL cache
        
    Returns:
        Dict containing:
        - graph: Nodes/edges for visualization (Mermaid-ready)
        - explanation_prompt: Ready-to-use LLM prompt
        - table_context: Detailed table metadata
        - relationships: Discovered relationships
        - stats: Execution statistics
    """
    start_time = datetime.now()
    stats = {
        "cache_hits": 0,
        "cache_misses": 0,
        "oracle_queries": 0
    }
    
    # Step 1: Extract tables from SQL
    raw_tables = extract_tables_from_sql(sql)
    logger.info(f"📋 Extracted {len(raw_tables)} table references")
    
    if not raw_tables:
        return {
            "error": "No tables found in SQL query",
            "sql": sql
        }
    
    # Step 2: Resolve schemas
    tables = resolve_table_schemas(oracle_cursor, raw_tables, default_schema)
    stats["oracle_queries"] += len([t for t in raw_tables if t[0] is None])
    
    # Step 3: Check cache
    cached_context = {}
    uncached_tables = tables
    
    if use_cache and knowledge_db:
        cached_context, uncached_tables = await get_cached_context(knowledge_db, db_name, tables)
        stats["cache_hits"] = len(cached_context)
        stats["cache_misses"] = len(uncached_tables)
    
    # Step 4: Collect context from Oracle for uncached tables
    if uncached_tables:
        oracle_context = collect_oracle_business_context(
            oracle_cursor,
            uncached_tables,
            follow_relationships=follow_relationships,
            max_depth=max_depth
        )
        stats["oracle_queries"] += oracle_context["stats"]["oracle_queries"]
        
        # Step 5: Cache the collected context
        if use_cache and knowledge_db:
            await cache_collected_context(knowledge_db, db_name, oracle_context)
        
        # Merge with cached context
        for key, ctx in oracle_context.get("table_context", {}).items():
            if key not in cached_context:
                cached_context[key] = ctx
        
        # Add relationship info
        relationships = oracle_context.get("relationships", [])
    else:
        # All from cache - get relationships from cache too
        relationships = []
        if knowledge_db:
            for owner, table in tables:
                rels = await knowledge_db.get_relationships_for_table(db_name, owner, table)
                for rel in rels:
                    relationships.append({
                        "from": (rel["from_owner"], rel["from_table"]),
                        "to": (rel["to_owner"], rel["to_table"]),
                        "from_columns": rel["from_columns"],
                        "to_columns": rel["to_columns"],
                        "type": rel.get("relationship_type", "FK")
                    })
    
    # Build final context
    final_context = {
        "table_context": cached_context,
        "relationships": relationships,
        "core_tables": [{"owner": o, "table": t} for o, t in tables]
    }
    
    # Mark core tables
    for owner, table in tables:
        if (owner, table) in final_context["table_context"]:
            final_context["table_context"][(owner, table)]["is_core_table"] = True
    
    # Step 6: Build graph for visualization
    graph = build_relationship_graph(final_context)
    
    # Step 7: Format for LLM
    formatted_context = format_context_for_explanation(final_context, sql)
    explanation_prompt = generate_business_explanation_prompt(formatted_context, graph["mermaid"])
    
    # Final stats
    duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
    stats["duration_ms"] = duration_ms
    stats["tables_analyzed"] = len(cached_context)
    stats["relationships_found"] = len(relationships)
    
    logger.info(f"✅ Context collected in {duration_ms}ms: {len(cached_context)} tables, {len(relationships)} relationships")
    
    return {
        "sql": sql,
        "graph": graph,
        "explanation_prompt": explanation_prompt,
        "tables": {
            f"{k[0]}.{k[1]}": {
                "name": v.get("table_name"),
                "type": v.get("inferred_entity_type"),
                "domain": v.get("inferred_domain"),
                "is_lookup": v.get("is_lookup"),
                "is_core": v.get("is_core_table"),
                "description": v.get("comment"),
                "row_count": v.get("row_count")
            }
            for k, v in final_context["table_context"].items()
        },
        "relationships": [
            {
                "from": f"{r['from'][0]}.{r['from'][1]}",
                "to": f"{r['to'][0]}.{r['to'][1]}",
                "columns": f"{', '.join(r['from_columns'])} → {', '.join(r['to_columns'])}"
            }
            for r in relationships
        ],
        "stats": stats
    }