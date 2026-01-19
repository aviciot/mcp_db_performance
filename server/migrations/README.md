# Database Migration Scripts

## Overview

Automated scripts to run SQL migrations against PostgreSQL database.

---

## Quick Start

### Windows:
```cmd
cd server\migrations
run_migrations.cmd
```

### Linux/Mac:
```bash
cd server/migrations
./run_migrations.sh docker
```

---

## Usage

### Windows (run_migrations.cmd)

**Default (Docker):**
```cmd
run_migrations.cmd
```

**Custom container:**
```cmd
run_migrations.cmd my_postgres_container
```

### Linux/Mac (run_migrations.sh)

**Docker mode (recommended):**
```bash
./run_migrations.sh docker
./run_migrations.sh docker omni_pg_db
```

**Local PostgreSQL:**
```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_USER=omni
export DB_PASSWORD=omni
export DB_NAME=omni
./run_migrations.sh
```

---

## Migration Files

Migrations run in alphabetical order:

```
000_initial_schema.sql
001_knowledge_base.sql
002_query_history.sql
003_feedback_system.sql
```

**Naming Convention:** `NNN_description.sql`
- `NNN` = sequential number (000, 001, 002, etc.)
- `description` = short name describing the migration

---

## Features

✅ **Automatic Discovery** - Finds all `.sql` files in migrations folder
✅ **Sequential Execution** - Runs in alphabetical order
✅ **Error Handling** - Stops on first error
✅ **Color Output** - Green for success, red for errors (Linux/Mac)
✅ **Table Verification** - Lists created tables after migration
✅ **Docker Support** - Works with Docker containers
✅ **Local Support** - Works with local PostgreSQL (Linux/Mac)

---

## Example Output

```
========================================
Migration Runner
========================================
Container: omni_pg_db
Database: omni
Schema: mcp_performance
========================================

Found 3 migration(s) to run

Running migration: 001_knowledge_base.sql ...
[SUCCESS] 001_knowledge_base.sql

Running migration: 002_query_history.sql ...
[SUCCESS] 002_query_history.sql

Running migration: 003_feedback_system.sql ...
[SUCCESS] 003_feedback_system.sql

========================================
[SUCCESS] All migrations completed!
  Success: 3
========================================

Verifying tables...
                    List of relations
     Schema      |           Name            | Type  | Owner
-----------------+---------------------------+-------+-------
 mcp_performance | feedback_blocked_sessions | table | omni
 mcp_performance | feedback_submissions      | table | omni
 mcp_performance | table_knowledge           | table | omni
```

---

## Troubleshooting

### Error: "Docker container not running"

**Solution:**
```bash
docker ps | grep postgres
# Find your container name, then:
./run_migrations.sh docker YOUR_CONTAINER_NAME
```

### Error: "psql command not found" (Linux/Mac local mode)

**Solution:**
Install PostgreSQL client or use Docker mode:
```bash
# Ubuntu/Debian
sudo apt-get install postgresql-client

# Or use Docker mode instead
./run_migrations.sh docker
```

### Error: "Migration failed"

**Solution:**
1. Check the error message for SQL syntax errors
2. Verify schema exists: `docker exec omni_pg_db psql -U omni -d omni -c "CREATE SCHEMA IF NOT EXISTS mcp_performance;"`
3. Check file permissions
4. Review migration SQL for errors

### Already applied migrations

**Safe to re-run:**
All migrations use `CREATE TABLE IF NOT EXISTS` and `CREATE OR REPLACE` for functions/views, so they're safe to run multiple times.

**Manual cleanup (if needed):**
```sql
-- Drop and recreate
DROP SCHEMA mcp_performance CASCADE;
CREATE SCHEMA mcp_performance;
```

---

## Adding New Migrations

### Step 1: Create SQL File

Create new file with next number:
```bash
# Find highest number
ls -1 *.sql | tail -1
# If last is 003_, create 004_

# Create new migration
touch 004_my_new_feature.sql
```

### Step 2: Write SQL

```sql
-- ============================================================================
-- Description: My new feature
-- ============================================================================

CREATE TABLE IF NOT EXISTS mcp_performance.my_new_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_my_table_name ON mcp_performance.my_new_table(name);

-- Add comments
COMMENT ON TABLE mcp_performance.my_new_table IS 'Description of what this table does';
```

### Step 3: Test

```bash
# Dry run (check syntax)
docker exec omni_pg_db psql -U omni -d omni --echo-all --dry-run < 004_my_new_feature.sql

# Run migration
./run_migrations.sh docker
```

---

## Best Practices

### DO:

✅ Use `IF NOT EXISTS` for tables/indexes
✅ Use `CREATE OR REPLACE` for functions/views
✅ Add comments to tables and columns
✅ Include rollback instructions in comments
✅ Test on dev database first
✅ Use sequential numbering
✅ Keep migrations idempotent (safe to re-run)

### DON'T:

❌ Don't use `DROP TABLE` without checking
❌ Don't mix DDL and DML in same migration
❌ Don't hardcode passwords or sensitive data
❌ Don't skip numbers in sequence
❌ Don't modify existing migration files after they're run

---

## Schema Structure

All tables go into `mcp_performance` schema:

```
mcp_performance/
├── table_knowledge          # Business context cache
├── table_relationships      # FK relationships
├── query_history            # Historical query data
├── feedback_submissions     # User feedback
├── feedback_blocked_sessions # Rate limiting
└── feedback_stats (view)    # Statistics dashboard
```

---

## CI/CD Integration

### GitHub Actions

```yaml
- name: Run Database Migrations
  run: |
    cd server/migrations
    chmod +x run_migrations.sh
    ./run_migrations.sh docker
```

### Docker Compose

Migrations run automatically on container init:

```yaml
postgres:
  volumes:
    - ./server/migrations:/docker-entrypoint-initdb.d/
```

---

## Manual Execution

If you prefer to run migrations manually:

### Via Docker:
```bash
docker exec -i omni_pg_db psql -U omni -d omni < 003_feedback_system.sql
```

### Via psql:
```bash
psql -h localhost -U omni -d omni -f 003_feedback_system.sql
```

### Via DBeaver/pgAdmin:
1. Open SQL editor
2. Paste migration content
3. Execute

---

## Migration History

| File | Description | Date Added |
|------|-------------|------------|
| 001_knowledge_base.sql | Business context tables | 2026-01-15 |
| 002_query_history.sql | Query tracking | 2026-01-16 |
| 003_feedback_system.sql | User feedback system | 2026-01-19 |

---

## Support

**Check migration status:**
```bash
docker exec omni_pg_db psql -U omni -d omni -c "\dt mcp_performance.*"
```

**View table details:**
```bash
docker exec omni_pg_db psql -U omni -d omni -c "\d+ mcp_performance.feedback_submissions"
```

**Check logs:**
```bash
docker logs omni_pg_db --tail 50
```

---

**Status:** ✅ Ready to use
