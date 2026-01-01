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

### Performance Monitoring Tools (Oracle)

### 4. `get_database_health(db_name, time_range_minutes)`

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

### 5. `get_top_queries(db_name, metric, top_n, time_range_hours, exclude_sys, schema_filter, module_filter)`

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

### 6. `get_performance_trends(db_name, metric, hours_back, interval_minutes)`

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

### 7. `explain_business_logic(db_name, sql_text, follow_relationships, max_depth)` ⭐ NEW

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
