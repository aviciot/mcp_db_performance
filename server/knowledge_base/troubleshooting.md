# Troubleshooting Guide

Common errors, their causes, and solutions when using Performance MCP.

---

## Permission Errors

### ORA-00942: table or view does not exist

**Symptom:**
```
Error analyzing query: ORA-00942: table or view does not exist (ALL_TABLES)
```

**Cause:** Database user doesn't have SELECT privilege on Oracle data dictionary views

**Solution:**
1. Run `check_oracle_access(db_preset="your_db")` to diagnose which views are missing
2. Request DBA to grant required permissions:

```sql
GRANT SELECT ON SYS.ALL_TABLES TO your_user;
GRANT SELECT ON SYS.ALL_INDEXES TO your_user;
GRANT SELECT ON SYS.ALL_IND_COLUMNS TO your_user;
GRANT SELECT ON SYS.ALL_CONSTRAINTS TO your_user;
GRANT SELECT ON SYS.ALL_TAB_COLUMNS TO your_user;
```

**See also:** [check_oracle_access tool documentation](tools/check_oracle_access.md)

---

### MySQL: Access denied for table 'information_schema.STATISTICS'

**Symptom:**
```
Error: Access denied for user 'readonly'@'%' to database 'information_schema'
```

**Cause:** MySQL user doesn't have SELECT privilege on information_schema

**Solution:**
```sql
GRANT SELECT ON information_schema.STATISTICS TO 'readonly'@'%';
GRANT SELECT ON information_schema.TABLES TO 'readonly'@'%';
```

**Note:** This is rare - information_schema is usually accessible by default

---

## Connection Errors

### Cannot connect to database: Connection refused

**Symptoms:**
- `Connection refused to host:port`
- `Could not establish connection`

**Common Causes:**

**1. Wrong Host/Port in settings.yaml**
```yaml
# Check your settings.yaml database config
transformer_prod:
  type: oracle
  dsn: bidb02.prod.bos.credorax.com:1521/stgprod  # ← Verify this
```

**2. Docker Networking (Container ↔ Host)**
If MCP runs in Docker and database is on host machine:
```yaml
# Replace localhost with:
dsn: host.docker.internal:1521/orcl  # For Docker Desktop
dsn: 172.17.0.1:1521/orcl            # For Linux Docker
```

**3. Firewall/Network Blocking**
Test connectivity:
```bash
# Oracle
telnet bidb02.prod.bos.credorax.com 1521

# MySQL
telnet devdb03.dev.bos.credorax.com 3306
```

**4. Database Service Down**
Verify database is running:
```sql
-- Oracle
SELECT * FROM v$instance;

-- MySQL
SHOW STATUS LIKE 'Uptime';
```

---

### ORA-01017: invalid username/password

**Cause:** Incorrect credentials in settings.yaml

**Solution:**
1. Verify credentials:
```yaml
transformer_prod:
  user: transformer
  password: transformer99  # ← Check this
```

2. Test credentials manually:
```bash
sqlplus transformer/transformer99@bidb02.prod.bos.credorax.com:1521/stgprod
```

3. Check if password has special characters that need escaping in YAML

---

## Query Analysis Errors

### Query rejected: Not a SELECT query

**Symptom:**
```
Error: Tool only accepts SELECT queries (security restriction)
```

**Cause:** Trying to analyze INSERT/UPDATE/DELETE/CREATE statement

**Solution:**
```python
# ❌ This will fail:
analyze_oracle_query(
    sql_query="INSERT INTO orders VALUES (...)",
    db_preset="prod"
)

# ✅ Extract and analyze the SELECT portion:
analyze_oracle_query(
    sql_query="SELECT * FROM orders WHERE order_date > SYSDATE-30",
    db_preset="prod"
)
```

**Why:** Performance MCP is read-only for security. It only analyzes SELECT queries.

---

### ORA-00933: SQL command not properly ended

**Symptom:**
```
Error: ORA-00933: SQL command not properly ended
```

**Cause:** Query contains semicolon or SQL*Plus commands

**Solution:**
```python
# ❌ Remove trailing semicolon:
analyze_oracle_query(
    sql_query="SELECT * FROM orders;",  # ← Remove ;
    db_preset="prod"
)

# ✅ Correct:
analyze_oracle_query(
    sql_query="SELECT * FROM orders",
    db_preset="prod"
)
```

---

### Stale statistics warning

**Symptom:**
```json
{
  "anti_patterns": {
    "stale_statistics": [
      {
        "table": "ORDERS",
        "last_analyzed": "2024-10-15",
        "days_old": 83
      }
    ]
  }
}
```

**Cause:** Table statistics haven't been gathered recently (>30 days)

**Impact:** Optimizer may choose suboptimal plan based on outdated row counts

**Solution:**
```sql
-- Oracle: Gather table stats
EXEC DBMS_STATS.GATHER_TABLE_STATS(
  ownname => 'STG',
  tabname => 'ORDERS',
  estimate_percent => DBMS_STATS.AUTO_SAMPLE_SIZE,
  method_opt => 'FOR ALL COLUMNS SIZE AUTO'
);

-- MySQL: Analyze table
ANALYZE TABLE orders;
```

**Prevention:** Set up automatic statistics gathering:
```sql
-- Oracle: Enable auto stats (usually enabled by default)
SELECT client_name, status FROM dba_autotask_client WHERE client_name = 'auto optimizer stats collection';
```

---

## Output and Performance Issues

### Token limit exceeded / Response too large

**Symptom:**
```
Response size ~45K tokens exceeds LLM context window
```

**Cause:** Using `output_preset="standard"` on complex query with many tables

**Solution:**
```python
# Change to compact preset
analyze_oracle_query(
    sql_query="<your query>",
    db_preset="prod",
    output_preset="compact"  # ← Reduces to ~20K tokens
)

# Or minimal for very large queries
analyze_oracle_query(
    sql_query="<your query>",
    db_preset="prod",
    output_preset="minimal"  # ← Reduces to ~5K tokens
)
```

**Preset Comparison:**
| Preset | Token Size | Use Case |
|--------|-----------|----------|
| standard | 40K | Deep analysis, small queries |
| compact | 20K | **Recommended default** |
| minimal | 5K | Quick checks, large queries |

---

### Analysis takes too long (> 30 seconds)

**Symptom:** Tool execution times out or takes excessive time

**Possible Causes:**

**1. Complex Query with Many Tables**
```python
# Solution: Use minimal preset
analyze_oracle_query(
    sql_query="<query with 20+ tables>",
    db_preset="prod",
    output_preset="minimal"  # Skips detailed metadata
)
```

**2. Database Performance Issues**
Check database health:
```python
collect_oracle_system_health(db_preset="prod")
# Look for high CPU, active sessions, wait events
```

**3. Network Latency**
If database is remote, metadata queries may be slow. Consider:
- Using compact/minimal presets
- Running MCP server closer to database

---

## Configuration Issues

### Database not found in settings.yaml

**Symptom:**
```
Error: Database 'prod_db' not found in settings.yaml
```

**Cause:** `db_preset` parameter doesn't match any database defined in settings.yaml

**Solution:**
1. List available databases:
```python
list_available_databases()
```

2. Use exact name from settings.yaml:
```python
# ❌ Wrong:
analyze_oracle_query(sql_query="...", db_preset="production")

# ✅ Correct (must match settings.yaml):
analyze_oracle_query(sql_query="...", db_preset="transformer_prod")
```

---

### Wrong database type

**Symptom:**
```
Error: analyze_oracle_query requires Oracle database, but 'mysql_dev' is MySQL
```

**Cause:** Using Oracle tool on MySQL database or vice versa

**Solution:**
```python
# ❌ Wrong tool for database type:
analyze_oracle_query(sql_query="...", db_preset="mysql_devdb03_avi")

# ✅ Use correct tool:
analyze_mysql_query(sql_query="...", db_preset="mysql_devdb03_avi")
```

---

## Analysis Result Issues

### Plan shows index exists but not used

**Symptom:**
- Index exists on WHERE clause column
- Plan still shows TABLE ACCESS FULL

**Common Causes:**

**1. Implicit Type Conversion**
```sql
-- Index on order_id (NUMBER)
SELECT * FROM orders WHERE order_id = '12345'  -- String passed!
-- Oracle does TO_NUMBER('12345'), index not used
```

**Fix:** Match data types
```sql
SELECT * FROM orders WHERE order_id = 12345  -- Pass as number
```

**2. Function on Indexed Column**
```sql
-- Index on order_date
SELECT * FROM orders WHERE TRUNC(order_date) = TRUNC(SYSDATE)
-- Function prevents index use!
```

**Fix:** Rewrite to avoid function
```sql
SELECT * FROM orders 
WHERE order_date >= TRUNC(SYSDATE) 
AND order_date < TRUNC(SYSDATE) + 1
```

**3. Stale Statistics**
Optimizer thinks index is inefficient due to old stats.

**Fix:** Gather fresh statistics (see "Stale statistics warning" above)

**4. Index Selectivity Too Low**
If column has few distinct values, full scan may be faster.

**Example:**
```sql
-- status column has only 3 values: 'ACTIVE', 'PENDING', 'CLOSED'
-- 90% of rows are 'ACTIVE'
SELECT * FROM orders WHERE status = 'ACTIVE'  -- Full scan is faster!
```

**Diagnosis:**
```python
result = analyze_oracle_query(sql_query="...", db_preset="prod")
# Check: result['tables']['ORDERS']['columns']['status']['distinct_values']
```

---

### Cost estimates seem unrealistic

**Symptom:**
- Plan shows cost = 2, but query takes minutes
- OR plan shows cost = 50000, but query is instant

**Cause:** Statistics are stale or missing

**Solution:**
1. Check last_analyzed dates:
```python
result = analyze_oracle_query(sql_query="...", db_preset="prod")
# Review: result['tables']['TABLE_NAME']['last_analyzed']
```

2. Gather fresh statistics
3. Re-analyze query

**Note:** Cost is relative, not absolute time. Compare costs between different versions of same query.

---

## MCP Server Issues

### Tool not found or unavailable

**Symptom:**
```
Tool 'check_oracle_access' not found
```

**Cause:** Tool may not be imported or MCP server needs restart

**Solution:**
1. Check server logs for tool registration:
```
📦 Auto-imported: tools.oracle_access_check
```

2. Restart MCP server:
```bash
docker-compose down
docker-compose up -d
```

3. Verify tool is available:
```python
# Tools should be auto-discovered by MCP protocol
# Use tools/list method to see all available tools
```

---

### Authentication failed

**Symptom:**
```
HTTP 401: Unauthorized
```

**Cause:** Missing or invalid API key for MCP server

**Solution:**
Check settings.yaml:
```yaml
server:
  authentication:
    enabled: true
    api_keys:
      - name: "client_1"
        key: "U1f1mzzSvNKhrtntjJeE0O1KUz-7r7TiuR1-ushQXoc"
```

Provide key in MCP client configuration:
```json
{
  "mcpServers": {
    "database-mcp": {
      "url": "http://localhost:8300/mcp",
      "headers": {
        "Authorization": "Bearer U1f1mzzSvNKhrtntjJeE0O1KUz-7r7TiuR1-ushQXoc"
      }
    }
  }
}
```

---

## Getting Help

### Diagnostic Checklist

Before reporting issues, run:

1. **Check Access:**
```python
check_oracle_access(db_preset="your_db")
# or
check_mysql_access(db_preset="your_db")
```

2. **Test Connection:**
```python
list_available_databases()
```

3. **Check Server Logs:**
```bash
docker logs database-mcp -f
```

4. **Verify Settings:**
```bash
cat server/config/settings.yaml
```

### Log Locations

- **Container logs:** `docker logs database-mcp`
- **Application logs:** `server/logs/` (if volume mounted)
- **SQL queries:** Enabled via `logging.show_sql_queries: true` in settings.yaml

### Common Log Messages

**Success:**
```
✓ Connected to transformer_prod (Oracle)
📊 EXPLAIN PLAN executed successfully
📦 Collected metadata for 3 tables
```

**Warnings:**
```
⚠️ Limited access to DBA_SEGMENTS (using fallback)
⚠️ Statistics for ORDERS table are 90 days old
```

**Errors:**
```
❌ ORA-00942: table or view does not exist
❌ Connection refused to host:port
```

---

## See Also

- [Workflows Guide](workflows.md) - Step-by-step usage scenarios
- [check_oracle_access](tools/check_oracle_access.md) - Permission diagnostics
- [check_mysql_access](tools/check_mysql_access.md) - MySQL permission diagnostics
- [Overview](overview.md) - Understanding what this MCP does
