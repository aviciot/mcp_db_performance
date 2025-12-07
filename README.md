# Oracle Performance MCP Server# Oracle Performance MCP Server



**Read-only SQL performance analysis tool** that provides LLMs with comprehensive Oracle database context for query tuning recommendations.This MCP exposes a single high-value tool:



## 🎯 What It Does### `analyze_full_sql_context(db_name, sql_text)`



This MCP server provides tools to analyze Oracle SQL queries **without executing them**. It collects execution plans, statistics, and metadata to help LLMs provide expert-level performance tuning advice.It connects to an internal Oracle database using **safe presets** defined in

`config/settings.yaml`, collects full performance metadata, and returns:

### Available Tools

- Execution Plan (DBMS_XPLAN)

#### 1. `analyze_full_sql_context(db_name, sql_text)`- Plan steps

Comprehensive analysis of a SQL query including:- Table statistics

- ✅ Execution Plan (EXPLAIN PLAN via DBMS_XPLAN)- Index statistics

- ✅ Plan details (costs, cardinality, predicates, partition info)- Index columns

- ✅ Table statistics (row counts, blocks, last analyzed date)- Partition metadata

- ✅ Index statistics (clustering factor, distinct keys, status)- Column histograms / distincts

- ✅ Index column mappings- SQL-parsed objects

- ✅ Partition metadata & keys- A ready-to-send **LLM tuning prompt**

- ✅ Column statistics (distinct values, nulls, histograms)- Structured **facts JSON**

- ✅ Constraints (PK, FK, unique)

- ✅ Optimizer parameters (mode, index cost adj, etc.)## 🚀 Run (development + hot reload)

- ✅ Segment sizes (actual disk space usage)

- ✅ Partition pruning diagnostics```bash

docker-compose up --build

#### 2. `compare_sql_plans(db_name, original_sql, improved_sql)` *(coming soon)*
Fast comparison of two SQL queries showing:
- Side-by-side execution plans
- Cost differences & improvements
- Access method changes
- Partition pruning differences

---

## ⚠️ Important: MCP Does NOT Execute Your SQL

**Safety First:**
- ✅ Only runs `EXPLAIN PLAN` (simulates execution)
- ✅ Queries metadata from system views
- ✅ **Never** executes the actual user SQL
- ✅ Safe for DELETE/UPDATE statements (won't modify data)
- ✅ Safe for long-running queries (analysis takes seconds)

---

## 🔐 Required Oracle Permissions

### Minimum Required (Core Functionality):
```sql
GRANT SELECT ON ALL_TABLES TO <your_user>;
GRANT SELECT ON ALL_INDEXES TO <your_user>;
GRANT SELECT ON ALL_IND_COLUMNS TO <your_user>;
GRANT SELECT ON ALL_TAB_COL_STATISTICS TO <your_user>;
GRANT SELECT ON ALL_CONSTRAINTS TO <your_user>;
GRANT SELECT ON ALL_CONS_COLUMNS TO <your_user>;
GRANT SELECT ON ALL_PART_TABLES TO <your_user>;
GRANT SELECT ON ALL_PART_KEY_COLUMNS TO <your_user>;

-- For EXPLAIN PLAN (usually included in CONNECT role)
GRANT SELECT ON PLAN_TABLE TO <your_user>;
-- Or ensure user can access their own PLAN_TABLE
```

### Recommended (Enhanced Features):
```sql
-- Optimizer parameters (helps explain plan choices)
GRANT SELECT ON V$PARAMETER TO <your_user>;

-- Segment sizes (shows actual disk space)
GRANT SELECT ON USER_SEGMENTS TO <your_user>;
-- OR for cross-schema analysis:
GRANT SELECT ON DBA_SEGMENTS TO <your_user>;
```

### Optional (Runtime Statistics):
```sql
-- Historical execution stats (only if analyzing already-run queries)
GRANT SELECT ON V$SQL TO <your_user>;
```

### Oracle Views Accessed by Feature:

| Feature | Oracle Views | Fallback Behavior |
|---------|-------------|-------------------|
| Execution Plan | `PLAN_TABLE` | ❌ Required |
| Table Stats | `ALL_TABLES` | ❌ Required |
| Index Stats | `ALL_INDEXES`, `ALL_IND_COLUMNS` | ❌ Required |
| Column Stats | `ALL_TAB_COL_STATISTICS` | ⚠️ Skip if unavailable |
| Constraints | `ALL_CONSTRAINTS`, `ALL_CONS_COLUMNS` | ⚠️ Skip if unavailable |
| Partitions | `ALL_PART_TABLES`, `ALL_PART_KEY_COLUMNS` | ⚠️ Skip if unavailable |
| Optimizer Params | `V$PARAMETER` | ⚠️ Skip if unavailable |
| Segment Sizes | `DBA_SEGMENTS` or `USER_SEGMENTS` | ⚠️ Calculate from blocks |
| Runtime Stats | `V$SQL` | ⚠️ Skip if unavailable |

---

## ⚙️ Configuration

Edit `server/config/settings.yaml` to:

### 1. Database Connections
```yaml
database_presets:
  my_prod_db:
    user: readonly_user
    password: secure_password
    dsn: hostname:1521/service_name
```

### 2. Analysis Features
Control what data is collected (see detailed config in `settings.yaml`):

```yaml
oracle_analysis:
  metadata:
    table_statistics:
      enabled: true  # Disable if lacking permissions
  optimizer:
    parameters:
      enabled: true
      fallback_on_error: true  # Gracefully skip if no V$ access
```

### 3. Logging Configuration
Control debug output and verbosity:

```yaml
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR
  show_tool_calls: true  # Log full tool invocations from LLM
  show_sql_queries: false  # Log actual SQL queries executed (very verbose)
```

**Log Levels:**
- **DEBUG**: Full SQL text, all queries, detailed traces
- **INFO**: Tool calls, SQL preview (200 chars), major steps (default)
- **WARNING**: Only warnings and errors
- **ERROR**: Only errors

**show_tool_calls**: When `true`, logs detailed information about each LLM tool invocation including:
  - Tool name
  - Database name
  - SQL length and preview
  - Execution timestamps

**show_sql_queries**: When `true`, enables verbose SQL query logging (metadata queries executed by the collector). Use for deep debugging only.

### 4. Analysis Modes
Quick presets for common scenarios:
- **quick**: Plan + basic stats only (fastest)
- **standard**: All metadata + optimizer params (recommended)
- **deep**: Everything enabled
- **custom**: Use individual feature flags

---

## 🚀 Run (development + hot reload)

```bash
docker-compose up --build
```

---

## 📋 Example Usage

```python
# In Claude Desktop or any MCP client
{
  "tool": "analyze_full_sql_context",
  "arguments": {
    "db_name": "transformer_master",
    "sql_text": "SELECT * FROM employees WHERE department_id = 10"
  }
}
```

**Response includes:**
- Full execution plan
- All relevant table/index statistics
- Optimizer parameters
- Structured JSON for programmatic access
- Ready-to-use prompt for LLM analysis

---

## 🛡️ Security Notes

1. **No Query Execution**: MCP never executes user SQL - only EXPLAIN PLAN
2. **Credential Management**: Database passwords stored in `settings.yaml` (consider using secrets manager in production)
3. **Read-Only**: All queries are SELECT statements on system views
4. **Preset Connections**: Users select from predefined database connections, cannot inject arbitrary connection strings

---

## 📦 Project Structure

```
server/
├── config/
│   ├── settings.yaml          # DB connections + analysis configuration
│   └── settings.template.yaml # Template for new installations
├── tools/
│   ├── oracle_analysis.py     # MCP tool definitions
│   └── oracle_collector_impl.py  # Core data collection logic
├── prompts/
│   └── analysis_prompts.py    # LLM prompt templates
├── resources/
│   └── (optional resources)
└── mcp_app.py                 # FastMCP application setup
```

---

## 🔧 Troubleshooting

### "ORA-00942: table or view does not exist"
- Check user has SELECT privileges on required views
- Verify connection credentials in `settings.yaml`

### "ORA-00918: column ambiguously defined"
- Bug in constraint query - ensure using latest version

### Missing optimizer parameters
- User needs SELECT on `V$PARAMETER` view
- Or disable via `oracle_analysis.optimizer.parameters.enabled: false`

### Slow analysis
- Try "quick" mode in settings
- Disable segment_sizes if DBA_SEGMENTS is slow
- Reduce column_statistics collection

---



### 

mcpjam prompt


You are a Oracle Database Performance Analyst.

DB: transformer_master
SQL: SELECT ID, ETL_RUN_ID FROM TRANSFORMER.DOC_ST WHERE ETL_RUN_ID > 100

1) Call mcp  analyze_full_sql_context(db_name, sql_text)
   - If facts are missing, empty, or {} → return:
     {"error": "Tool returned no data. Cannot analyze."}

2) Use only the returned “facts”.

3. Produce a SHORT, focused JSON with ONLY the following keys:

{
  "summary": "Very short description of what the query does and its expected cost.",
  
  "bottlenecks": [
    {
      "issue": "Root cause",
      "reason": "Why this hurts performance",
      "evidence": "Specific plan step or statistic",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW"
    }
  ],

  "recommendations": {
    "indexes": [
      {
        "action": "create|drop",
        "table": "OWNER.TABLE",
        "columns": ["COL1", "COL2"],
        "reason": "Why this index will help"
      }
    ],
    "query_rewrite": {
      "should_rewrite": true|false,
      "suggestion": "One-sentence improved SQL pattern"
    }
  },

  "stats_actions": [
    {
      "object": "OWNER.TABLE/COLUMN",
      "action": "gather|histogram|extended",
      "reason": "Why statistics need refresh"
    }
  ],

  "partitioning": [
    {
      "table": "OWNER.TABLE",
      "issue": "Missing pruning / scanning all partitions",
      "suggestion": "How to improve pruning"
    }
  ],

  "expected_gain": "Short estimate (e.g., 2x faster, major I/O drop)"
}

STRICT RULES:
- Output MUST be valid JSON only (no commentary, no markdown).
- Be concise. Avoid long explanations.
- Base ALL conclusions ONLY on the provided MCP facts.


## � Author
Avi Cohen
email: aviciot@gmail.com
