# Analysis Depth Modes - Quick Reference

**Feature:** Configurable analysis depth for `analyze_oracle_query` and `analyze_mysql_query`

---

## 🎯 Overview

Choose between **fast plan-only analysis** (educational) or **full optimization analysis** (production-ready recommendations).

### Parameter

```python
depth = "plan_only" | "standard"  # default: "standard"
```

---

## 📊 Comparison Table

| Aspect | plan_only | standard |
|--------|-----------|----------|
| **Speed** | ⚡ 0.3 seconds | 🔄 1-3 seconds |
| **Token Cost** | ~500 tokens | ~13,000 tokens |
| **Execution Plan** | ✅ Full detail | ✅ Full detail |
| **Table Statistics** | ❌ Not collected | ✅ Row counts, sizes |
| **Index Statistics** | ❌ Not collected | ✅ Usage, selectivity |
| **Column Statistics** | ❌ Not collected | ✅ Cardinality, histograms |
| **Partition Info** | ❌ Not collected | ✅ Pruning diagnostics |
| **Diagnostics** | ❌ None | ✅ Full table scans, Cartesian products |
| **Recommendations** | ❌ None | ✅ Index DDL, query rewrites |
| **Historical Tracking** | ❌ Skipped | ✅ Tracked |

---

## 🎓 Use Case: Plan-Only Mode

### When to Use
- Understanding execution plans
- Learning SQL optimization
- Explaining plan operations to users
- Quick sanity check of query structure

### What You Get
```json
{
  "facts": {
    "execution_plan": "...",
    "plan_details": [
      {
        "operation": "SELECT STATEMENT",
        "cost": 450,
        "cardinality": 1000
      },
      {
        "operation": "INDEX RANGE SCAN",
        "object_name": "IDX_STATUS",
        "cost": 50
      }
    ],
    "summary": {
      "mode": "plan_only",
      "operations": 3,
      "total_cost": 450
    }
  }
}
```

### Example Questions
- "What does this execution plan mean?"
- "Explain INDEX SKIP SCAN"
- "Why is there a NESTED LOOP?"
- "Show me how the query executes"

---

## 🚀 Use Case: Standard Mode (Default)

### When to Use
- Query optimization
- Performance troubleshooting
- Index recommendations
- Production readiness checks

### What You Get
```json
{
  "facts": {
    "execution_plan": "...",
    "plan_details": [...],
    "table_stats": [
      {
        "table": "ORDERS",
        "rows": 5000000,
        "size_mb": 1500,
        "last_analyzed": "2025-01-20"
      }
    ],
    "index_stats": [
      {
        "index": "IDX_STATUS",
        "columns": ["STATUS"],
        "unique": false,
        "selectivity": "low"
      }
    ],
    "column_stats": [...],
    "full_table_scans": [
      {
        "table": "ORDERS",
        "severity": "HIGH",
        "recommendation": "CREATE INDEX idx_status..."
      }
    ],
    "historical_context": {...}
  }
}
```

### Example Questions
- "Optimize this query"
- "Why is this slow?"
- "Recommend indexes"
- "Fix this performance issue"

---

## 💡 Code Examples

### Oracle - Plan Only (Fast)
```python
analyze_oracle_query(
    db_name="transformer_prod",
    sql_text="""
        SELECT o.order_id, o.total_amount
        FROM orders o
        WHERE o.status = 'PENDING'
    """,
    depth="plan_only"  # Fast analysis
)
```

**Response Time:** 0.3s
**Use Case:** User wants to understand how the query executes

---

### Oracle - Standard (Full)
```python
analyze_oracle_query(
    db_name="transformer_prod",
    sql_text="""
        SELECT o.order_id, o.total_amount
        FROM orders o
        WHERE o.status = 'PENDING'
    """,
    depth="standard"  # Full optimization analysis
)

# Or omit depth - standard is default
analyze_oracle_query(
    db_name="transformer_prod",
    sql_text="SELECT ..."
)
```

**Response Time:** 2s
**Use Case:** User wants to optimize the query

---

### MySQL - Plan Only (Fast)
```python
analyze_mysql_query(
    db_name="mysql_devdb03",
    sql_text="""
        SELECT * FROM customers
        WHERE country = 'US'
        AND status = 'ACTIVE'
    """,
    depth="plan_only"
)
```

**Response Time:** 0.3s
**Use Case:** Explain how MySQL executes this query

---

### MySQL - Standard (Full)
```python
analyze_mysql_query(
    db_name="mysql_devdb03",
    sql_text="""
        SELECT * FROM customers
        WHERE country = 'US'
        AND status = 'ACTIVE'
    """,
    depth="standard"
)
```

**Response Time:** 1-2s
**Use Case:** Get index recommendations and optimization

---

## 🤖 LLM Auto-Detection

The LLM automatically selects the appropriate depth based on user intent:

### Plan-Only Triggers
- "explain", "what does", "how does", "show me the plan"
- "what's a [operation name]"
- "why does it use [operation]"
- Educational/learning questions

### Standard Triggers (Default)
- "optimize", "make faster", "fix", "improve"
- "recommend", "suggest", "what indexes"
- "why is it slow", "performance issue"
- Production optimization requests

---

## ⚡ Performance Impact

### Large Query (50K+ characters)

**Without depth modes:**
- Analysis time: 3-5s
- Token usage: ~15,000
- Cost: High

**With plan_only mode:**
- Analysis time: 0.3s ✅ (10x faster)
- Token usage: ~500 ✅ (30x reduction)
- Cost: Minimal ✅

---

## 🔄 Workflow Integration

### Typical User Journey

1. **Initial Understanding** (plan_only)
   ```
   User: "What does this query do?"
   → depth="plan_only"
   → Fast explanation of execution flow
   ```

2. **Identify Issues** (plan_only)
   ```
   User: "Why is there a full table scan?"
   → depth="plan_only"
   → Explain the operation
   ```

3. **Optimization** (standard)
   ```
   User: "How do I fix it?"
   → depth="standard"
   → Full analysis with recommendations
   ```

---

## 📝 Best Practices

### ✅ DO Use plan_only when:
- Answering "what" or "how" questions
- Educational/learning scenarios
- Quick sanity checks
- Explaining plan operations

### ✅ DO Use standard when:
- User asks to "optimize" or "fix"
- Generating recommendations
- Production troubleshooting
- Comparing query performance

### ❌ DON'T Use plan_only when:
- User needs optimization
- Recommendations required
- Index suggestions needed
- Full context necessary

---

## 🐛 Troubleshooting

### "Plan shows full scan but I want recommendations"
**Solution:** Use `depth="standard"` to get diagnostics and DDL recommendations

### "Analysis is too slow for learning"
**Solution:** Use `depth="plan_only"` for instant plan explanations

### "Not enough data for optimization"
**Solution:** You used `depth="plan_only"`. Change to `depth="standard"`

---

## 📚 Related Documentation

- [workflows.md](workflows.md) - Complete workflow examples
- [troubleshooting.md](troubleshooting.md) - Error solutions
- [QUERY_OPTIMIZATION_IMPROVEMENTS.md](../../QUERY_OPTIMIZATION_IMPROVEMENTS.md) - Technical details

---

## 🎯 Summary

| Question Type | Depth Mode | Example |
|---------------|------------|---------|
| Educational | plan_only | "Explain this INDEX SKIP SCAN" |
| Optimization | standard | "Optimize this query" |
| Quick Check | plan_only | "Show me the execution plan" |
| Recommendations | standard | "What indexes should I add?" |

**Default:** When in doubt, use `depth="standard"` (or omit the parameter)
