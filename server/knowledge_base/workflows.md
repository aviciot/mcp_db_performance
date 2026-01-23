# Common Workflows

This guide provides step-by-step workflows for common Performance MCP usage scenarios.

---

## Choosing Analysis Depth

**NEW FEATURE:** Both Oracle and MySQL analysis tools support two analysis modes via the `depth` parameter.

### Depth Modes

| Mode | Speed | Use Case | What You Get |
|------|-------|----------|--------------|
| **plan_only** | ⚡ Fast (0.3s) | Understanding execution<br>Learning how queries work<br>Quick plan review | • Execution plan<br>• Operation details<br>• Cost estimates<br>• ❌ No metadata |
| **standard** | 🔄 Full (1-3s) | Query optimization<br>Getting recommendations<br>Full analysis | • Everything in plan_only<br>• Table/index statistics<br>• Column selectivity<br>• Diagnostics & fixes |

### When to Use Each Mode

#### Use `depth="plan_only"` when:
- ✅ "Explain what this execution plan means"
- ✅ "What's an INDEX SKIP SCAN?"
- ✅ "Why is there a NESTED LOOP?"
- ✅ "How does the optimizer process this query?"
- ✅ Learning and education

#### Use `depth="standard"` (default) when:
- ✅ "Optimize this query"
- ✅ "Make this faster"
- ✅ "Recommend indexes"
- ✅ "Fix performance issues"
- ✅ Production optimization

### Examples

**Fast Plan Explanation:**
```python
# Oracle
analyze_oracle_query(
    db_name="prod_db",
    sql_text="SELECT * FROM orders WHERE status = 'PENDING'",
    depth="plan_only"  # Fast, educational
)

# MySQL
analyze_mysql_query(
    db_name="mysql_db",
    sql_text="SELECT * FROM customers WHERE country = 'US'",
    depth="plan_only"  # Fast, educational
)
```

**Full Optimization Analysis:**
```python
# Oracle (default behavior)
analyze_oracle_query(
    db_name="prod_db",
    sql_text="SELECT * FROM orders WHERE status = 'PENDING'",
    depth="standard"  # Full analysis for optimization
)
# Or simply omit depth parameter - standard is default
analyze_oracle_query(
    db_name="prod_db",
    sql_text="SELECT * FROM orders WHERE status = 'PENDING'"
)
```

### LLM Guidance

**The LLM will automatically choose the right mode based on user intent:**

| User Says | LLM Uses | Reason |
|-----------|----------|--------|
| "Explain this plan" | plan_only | Just needs understanding |
| "What does INDEX RANGE SCAN mean?" | plan_only | Educational |
| "Optimize this query" | standard | Needs full context for optimization |
| "Why is this slow?" | standard | Needs diagnostics |
| "Recommend indexes" | standard | Needs column statistics |

---

## Workflow 1: Slow Query Analysis

**Scenario:** User reports "This query takes 5 minutes, why is it slow?"

### Steps:

**1. Verify Database Access**
```python
check_oracle_access(db_preset="transformer_prod")
# or
check_mysql_access(db_preset="mysql_devdb03_avi")
```

**What to look for:**
- Ensure ALL_TABLES / information_schema.TABLES is accessible
- Impact score should be 7+ for full analysis capabilities
- If access is limited, analysis will use fallback methods

**2. Analyze the Query**
```python
analyze_oracle_query(
    sql_query="SELECT * FROM orders WHERE order_date > SYSDATE-30",
    db_preset="transformer_prod"
)
```

**3. Review Execution Plan**
Look for these expensive operations:
- **TABLE ACCESS FULL** on large tables → Missing index
- **HASH JOIN** with high cost → Consider nested loops with index
- **SORT ORDER BY** → Check if index can eliminate sort

**4. Check Anti-Pattern Detections**
- `full_table_scans`: Lists tables scanned without indexes
- `cartesian_detections`: Identifies missing join conditions
- `large_table_scans`: Highlights tables with millions of rows being fully scanned

**5. Suggest Optimization**
Based on findings:
- **Full scan on ORDERS(order_date)** → `CREATE INDEX idx_orders_date ON orders(order_date)`
- **Cartesian product** → Add missing join condition
- **Stale statistics** → Recommend `EXEC DBMS_STATS.GATHER_TABLE_STATS('OWNER','ORDERS')`

**6. Verify Improvement**
```python
compare_oracle_plans(
    original_sql="SELECT * FROM orders WHERE order_date > SYSDATE-30",
    optimized_sql="SELECT * FROM orders WHERE order_date > SYSDATE-30",
    db_preset="transformer_prod"
)
```

Look for:
- Cost reduction percentage
- Operation changes (FULL → INDEX RANGE SCAN)
- Cardinality estimate improvements

---

## Workflow 2: Query Plan Comparison

**Scenario:** "I added an index, did it help?"

### Steps:

**1. Capture Original Plan**
```python
original_result = analyze_oracle_query(
    sql_query="<original query>",
    db_preset="transformer_prod"
)
```

**2. Apply Optimization**
Options:
- Add index in database
- Rewrite query
- Add optimizer hints

**3. Compare Plans**
```python
compare_oracle_plans(
    original_sql="<original query>",
    optimized_sql="<optimized query>",  # Can be same if index was added
    db_preset="transformer_prod"
)
```

**4. Interpret Results**
```json
{
  "cost_change": {
    "original": 8234,
    "optimized": 125,
    "reduction_pct": 98.5
  },
  "operation_changes": [
    "TABLE ACCESS FULL → INDEX RANGE SCAN on ORDERS"
  ],
  "verdict": "IMPROVEMENT: Cost reduced significantly"
}
```

**Success Indicators:**
- ✅ Cost reduction > 50%
- ✅ Full scans eliminated
- ✅ Cardinality estimates closer to actuals

**Warning Signs:**
- ⚠️ Cost increased → Optimization made it worse
- ⚠️ Plan unchanged → Index not used (check predicates)
- ⚠️ New full scans introduced → Unexpected side effects

---

## Workflow 3: Permission Verification

**Scenario:** "Analysis fails with ORA-00942 or missing metadata"

### Steps:

**1. Run Access Check**
```python
check_oracle_access(db_preset="transformer_prod")
```

**2. Review Report**
```json
{
  "access_report": {
    "ALL_TABLES": "✓ Accessible",
    "ALL_INDEXES": "✗ No access: ORA-00942",
    "DBA_SEGMENTS": "✗ No access: insufficient privileges"
  },
  "impact_score": 4,
  "impact_level": "MEDIUM - Some features limited",
  "recommendations": [
    "CRITICAL: Grant SELECT on ALL_INDEXES for index analysis",
    "Grant SELECT on DBA_SEGMENTS for storage sizing"
  ]
}
```

**3. Interpret Impact Score**

| Score | Level | Capabilities |
|-------|-------|-------------|
| 9-10 | EXCELLENT | Full analysis with all features |
| 7-8 | GOOD | Most features available |
| 5-6 | MEDIUM | Basic analysis, some metadata missing |
| 3-4 | LIMITED | Plan only, limited recommendations |
| 0-2 | CRITICAL | Cannot perform meaningful analysis |

**4. Request Missing Permissions**
Send to DBA:
```sql
-- Oracle
GRANT SELECT ON SYS.ALL_TABLES TO transformer;
GRANT SELECT ON SYS.ALL_INDEXES TO transformer;
GRANT SELECT ON SYS.ALL_IND_COLUMNS TO transformer;
GRANT SELECT ON SYS.ALL_CONSTRAINTS TO transformer;
GRANT SELECT ON SYS.V_$PARAMETER TO transformer;

-- MySQL
GRANT SELECT ON information_schema.TABLES TO inform;
GRANT SELECT ON information_schema.STATISTICS TO inform;
GRANT SELECT ON performance_schema.table_io_waits_summary_by_index_usage TO inform;
```

**5. Re-verify After Grants**
```python
check_oracle_access(db_preset="transformer_prod")
# Impact score should increase to 8-10
```

---

## Workflow 4: Understanding Legacy Queries

**Scenario:** "What does this 500-line query do?"

### Steps:

**1. Analyze Query Structure**
```python
analyze_oracle_query(
    sql_query="<legacy 500-line query>",
    db_preset="transformer_prod",
    output_preset="standard"  # Get all metadata
)
```

**2. Review Query Intent**
Check `query_intent` field:
```json
{
  "query_intent": {
    "pattern": "JOIN_AGGREGATION",
    "description": "Multi-table join with GROUP BY aggregation",
    "tables_involved": ["ORDERS", "CUSTOMERS", "ADDRESSES", "PRODUCTS"],
    "join_type": "INNER JOINS with LEFT OUTER JOIN"
  }
}
```

**3. Map Relationships**
Review `table_relationships`:
```json
{
  "foreign_keys": [
    "ORDERS.customer_id → CUSTOMERS.id",
    "ORDERS.product_id → PRODUCTS.id",
    "CUSTOMERS.address_id → ADDRESSES.id"
  ]
}
```

**4. Read Business Context**
Check `table_comments` and `column_comments`:
```json
{
  "ORDERS": "Customer purchase transactions",
  "ORDERS.order_date": "Date when order was placed",
  "ORDERS.total_amount": "Total order value in USD"
}
```

**5. Summarize for User**
Example response:
> "This query generates a customer order history report. It joins:
> - ORDERS (main table)
> - CUSTOMERS (to get customer name)
> - ADDRESSES (to get shipping address)
> - PRODUCTS (to get product details)
> 
> The query aggregates by customer and calculates:
> - Total orders per customer
> - Total revenue per customer
> - Date range: Last 90 days
> 
> Current performance issue: Full scan on ORDERS table (5M rows)"

---

## Workflow 5: Real-Time Performance Monitoring

**Scenario:** "Database is slow right now, what's happening?"

### Steps (Oracle Only):

**1. Check System Health**
```python
collect_oracle_system_health(
    db_preset="transformer_prod",
    output_preset="compact"
)
```

**What to look for:**
- **CPU Usage** > 80% → Resource saturation
- **Active Sessions** spike → Possible blocking
- **Buffer Cache Hit Ratio** < 90% → Memory pressure
- **Wait Events** → What database is waiting on

**2. Identify Top Expensive Queries**
```python
get_oracle_top_queries(
    db_preset="transformer_prod",
    limit=10
)
```

**Results:**
```json
{
  "top_queries": [
    {
      "sql_id": "abc123xyz",
      "sql_text": "SELECT * FROM orders WHERE...",
      "executions": 15234,
      "avg_elapsed_ms": 5234,
      "total_cpu_seconds": 1234,
      "buffer_gets": 5000000
    }
  ]
}
```

**3. Analyze Problem Queries**
For each expensive query:
```python
analyze_oracle_query(
    sql_query="<sql_text from top_queries>",
    db_preset="transformer_prod"
)
```

**4. Check for Blocking**
```python
get_oracle_wait_events(db_preset="transformer_prod")
```

Look for:
- **enq: TX - row lock contention** → Blocking sessions
- **db file sequential read** → Index contention
- **direct path read** → Large table scans

**5. Recommend Actions**
Based on findings:
- High CPU + full scans → Add indexes
- Blocking sessions → Identify and kill blocker
- Memory pressure → Tune buffer cache
- Wait on temp → Increase temp tablespace

---

## Workflow 6: Index Effectiveness Check

**Scenario:** "We have indexes, but queries are still slow"

### Steps:

**1. Analyze Query with Index Info**
```python
analyze_mysql_query(
    sql_query="SELECT * FROM orders WHERE customer_id = 123",
    db_preset="mysql_devdb03_avi",
    output_preset="standard"  # Include index usage stats
)
```

**2. Review Index Usage**
Check `index_usage_stats` in MySQL results:
```json
{
  "index_usage_stats": [
    {
      "index_name": "idx_customer_id",
      "read_count": 0,        # ⚠️ Index never used!
      "write_count": 12453,   # But maintenance overhead exists
      "last_access": null
    }
  ]
}
```

**3. Check for Duplicate Indexes**
Look for `duplicate_indexes`:
```json
{
  "duplicate_indexes": [
    {
      "redundant": "idx_customer_id_2",
      "covered_by": "idx_customer_full",
      "recommendation": "DROP idx_customer_id_2 (same columns)"
    }
  ]
}
```

**4. Verify Index Selection in Plan**
Review execution plan:
- **Using index: idx_customer_id** ✅ Good
- **Using filesort** ⚠️ Index not helping sort
- **Using temporary** ⚠️ GROUP BY not using index

**5. Optimize Index Design**
Common fixes:
- **Covering index:** Add columns to index to avoid table lookup
- **Composite index:** Reorder columns for better selectivity
- **Remove unused:** Drop indexes with 0 reads
- **Partial index:** Use WHERE clause for MySQL 8.0+

---

## Workflow 7: Before Production Deployment

**Scenario:** "We're deploying query changes to production tomorrow. Will they work?"

### Steps:

**1. Test Against Production-Like Data**
```python
# Use production preset (with read-only credentials)
analyze_oracle_query(
    sql_query="<new optimized query>",
    db_preset="transformer_prod"  # Read-only prod access
)
```

**2. Compare Plans**
```python
compare_oracle_plans(
    original_sql="<current production query>",
    optimized_sql="<new optimized query>",
    db_preset="transformer_prod"
)
```

**3. Verify Success Criteria**
Before deploying, confirm:
- ✅ Cost reduced by > 50%
- ✅ No new full table scans
- ✅ Cardinality estimates reasonable
- ✅ No Cartesian products
- ✅ Index usage confirmed

**4. Document Changes**
Include in deployment notes:
- Old cost vs new cost
- Operations changed
- Indexes required (if any)
- Expected performance improvement

**5. Post-Deployment Verification**
After deployment:
```python
# Check if plan matches expectations
analyze_oracle_query(
    sql_query="<deployed query>",
    db_preset="transformer_prod"
)

# Monitor actual performance
get_oracle_top_queries(db_preset="transformer_prod")
```

---

## Common Troubleshooting During Workflows

### Issue: "Analysis returns minimal data"
**Cause:** Limited permissions or wrong output preset
**Fix:** 
1. Run `check_oracle_access()` to verify permissions
2. Change `output_preset="standard"` for more details

### Issue: "Plan shows index exists but not used"
**Cause:** Stale statistics or incompatible predicate
**Fix:**
1. Check `last_analyzed` date in table stats
2. Verify WHERE clause matches index columns exactly
3. Check for implicit type conversions (e.g., VARCHAR vs NUMBER)

### Issue: "Cost estimates seem wrong"
**Cause:** Stale or missing statistics
**Fix:**
```sql
-- Oracle
EXEC DBMS_STATS.GATHER_TABLE_STATS('OWNER','TABLE_NAME');

-- MySQL
ANALYZE TABLE table_name;
```

### Issue: "Compare shows no difference after adding index"
**Cause:** Optimizer not aware of new index
**Fix:**
1. Verify index was created successfully
2. Oracle: Gather stats on new index
3. MySQL: Run ANALYZE TABLE
4. Check if query needs hint to force index use

---

## Best Practices

1. **Always check access first** - Run check_oracle_access() before deep analysis
2. **Use appropriate preset** - compact for routine, standard for deep dive
3. **Compare plans** - Never deploy optimization without comparison
4. **Document findings** - Save analysis results for reference
5. **Monitor after changes** - Use monitoring tools to verify improvements
6. **Gather statistics** - Keep database statistics current for accurate plans

---

## Next Steps

- **Detailed tool docs:** See [tools/](tools/) for individual tool documentation
- **Troubleshooting:** See [troubleshooting.md](troubleshooting.md) for error solutions
- **Architecture:** See [architecture.md](architecture.md) for how presets work
