# Oracle Performance MCP Server 🚀

**AI-powered SQL performance analysis with historical tracking and intelligent security**

## 🎯 What It Does

This MCP server provides advanced tools to analyze Oracle SQL queries **without executing them**. It collects execution plans, statistics, and metadata to help LLMs provide expert-level performance tuning advice with:

- 🔍 **Smart SQL Validation** - Catches dangerous operations before execution
- 📊 **Historical Query Tracking** - Detects performance regressions over time
- 🎨 **Visual Execution Plans** - ASCII tree visualization with warning emojis
- 🤖 **What-If Analysis** - LLM-powered growth prediction and scaling insights
- 🔐 **Multi-Layer Security** - Prevents dangerous operations at multiple levels

### Available Tools

#### 1. `list_available_databases()`
Lists all configured database endpoints and their connection status:
- Tests connectivity to each configured database
- Returns database version and instance information
- Shows which databases are accessible

**Returns:**
```json
{
  "databases": [
    {
      "name": "transformer_master",
      "status": "connected",
      "version": "Oracle Database 19c Enterprise Edition",
      "instance": "PROD01"
    },
    {
      "name": "backup_db",
      "status": "error",
      "error": "ORA-12154: TNS:could not resolve the connect identifier"
    }
  ]
}
```

#### 2. `analyze_full_sql_context(db_name, sql_text)` ⭐ **Enhanced with New Features**
Comprehensive analysis of a SQL query including:

**Core Analysis:**
- ✅ Execution Plan (EXPLAIN PLAN via DBMS_XPLAN)
- ✅ Plan details (costs, cardinality, predicates, partition info)
- ✅ Table statistics (row counts, blocks, last analyzed date)
- ✅ Index statistics (clustering factor, distinct keys, status)
- ✅ Index column mappings
- ✅ Partition metadata & keys
- ✅ Column statistics (distinct values, nulls, histograms)
- ✅ Constraints (PK, FK, unique)
- ✅ Optimizer parameters (mode, index cost adj, etc.)
- ✅ Segment sizes (actual disk space usage)
- ✅ Partition pruning diagnostics

**🆕 New Features:**
- 🔐 **SQL Validation** - Pre-validates query syntax and detects dangerous operations (INSERT, UPDATE, DELETE, DROP, etc.)
- 📊 **Historical Tracking** - Stores query fingerprints and compares with previous executions to detect:
  - Plan changes (optimizer picking different paths)
  - Data growth (table sizes increasing)
  - Performance regressions (cost increases)
- 🎨 **Visual Execution Plan** - ASCII tree visualization with:
  - Depth-based indentation
  - Cost and cardinality display
  - Warning emojis for inefficient operations (⚠️ FULL SCAN, 🚨 CARTESIAN JOIN, ✅ INDEX SCAN)
- 📈 **Historical Context** - When query was run before, shows:
  - Number of previous executions
  - Cost comparison (stable/increased/decreased)
  - Plan change detection
  - Data growth trends

**Returns:**
```json
{
  "facts": {
    "execution_plan": "Traditional DBMS_XPLAN output",
    "plan_details": [...],
    "visual_plan": "ASCII tree with emojis",
    "historical_context": "Comparison with previous runs",
    "tables": [...],
    "indexes": [...]
  }
}
```

#### 3. `compare_query_plans(db_name, original_sql, improved_sql)` ✅ **Implemented**
Side-by-side comparison of two SQL queries showing:
- Cost differences & percentage improvement
- Access method changes (full scan → index scan)
- Cardinality estimation differences
- Plan structure comparison

**Security:** Both queries are validated before analysis to prevent dangerous operations.

---

## 🆕 What's New in This Version

### 🔐 Multi-Layer Security System
**Three levels of defense to prevent dangerous operations:**

1. **LLM Prompt Warnings** - Tool descriptions include security warnings visible to AI
2. **Tool-Level Validation** - Pre-validates SQL before expensive metadata collection
3. **Collector Validation** - Deep validation with keyword blocking before EXPLAIN PLAN

**Blocked Operations:**
- INSERT, UPDATE, DELETE, MERGE, TRUNCATE
- CREATE, DROP, ALTER (DDL operations)
- GRANT, REVOKE (permission changes)
- SELECT INTO (can create tables)
- Excessive subquery nesting (DoS prevention)
- Query length limits (100KB max)

**Validation Response:**
```json
{
  "error": "DANGEROUS OPERATION BLOCKED",
  "details": "Query contains UPDATE/DELETE/INSERT - only SELECT queries allowed",
  "is_dangerous": true
}
```

### 📊 Historical Query Tracking
**Automatic fingerprinting and performance trend detection:**

- **Query Normalization** - Converts literals to placeholders so identical queries match:
  ```sql
  WHERE id = 12345 → WHERE id = :N
  WHERE name = 'John' → WHERE name = :S
  ```
- **MD5 Fingerprinting** - Generates unique hash for each query structure
- **SQLite Storage** - Persists execution history in `server/data/query_history.db`
- **Regression Detection** - Compares current run with previous executions:
  - Plan changes (optimizer switched strategies)
  - Cost increases (performance degradation)
  - Data growth (row count changes)

**Example Historical Context:**
```
📊 Found 3 historical executions for this query...

Historical context:
✅ Performance stable - plan unchanged
📈 Data growth: 15,000 → 18,500 rows (+23%)
💡 Cost consistent: 450 → 465 (stable)
```

### 🎨 Visual Execution Plans
**ASCII tree visualization with performance warnings:**

```
SELECT STATEMENT (Cost: 465)
└─ COUNT (Cost: 465)
   └─ FILTER (Cost: 465)
      ├─ TABLE ACCESS BY INDEX ROWID: OWS.MERCHANT_STATEMENT (Cost: 450, Rows: 1,850)
      │  └─ INDEX RANGE SCAN: OWS.IDX_MS_CONTRACT ✅ (Cost: 5, Rows: 1,850)
      └─ FILTER (Cost: 5)
```

**Warning Indicators:**
- ✅ Efficient index access
- ⚠️ HIGH-COST FULL SCAN - Full table scan with high cost
- ⚠️ SKIP SCAN - Index skip scan (usually inefficient)
- ⚠️ LARGE NESTED LOOP - Nested loop with high cardinality
- ⚠️ ALL PARTITIONS - Scanning all partitions (no pruning)
- 🚨 CARTESIAN JOIN - Cartesian product detected

### 🤖 Smart MCP Prompts
**Five specialized prompts with security and intelligent caching:**

1. **`oracle_full_analysis`** - Comprehensive performance analysis with bottlenecks and recommendations
2. **`oracle_index_analysis`** - Focused index strategy and missing index detection
3. **`oracle_partition_analysis`** - Partition pruning diagnostics and optimization
4. **`oracle_rewrite_query`** - SQL rewrite suggestions for better performance
5. **`oracle_what_if_growth`** - 🆕 **Growth prediction and capacity planning**

**What-If Analysis Features:**
- Predicts performance at 2x, 5x, 10x data volumes
- Identifies O(n²) complexity issues
- Suggests preemptive optimizations
- **Smart caching** - Reuses previous analysis context to avoid redundant tool calls

**Example What-If Prompt:**
```
"What happens to this query's performance if the table grows 10x?"

Response:
- Current: 450 cost at 15K rows
- Projected: 4,500 cost at 150K rows (linear scaling)
- Recommendation: Add composite index on (contract_id, ready_date) before growth
- Complexity: O(n) - scales linearly, no major issues expected
```

---

## ⚠️ Important: MCP Does NOT Execute Your SQL

**Safety First:**
- ✅ Only runs `EXPLAIN PLAN` (simulates execution)
- ✅ Queries metadata from system views
- ✅ **Never** executes the actual user SQL
- ✅ Safe for DELETE/UPDATE statements (won't modify data)
- ✅ Safe for long-running queries (analysis takes seconds)
- 🆕 **Multi-layer validation** blocks dangerous operations before any database interaction

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

| Feature | Oracle Views | Required | Fallback Behavior |
|---------|-------------|----------|-------------------|
| **Core Analysis** |
| Execution Plan | `PLAN_TABLE` | ✅ Yes | ❌ Analysis fails without it |
| Table Stats | `ALL_TABLES` | ✅ Yes | ❌ Required for basic analysis |
| Index Stats | `ALL_INDEXES`, `ALL_IND_COLUMNS` | ✅ Yes | ❌ Required for index analysis |
| **Enhanced Features** |
| Column Stats | `ALL_TAB_COL_STATISTICS` | ⚠️ Recommended | ⚠️ Skip if unavailable |
| Constraints | `ALL_CONSTRAINTS`, `ALL_CONS_COLUMNS` | ⚠️ Recommended | ⚠️ Skip if unavailable |
| Partitions | `ALL_PART_TABLES`, `ALL_PART_KEY_COLUMNS` | ⚠️ Optional | ⚠️ Skip if unavailable |
| Optimizer Params | `V$PARAMETER` | ⚠️ Optional | ⚠️ Skip if unavailable |
| Segment Sizes | `DBA_SEGMENTS` or `USER_SEGMENTS` | ⚠️ Optional | ⚠️ Calculate from blocks |
| **Historical Tracking** |
| Query History | SQLite local file (`server/data/query_history.db`) | 🆕 Automatic | Created automatically on first run |

**Privilege Levels:**

- **Minimum (Core)**: `CONNECT` role + `SELECT` on `ALL_*` views → Basic analysis works
- **Standard (Recommended)**: Above + `V$PARAMETER` access → Enhanced analysis with optimizer insights
- **Full (Ideal)**: Above + `DBA_SEGMENTS` access → Complete analysis with actual disk usage

**Historical Tracking Requirements:**
- No additional Oracle privileges needed
- Uses local SQLite database for storage
- Automatically creates `server/data/query_history.db` on first run
- Persists across container restarts via Docker volume mount

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

### 4. Output Format Presets
Control response size and content for different use cases:

```yaml
oracle_analysis:
  output_preset: "compact"  # standard | compact | minimal
```

**Available Presets:**

| Preset | Size | Content | Best For |
|--------|------|---------|----------|
| **standard** | ~40K tokens | • Text + JSON plan<br>• All tables/indexes<br>• All stats & constraints | Human review, comprehensive reports |
| **compact** | ~20K tokens<br>**(recommended)** | • JSON plan only<br>• Only plan objects<br>• Essential stats | LLM analysis, cost optimization |
| **minimal** | ~12K tokens | • JSON plan<br>• Basic table stats only<br>• No indexes/constraints | Quick feedback, simple queries |

**What Gets Filtered:**
- **compact**: Removes text plan, filters to tables/indexes actually in execution plan
- **minimal**: Only plan + table row counts, excludes all detailed statistics

**Collection vs Output:**
- Data collection settings (metadata.table_statistics, etc.) control **what is collected** from Oracle
- Output preset controls **what is returned** to the LLM
- Use `standard` for collection + `compact` for output = collect everything, return only what's needed

### 5. Analysis Modes (deprecated - use output_preset instead)
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

### Example 1: Basic Query Analysis (First Run)

**Test Query:**
```sql
SELECT ms.contract_id, ms.ready_date 
FROM ows.merchant_statement ms
WHERE ms.contract_id = 12313
  AND ms.ready_date > SYSDATE - 30
  AND ROWNUM <= 5
```

**MCP Tool Call:**
```json
{
  "tool": "analyze_full_sql_context",
  "arguments": {
    "db_name": "way4_docker7",
    "sql_text": "SELECT ms.contract_id, ms.ready_date FROM ows.merchant_statement ms WHERE ms.contract_id = 12313 AND ms.ready_date > SYSDATE - 30 AND ROWNUM <= 5"
  }
}
```

**Expected Response (First Run):**
```json
{
  "facts": {
    "query_fingerprint": "a1722d1c...",
    "historical_executions": 0,
    "historical_context": "First execution - no historical data available",
    
    "visual_plan": "SELECT STATEMENT (Cost: 450)\n└─ COUNT (Cost: 450)\n   └─ FILTER (Cost: 450)\n      ├─ TABLE ACCESS BY INDEX ROWID: OWS.MERCHANT_STATEMENT ✅\n      │  └─ INDEX RANGE SCAN: OWS.IDX_MS_CONTRACT ✅",
    
    "plan_details": [
      {
        "step_id": 0,
        "operation": "SELECT STATEMENT",
        "cost": 450,
        "cardinality": 5
      },
      {
        "step_id": 1,
        "operation": "INDEX",
        "options": "RANGE SCAN",
        "object_name": "OWS.IDX_MS_CONTRACT",
        "cost": 5,
        "cardinality": 1850
      }
    ],
    
    "tables": [
      {
        "owner": "OWS",
        "table": "MERCHANT_STATEMENT",
        "num_rows": 15000,
        "blocks": 250,
        "last_analyzed": "2025-12-01"
      }
    ],
    
    "indexes": [
      {
        "owner": "OWS",
        "index": "IDX_MS_CONTRACT",
        "table": "MERCHANT_STATEMENT",
        "columns": ["CONTRACT_ID"],
        "uniqueness": "NONUNIQUE",
        "status": "VALID"
      }
    ]
  }
}
```

### Example 2: Second Run - Historical Comparison

**Run the exact same query again:**

**Expected Response (Second Run):**
```json
{
  "facts": {
    "query_fingerprint": "a1722d1c...",
    "historical_executions": 1,
    "historical_context": "📊 Found 1 historical execution\n✅ Performance stable - plan unchanged\n📊 Cost consistent: 450 → 450 (0% change)\n📈 Data stable: 15,000 rows (no growth)",
    
    "visual_plan": "... same as before ...",
    "plan_details": "... same as before ..."
  }
}
```

### Example 3: Query Comparison

**Compare two versions of a query:**

```json
{
  "tool": "compare_query_plans",
  "arguments": {
    "db_name": "way4_docker7",
    "original_sql": "SELECT * FROM ows.merchant_statement WHERE contract_id = 12313",
    "improved_sql": "SELECT contract_id, ready_date FROM ows.merchant_statement WHERE contract_id = 12313 AND ROWNUM <= 100"
  }
}
```

**Expected Response:**
```json
{
  "comparison": {
    "cost_difference": {
      "original_cost": 850,
      "improved_cost": 450,
      "improvement_pct": "47% faster",
      "verdict": "IMPROVED"
    },
    "access_method_changes": [
      "Original: FULL TABLE SCAN",
      "Improved: INDEX RANGE SCAN on IDX_MS_CONTRACT ✅"
    ],
    "recommendations": "Improved query uses index and limits result set with ROWNUM, reducing cost by 47%"
  }
}
```

### Example 4: Security Validation

**Attempt to run a dangerous query:**

```json
{
  "tool": "analyze_full_sql_context",
  "arguments": {
    "db_name": "way4_docker7",
    "sql_text": "DELETE FROM ows.merchant_statement WHERE contract_id = 12313"
  }
}
```

**Expected Response (Blocked):**
```json
{
  "error": "DANGEROUS OPERATION BLOCKED",
  "details": "Query contains DELETE operation - only SELECT queries allowed for analysis",
  "is_dangerous": true,
  "blocked_keywords": ["DELETE"],
  "recommendation": "Use EXPLAIN PLAN with SELECT queries only. This tool does not execute queries."
}
```

---

## 🧪 Test Prompts for MCP Inspector

### Prompt 1: Basic Analysis
```
Analyze this query on way4_docker7:

SELECT ms.contract_id, ms.ready_date 
FROM ows.merchant_statement ms
WHERE ms.contract_id = 12313
  AND ms.ready_date > SYSDATE - 30
  AND ROWNUM <= 5

Identify any performance bottlenecks and suggest improvements.
```

### Prompt 2: Historical Tracking Test
```
Run the same query twice to test historical tracking:

First run: SELECT owner, table_name, num_rows FROM all_tables WHERE owner = 'OWS' AND ROWNUM <= 3

Wait a moment, then run again to see historical comparison.
```

### Prompt 3: What-If Growth Analysis
```
Using the oracle_what_if_growth prompt, analyze:

What happens to performance if the merchant_statement table grows from 15K to 150K rows?

Use this query: SELECT * FROM ows.merchant_statement WHERE contract_id = 12313
```

### Prompt 4: Index Recommendation
```
Using oracle_index_analysis prompt:

Analyze index usage for this query and recommend any missing indexes:

SELECT ms.contract_id, ms.ready_date, ms.amount
FROM ows.merchant_statement ms
WHERE ms.ready_date BETWEEN SYSDATE - 90 AND SYSDATE
  AND ms.amount > 1000
```

### Prompt 5: Query Rewrite
```
Using oracle_rewrite_query prompt:

Suggest a better way to write this query:

SELECT * FROM ows.merchant_statement ms
WHERE ms.contract_id IN (SELECT contract_id FROM ows.contracts WHERE status = 'ACTIVE')
  AND ms.ready_date > SYSDATE - 365
```

### Prompt 6: Security Test
```
Try to analyze this query (should be blocked):

UPDATE ows.merchant_statement 
SET amount = 0 
WHERE contract_id = 12313

Expected: Security validation blocks the query with clear error message.
```

---

## 📊 Understanding the Response Structure

**Response Structure:**
```json
{
  "facts": {
    "query_fingerprint": "MD5 hash of normalized query",
    "historical_executions": "Number of times this query was run before",
    "historical_context": "Human-readable comparison with previous runs",
    "visual_plan": "ASCII tree visualization with emojis",
    "execution_plan": "Traditional DBMS_XPLAN output",
    "plan_details": [
      {
        "step_id": 0,
        "operation": "SELECT STATEMENT",
        "cost": 100,
        "cardinality": 500,
        "access_predicates": "...",
        "filter_predicates": "..."
      }
    ],
    "tables": [
      {
        "owner": "SCHEMA",
        "table": "EMPLOYEES",
        "num_rows": 10000,
        "blocks": 150,
        "last_analyzed": "2025-12-01",
        "partitioned": "NO"
      }
    ],
    "indexes": [
      {
        "owner": "SCHEMA",
        "index": "EMP_DEPT_IDX",
        "columns": ["DEPARTMENT_ID"],
        "uniqueness": "NONUNIQUE",
        "status": "VALID",
        "clustering_factor": 150
      }
    ],
    "columns": [
      {
        "owner": "SCHEMA",
        "table": "EMPLOYEES",
        "column": "DEPARTMENT_ID",
        "num_distinct": 15,
        "num_nulls": 0,
        "density": 0.067
      }
    ],
    "constraints": [...],
    "optimizer_params": {...},
    "segment_sizes": {...},
    "partition_diagnostics": {...}
  }
}
```

**Key Fields Explained:**

- 🆕 **query_fingerprint**: Unique MD5 hash for query structure (ignores literal values)
- 🆕 **historical_executions**: Number of previous runs found in history database
- 🆕 **historical_context**: Performance comparison, plan changes, data growth trends
- 🆕 **visual_plan**: ASCII tree with emojis showing execution flow
- **execution_plan**: Human-readable DBMS_XPLAN output (traditional format)
- **plan_details**: Structured array of plan steps with costs, cardinality, predicates
- **tables**: Row counts, blocks, partitioning info, last analyzed date
- **indexes**: Index stats, clustering factor, distinct keys, usage in plan
- **columns**: Cardinality, nulls, histograms for optimizer estimates
- **constraints**: Primary keys, foreign keys, unique constraints
- **optimizer_params**: Optimizer mode, index cost adjustments, parallel settings
- **segment_sizes**: Actual disk space used by tables/indexes
- **partition_diagnostics**: Partition pruning analysis (if applicable)

---

## 🛡️ Security Features

### Multi-Layer Defense System

**Layer 1: LLM Awareness**
- Tool descriptions include prominent security warnings
- LLM sees dangerous operation alerts before making tool calls
- Encourages safe query patterns in prompt design

**Layer 2: Tool-Level Validation**
- Pre-validates SQL before expensive metadata collection
- Returns clear error messages for dangerous operations
- Prevents wasted resources on invalid queries

**Layer 3: Collector Validation**
- Deep validation with comprehensive keyword blocking
- Syntax validation using Oracle's parser (ROWNUM=0 trick)
- Subquery depth limiting (prevents DoS via deeply nested queries)
- Query length limits (100KB max)

### Blocked Operations

**Data Modification (DML):**
- INSERT, UPDATE, DELETE, MERGE, TRUNCATE

**Schema Changes (DDL):**
- CREATE, DROP, ALTER, RENAME

**Permission Changes (DCL):**
- GRANT, REVOKE

**Special Cases:**
- SELECT INTO (can create tables)
- EXECUTE (stored procedure execution)
- CALL (function/procedure calls)

**DoS Prevention:**
- Maximum 10 levels of subquery nesting
- Query length limit: 100KB
- Timeout for validation queries

### Validation Response Format

```json
{
  "error": "DANGEROUS OPERATION BLOCKED",
  "details": "Query contains UPDATE operation - only SELECT queries allowed",
  "is_dangerous": true,
  "blocked_keywords": ["UPDATE"],
  "sql_preview": "UPDATE ows.merchant_statement SET...",
  "recommendation": "Use EXPLAIN PLAN with SELECT queries only"
}
```

### Prompt Input Sanitization

All MCP prompts sanitize user inputs to prevent injection attacks:

```python
# Input: query = "SELECT * FROM users WHERE name = '"; DROP TABLE users; --'"
# Sanitized: "SELECT * FROM users WHERE name = \'\\\"; DROP TABLE users; --\'"
# Validated: REJECTED (contains DROP keyword)
```

**Sanitization Steps:**
1. Escape quotes, newlines, backslashes
2. Validate query starts with SELECT/WITH
3. Check for dangerous keywords
4. Verify query length within limits

---

## 📊 Historical Tracking System

### How It Works - Visual Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER SUBMITS QUERY                           │
│  "SELECT * FROM employees WHERE dept_id = 10 AND salary > 5000"│
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 1: NORMALIZE QUERY                            │
│  • Strip semicolons: "...salary > 5000;"  →  "...salary > 5000"│
│  • Replace numbers:   dept_id = 10         →  dept_id = :N     │
│  • Replace strings:   name = 'John'        →  name = :S         │
│  • Uppercase & trim:  select * from        →  SELECT * FROM    │
│                                                                 │
│  Result: "SELECT * FROM EMPLOYEES WHERE DEPT_ID = :N AND..."   │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 2: GENERATE FINGERPRINT                       │
│  MD5 Hash of normalized SQL:                                   │
│  "SELECT * FROM EMPLOYEES WHERE DEPT_ID = :N..." → 7f3a8b2c... │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 3: QUERY SQLITE HISTORY DB                    │
│  SELECT * FROM query_history                                    │
│  WHERE query_fingerprint = '7f3a8b2c...'                        │
│  ORDER BY executed_at DESC                                      │
│  LIMIT 10                                                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        ▼                                 ▼
┌──────────────────┐            ┌──────────────────┐
│   FOUND = 0      │            │   FOUND = 1+     │
│  (First Run)     │            │  (Repeat Run)    │
└────────┬─────────┘            └────────┬─────────┘
         │                               │
         │                               ▼
         │                    ┌─────────────────────────┐
         │                    │  STEP 4: COMPARE        │
         │                    │  • Plan hash changed?   │
         │                    │  • Cost increased?      │
         │                    │  • Data growth?         │
         │                    │                         │
         │                    │  Generate comparison:   │
         │                    │  ✅ Performance stable  │
         │                    │  📊 Cost: 450 → 450     │
         │                    └────────┬────────────────┘
         │                             │
         └────────────┬────────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 5: RUN EXPLAIN PLAN                           │
│  • Collect execution plan from Oracle                           │
│  • Gather table/index statistics                               │
│  • Generate visual ASCII tree                                  │
│  • Calculate plan hash                                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 6: STORE IN SQLITE                            │
│  INSERT INTO query_history (                                    │
│    query_fingerprint = '7f3a8b2c...',                           │
│    executed_at = '2025-12-09 07:22:05',                         │
│    plan_hash = 'abc123...',                                     │
│    total_cost = 450,                                            │
│    num_tables = 1,                                              │
│    tables_summary = 'EMPLOYEES(10000 rows)'                     │
│  )                                                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 7: RETURN RESPONSE                            │
│  {                                                              │
│    "facts": {                                                   │
│      "query_fingerprint": "7f3a8b2c...",                        │
│      "historical_executions": 1,                                │
│      "historical_context": "✅ Performance stable...",          │
│      "visual_plan": "SELECT STATEMENT...",                      │
│      "plan_details": [...]                                      │
│    }                                                            │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
```

### Key Points

**Why Normalization?**
- Different literal values should match: `dept_id = 10` and `dept_id = 25` are the same query structure
- Semicolon differences ignored: `SELECT * FROM...` and `SELECT * FROM...;` are identical
- Case-insensitive: `select` and `SELECT` are the same

**What Gets Compared?**
- **Plan Hash** - Did optimizer choose a different execution path?
- **Cost** - Did estimated cost increase/decrease?
- **Table Stats** - Did table sizes grow significantly?

**Where Is Data Stored?**
- Local SQLite file: `server/data/query_history.db`
- Persists across container restarts (Docker volume mount)
- No additional Oracle privileges needed

---

### Query Normalization Examples

**Query Normalization:**
```sql
-- Original Query 1
SELECT * FROM employees WHERE department_id = 10 AND salary > 50000

-- Original Query 2  
SELECT * FROM employees WHERE department_id = 25 AND salary > 75000

-- Both normalize to:
SELECT * FROM EMPLOYEES WHERE DEPARTMENT_ID = :N AND SALARY > :N

-- Generate same fingerprint: 7f3a8b2c...
```

**Fingerprint Generation:**
1. Strip trailing semicolons
2. Replace numbers with `:N`
3. Replace strings with `:S`
4. Normalize whitespace
5. Convert to uppercase
6. Calculate MD5 hash

**Storage:**
```sql
CREATE TABLE query_history (
    id INTEGER PRIMARY KEY,
    query_fingerprint TEXT NOT NULL,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    plan_hash TEXT,
    total_cost INTEGER,
    num_tables INTEGER,
    tables_summary TEXT
);
```

**Comparison Logic:**
```python
if previous_runs:
    # Compare plan hashes
    if current_plan_hash != previous_plan_hash:
        warning = "⚠️ PLAN CHANGED - optimizer picked different strategy"
    
    # Compare costs
    cost_change = (current_cost - avg_previous_cost) / avg_previous_cost
    if cost_change > 0.2:
        warning = "🚨 REGRESSION - cost increased by 20%+"
    
    # Compare row counts
    if current_rows > previous_rows * 1.5:
        info = "📈 DATA GROWTH - table size increased significantly"
```

### Benefits

- **Regression Detection** - Catch performance degradation early
- **Plan Stability** - Track when optimizer changes strategies
- **Data Growth Monitoring** - See table size trends over time
- **Baseline Comparison** - Compare current performance to historical norms

### Persistence

- **Storage**: SQLite database at `server/data/query_history.db`
- **Docker Volume**: Mounted at `./server/data:/app/data` for persistence
- **Automatic Cleanup**: Old records can be purged (not yet implemented)
- **Migration-Free**: SQLite schema created automatically on first run

---

## 🎨 Visual Execution Plans

### Features

**ASCII Tree Structure:**
- Parent-child relationships visualized with `├─` and `└─`
- Depth-based indentation shows operation hierarchy
- Clean, readable format for quick understanding

**Performance Indicators:**
- Cost and cardinality displayed inline
- Row estimates help identify data volume issues
- Step-by-step execution flow

**Warning Emojis:**
- ✅ Efficient operations (index unique scan, low-cost range scan)
- ⚠️ Warning indicators (full scans, skip scans, large nested loops)
- 🚨 Critical issues (cartesian joins, all partition scans)

### Example

```
SELECT STATEMENT (Cost: 450)
└─ COUNT (Cost: 450)
   └─ FILTER (Cost: 450)
      ├─ TABLE ACCESS BY INDEX ROWID: OWS.MERCHANT_STATEMENT (Cost: 450, Rows: 1,850)
      │  └─ INDEX RANGE SCAN: OWS.IDX_MS_CONTRACT ✅ (Cost: 5, Rows: 1,850)
      └─ FILTER (Cost: 5)
         └─ SYSDATE (Cost: 0)
```

### Operation Warnings

| Emoji | Operation | Meaning | Threshold |
|-------|-----------|---------|-----------|
| ✅ | INDEX UNIQUE SCAN | Perfect - single row lookup | Always |
| ✅ | INDEX RANGE SCAN (low cost) | Good - efficient index access | Cost < 10 |
| ⚠️ | TABLE ACCESS FULL | Warning - full table scan | Cost > 100 |
| ⚠️ | INDEX SKIP SCAN | Warning - inefficient index usage | Always |
| ⚠️ | NESTED LOOPS | Warning - large cartesian product risk | Cardinality > 10,000 |
| ⚠️ | PARTITION ALL | Warning - not using partition pruning | Always |
| 🚨 | CARTESIAN | Critical - cartesian join detected | Always |

---

## 🔧 Project Structure

```
server/
├── config/
│   ├── settings.yaml          # DB connections + analysis configuration
│   └── settings.template.yaml # Template for new installations
├── tools/
│   ├── oracle_analysis.py          # 🆕 Enhanced with validation & history
│   ├── oracle_collector_impl.py    # 🆕 Added validate_sql() function
│   └── plan_visualizer.py          # 🆕 NEW - ASCII tree generator
├── prompts/
│   └── analysis_prompts.py         # 🆕 Enhanced with security & smart caching
├── resources/
│   └── (optional resources)
├── data/                            # 🆕 NEW - Historical storage
│   └── query_history.db            # SQLite database (auto-created)
├── history_tracker.py              # 🆕 NEW - Query fingerprinting & tracking
└── mcp_app.py                      # FastMCP application setup
```

### New Files

- **`history_tracker.py`** - Query normalization, fingerprinting, and SQLite storage
- **`tools/plan_visualizer.py`** - ASCII tree builder with emoji warnings
- **`data/query_history.db`** - SQLite database for execution history (auto-created)

### Modified Files

- **`tools/oracle_analysis.py`** - Added validation, history checks, and visual plans
- **`tools/oracle_collector_impl.py`** - Added `validate_sql()` with comprehensive security
- **`prompts/analysis_prompts.py`** - Added input sanitization and smart caching
- **`docker-compose.yml`** - Added volume mount for persistent history storage
- **`Dockerfile`** - Added data directory creation

---

## 🚀 Quick Start

### 1. Configure Database Connections

Edit `server/config/settings.yaml`:

```yaml
database_presets:
  way4_docker7:
    user: inform
    password: Term1k50
    dsn: way4_docker7:1521/transformer_master
  
  my_prod_db:
    user: readonly_user
    password: secure_password
    dsn: hostname:1521/service_name
```

### 2. Run with Docker

```bash
docker compose up --build
```

The server will:
- Start on port 8300
- Create `server/data/query_history.db` automatically
- Auto-reload on code changes (development mode)

### 3. Test with MCP Inspector

Open your MCP client and run:

```
List available databases
```

Then analyze a query:

```
Analyze this query on way4_docker7:

SELECT ms.contract_id, ms.ready_date 
FROM ows.merchant_statement ms
WHERE ms.contract_id = 12313 
  AND ROWNUM <= 5
```

### 4. Verify Historical Tracking

Run the same query twice to see historical comparison in the second response.

---

## 🧪 Testing Checklist

- [ ] **Security**: Try UPDATE/DELETE queries → Should be blocked
- [ ] **Validation**: Try invalid SQL syntax → Should return clear error
- [ ] **History (First Run)**: Run new query → Should show "0 historical executions"
- [ ] **History (Second Run)**: Run same query again → Should show "1 historical execution" with comparison
- [ ] **Visual Plan**: Check response has ASCII tree with emojis
- [ ] **MCP Prompts**: Test `oracle_what_if_growth` prompt → Should predict performance at scale
- [ ] **Compare Plans**: Use `compare_query_plans` tool → Should show cost differences

---

## 🛡️ Security Notes

1. 🆕 **Multi-Layer Validation** - Dangerous operations blocked at 3 levels
2. 🆕 **Prompt Injection Prevention** - All user inputs sanitized before prompt generation
3. **No Query Execution** - MCP never executes user SQL - only EXPLAIN PLAN
4. **Credential Management** - Database passwords stored in `settings.yaml` (consider secrets manager in production)
5. **Read-Only** - All queries are SELECT statements on system views
6. **Preset Connections** - Users select from predefined databases, cannot inject connection strings
7. 🆕 **DoS Prevention** - Query length limits, subquery depth limits, validation timeouts

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




Please analyze the SQL and give a clear, expert, human explanation covering:

1. Summary

What the query does and the main performance characteristics (cost, rows, access paths).

2. Bottlenecks

List only the important issues:

Full scans

Bad join methods

Missing/misleading stats

Missing or unused indexes

Partition pruning failures

Inefficient predicates or rewrite needs

Parallel execution issues

For each bottleneck, explain why it’s slow and show which plan step or statistic proves it.

3. Recommendations

Focus only on high-impact fixes:

A. Indexes

Which index to add/drop/modify (table + columns) and why it will help.

B. Query Rewrite

If the SQL pattern is causing a bad plan, explain:

What to change

Why

What benefit it brings

Only rewrite the full SQL if absolutely needed.

C. Statistics

Identify tables/indexes/columns with stale/missing stats and give the exact DBMS_STATS command to fix it.

D. Partitioning

Say whether partition pruning should work, whether it fails, and what to change.

4. Performance Insights

Summarize the main cost drivers:

Estimated rows scanned

Heavy operations

Join method observations

Whether parallelism helps or harms

5. Expected Improvement

Give a realistic estimate of expected performance gain for the recommended actions.

6. Priority List

Give a simple list of actions:

Highest impact

Medium

Nice-to-have

Include effort (low/medium/high) and expected impact.

Important Instructions

No JSON

Base everything strictly on the provided plan/stats

Focus on big-impact issues only (no micro-optimizations)



## � Author
Avi Cohen
email: aviciot@gmail.com
