# server/resources/help_resources.py
"""
Help resources for Performance MCP Server
Provides passive documentation that LLM can discover when connected to multiple MCPs
"""

from mcp_app import mcp
from config import config


@mcp.resource("help://performance-mcp/capabilities")
def get_mcp_capabilities() -> str:
    """
    Performance MCP Server - What makes this MCP unique
    """
    return f"""# Performance MCP Server - Capabilities

## 🎯 Purpose
**SQL Query Performance Analyzer** - Analyzes Oracle/MySQL queries WITHOUT execution.
This MCP specializes in query optimization by collecting execution plans and database metadata.

**What This MCP Does:**
- Generates execution plans (EXPLAIN PLAN) without running queries
- Collects table/index statistics from data dictionary
- Detects performance issues (full table scans, Cartesian products)
- Maps business logic through foreign key relationships
- Compares query plans before/after optimization
- Provides real-time database performance monitoring

**What This MCP Does NOT Do:**
- ❌ Does not execute queries or return data
- ❌ Does not modify database (READ-ONLY)
- ❌ Not for data retrieval or reporting
- ❌ Not for schema migrations

## 🗄️ Supported Databases
- Oracle: 11g, 12c, 18c, 19c, 21c
- MySQL: 5.7, 8.0+

## 🔧 Available Tools ({len(mcp.tools)})

**Oracle Analysis:**
- `analyze_oracle_query` - Main performance analysis tool
- `compare_oracle_query_plans` - Compare before/after optimization
- `explain_oracle_query_logic` - Business logic + ER diagrams
- `get_table_business_context` - Deep table relationship analysis

**MySQL Analysis:**
- `analyze_mysql_query` - MySQL performance analysis
- `compare_mysql_query_plans` - MySQL plan comparison

**Monitoring:**
- `get_oracle_real_time_performance` - Current database metrics
- `get_oracle_historical_stats` - Historical trends
- `analyze_oracle_session_activity` - Active sessions
- `check_database_health` - Overall health check

**Help:**
- `get_mcp_help` - Interactive help system (call for details)

## ⚡ Quick Start
```
1. User asks: "Why is this query slow?"
2. Call: analyze_oracle_query(db_name='prod', sql_text='SELECT...')
3. Review: facts['execution_plan'], facts['full_table_scans']
4. Suggest: Index creation or query rewrite
5. Verify: compare_oracle_query_plans(original, optimized)
```

## 🔒 Security
- READ-ONLY operations only
- SELECT queries only (no DML/DDL/DCL)
- Built-in SQL injection protection
- No PL/SQL execution

## 📊 Output Control
- **standard**: Full data (15K-40K tokens) - deep analysis
- **compact**: Plan objects only (6K-18K tokens) - routine work  
- **minimal**: Essentials (1.5K-4.5K tokens) - large queries

Current preset: {config.output_preset}

## 🆚 Differentiation from Other MCPs
This MCP is specifically for **query performance optimization**.
Use other MCPs for:
- Data retrieval/reporting → Use database query MCPs
- Schema migrations → Use database admin MCPs
- Code analysis → Use code analysis MCPs
- File operations → Use filesystem MCPs

**Call `get_mcp_help(topic='tools')` for detailed tool documentation.**
"""


@mcp.resource("help://performance-mcp/quick-reference")
def get_quick_reference() -> dict:
    """
    Quick reference card for most common operations
    """
    return {
        "mcp_identity": {
            "name": "Performance MCP",
            "purpose": "SQL query performance analysis without execution",
            "specialty": "Execution plan analysis + metadata collection"
        },
        
        "top_3_use_cases": [
            {
                "scenario": "Slow query troubleshooting",
                "tool": "analyze_oracle_query or analyze_mysql_query",
                "what_you_get": "Execution plan, table stats, index usage, full table scan detection"
            },
            {
                "scenario": "Understanding legacy query logic",
                "tool": "explain_oracle_query_logic",
                "what_you_get": "ER diagram, FK relationships, table/column descriptions"
            },
            {
                "scenario": "Verify optimization worked",
                "tool": "compare_oracle_query_plans",
                "what_you_get": "Cost comparison, operation differences, performance impact"
            }
        ],
        
        "common_workflow": {
            "step_1": "analyze_oracle_query(db_name, sql_text) → Get baseline",
            "step_2": "Review facts['full_table_scans'] → Find issues",
            "step_3": "Suggest index or rewrite query",
            "step_4": "compare_oracle_query_plans(original, optimized) → Verify"
        },
        
        "key_outputs": {
            "execution_plan": "Visual tree of query operations with costs",
            "full_table_scans": "Tables missing indexes (factual data only)",
            "cartesian_detections": "Missing join conditions",
            "query_intent": "Detected query pattern (aggregation, pagination, etc)",
            "table_stats": "Row counts, block counts, last analyzed date",
            "index_stats": "Available indexes, columns, uniqueness",
            "constraints": "Primary keys, foreign keys, relationships"
        },
        
        "configuration": {
            "file": "settings.yaml or server/config.py",
            "important_setting": "output_preset (standard/compact/minimal)",
            "current_value": config.output_preset,
            "impact": "Controls token usage: standard=40K, compact=18K, minimal=4.5K"
        },
        
        "when_to_use_this_mcp": [
            "✅ User mentions: slow query, performance, execution plan, optimization",
            "✅ User asks: why is query slow? what indexes needed? explain this query",
            "✅ User wants: query analysis without running it"
        ],
        
        "when_NOT_to_use": [
            "❌ User wants: actual data from query (use data retrieval MCP)",
            "❌ User wants: create/alter table (use admin MCP)",
            "❌ User wants: insert/update/delete data (read-only MCP)"
        ],
        
        "get_detailed_help": "Call get_mcp_help(topic) with: tools, oracle, mysql, monitoring, troubleshooting, examples"
    }
