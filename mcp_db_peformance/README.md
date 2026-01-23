# Oracle & MySQL Business Intelligence MCP Server

**AI-powered SQL business logic analysis with intelligent caching for instant insights**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Database: Oracle](https://img.shields.io/badge/Database-Oracle%2011g%2B-red)](https://www.oracle.com/database/)
[![Database: MySQL](https://img.shields.io/badge/Database-MySQL%208.0%2B-blue)](https://www.mysql.com/)
[![MCP: Protocol](https://img.shields.io/badge/MCP-Protocol-green)](https://modelcontextprotocol.io/)

---

## 🎯 What It Does

Transform complex SQL queries into clear business insights using AI-powered analysis. This MCP server automatically discovers table relationships, infers business logic, and explains what your queries actually do - perfect for onboarding, documentation, and understanding legacy systems.

### Key Features

- 🧠 **AI Business Logic Explanation** - Understand query purpose in plain English
- 🔗 **Automatic Relationship Discovery** - Follows foreign keys up to N levels deep
- ⚡ **PostgreSQL Intelligent Caching** - 93% faster subsequent queries (0.7s vs 10s)
- 📊 **ER Diagram Generation** - Visual Mermaid diagrams of table relationships
- 🎯 **Entity & Domain Classification** - Infers business context from table/column names
- 📈 **Performance Analysis** - Deep SQL optimization with execution plan analysis
- 🔒 **Multi-Layer Security** - Blocks dangerous operations before execution
- 🐬 **MySQL + Oracle Support** - Native support for both database engines
- ⚡ **✨ NEW: Analysis Depth Modes** - Fast plan-only (0.3s) or full optimization (Jan 2025)
- 🎯 **✨ NEW: Smart Token Optimization** - 80% reduction with output minimization (Jan 2025)
- 📏 **✨ NEW: Auto-Preset Adjustment** - Handles large queries intelligently (Jan 2025)
- 🔐 **✨ NEW: Role-Based Access Control** - Secure DBA operational tools with RBAC (Jan 2025)

---

## 🚀 Quick Start

### Automated Deployment (Recommended)

```bash
git clone https://github.com/aviciot/mcp_db_performance.git
cd mcp_db_peformance

# Edit configuration files
cp server/config/settings.template.yaml server/config/settings.yaml
# Edit settings.yaml with your database credentials

# Run automated deployment script
chmod +x deploy.sh
./deploy.sh
```

The `deploy.sh` script will:
- ✅ Check Docker is running
- ✅ Create required Docker networks
- ✅ Deploy PostgreSQL cache database
- ✅ Deploy MCP server
- ✅ Initialize database schema
- ✅ Run health checks

### Manual Deployment

```bash
# 1. Start PostgreSQL cache database
cd ../pg_mcp
docker-compose up -d

# 2. Start MCP server
cd ../mcp_db_peformance
docker-compose up -d

# 3. Initialize schema (one-time)
docker exec mcp_db_performance python test-scripts/run_complete_init.py
```

### 3. Connect Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "database-performance": {
      "command": "docker",
      "args": ["exec", "-i", "mcp_db_performance", "python", "-m", "mcp_app"],
      "env": {}
    }
  }
}
```

Restart Claude Desktop and start asking questions about your SQL!

---

## 💡 Example Use Cases

### Business Logic Explanation

```
User: "Explain what this query does:

SELECT t.payment_id, t.amount, r.retry_count, c.challenge_status
FROM gateway_transactions t
LEFT JOIN gtw_trans_retry r ON t.payment_id = r.payment_id
LEFT JOIN gtw_trans_3ds_challenge c ON t.payment_id = c.payment_id
WHERE t.processing_date = '2024-01-01'"

Response:
📊 Business Purpose: Payment transaction processing with retry tracking and 3DS authentication

📦 Tables Analyzed:
• GATEWAY_TRANSACTIONS (45M rows) - Main payment processing table
• GTW_TRANS_RETRY (2.3M rows) - Retry attempt tracking
• GTW_TRANS_3DS_CHALLENGE (1.8M rows) - 3D Secure authentication

🔗 Relationships:
• GTW_TRANS_RETRY → GATEWAY_TRANSACTIONS (FK: payment_id)
• GTW_TRANS_3DS_CHALLENGE → GATEWAY_TRANSACTIONS (FK: payment_id)

🎯 Domain: Payment Processing | Entity: Transaction
⚡ Performance: 742ms (cached)
```

### Performance Analysis

```
User: "Why is this query slow?

SELECT * FROM orders WHERE customer_id = 12345"

Response:
🚨 CRITICAL Performance Issue Detected

Problem: Full table scan on ORDERS table (45M rows)
Cost: 8,234 | Estimated Time: 45+ seconds

Root Cause:
• 3 indexes exist but not being used
• Likely causes: Implicit type conversion, function on column

Recommendation:
CREATE INDEX idx_orders_customer ON orders(customer_id);

Estimated Improvement: 90-99% reduction in execution time
```

---

## ✨ Recent Features (January 2025)

### 🎯 Analysis Depth Modes
Choose between fast plan-only analysis or full optimization:

```python
# Fast plan explanation (0.3s, educational)
analyze_oracle_query(db="prod", sql="SELECT...", depth="plan_only")

# Full optimization analysis (1-3s, production-ready)
analyze_oracle_query(db="prod", sql="SELECT...", depth="standard")  # default
```

**Benefits:**
- ⚡ **10x faster** for educational queries
- 💰 **96% token reduction** (500 vs 13,000 tokens)
- 🎓 Perfect for learning execution plans
- 🚀 Full context when optimizing

**Documentation:** See `server/knowledge_base/depth_modes.md`

---

### 🎯 Smart Token Optimization
Output minimization reduces token usage by 80% without losing optimization context:

**Before:** ~63,000 tokens per analysis
**After:** ~12,700 tokens per analysis

- Removes NULL/empty fields from execution plans
- Merges related data (indexes + columns)
- Converts raw statistics to actionable insights
- Keeps all essential optimization data

**Impact:** Lower costs, faster analysis, same quality

---

### 📏 Auto-Preset Adjustment for Large Queries
Automatically handles queries of any size:

| Query Size | Action | Metadata Depth |
|------------|--------|----------------|
| < 10KB | Use configured preset | Full/Compact/Minimal |
| 10-50KB | Auto-switch to compact | Tables + Indexes |
| > 50KB | Auto-switch to minimal | Essential only |

**Benefits:**
- ✅ UNION queries with 100+ columns work perfectly
- ✅ Full SQL always preserved (never truncated)
- ✅ User notified when preset adjusts
- ✅ Handles 50K+ character queries

**Documentation:** See `QUERY_OPTIMIZATION_IMPROVEMENTS.md`

---

### 🔐 Role-Based Access Control (RBAC)
Secure, role-based access to DBA operational tools:

**New Tools:**
- 👤 **`who_am_i`** - Shows your identity, role, and capabilities
- 📋 **`list_my_tools`** - Lists all tools available to your role
- 🔧 **`get_active_sessions`** - List database connections (admin/dba only)
- 🔒 **`get_lock_info`** - Show blocking/locking info (admin/dba only)
- 👥 **`get_db_users`** - List users and permissions (admin/dba only)
- 📚 **`show_dba_tools`** - Comprehensive DBA tools guide (admin/dba only)

**Role Matrix:**

| Role | Query Analysis | Feedback | DBA Tools | Admin Tools |
|------|---------------|----------|-----------|-------------|
| Admin | ✅ | ✅ | ✅ | ✅ |
| DBA | ✅ | ✅ | ✅ | ❌ |
| User | ✅ | ✅ | ❌ | ❌ |

**Key Features:**
- 🔒 Decorator-based access control (`@require_roles(['admin', 'dba'])`)
- 🛡️ All DBA tools are read-only (SELECT queries only)
- 📝 Access attempts logged for audit trail
- 💡 Helpful error messages guide users
- 🎯 Welcome message shows identity and capabilities

**Example:**
```python
# Check your identity and access
who_am_i()
# Response: "Welcome, admin! You have full admin access..."

# List active sessions (admin/dba only)
get_active_sessions(db_name='transformer_prod', limit=10)

# Show DBA tools documentation
show_dba_tools()
```

**Configuration:**
```yaml
# server/config/settings.yaml
security:
  api_keys:
    - name: "admin"        # Full access
      token: "admin-token"
    - name: "dba"          # Query analysis + DBA tools
      token: "dba-token"
    - name: "analyst_team" # Query analysis only
      token: "analyst-token"
```

**Benefits:**
- ✅ Secure operational visibility for DBAs
- ✅ Users discover what they can access
- ✅ Admin controls via simple role assignment
- ✅ Production-ready with audit logging

**Documentation:** See `ROLE_BASED_ACCESS_IMPLEMENTATION.md`

---

## 🛠️ Core Tools

### 1. `explain_business_logic` ⭐ Primary Tool

**What it does:** Analyzes SQL queries to explain business logic and relationships

**Parameters:**
- `db_name` (required) - Database name from settings.yaml
- `sql_text` (required) - SQL query to analyze
- `follow_relationships` (optional, default: true) - Follow FK relationships
- `max_depth` (optional, default: 2) - Relationship depth to traverse

**Returns:**
- Business purpose explanation
- Table metadata with row counts and comments
- Column details with inferred semantics
- Foreign key relationships (recursive)
- Mermaid ER diagram
- Entity and domain classifications
- Cache statistics

**Performance:**
- First run: ~10 seconds (collects from database + caches)
- Cached run: ~0.7 seconds (93% faster)
- Cache TTL: 7 days

**Example:**
```
explain_business_logic("production_db", "SELECT * FROM customer_orders WHERE order_date > '2024-01-01'")
```

---

### 2. `analyze_full_sql_context`

**What it does:** Deep performance analysis with execution plans and optimization recommendations

**Parameters:**
- `db_name` (required) - Database name
- `sql_text` (required) - SQL query to analyze

**Returns:**
- Execution plan with costs and cardinality
- Table and index statistics
- Performance issue diagnostics (full scans, cartesian products)
- Historical comparison (regression detection)
- Visual plan tree with emoji warnings
- Optimization recommendations

**Example:**
```
analyze_full_sql_context("production_db", "SELECT * FROM orders o JOIN customers c ON o.customer_id = c.id WHERE o.amount > 1000")
```

---

### 3. `compare_query_plans`

**What it does:** Side-by-side comparison of original vs optimized query

**Parameters:**
- `db_name` (required) - Database name
- `original_sql` (required) - Original query
- `improved_sql` (required) - Optimized query

**Returns:**
- Cost difference and % improvement
- Access method changes (full scan → index scan)
- Cardinality estimation differences
- Plan structure comparison

---

### 4. `list_available_databases`

**What it does:** Lists all configured database connections with status

**Returns:**
- Database names and types (Oracle/MySQL)
- Connection status (connected/error)
- Database version and instance info

---

## 📊 PostgreSQL Caching Architecture

### How It Works

```
First Query:
┌─────────┐     ┌──────────────┐     ┌────────────┐
│ Claude  │────>│  MCP Server  │────>│   Oracle   │
└─────────┘     │              │     │            │
                │  10 seconds  │     └────────────┘
                │              │
                │              │     ┌────────────┐
                │              │────>│ PostgreSQL │
                └──────────────┘     │   Cache    │
                                     └────────────┘

Subsequent Queries (same tables):
┌─────────┐     ┌──────────────┐     ┌────────────┐
│ Claude  │────>│  MCP Server  │────>│ PostgreSQL │
└─────────┘     │              │     │   Cache    │
                │  0.7 seconds │     └────────────┘
                └──────────────┘
                     93% faster!
```

### Cached Data

- **Table metadata**: Row counts, comments, partition info
- **Column details**: Names, types, nullability, comments
- **Primary keys**: Indexed columns
- **Foreign keys**: Relationships between tables
- **Business semantics**: Inferred entity types and domains
- **TTL**: 7 days (configurable)

### Cache Management

All caching is automatic - no manual intervention needed:
- ✅ Automatic cache population on first query
- ✅ Automatic TTL expiration (7 days)
- ✅ Automatic cache refresh when stale
- ✅ Admin can override with custom documentation

---

## ⚙️ Configuration

### Database Connections

Edit `server/config/settings.yaml`:

```yaml
database_presets:
  # Oracle Database
  production_oracle:
    type: oracle
    user: app_user
    password: your_password
    dsn: hostname:1521/service_name

  # MySQL Database
  production_mysql:
    type: mysql
    host: mysql.example.com
    port: 3306
    user: app_user
    password: your_password
    database: application_db
```

### PostgreSQL Cache

Edit `.env` file:

```bash
KNOWLEDGE_DB_HOST=omni_db
KNOWLEDGE_DB_PORT=5432
KNOWLEDGE_DB_NAME=omni
KNOWLEDGE_DB_USER=omni
KNOWLEDGE_DB_PASSWORD=omni
KNOWLEDGE_DB_SCHEMA=mcp_performance
```

---

## 🔐 Security

### What's Protected

This MCP server is **read-only** and **safe by design**:

- ✅ Only uses EXPLAIN PLAN (never executes user SQL)
- ✅ Only queries metadata views (information_schema, ALL_* views)
- ✅ Blocks all write operations (INSERT, UPDATE, DELETE, DROP, etc.)
- ✅ Blocks dangerous operations (GRANT, REVOKE, SHUTDOWN, etc.)
- ✅ Validates query complexity (max depth, length limits)
- ✅ Zero possibility of data modification

### Multi-Layer Defense

1. **LLM Level**: Tool descriptions include prominent security warnings
2. **Tool Level**: Pre-validates SQL before any database interaction
3. **Collector Level**: Deep validation with 25+ blocked keywords

**Blocked operations:** INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, GRANT, REVOKE, TRUNCATE, SHUTDOWN, KILL, EXECUTE, COMMIT, ROLLBACK, LOCK/UNLOCK, SELECT INTO, INTO OUTFILE

---

## 🔧 Required Permissions

### Oracle Minimum Permissions

```sql
-- Core metadata access
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

-- For EXPLAIN PLAN
GRANT INSERT, DELETE ON PLAN_TABLE TO your_user;
```

### MySQL Minimum Permissions

```sql
-- Core metadata access
GRANT SELECT ON information_schema.TABLES TO 'your_user'@'%';
GRANT SELECT ON information_schema.STATISTICS TO 'your_user'@'%';
GRANT SELECT ON information_schema.COLUMNS TO 'your_user'@'%';
GRANT SELECT ON your_database.* TO 'your_user'@'%';

-- For index usage statistics (recommended)
GRANT SELECT ON performance_schema.table_io_waits_summary_by_index_usage TO 'your_user'@'%';
```

---

## 📚 Detailed Documentation

For comprehensive technical details, see [FEATURES_DETAILED.md](FEATURES_DETAILED.md):

- **Business Logic Analysis** - Deep dive into SQL parsing, metadata collection, and semantic inference
- **PostgreSQL Caching System** - Architecture, schema design, and optimization strategies
- **Performance Monitoring** - Database health metrics and top queries analysis
- **Output Filtering Presets** - How to control response size and token usage
- **Future Improvements** - Roadmap and planned enhancements

---

## 📈 Performance Benchmarks

### Business Logic Analysis

| Scenario | First Run | Cached Run | Improvement |
|----------|-----------|------------|-------------|
| Single table query | 2.1s | 0.3s | 85% faster |
| 3-table join | 5.8s | 0.6s | 90% faster |
| Complex query (10+ tables) | 12.4s | 0.9s | 93% faster |

### Cache Operations

| Operation | Time | Throughput |
|-----------|------|------------|
| Single table lookup | 5ms | 200 ops/sec |
| Batch lookup (10 tables) | 9ms | 1,111 ops/sec |
| Save table metadata | 12ms | 83 ops/sec |
| Batch save (10 tables) | 25ms | 400 ops/sec |

---

## 🧪 Testing

### Verify Installation

```bash
# Check services are running
docker ps | grep -E "(mcp_db_performance|omni_pg_db)"

# Test PostgreSQL connection
docker exec mcp_db_performance python -c "from knowledge_db import get_knowledge_db; import asyncio; db = get_knowledge_db(); print('Connected:', asyncio.run(db.connect()))"

# Test database connection
docker exec mcp_db_performance python -m mcp_app
```

### Test in Claude Desktop

```
User: "List available databases"

Expected: Should show all configured databases with connection status

User: "Explain the business logic of this query:
SELECT * FROM customer_orders WHERE order_date > '2024-01-01'"

Expected: Should return business analysis with table relationships and domain classification
```

---

## 📁 Project Structure

```
mcp_db_peformance/
├── server/
│   ├── tools/                    # MCP tool implementations
│   │   ├── oracle_explain_logic.py   # Business logic analysis
│   │   ├── oracle_analysis.py         # Performance analysis
│   │   └── mysql_analysis.py          # MySQL support
│   ├── knowledge_db.py           # PostgreSQL cache connector
│   ├── config.py                 # Configuration management
│   ├── server.py                 # MCP server
│   ├── mcp_app.py               # FastMCP application
│   ├── test-scripts/
│   │   └── run_complete_init.py  # Schema initialization
│   └── migrations/
│       └── 000_complete_schema_init.sql
├── docker-compose.yml
├── .env
└── README.md

pg_mcp/                           # PostgreSQL cache database
├── docker-compose.yml
└── postgres-init/
    └── init.sql
```

---

## 📊 Architecture

```
┌─────────────────┐
│  Claude Desktop │
│   (MCP Client)  │
└────────┬────────┘
         │
         │ MCP Protocol
         ▼
┌─────────────────┐      ┌──────────────┐
│  MCP Server     │─────>│   Oracle     │
│  (FastMCP)      │      │   Database   │
└────────┬────────┘      └──────────────┘
         │
         │ Cache Layer
         ▼
┌─────────────────┐      ┌──────────────┐
│  PostgreSQL     │      │    MySQL     │
│  Cache (omni)   │      │   Database   │
└─────────────────┘      └──────────────┘
```

---

## 🛠️ Troubleshooting

### Common Issues

**"Database connection failed"**
- Check credentials in `server/config/settings.yaml`
- Verify database is accessible from Docker container
- Test with: `docker exec mcp_db_performance ping <db_host>`

**"Cache not working"**
- Verify PostgreSQL is running: `docker ps | grep omni_pg_db`
- Check connection: `docker logs mcp_db_performance | grep PostgreSQL`
- Re-run init script: `docker exec mcp_db_performance python test-scripts/run_complete_init.py`

**"ORA-00942: table or view does not exist"**
- Grant required Oracle permissions (see above)
- Check user has SELECT on ALL_* views

**"Slow performance"**
- First query always slower (cache population)
- Subsequent queries should be sub-second
- Check PostgreSQL connection latency

---

## 📚 Additional Documentation

- [FEATURES_DETAILED.md](FEATURES_DETAILED.md) - In-depth technical documentation
- [POSTGRESQL_COMPREHENSIVE_AUDIT_2026-01-16.md](POSTGRESQL_COMPREHENSIVE_AUDIT_2026-01-16.md) - PostgreSQL audit report with test results
- `server/knowledge_base/` - MCP tool documentation
- `to_delete/` - Obsolete files ready for deletion (includes README)

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📜 License

MIT License - see [LICENSE](LICENSE) file for details

---

## 👤 Author

**Avi Cohen**
📧 Email: aviciot@gmail.com
🐙 GitHub: [@aviciot](https://github.com/aviciot)

---

## 🙏 Acknowledgments

- Built with [FastMCP](https://github.com/jlowin/fastmcp)
- Powered by [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- Database drivers: [cx_Oracle](https://oracle.github.io/python-cx_Oracle/), [PyMySQL](https://github.com/PyMySQL/PyMySQL), [asyncpg](https://github.com/MagicStack/asyncpg)

---

<div align="center">

**⭐ Star this repo if you find it useful! ⭐**

[Report Bug](https://github.com/aviciot/mcp_db_performance/issues) · [Request Feature](https://github.com/aviciot/mcp_db_performance/issues)

</div>
