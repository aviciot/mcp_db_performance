# Oracle & MySQL Performance MCP Server 🚀

**AI-powered SQL performance analysis with historical tracking, multi-layer security, authentication, and multi-database support**

---

## 🎯 What It Does

This MCP server performs **deep SQL performance analysis without executing queries**, supporting both **Oracle** and **MySQL**, with more databases coming soon.

**Key Features:**
- 🔍 **Smart SQL Validation** - Blocks dangerous operations before execution
- 📊 **Historical Query Tracking** - Detects performance regressions over time
- 🎨 **Visual Execution Plans** - ASCII tree diagrams with warning emojis
- 🤖 **What-If Growth Simulation** - Predicts performance at scale
- 🔐 **Multi-Layer Security** - 3-layer defense against dangerous SQL
- 🔑 **Optional API Authentication** - Bearer token authentication for secure deployments
- 📈 **Real-Time Performance Monitoring** - Database health, top queries, and trends
- 🐬 **Native MySQL 8.0+ Analysis** - Full MySQL support with performance_schema

Future database engines (PostgreSQL, Snowflake, SQL Server) can be added easily with the modular architecture.

---

## 🗄️ Supported Databases

### Oracle Database
- **Versions**: 11g, 12c, 18c, 19c, 21c
- **Features**: DBMS_XPLAN plan parsing, partition diagnostics, what-if analysis, historical plan comparison, ASCII visual plans

### MySQL
- **Versions**: 5.7+, 8.0+ (recommended)
- **Features**: EXPLAIN FORMAT=JSON, performance_schema index usage, duplicate index detection, historical tracking

---

## 🤖 How the LLM Chooses the Right Tool

The LLM automatically selects the correct analysis tool based on:

1. **Tool Description Tags** - Each tool clearly states `[ORACLE ONLY]` or `[MYSQL ONLY]`
2. **Database Naming Conventions**:
   - Oracle: `transformer_master`, `way4_docker7`
   - MySQL: `mysql_devdb03_avi`, `mysql_production`
3. **User Context** - Phrases like "Analyze this MySQL query" guide tool selection
4. **Error Handling** - Clear error messages redirect to the correct tool if needed

---

## 🛠️ Available Tools

### SQL Analysis Tools

### 1. `list_available_databases()`

Lists all configured database endpoints with connection status and version information.

**Returns:**
- Database names
- Connection status (connected/error)
- Database version
- Instance information

---

### 2. `analyze_full_sql_context(db_name, sql_text)`

**Unified Oracle + MySQL analysis API**

#### Core Analysis
- ✅ Execution plan (Oracle DBMS_XPLAN / MySQL EXPLAIN JSON)
- ✅ Plan steps, costs, cardinality
- ✅ Table metadata (row counts, sizes, last analyzed)
- ✅ Index metadata (columns, cardinality, status)
- ✅ Column statistics (distinct values, nulls, histograms)
- ✅ Segment sizes (actual disk space)
- ✅ Partition diagnostics (pruning detection)
- ✅ Optimizer parameters
- ✅ Constraints (PK, FK, unique)

#### Enhanced Features
- 🔐 **SQL Validation** - Blocks INSERT, UPDATE, DELETE, DROP, etc.
- 📊 **Historical Tracking** - MD5 fingerprinting with SQLite storage
- 🎨 **Visual Execution Plan** - ASCII tree with emoji warnings
- 📈 **Data Growth Trends** - Detects table size changes over time
- ⚠️ **Plan Regression Detection** - Alerts when optimizer changes strategies

---

### 3. `compare_query_plans(db_name, original_sql, improved_sql)`

Side-by-side execution plan comparison for both Oracle and MySQL.

**Shows:**
- Cost differences & percentage improvement
- Access method changes (full scan → index scan)
- Cardinality estimation differences
- Plan structure comparison

---

### Diagnostic Tools

### 4. `check_oracle_access(db_name)`

**[ORACLE ONLY]** Check Oracle user permissions and data dictionary access.

**Checks:**
- ALL_TABLES, ALL_INDEXES, ALL_IND_COLUMNS (critical)
- ALL_CONSTRAINTS, ALL_TAB_COLUMNS (important)
- ALL_TAB_PARTITIONS (helpful)
- DBA_SEGMENTS (storage analysis - requires DBA role)
- V$PARAMETER (optimizer settings)
- EXPLAIN PLAN capability (PLAN_TABLE)

**Returns:**
- Access report (✓ accessible / ✗ blocked with error)
- Impact score (0-10)
- Impact level (HIGH/MEDIUM/LOW)
- Analysis capability breakdown
- Specific recommendations for missing permissions

**Example:**
```
check_oracle_access("transformer_master")
```

---

### 5. `check_mysql_access(db_name)`

**[MYSQL ONLY]** Check MySQL user permissions and schema access.

**Checks:**
- information_schema.TABLES (critical)
- information_schema.STATISTICS (critical)
- information_schema.COLUMNS (helpful)
- performance_schema.table_io_waits_summary_by_index_usage (important)
- EXPLAIN capability

**Returns:**
- Access report (✓ accessible / ✗ blocked with error)
- Impact score (0-10)
- Impact level (HIGH/MEDIUM/LOW)
- Analysis capability breakdown
- Specific recommendations for missing permissions

**Example:**
```
check_mysql_access("mysql_devdb03_avi")
```

---

### Performance Monitoring Tools (Oracle)

### 6. `get_database_health(db_name, time_range_minutes)`

Real-time Oracle database health monitoring.

**Returns:**
- Overall health score (0-100)
- System metrics: CPU usage, active sessions, memory
- Cache hit ratios (buffer cache, library cache, dictionary cache)
- Top wait events with time spent
- Health status: HEALTHY / WARNING / CRITICAL

**Example:**
```
get_database_health("transformer_master", 5)
```

---

### 7. `get_top_queries(db_name, metric, top_n, time_range_hours, exclude_sys, schema_filter, module_filter)`

Retrieve top queries by performance metric.

**Metrics:**
- `cpu_time` - Highest CPU consumers
- `elapsed_time` - Longest running queries
- `buffer_gets` - Most logical reads
- `executions` - Most frequently executed

**Filtering:**
- `exclude_sys=true` - Filter out system/internal queries (default)
- `schema_filter` - Limit to specific schema (e.g., "OWS")
- `module_filter` - Filter by application module

**Returns:**
- SQL text with query patterns
- Execution statistics
- Resource usage (CPU, buffer gets, disk reads)
- First/last seen timestamps

---

### 8. `get_performance_trends(db_name, metric, hours_back, interval_minutes)`

Historical performance trends with JSON chart data.

**Metrics:**
- `cpu_usage` - CPU percentage over time
- `active_sessions` - Session count trends
- `wait_events` - Wait event patterns
- `cache_hit_ratio` - Buffer cache efficiency

**Returns:**
- Time-series data points
- JSON chart data (Chart.js compatible)
- Trend analysis (increasing/decreasing/stable)
- Anomaly detection

**Example:**
```
get_performance_trends("way4_docker7", "cpu_usage", 24, 60)
```

---

## 🐬 MySQL-Specific Tools

### `analyze_mysql_query(db_name, sql_text)`

Comprehensive MySQL query performance analysis:
- ✅ EXPLAIN FORMAT=JSON parsing
- ✅ Table + index metadata from information_schema
- ✅ Index usage statistics from performance_schema
- ✅ Duplicate index detection
- ✅ Historical query tracking (shared with Oracle)

### `compare_mysql_query_plans(db_name, original_sql, optimized_sql)`

MySQL-specific plan comparison:
- Cost differences
- Access method improvements
- Row estimate reductions
- Index usage comparison

---

## 🔐 Oracle Analysis - Permissions & Data Collection

### Required Oracle Permissions

**Minimum Permissions (All features work):**
```sql
-- Standard Oracle user with:
GRANT CONNECT TO your_user;
GRANT SELECT ANY TABLE TO your_user;  -- Or explicit grants on target schemas

-- Required for metadata collection:
GRANT SELECT ON ALL_TABLES TO your_user;
GRANT SELECT ON ALL_INDEXES TO your_user;
GRANT SELECT ON ALL_IND_COLUMNS TO your_user;
GRANT SELECT ON ALL_TAB_COLUMNS TO your_user;
GRANT SELECT ON ALL_TAB_COL_STATISTICS TO your_user;
GRANT SELECT ON ALL_CONSTRAINTS TO your_user;
GRANT SELECT ON ALL_CONS_COLUMNS TO your_user;
GRANT SELECT ON ALL_PART_TABLES TO your_user;
GRANT SELECT ON ALL_PART_KEY_COLUMNS TO your_user;
GRANT SELECT ON ALL_TAB_COMMENTS TO your_user;
GRANT SELECT ON ALL_COL_COMMENTS TO your_user;

-- For PLAN_TABLE (usually exists, or create with @?/rdbms/admin/utlxplan.sql):
GRANT INSERT, DELETE ON PLAN_TABLE TO your_user;
```

**Enhanced Permissions (Recommended):**
```sql
-- For optimizer parameters (performance insights):
GRANT SELECT ON V$PARAMETER TO your_user;  
-- Or: GRANT SELECT_CATALOG_ROLE TO your_user;

-- For disk space analysis (segment sizes):
GRANT SELECT ON DBA_SEGMENTS TO your_user;  
-- Falls back to USER_SEGMENTS if not granted
```

**Permissions Test:**
```sql
-- Test access to required views
SELECT COUNT(*) FROM ALL_TABLES WHERE ROWNUM = 1;
SELECT COUNT(*) FROM ALL_INDEXES WHERE ROWNUM = 1;
SELECT COUNT(*) FROM V$PARAMETER WHERE ROWNUM = 1;  -- Optional
SELECT COUNT(*) FROM DBA_SEGMENTS WHERE ROWNUM = 1;  -- Optional
```

---

### Data Collection Overview

**What We Collect & Why It Matters:**

| Data Type | Source | Severity | Why Important | Performance Impact |
|-----------|--------|----------|---------------|-------------------|
| **Execution Plan** | PLAN_TABLE, DBMS_XPLAN | 🔴 CRITICAL | Shows optimizer's strategy, identifies full scans, join methods, costs | High - this is the foundation |
| **Plan Details** | PLAN_TABLE | 🔴 CRITICAL | Structured plan steps with IDs, costs, cardinality for detailed analysis | High - enables diagnostics |
| **Table Statistics** | ALL_TABLES | 🔴 CRITICAL | Row counts, blocks, last analyzed date - optimizer uses these for cost calculations | Medium - affects all queries |
| **Index Statistics** | ALL_INDEXES | 🟡 HIGH | B-tree levels, clustering factor, distinct keys - determines index efficiency | Medium - key for recommendations |
| **Index Columns** | ALL_IND_COLUMNS | 🟡 HIGH | Which columns each index covers - identifies missing/redundant indexes | Low - small dataset |
| **Column Statistics** | ALL_TAB_COL_STATISTICS | 🟡 HIGH | Distinct values, nulls, histograms - explains cardinality estimates | Medium - can be large |
| **Constraints** | ALL_CONSTRAINTS, ALL_CONS_COLUMNS | 🟢 MEDIUM | Primary keys, foreign keys, unique constraints - shows data relationships | Low - small dataset |
| **Partition Info** | ALL_PART_TABLES, ALL_PART_KEY_COLUMNS | 🟢 MEDIUM | Partitioning strategy and keys - detects pruning failures | Low - only for partitioned tables |
| **Optimizer Parameters** | V$PARAMETER | 🔵 LOW | Optimizer mode, cost adjustments - explains unexpected plans | Low - ~20 rows |
| **Segment Sizes** | DBA_SEGMENTS / USER_SEGMENTS | 🔵 LOW | Actual disk space in MB/GB - provides physical storage context | Medium - can be slow on large DBs |
| **Table Comments** | ALL_TAB_COMMENTS | 🔵 LOW | Business descriptions - used by explain_business_logic tool | Low - small dataset |
| **Column Comments** | ALL_COL_COMMENTS | 🔵 LOW | Column meanings - semantic analysis | Medium - can be many rows |

**Severity Legend:**
- 🔴 **CRITICAL**: Analysis will fail or be meaningless without this data
- 🟡 **HIGH**: Analysis works but recommendations will be limited
- 🟢 **MEDIUM**: Nice-to-have, adds depth to analysis
- 🔵 **LOW**: Optional, provides additional context

---

### Output Filtering Configuration

Control how much data is returned using the `output_preset` setting in `server/config.py`:

**Option 1: `standard` (Default - Full Data)**
```python
OUTPUT_PRESET = "standard"  # Returns everything
```

**Returns:**
- All execution plan steps
- All table/index statistics
- All column statistics  
- All constraints
- All optimizer parameters
- All segment sizes
- All partition diagnostics
- Historical context

**Use when:** You need complete analysis for deep optimization, or working with small queries (1-5 tables)

---

**Option 2: `compact` (Filtered - Plan Objects Only)**
```python
OUTPUT_PRESET = "compact"  # Returns only data for tables/indexes in execution plan
```

**Returns:**
- Execution plan (structured plan_details only, no text)
- Table/index stats for objects in plan only
- Column stats (all - needed for cardinality)
- Constraints (all - needed for relationships)
- Optimizer parameters (all - small dataset)
- Segment sizes for plan objects only
- Partition diagnostics

**Filters out:**
- Execution plan text (saves ~10KB per query)
- Tables not in execution plan
- Indexes not referenced in plan

**Use when:** Query joins 10+ tables but plan only uses 3-4 (common in star schemas)

---

**Option 3: `minimal` (Essentials Only)**
```python
OUTPUT_PRESET = "minimal"  # Bare minimum for analysis
```

**Returns:**
- Structured plan details
- Basic table stats (owner, name, num_rows, blocks only)
- Summary counts

**Filters out:**
- Execution plan text
- Index statistics
- Column statistics
- Constraints
- Optimizer parameters
- Segment sizes
- Partition info

**Use when:** You only need high-level cost/cardinality analysis, or handling 20+ table queries

---

**Performance Comparison:**

| Preset | Typical Response Size | LLM Context Tokens | Best For |
|--------|----------------------|-------------------|----------|
| **standard** | 50-150 KB | 15,000-40,000 | Deep analysis, optimization projects |
| **compact** | 20-60 KB | 6,000-18,000 | Production queries, routine analysis |
| **minimal** | 5-15 KB | 1,500-4,500 | Quick checks, very large queries |

**Configuration:**
Edit `server/config.py`:
```python
class Config:
    output_preset: str = "compact"  # Change to "standard" or "minimal"
```

---

#### 🧠 **How Output Preset Affects LLM Analysis**

The `output_preset` configuration directly impacts the quality and depth of analysis the LLM can provide:

**`standard` Preset (Maximum Analysis Quality):**
- ✅ **Full Index Recommendations**: LLM can suggest new indexes because it sees all index statistics
- ✅ **Detailed Constraint Analysis**: Can identify missing foreign keys or constraint issues
- ✅ **Physical Storage Insights**: Can recommend partition strategies based on segment sizes
- ✅ **Execution Plan Text**: Visual plan tree helps LLM understand operation hierarchy
- ⚠️ **Trade-off**: Requires 15K-40K tokens - may hit context limits on complex queries

**`compact` Preset (Balanced Recommendations):**
- ✅ **Focused Index Recommendations**: Can suggest indexes for objects in execution plan only
- ✅ **Constraint Analysis**: Full constraint data preserved for relationship understanding
- ✅ **Cost/Cardinality Analysis**: Structured plan_details sufficient for join order analysis
- ⚠️ **Limited**: Cannot recommend indexes for unused tables, cannot analyze storage issues
- ⚠️ **No Visual Plan**: Missing execution plan text may reduce plan comprehension

**`minimal` Preset (Limited Recommendations):**
- ✅ **Join Order Analysis**: Can still analyze cardinality and cost estimates
- ✅ **High-Level Optimization**: Can identify expensive operations and table access patterns
- ⚠️ **No Index Recommendations**: Missing index statistics prevent index creation suggestions
- ⚠️ **No Constraint Analysis**: Cannot identify relationship issues or missing foreign keys
- ⚠️ **No Storage Analysis**: Cannot recommend partitioning or storage optimizations

**Recommendation Guidance:**

| Use Case | Recommended Preset | Rationale |
|----------|-------------------|-----------|
| **Production Query Optimization** | `compact` | Balanced - good recommendations without excessive token usage |
| **New Feature Development** | `standard` | Need comprehensive analysis including unused table optimization |
| **Quick Troubleshooting** | `compact` | Faster response, adequate for identifying immediate issues |
| **Very Large Queries (20+ tables)** | `minimal` → upgrade to `compact` if needed | Start minimal to avoid token limits, upgrade if analysis insufficient |
| **Index Tuning Projects** | `standard` | Must see all index statistics for comprehensive recommendations |
| **Storage Planning** | `standard` | Need segment sizes and partition info for storage decisions |

**💡 Pro Tip:** If LLM responds with "I need more data to make recommendations", it's a signal to increase the preset level for that specific query.

---

### New Diagnostic Features ⭐

**What's New in This Version:**

#### 1. **Query Intent Classification**
Automatically detects query type and purpose:
```json
{
  "query_intent": {
    "type": "aggregation_report",
    "patterns": ["GROUP BY aggregation", "date range filter"],
    "typical_use": "Aggregated reporting or analytics",
    "complexity": "moderate"
  }
}
```

**Detected Patterns:**
- `aggregation_report` - GROUP BY queries
- `pagination_query` - ROWNUM/FETCH FIRST
- `top_n_query` - ORDER BY + ROWNUM
- `reconciliation_query` - Multiple LEFT JOINs with NULL checks
- `multi_source_query` - UNION/UNION ALL
- `complex_join_query` - 4+ table joins
- `count_query` - Simple COUNT(*) queries
- `full_data_export` - SELECT * queries

---

#### 2. **Performance Issue Diagnosis**
Natural language explanations of performance problems:
```json
{
  "performance_issues": [
    {
      "severity": "CRITICAL",
      "issue": "Full table scan on GTW_ODS.GATEWAY_TRANSACTIONS",
      "rows_scanned": 45000000,
      "cost": 8234,
      "why": "Oracle is reading all 45,000,000 rows instead of using an index",
      "causes": [
        "3 index(es) exist but not being used",
        "Possible reasons: data type mismatch, function on column, OR conditions"
      ],
      "fix": "CREATE INDEX idx_gateway_transactions_date ON GTW_ODS.GATEWAY_TRANSACTIONS(transaction_date)",
      "estimated_improvement": "Potential 90-99% reduction in execution time"
    }
  ]
}
```

**Severity Levels:**
- `CRITICAL` - Full scan on 10M+ rows
- `HIGH` - Full scan on 1M-10M rows  
- `MEDIUM` - Full scan on 100K-1M rows
- `LOW` - Full scan on <100K rows

---

#### 3. **Cartesian Product Detection**
Identifies accidental cross joins:
```json
{
  "cartesian_warnings": [
    {
      "severity": "CRITICAL",
      "issue": "Potential Cartesian product (cross join)",
      "operation": "NESTED LOOPS",
      "cardinality": 5000000,
      "why": "NESTED LOOPS operation with very high cardinality and no join predicate",
      "impact": "Produces 5,000,000 rows (likely unintended)",
      "fix": "Add join condition between tables (e.g., AND t1.id = t2.id)"
    }
  ]
}
```

**Detects:**
- NESTED LOOPS with high cardinality and no predicates
- Explicit MERGE JOIN CARTESIAN operations
- Missing join conditions causing exponential row growth

---

#### 4. **Anomaly Detection**
Flags unusual data patterns:
```json
{
  "anomalies": [
    {
      "severity": "MEDIUM",
      "type": "missing_statistics",
      "table": "GTW_ODS.PAYMENT_METHODS",
      "issue": "Table has no statistics or zero rows",
      "impact": "Optimizer cannot make informed decisions - may choose inefficient plan",
      "fix": "EXEC DBMS_STATS.GATHER_TABLE_STATS('GTW_ODS', 'PAYMENT_METHODS')"
    }
  ]
}
```

**Detects:**
- Missing or stale statistics
- Extreme cardinality mismatches (estimated vs actual)
- Tables with zero rows (possible data issues)

---

#### 5. **Smart Prompts**
The tool now provides contextual hints:
- Warns about critical performance issues
- Suggests using `explain_business_logic` for business context
- Highlights historical regressions
- Points out Cartesian products immediately

**Example Prompt:**
```
🚨 CRITICAL: 2 critical performance issue(s) detected! 
Review facts['performance_issues'] for detailed diagnostics with fix recommendations.

💡 TIP: To understand the BUSINESS PURPOSE of this query (what it does, not just performance), 
use the 'explain_business_logic' tool. It will analyze table relationships, 
infer business domains, and explain the query in plain English. 
Cached lookups make it very fast (~700ms).
```

---

###  7. `explain_business_logic(db_name, sql_text, follow_relationships, max_depth)` ⭐ NEW

**AI-Powered Business Logic Explanation with PostgreSQL Caching**

Understands the business purpose behind your SQL queries by analyzing table relationships, column semantics, and data patterns. Perfect for onboarding new team members or documenting complex queries.

**What It Does:**
- 📊 **Extracts all tables** from your SQL query
- 🔗 **Follows foreign key relationships** up to N levels deep (default: 2)
- 🧠 **Infers business meaning** from table/column names and comments
- 🎨 **Generates Mermaid ER diagrams** showing relationships
- 💾 **Caches metadata in PostgreSQL** for 14x faster subsequent queries
- 🔍 **Filters out system tables** (V$, DBA_, ALL_, SYS schema)

**Parameters:**
- `db_name` (required) - Oracle database name
- `sql_text` (required) - SQL query to analyze
- `follow_relationships` (optional, default: true) - Follow FK relationships
- `max_depth` (optional, default: 2) - Relationship depth to traverse

**Returns:**
```json
{
  "tables": [
    {
      "schema": "GTW_ODS",
      "name": "GATEWAY_TRANSACTIONS",
      "row_count": 45000000,
      "comment": "Credit card transaction processing",
      "table_type": "business",
      "inferred_entity": "Transaction",
      "inferred_domain": "Payment Processing",
      "columns": [
        {
          "name": "PAYMENT_ID",
          "type": "VARCHAR2(50)",
          "comment": "Unique payment identifier",
          "nullable": false
        }
      ],
      "primary_key": ["PAYMENT_ID"]
    }
  ],
  "relationships": [
    {
      "from": "GTW_TRANS_RETRY",
      "to": "GATEWAY_TRANSACTIONS",
      "columns": ["PAYMENT_ID"],
      "type": "FK"
    }
  ],
  "graph": {
    "mermaid": "erDiagram\n  GATEWAY_TRANSACTIONS ||--o{ GTW_TRANS_RETRY : retries\n"
  },
  "stats": {
    "cache_hits": 4,
    "cache_misses": 0,
    "duration_ms": 742
  }
}
```

**Usage Examples:**

**Example 1: Simple Query Analysis**
```
User: "Explain the business logic of this query:
SELECT * FROM customer_orders WHERE order_date > '2024-01-01'"

Result:
- Analyzes CUSTOMER_ORDERS table
- Identifies it as a transaction table
- Shows it relates to CUSTOMERS (FK: customer_id)
- Shows it relates to ORDER_ITEMS (FK: order_id)
- Infers domain: "Order Management"
- Generates ER diagram with relationships
```

**Example 2: Complex Join with Relationships**
```
User: "What does this query do?
SELECT t.*, r.retry_count, c.challenge_status
FROM gateway_transactions t
LEFT JOIN gtw_trans_retry r ON t.payment_id = r.payment_id
LEFT JOIN gtw_trans_3ds_challenge c ON t.payment_id = c.payment_id
WHERE t.processing_date = '2024-01-01'"

Result:
- Main table: GATEWAY_TRANSACTIONS (45M rows, "Transaction" entity)
- Related: GTW_TRANS_RETRY (retry tracking, lookup table)
- Related: GTW_TRANS_3DS_CHALLENGE (3DS authentication, operational table)
- Business purpose: "Payment transaction processing with retry logic and 3DS authentication"
- Performance: 742ms (all from cache on 2nd run)
```

**Example 3: Deep Relationship Discovery**
```
User: "Analyze this query and show me all related tables:
SELECT * FROM orders WHERE customer_id = 12345"

With follow_relationships=true, max_depth=2:
- Level 0: ORDERS table
- Level 1: CUSTOMERS, ORDER_ITEMS, SHIPMENTS (direct FKs)
- Level 2: ADDRESSES, PRODUCTS, SHIPPING_CARRIERS (related to level 1)
- Generates complete ER diagram
```

**Performance:**
- **First run**: ~10-12 seconds (collects from Oracle + caches)
- **Second run**: ~0.7 seconds (reads from PostgreSQL cache)
- **Cache TTL**: 7 days (configurable)
- **93% faster** with caching enabled

**Cache Management:**
- Automatic caching to PostgreSQL (omni database)
- Timestamps track freshness
- Admin can override with custom documentation
- Cache invalidates after 7 days

**What Gets Cached:**
- Table metadata (name, row count, comments)
- Column details (names, types, comments, nullability)
- Primary keys
- Foreign key relationships
- Inferred business semantics
- Domain classifications

**System Table Filtering:**
Automatically excludes:
- Oracle system views: `V$%`, `DBA_%`, `ALL_%`, `USER_%`
- System schema: `SYS`, `SYSTEM`, `DBSNMP`
- Audit/log tables: `%_LOG`, `%_HIST`, `%_AUDIT`
- Temporary tables: `%_TEMP`, `%_TMP`
- CTEs and inline views

---

#### 🔧 How It Works - Technical Details

**1. SQL Parsing & Table Extraction**
```python
# Extracts table references from SQL
SELECT t.*, r.retry_count FROM gateway_transactions t JOIN gtw_trans_retry r
                                ↓
["GATEWAY_TRANSACTIONS", "GTW_TRANS_RETRY"]
```

**2. Schema Resolution**
- Queries `ALL_TABLES` to find actual schema for each table
- Handles unqualified table names using default schema (current user)
- Resolves aliases and CTEs

**3. Metadata Collection (Oracle Queries)**
```sql
-- Table metadata
SELECT table_name, num_rows, comments 
FROM ALL_TABLES, ALL_TAB_COMMENTS
WHERE owner = :schema AND table_name = :table

-- Column metadata
SELECT column_name, data_type, nullable, comments
FROM ALL_TAB_COLUMNS, ALL_COL_COMMENTS
WHERE owner = :schema AND table_name = :table
ORDER BY column_id

-- Primary Keys
SELECT cols.column_name
FROM ALL_CONSTRAINTS cons
JOIN ALL_CONS_COLUMNS cols 
  ON cons.constraint_name = cols.constraint_name
WHERE cons.constraint_type = 'P'
  AND cons.owner = :schema
  AND cons.table_name = :table

-- Foreign Key Relationships
SELECT 
  a.table_name as from_table,
  a.column_name as from_column,
  c_pk.table_name as to_table,
  b.column_name as to_column,
  a.constraint_name
FROM ALL_CONS_COLUMNS a
JOIN ALL_CONSTRAINTS c ON a.constraint_name = c.constraint_name
JOIN ALL_CONSTRAINTS c_pk ON c.r_constraint_name = c_pk.constraint_name
JOIN ALL_CONS_COLUMNS b ON c_pk.constraint_name = b.constraint_name
WHERE c.constraint_type = 'R'
  AND c.owner = :schema
  AND c.table_name = :table
```

**4. Relationship Traversal**
```
Level 0: Query tables [A, B]
Level 1: Find all FKs from A and B → discovers [C, D]
Level 2: Find all FKs from C and D → discovers [E, F]
Max depth = 2: Stop here
```

**5. Business Semantics Inference**
```python
# Entity type classification
if "transaction" in table_name.lower(): entity = "Transaction"
if "_id" in column_name.lower(): entity = infer_from_id_column()

# Domain inference
keywords = {
  "payment|transaction|gateway": "Payment Processing",
  "customer|order|cart": "Order Management",
  "user|account|auth": "User Management"
}

# Table type classification
if row_count < 1000 and has_foreign_keys: type = "lookup"
if row_count > 1M and has_timestamps: type = "business"
if "LOG" in name or "AUDIT" in name: type = "audit"
```

**6. PostgreSQL Caching**
```sql
-- Cache storage schema
table_knowledge (
  id SERIAL PRIMARY KEY,
  db_name VARCHAR(100),
  owner VARCHAR(100),
  table_name VARCHAR(100),
  oracle_comment TEXT,
  num_rows BIGINT,
  columns JSONB,
  primary_key_columns TEXT[],
  inferred_entity_type VARCHAR(100),
  inferred_domain VARCHAR(100),
  last_refreshed TIMESTAMP DEFAULT NOW(),
  UNIQUE(db_name, owner, table_name)
)

relationship_knowledge (
  id SERIAL PRIMARY KEY,
  db_name VARCHAR(100),
  from_schema VARCHAR(100),
  from_table VARCHAR(100),
  from_columns TEXT[],
  to_schema VARCHAR(100),
  to_table VARCHAR(100),
  to_columns TEXT[],
  constraint_name VARCHAR(200),
  relationship_type VARCHAR(10),
  last_refreshed TIMESTAMP DEFAULT NOW()
)
```

**7. Cache Lookup Flow**
```
1. Generate cache key: (db_name, schema, table_name)
2. Query PostgreSQL: SELECT * FROM table_knowledge WHERE db_name = ? AND owner = ? AND table_name = ?
3. Check freshness: last_refreshed > NOW() - INTERVAL '7 days'
4. If fresh: Return cached data
5. If stale/missing: Query Oracle + Update cache
```

---

#### ⚙️ Configuration

**PostgreSQL Connection** (Required for caching)

Add to `.env` file:
```bash
KNOWLEDGE_DB_HOST=host.docker.internal
KNOWLEDGE_DB_PORT=5433
KNOWLEDGE_DB_NAME=omni
KNOWLEDGE_DB_USER=postgres
KNOWLEDGE_DB_PASSWORD=postgres
```

Add to `docker-compose.yml`:
```yaml
services:
  oracle_performance_mcp:
    environment:
      KNOWLEDGE_DB_HOST: ${KNOWLEDGE_DB_HOST:-host.docker.internal}
      KNOWLEDGE_DB_PORT: ${KNOWLEDGE_DB_PORT:-5433}
      KNOWLEDGE_DB_NAME: ${KNOWLEDGE_DB_NAME:-omni}
      KNOWLEDGE_DB_USER: ${KNOWLEDGE_DB_USER:-postgres}
      KNOWLEDGE_DB_PASSWORD: ${KNOWLEDGE_DB_PASSWORD:-postgres}
```

**Database Schema Setup** (One-time)

Run the migration to create PostgreSQL tables:
```bash
# From omni2 directory (where PostgreSQL runs)
cd omni2
docker-compose exec -T postgres psql -U postgres -d omni < ../server/migrations/001_knowledge_base.sql
```

This creates 6 tables:
- `table_knowledge` - Table metadata cache
- `relationship_knowledge` - Foreign key relationships
- `query_explanation_cache` - Full query analysis cache
- `domain_glossary` - Business term definitions
- `user_table_documentation` - Admin-provided docs
- `knowledge_refresh_log` - Cache refresh history

**Cache TTL Settings** (Optional)

Default TTL values in `server/knowledge_db.py`:
```python
TABLE_CACHE_TTL_DAYS = 7        # Table metadata freshness
RELATIONSHIP_CACHE_TTL_DAYS = 7  # FK relationships freshness
QUERY_CACHE_TTL_DAYS = 30        # Full query analysis freshness
```

---

#### 📊 Storage Architecture

**Storage Flow:**
```
Oracle DB (Source)
    ↓ First Query
    ↓ Metadata Collection
    ↓
PostgreSQL (Cache)
    ↓ 7-day TTL
    ↓ Subsequent Queries
    ↓
MCP Response (JSON)
```

**Database Separation:**
- **Oracle**: Source of truth for table/column metadata
- **PostgreSQL**: Fast cache layer (shared with omni2 project)
- **SQLite**: Query history tracking (separate concern)

**Why PostgreSQL for Cache?**
- ✅ JSONB support for flexible column storage
- ✅ Array types for multi-column keys
- ✅ Timestamp precision for TTL management
- ✅ Shared infrastructure with omni2 project
- ✅ No impact on Oracle performance

**Cache Size Estimates:**
- Table metadata: ~5KB per table
- Relationships: ~500 bytes per FK
- 100 tables with 20 relationships: ~520KB total
- Negligible storage footprint

---

#### 📝 TODO - Future Enhancements

**High Priority:**
- [ ] Add MySQL support for business logic analysis
- [ ] Implement cache warming on server startup (pre-populate frequently used tables)
- [ ] Add cache invalidation endpoint for admins
- [ ] Improve entity inference with ML-based classification
- [ ] Add support for views and materialized views

**Medium Priority:**
- [ ] Generate natural language summaries using LLM
- [ ] Support composite foreign keys (currently simple FK only)
- [ ] Add confidence scores to inferred semantics
- [ ] Create admin UI for managing table documentation overrides
- [ ] Add query pattern recognition (e.g., "This is a pagination query")
- [ ] Support for detecting anti-patterns (N+1 queries, Cartesian joins)

**Low Priority:**
- [ ] Export ER diagrams to PNG/SVG
- [ ] Add support for dbdocs.io schema documentation
- [ ] Integrate with data lineage tools
- [ ] Support for Oracle synonyms and database links
- [ ] Add business glossary auto-population from table comments
- [ ] Generate sample queries based on relationships

**Performance Improvements:**
- [ ] Batch cache lookups (query multiple tables in one DB round-trip)
- [ ] Add Redis layer for sub-100ms response times
- [ ] Implement partial cache updates (only refresh changed columns)
- [ ] Add cache warming scheduler (background job)

**Security & Compliance:**
- [ ] Add audit logging for sensitive table access
- [ ] Implement row-level security for cached data
- [ ] Add PII detection in column names/comments
- [ ] Support for masking sensitive column details

---

**Example Output:**
```
📊 Business Logic Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 Query Purpose:
This query retrieves payment transactions with their retry attempts and 
3DS authentication challenges for a specific processing date.

📦 Tables Analyzed (4):
┌─────────────────────────────────────────────────────────────────┐
│ GTW_ODS.GATEWAY_TRANSACTIONS_FULL_EMERGENCY                     │
│ Type: Business | Rows: 45M | Entity: Transaction               │
│ Purpose: Main payment transaction processing table              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ GTW_ODS.GTW_TRANS_RETRY                                         │
│ Type: Operational | Rows: 2.3M | Entity: Retry                 │
│ Purpose: Tracks payment retry attempts                          │
└─────────────────────────────────────────────────────────────────┘

🔗 Relationships (2):
• GTW_TRANS_RETRY ──FK──> GATEWAY_TRANSACTIONS (payment_id)
• GTW_TRANS_3DS_CHALLENGE ──FK──> GATEWAY_TRANSACTIONS (payment_id)

🎯 Domain: Payment Processing
💾 Cache: 4 hits, 0 misses | Duration: 742ms
```

---

### 8. `get_table_business_context(db_name, tables)`

Get business context for specific tables without analyzing a full query.

**Parameters:**
- `db_name` (required) - Database name
- `tables` (required) - List of fully-qualified table names (e.g., "SCHEMA.TABLE")

**Returns:** Same structure as `explain_business_logic` but for specified tables only.

**Example:**
```
get_table_business_context("transformer_master", 
  ["GTW_ODS.GATEWAY_TRANSACTIONS", "GTW_ODS.GTW_TRANS_RETRY"])
```

---

## 🆕 What's New in This Version

### Business Logic Explanation (Oracle) ⭐ NEW
- ✅ AI-powered query business logic inference
- ✅ Automatic table relationship discovery (2 levels deep)
- ✅ PostgreSQL caching with 7-day TTL (93% faster on cache hits)
- ✅ System table filtering (V$, DBA_, SYS schema)
- ✅ Mermaid ER diagram generation
- ✅ Entity and domain classification
- ✅ Column semantics analysis
- ✅ Admin documentation override capability

### Performance Monitoring (Oracle)
- ✅ Real-time database health monitoring (CPU, memory, sessions, cache)
- ✅ Top queries analysis with filtering (exclude system queries, filter by schema/module)
- ✅ Performance trends with JSON chart data (Chart.js compatible)
- ✅ Historical snapshots with 30-day retention
- ✅ Configurable output formats (standard/compact/minimal)

### API Authentication
- ✅ Optional Bearer token authentication
- ✅ Multiple API key support with client naming
- ✅ Per-client request logging
- ✅ Public health check endpoints
- ✅ Zero performance overhead
- ✅ Easy setup with key generator utility

### MySQL Support
- ✅ Full EXPLAIN FORMAT=JSON parsing
- ✅ Index usage insights from performance_schema
- ✅ Duplicate index detection across tables
- ✅ MySQL-specific optimizations (skip scan, covering indexes)

### Enhanced Security System (3 Layers)
1. **LLM-Level Warnings** - Tool descriptions include prominent security alerts
2. **Tool-Level SQL Validation** - Pre-validates queries before metadata collection
3. **Collector-Level Validation** - Deep validation with 25+ blocked keywords

**Blocked Operations:**
- INSERT, UPDATE, DELETE, REPLACE, MERGE, TRUNCATE
- CREATE, DROP, ALTER, RENAME
- GRANT, REVOKE
- COMMIT, ROLLBACK, SAVEPOINT
- SHUTDOWN, KILL, EXECUTE, CALL
- INTO OUTFILE/DUMPFILE (MySQL data exfiltration)
- LOCK/UNLOCK TABLES
- Subquery depth > 10 levels
- Query length > 100KB

### Historical Query Tracking
- **Normalization** - Converts literals to placeholders (`WHERE id = 123` → `WHERE id = :N`)
- **Fingerprinting** - MD5 hash generation for query structure matching
- **SQLite Persistence** - Local storage at `server/data/query_history.db`
- **Comparison** - Detects plan changes, cost increases, data growth

### Visual Execution Plans
- ASCII tree structure with hierarchy
- Cost and cardinality display
- Warning emojis:
  - ✅ Efficient index access
  - ⚠️ Full table scans, skip scans
  - 🚨 Cartesian joins, partition issues

### Smart MCP Prompts
- `oracle_full_analysis` - Comprehensive performance analysis
- `oracle_index_analysis` - Index strategy recommendations
- `oracle_partition_analysis` - Partition pruning diagnostics
- `oracle_rewrite_query` - SQL rewrite suggestions
- `oracle_what_if_growth` - Growth prediction and capacity planning

---

## ⚠️ Safety Notice — MCP Does NOT Execute SQL

**This tool is 100% safe:**
- ✅ Only uses metadata queries (information_schema, ALL_* views)
- ✅ Only uses EXPLAIN PLAN / EXPLAIN (simulates execution)
- ✅ **Never executes user SQL**
- ✅ Safe for DELETE/UPDATE statements (will be blocked before analysis)
- ✅ Zero data modification possible

---

## 🔐 Required Oracle Permissions

### Minimum (Core Functionality)
```sql
GRANT SELECT ON ALL_TABLES TO <your_user>;
GRANT SELECT ON ALL_INDEXES TO <your_user>;
GRANT SELECT ON ALL_IND_COLUMNS TO <your_user>;
GRANT SELECT ON ALL_TAB_COL_STATISTICS TO <your_user>;
GRANT SELECT ON ALL_CONSTRAINTS TO <your_user>;
GRANT SELECT ON ALL_CONS_COLUMNS TO <your_user>;
GRANT SELECT ON ALL_PART_TABLES TO <your_user>;
GRANT SELECT ON ALL_PART_KEY_COLUMNS TO <your_user>;
GRANT SELECT ON PLAN_TABLE TO <your_user>;
```

### Recommended (Enhanced Features)
```sql
GRANT SELECT ON V$PARAMETER TO <your_user>;
GRANT SELECT ON DBA_SEGMENTS TO <your_user>;
-- OR
GRANT SELECT ON USER_SEGMENTS TO <your_user>;
```

### Optional (Runtime Statistics)
```sql
GRANT SELECT ON V$SQL TO <your_user>;
```

---

## 🐬 Required MySQL Permissions

### Minimum (Core Functionality)
```sql
GRANT SELECT ON information_schema.TABLES TO '<your_user>'@'%';
GRANT SELECT ON information_schema.STATISTICS TO '<your_user>'@'%';
GRANT SELECT ON information_schema.COLUMNS TO '<your_user>'@'%';
GRANT SELECT ON <your_database>.* TO '<your_user>'@'%';
```

### Recommended (Enhanced Features)
```sql
GRANT SELECT ON performance_schema.table_io_waits_summary_by_index_usage TO '<your_user>'@'%';
GRANT SELECT ON performance_schema.events_statements_summary_by_digest TO '<your_user>'@'%';
```

### Performance Schema Setup
```sql
-- Enable performance_schema (add to my.cnf and restart)
[mysqld]
performance_schema = ON

-- Check if enabled
SELECT @@performance_schema;

-- Enable table I/O monitoring
UPDATE performance_schema.setup_instruments 
SET ENABLED = 'YES', TIMED = 'YES' 
WHERE NAME LIKE 'wait/io/table/%';

UPDATE performance_schema.setup_consumers 
SET ENABLED = 'YES' 
WHERE NAME LIKE '%table%';
```

---

## ⚙️ Configuration

Edit `server/config/settings.yaml`:

### Database Connections
```yaml
database_presets:
  way4_docker7:
    user: inform
    password: your_password
    dsn: hostname:1521/service_name
  
  mysql_devdb03_avi:
    host: devdb03.dev.bos.credorax.com
    port: 3306
    user: avi
    password: your_password
    database: avi
```

### Analysis Features
```yaml
oracle_analysis:
  output_preset: "compact"  # standard | compact | minimal
  metadata:
    table_statistics:
      enabled: true
  optimizer:
    parameters:
      enabled: true

mysql_analysis:
  output_preset: "compact"
  features:
    index_usage:
      enabled: true
    duplicate_detection:
      enabled: true

performance_monitoring:
  snapshots:
    retention_days: 30  # Keep history for 30 days
  output_preset: "compact"
  chart_format: "json"
```

### Authentication (Optional)
```yaml
server:
  authentication:
    enabled: false  # Set to true to enable API key authentication
    api_keys:
      - name: "claude_desktop"
        key: "your-secure-api-key-here"
        description: "Claude Desktop client"
```

**To enable authentication:**
1. Generate API key: `python generate_api_key.py`
2. Add key to `settings.yaml` (set `enabled: true`)
3. Configure client with `Authorization: Bearer <api_key>` header
4. See [AUTHENTICATION_GUIDE.md](./AUTHENTICATION_GUIDE.md) for details

### Logging
```yaml
logging:
  level: INFO  # DEBUG | INFO | WARNING | ERROR
  show_tool_calls: true
  show_sql_queries: false
```

---

## 🚀 Quick Start

### 1. Configure Databases
Edit `server/config/settings.yaml` with your database credentials.

### 2. Run with Docker
```bash
docker compose up --build
```

The server will:
- Start on port 8300
- Auto-create `server/data/query_history.db`
- Enable hot-reload for development

### 3. Test with MCP Inspector
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
Run the same query twice to see historical comparison.

---

## 📋 Example Usage

### Oracle Analysis
```json
{
  "tool": "analyze_full_sql_context",
  "arguments": {
    "db_name": "way4_docker7",
    "sql_text": "SELECT * FROM ows.merchant_statement WHERE contract_id = 12313"
  }
}
```

**Response includes:**
- Query fingerprint
- Historical executions count
- Visual execution plan with emojis
- Plan details (costs, cardinality)
- Table/index statistics
- Historical context (plan changes, cost trends, data growth)

### MySQL Analysis
```json
{
  "tool": "analyze_mysql_query",
  "arguments": {
    "db_name": "mysql_devdb03_avi",
    "sql_text": "SELECT * FROM avi.customer_order WHERE amount > 20 ORDER BY order_date LIMIT 10"
  }
}
```

**Response includes:**
- EXPLAIN FORMAT=JSON plan
- Index usage statistics from performance_schema
- Duplicate index detection results
- Historical tracking comparison
- UNUSED index warnings

### Query Comparison
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

### Security Block Example
```json
{
  "tool": "analyze_full_sql_context",
  "arguments": {
    "db_name": "way4_docker7",
    "sql_text": "DELETE FROM ows.merchant_statement WHERE contract_id = 12313"
  }
}
```

**Response:**
```json
{
  "error": "DANGEROUS OPERATION BLOCKED",
  "details": "Query contains DELETE operation - only SELECT queries allowed",
  "is_dangerous": true
}
```

---

## 🧪 Test Prompts

### Oracle Tests

#### 1. Basic Analysis
```
Analyze this query on way4_docker7:

SELECT ms.contract_id, ms.ready_date 
FROM ows.merchant_statement ms
WHERE ms.contract_id = 12313
  AND ms.ready_date > SYSDATE - 30
  AND ROWNUM <= 5

Identify any performance bottlenecks and suggest improvements.
```

#### 2. Historical Tracking
```
Run this query twice to test historical tracking:

SELECT owner, table_name, num_rows 
FROM all_tables 
WHERE owner = 'OWS' 
  AND ROWNUM <= 3

Wait a moment, then run again to see historical comparison.
```

#### 3. Security Test
```
Try to analyze this query (should be blocked):

UPDATE ows.merchant_statement 
SET amount = 0 
WHERE contract_id = 12313

Expected: Security validation blocks the query with clear error message.
```

### MySQL Tests

#### 4. Basic MySQL Analysis
```
Analyze this MySQL query on mysql_devdb03_avi:

SELECT * 
FROM avi.customer_order
WHERE amount > 20
  AND status = 'pending'
ORDER BY order_date DESC
LIMIT 10;

Show me the execution plan and any performance issues.
```

#### 5. Index Usage Analysis
```
Analyze this query and check which indexes are actually being used:

SELECT co.order_id, co.customer_id, co.amount, co.status
FROM avi.customer_order co
WHERE co.amount > 100
  AND co.order_date > DATE_SUB(NOW(), INTERVAL 30 DAY)
ORDER BY co.status, co.order_date;

Include index usage statistics from performance_schema.
```

#### 6. Duplicate Index Detection
```
Check the customer_order table for any duplicate or redundant indexes.

Analyze query: SELECT * FROM avi.customer_order WHERE customer_id = 123

Tell me if there are unused indexes that could be dropped.
```

#### 7. MySQL Security Test
```
Try to analyze this MySQL query (should be blocked):

DELETE FROM avi.customer_order WHERE amount = 0;

Expected: Security validation blocks the query immediately with error message.
```

### Performance Monitoring Tests

#### 8. Database Health Check
```
Check the current health status of transformer_master database.

Use get_database_health to see CPU usage, active sessions, cache hit ratios, and top wait events.
```

#### 9. Top CPU Queries
```
Show me the top 10 queries consuming the most CPU time on way4_docker7 in the last 4 hours.

Filter out system queries and focus on application queries.
```

#### 10. Performance Trends
```
Show me the CPU usage trend for transformer_master over the last 24 hours with hourly intervals.

Include a chart visualization of the trend.
```

---

## 📊 Response Structure

```json
{
  "facts": {
    "query_fingerprint": "MD5 hash of normalized query",
    "historical_executions": "Number of previous runs",
    "historical_context": "Human-readable comparison",
    "visual_plan": "ASCII tree with emojis",
    "execution_plan": "Traditional DBMS_XPLAN output",
    "plan_details": [...],
    "tables": [...],
    "indexes": [...],
    "columns": [...],
    "constraints": [...],
    "optimizer_params": {...},
    "segment_sizes": {...},
    "partition_diagnostics": {...}
  }
}
```

**Key Fields:**
- `query_fingerprint` - Unique MD5 hash for query structure
- `historical_executions` - Number of previous runs
- `historical_context` - Performance comparison, plan changes, data growth
- `visual_plan` - ASCII tree with emoji warnings
- `plan_details` - Structured plan steps with costs/cardinality
- `tables` - Row counts, sizes, partitioning info
- `indexes` - Index stats, clustering factor, usage in plan

---

## 🛡️ Security Features

### Multi-Layer Defense
1. **LLM Awareness** - Tool descriptions include security warnings
2. **Tool-Level Validation** - Pre-validates SQL before metadata collection
3. **Collector Validation** - Deep validation with comprehensive keyword blocking

### Blocked Operations
- **Data Modification**: INSERT, UPDATE, DELETE, REPLACE, MERGE, TRUNCATE
- **Schema Changes**: CREATE, DROP, ALTER, RENAME
- **Permissions**: GRANT, REVOKE
- **System Operations**: SHUTDOWN, KILL, EXECUTE, CALL
- **Data Exfiltration**: SELECT INTO (Oracle), INTO OUTFILE/DUMPFILE (MySQL)
- **Table Locking**: LOCK, UNLOCK TABLES (MySQL)

### DoS Prevention
- Maximum 10 levels of subquery nesting
- Query length limit: 100KB
- Validation query timeouts

### Optional API Authentication
- **Bearer Token Authentication** - API key validation via Authorization header
- **Multi-Client Support** - Track and manage multiple API keys
- **Public Endpoints** - Health checks remain accessible without auth
- **Zero Performance Impact** - <1ms overhead per request

**See [AUTHENTICATION_GUIDE.md](./AUTHENTICATION_GUIDE.md) for setup details**
- **System Operations**: SHUTDOWN, KILL, EXECUTE, CALL
- **Data Exfiltration**: SELECT INTO (Oracle), INTO OUTFILE/DUMPFILE (MySQL)
- **Table Locking**: LOCK, UNLOCK TABLES (MySQL)

### DoS Prevention
- Maximum 10 levels of subquery nesting
- Query length limit: 100KB
- Validation query timeouts

---

## 📊 Historical Tracking System

### How It Works

1. **Normalization** - Converts literals to placeholders
   ```sql
   -- Original
   SELECT * FROM employees WHERE dept_id = 10 AND salary > 50000
   
   -- Normalized
   SELECT * FROM EMPLOYEES WHERE DEPT_ID = :N AND SALARY > :N
   ```

2. **Fingerprinting** - Generates MD5 hash of normalized SQL

3. **Storage** - Saves to SQLite (`server/data/query_history.db`)
   ```sql
   CREATE TABLE query_history (
       id INTEGER PRIMARY KEY,
       query_fingerprint TEXT NOT NULL,
       executed_at TIMESTAMP,
       plan_hash TEXT,
       total_cost INTEGER,
       num_tables INTEGER,
       tables_summary TEXT
   );
   ```

4. **Comparison** - Detects changes:
   - Plan hash changed (optimizer switched strategies)
   - Cost increased (performance regression)
   - Row counts changed (data growth)

### Benefits
- **Regression Detection** - Catch performance degradation early
- **Plan Stability** - Track when optimizer changes strategies
- **Data Growth Monitoring** - See table size trends
- **Baseline Comparison** - Compare to historical norms

---

## 🎨 Visual Execution Plans

### Example
```
SELECT STATEMENT (Cost: 450)
└─ COUNT (Cost: 450)
   └─ FILTER (Cost: 450)
      ├─ TABLE ACCESS BY INDEX ROWID: OWS.MERCHANT_STATEMENT (Cost: 450, Rows: 1,850)
      │  └─ INDEX RANGE SCAN: OWS.IDX_MS_CONTRACT ✅ (Cost: 5, Rows: 1,850)
      └─ FILTER (Cost: 5)
```

### Warning Indicators
| Emoji | Operation | Meaning |
|-------|-----------|---------|
| ✅ | INDEX UNIQUE SCAN | Perfect - single row lookup |
| ✅ | INDEX RANGE SCAN (low cost) | Good - efficient index access |
| ⚠️ | TABLE ACCESS FULL | Warning - full table scan |
| ⚠️ | INDEX SKIP SCAN | Warning - inefficient index usage |
| ⚠️ | NESTED LOOPS (high rows) | Warning - large cartesian risk |
| 🚨 | CARTESIAN | Critical - cartesian join |

---

## 🔧 Project Structure

```
server/
├── config/
│   ├── settings.yaml              # Database connections + configuration
│   └── settings.template.yaml     # Template for new installations
├── tools/
│   ├── oracle_analysis.py         # Oracle MCP tools
│   ├── oracle_collector_impl.py   # Oracle data collection
│   ├── mysql_analysis.py          # MySQL MCP tools
│   ├── mysql_collector_impl.py    # MySQL data collection
│   ├── database_tools.py          # Database listing tool
│   └── plan_visualizer.py         # ASCII tree generator
├── prompts/
│   └── analysis_prompts.py        # Smart MCP prompts
├── resources/
│   └── (optional resources)
├── data/
│   └── query_history.db           # SQLite history (auto-created)
├── history_tracker.py             # Query fingerprinting
├── db_connector.py                # Oracle connector
├── mysql_connector.py             # MySQL connector
└── mcp_app.py                     # FastMCP application
```

---

## 🧪 Testing Checklist

- [ ] **Security**: Try UPDATE/DELETE → Should be blocked
- [ ] **Validation**: Try invalid syntax → Should return clear error
- [ ] **History (First Run)**: New query → Shows "0 historical executions"
- [ ] **History (Second Run)**: Same query → Shows comparison
- [ ] **Visual Plan**: Response includes ASCII tree with emojis
- [ ] **MySQL Index Usage**: Shows performance_schema statistics
- [ ] **Duplicate Detection**: Identifies redundant indexes
- [ ] **Query Comparison**: Shows cost differences

---

## 🛠️ Troubleshooting

### Oracle Issues

**"ORA-00942: table or view does not exist"**
- Check user has SELECT on required views
- Verify connection credentials in settings.yaml

**Missing optimizer parameters**
- User needs SELECT on V$PARAMETER
- Or disable via `oracle_analysis.optimizer.parameters.enabled: false`

**Slow analysis**
- Try "compact" output preset
- Disable segment_sizes if DBA_SEGMENTS is slow

### MySQL Issues

**"Access denied for user"**
- Verify MySQL user has SELECT on information_schema
- Check target database access permissions

**Missing index usage statistics**
- Enable performance_schema in my.cnf
- Check setup_instruments and setup_consumers

**EXPLAIN fails**
- Verify user has SELECT on target tables
- Check for syntax errors in SQL

---

## 👤 Author

**Avi Cohen**  
Email: aviciot@gmail.com  
GitHub: [aviciot/MetaQuery-MCP](https://github.com/aviciot/MetaQuery-MCP)

---

## 📜 License

MIT License - See LICENSE file for details
