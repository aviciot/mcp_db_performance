from mcp_app import mcp

@mcp.prompt()
def oracle_full_analysis(db_name: str, query: str):
    """Full Oracle query performance analysis - checks everything"""
    tool_call = f'analyze_full_sql_context(db_name="{db_name}", sql_text="{query}")'
    
    return f"""Analyze this Oracle query for ALL performance issues.

Database: {db_name}
Query: {query}

Use tool: {tool_call}

Focus on:
- Execution plan cost and operations
- Index usage (SKIP SCAN, missing indexes, wrong column order)
- Partition pruning effectiveness
- Table/join efficiency
- Cardinality estimates

Provide specific fixes with DDL statements."""

@mcp.prompt()
def oracle_index_analysis(db_name: str, query: str):
    """Analyze only index-related problems"""
    tool_call = f'analyze_full_sql_context(db_name="{db_name}", sql_text="{query}")'
    
    return f"""Check index problems for this Oracle query.

Database: {db_name}
Query: {query}

Use tool: {tool_call}

Focus ONLY on:
- INDEX SKIP SCAN problems
- Missing indexes
- Wrong index column order
- Unused indexes

Ignore: partitions, joins, table stats (unless related to index usage)

Provide CREATE INDEX statements to fix issues."""

@mcp.prompt()
def oracle_partition_analysis(db_name: str, query: str):
    """Analyze partition pruning problems"""
    tool_call = f'analyze_full_sql_context(db_name="{db_name}", sql_text="{query}")'
    
    return f"""Check partition pruning for this Oracle query.

Database: {db_name}
Query: {query}

Use tool: {tool_call}

Focus ONLY on:
- Are all partitions being scanned?
- Is partition key in WHERE clause?
- PARTITION HASH ALL vs SINGLE
- Partition key recommendations

Ignore: index problems, join problems (unless related to partitions)

Explain how to improve partition pruning."""
