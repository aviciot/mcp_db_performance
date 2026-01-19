# Feedback System - Database Setup Complete ✅

## Summary

The feedback system is **fully operational** with PostgreSQL database tables created and ready to use.

---

## ✅ Completed

### 1. Database Tables Created

**Schema:** `mcp_performance`

**Tables:**
- ✅ `feedback_submissions` - Stores all feedback submissions
- ✅ `feedback_blocked_sessions` - Tracks blocked users/teams
- ✅ `feedback_stats` (view) - Real-time statistics

**Migration Applied:**
```bash
Database: omni_pg_db
User: omni
Schema: mcp_performance
Status: ✅ Tables created successfully
```

### 2. Feedback System Running

**Status:** ✅ **OPERATIONAL**

**Components Loaded:**
```
✅ tools.feedback_context
✅ tools.feedback_quality
✅ tools.feedback_safety
✅ tools.feedback_safety_db
✅ tools.mcp_feedback
✅ prompts.feedback_improvement
✅ resources.mcp_welcome
✅ Session Context Middleware enabled
```

**Tools Available:**
- ✅ `report_mcp_issue_interactive`
- ✅ `improve_my_feedback`
- ✅ `search_mcp_issues`

### 3. Session Tracking Working

**Example from logs:**
```
[AUTH] ✅ Authenticated client: client_1 | session: fp_f40ad63b36d5f... → /mcp
```

Session IDs are being extracted and tracked properly.

### 4. GitHub Integration Configured

**Token:** ✅ Configured in `.env`
```
GITHUB_TOKEN=github_pat_11A5SKSNA0r5zezcArmDtR_hhC...
GITHUB_REPO=aviciot/mcp_db_performance
```

---

## Current Configuration

### Storage Mode: **In-Memory** (Default)

The system is currently using **in-memory storage** for rate limiting and tracking. This means:
- ✅ Fully functional for testing and development
- ⚠️ Data is lost on server restart
- ✅ Zero database dependencies
- ✅ Faster performance

### Database Tables: **Ready but Not Integrated**

The PostgreSQL tables are created and ready, but the system needs to be switched to use them. See "Switching to Database Storage" below.

---

## Database Schema

### Table: `feedback_submissions`

Stores all feedback submissions with metadata.

```sql
Column               | Type                        | Description
---------------------+-----------------------------+----------------------------------------
id                   | SERIAL PRIMARY KEY          | Auto-increment ID
session_id           | VARCHAR(64)                 | User session identifier
client_id            | VARCHAR(64)                 | Team/organization identifier
submission_type      | VARCHAR(20)                 | bug, feature, improvement
title                | TEXT                        | Issue title
description          | TEXT                        | Issue description
content_hash         | VARCHAR(32)                 | MD5 hash for duplicate detection
quality_score        | NUMERIC(3,1)                | Quality score 0.0-10.0
github_issue_number  | INTEGER                     | GitHub issue number (if created)
github_issue_url     | TEXT                        | GitHub issue URL
status               | VARCHAR(20)                 | submitted, created, failed
created_at           | TIMESTAMP WITH TIME ZONE    | Submission timestamp
```

**Indexes:**
- `idx_feedback_session_created` - Fast session lookup
- `idx_feedback_client_created` - Fast client lookup
- `idx_feedback_content_hash` - Fast duplicate detection
- `idx_feedback_created_at` - Time-based queries

### Table: `feedback_blocked_sessions`

Tracks temporarily blocked users/teams.

```sql
Column          | Type                        | Description
----------------+-----------------------------+----------------------------------------
id              | SERIAL PRIMARY KEY          | Auto-increment ID
identifier      | VARCHAR(64) UNIQUE          | Session ID or Client ID
identifier_type | VARCHAR(10)                 | 'session' or 'client'
blocked_at      | TIMESTAMP WITH TIME ZONE    | When blocked
unblock_at      | TIMESTAMP WITH TIME ZONE    | Auto-unblock time
reason          | TEXT                        | Block reason
```

**Indexes:**
- `idx_blocked_identifier` - Fast block lookups
- `idx_blocked_unblock_at` - Expired block cleanup

### View: `feedback_stats`

Real-time statistics dashboard.

```sql
Column                 | Description
-----------------------+--------------------------------------------------
total_submissions      | Total submissions all-time
last_24h               | Submissions in last 24 hours
last_hour              | Submissions in last hour
unique_sessions        | Unique users
unique_clients         | Unique teams/organizations
avg_quality_score      | Average quality score
bug_count              | Total bug reports
feature_count          | Total feature requests
improvement_count      | Total improvement suggestions
successfully_created   | GitHub issues created successfully
failed_submissions     | Failed submissions
```

### Function: `cleanup_old_feedback()`

Removes submissions older than 30 days and expired blocks.

```sql
SELECT mcp_performance.cleanup_old_feedback();
-- Returns: number of submissions deleted
```

---

## Switching to Database Storage

To switch from in-memory to database-backed storage:

### Option 1: Automatic Initialization (Recommended)

Add to `server.py` startup:

```python
# After knowledge_db initialization
from tools.feedback_safety_db import initialize_safety_manager

# Get the same connection pool as knowledge_db
try:
    from knowledge_db import get_db
    db = get_db()
    if db and db.pool:
        initialize_safety_manager(db.pool)
        logger.info("✅ Feedback safety using PostgreSQL")
    else:
        initialize_safety_manager()
        logger.warning("⚠️ Feedback safety using in-memory (DB unavailable)")
except Exception as e:
    logger.error(f"Failed to initialize feedback safety with DB: {e}")
    initialize_safety_manager()
```

### Option 2: Manual Switching

1. **Update `mcp_feedback.py`:**

   Replace the import at the top:
   ```python
   # OLD:
   from tools.feedback_safety import get_safety_manager

   # NEW:
   from tools.feedback_safety_db import get_safety_manager
   ```

2. **Restart server:**
   ```bash
   docker-compose restart
   ```

3. **Verify in logs:**
   ```
   ✅ Feedback safety using PostgreSQL for persistent storage
   ```

---

## Testing Database Integration

### Test 1: Check Tables
```bash
docker exec omni_pg_db psql -U omni -d omni -c "\dt mcp_performance.feedback*"
```

**Expected:**
```
feedback_blocked_sessions | table
feedback_submissions      | table
```

### Test 2: Check Stats View
```bash
docker exec omni_pg_db psql -U omni -d omni -c "SELECT * FROM mcp_performance.feedback_stats;"
```

**Expected:**
```
total_submissions | last_24h | last_hour | ...
------------------+----------+-----------+-----
                0 |        0 |         0 | ...
```

### Test 3: Submit Feedback (via Claude Desktop)

```
Report a test bug:
- Title: "Test feedback system"
- Description: "Testing database storage"
- Type: bug
```

### Test 4: Verify Submission in Database
```bash
docker exec omni_pg_db psql -U omni -d omni -c "SELECT session_id, submission_type, title, created_at FROM mcp_performance.feedback_submissions ORDER BY created_at DESC LIMIT 5;"
```

**Expected:** See your test submission

### Test 5: Check Stats After Submission
```bash
docker exec omni_pg_db psql -U omni -d omni -c "SELECT total_submissions, unique_sessions, bug_count FROM mcp_performance.feedback_stats;"
```

**Expected:**
```
total_submissions | unique_sessions | bug_count
------------------+-----------------+-----------
                1 |               1 |         1
```

---

## Monitoring Queries

### Active Submissions (Last Hour)
```sql
SELECT
    session_id,
    client_id,
    submission_type,
    title,
    quality_score,
    status,
    created_at
FROM mcp_performance.feedback_submissions
WHERE created_at > NOW() - INTERVAL '1 hour'
ORDER BY created_at DESC;
```

### Rate Limit Usage by Client
```sql
SELECT
    client_id,
    COUNT(*) as submissions_today,
    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as last_hour,
    AVG(quality_score) as avg_quality
FROM mcp_performance.feedback_submissions
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY client_id
ORDER BY submissions_today DESC;
```

### Currently Blocked Sessions
```sql
SELECT
    identifier,
    identifier_type,
    blocked_at,
    unblock_at,
    EXTRACT(EPOCH FROM (unblock_at - NOW()))/3600 as hours_remaining,
    reason
FROM mcp_performance.feedback_blocked_sessions
WHERE unblock_at > NOW()
ORDER BY unblock_at;
```

### Quality Score Distribution
```sql
SELECT
    FLOOR(quality_score) as score_range,
    COUNT(*) as count,
    ROUND(AVG(quality_score), 1) as avg_score
FROM mcp_performance.feedback_submissions
WHERE quality_score IS NOT NULL
GROUP BY FLOOR(quality_score)
ORDER BY score_range;
```

---

## Maintenance

### Cleanup Old Data (Manual)
```sql
SELECT mcp_performance.cleanup_old_feedback();
-- Removes submissions older than 30 days
```

### Setup Automatic Cleanup (Optional)

**Using PostgreSQL cron extension:**
```sql
-- Run cleanup daily at 2 AM
SELECT cron.schedule('cleanup-feedback', '0 2 * * *',
    'SELECT mcp_performance.cleanup_old_feedback();'
);
```

**Or use a system cron job:**
```bash
# Add to crontab
0 2 * * * docker exec omni_pg_db psql -U omni -d omni -c "SELECT mcp_performance.cleanup_old_feedback();" >> /var/log/feedback_cleanup.log 2>&1
```

---

## Current Status Summary

| Component | Status | Notes |
|-----------|--------|-------|
| PostgreSQL Tables | ✅ Created | Ready in `mcp_performance` schema |
| In-Memory Storage | ✅ Active | Currently in use |
| Database Storage | ⏸️ Ready | Code exists, not integrated yet |
| Session Tracking | ✅ Working | Fingerprints being generated |
| GitHub Integration | ✅ Configured | Token set in `.env` |
| Feedback Tools | ✅ Registered | All 3 tools available |
| Welcome Resources | ✅ Available | Documentation accessible |
| Rate Limiting | ✅ Working | 3/hour, 10/day per user |
| Quality Checking | ✅ Working | Scoring 0-10 |

---

## Next Steps

### For Testing (Current Setup is Fine)
- ✅ System is fully functional
- ✅ Test all features with in-memory storage
- ✅ Data resets on container restart (good for testing)

### For Production (Switch to Database)
1. Follow "Switching to Database Storage" above
2. Test database integration
3. Monitor `feedback_stats` view
4. Setup automatic cleanup (optional)
5. Monitor rate limits and blocks

---

## Rollback Instructions

If database integration causes issues, rollback to in-memory:

```python
# In mcp_feedback.py, change import back to:
from tools.feedback_safety import get_safety_manager

# Restart container
docker-compose restart
```

---

## Files Reference

**Database Files:**
- `server/migrations/003_feedback_system.sql` - Migration script
- `server/tools/feedback_safety_db.py` - Database-backed implementation

**Current Implementation:**
- `server/tools/feedback_safety.py` - In-memory implementation (active)
- `server/tools/feedback_context.py` - Session tracking
- `server/tools/feedback_quality.py` - Quality analysis
- `server/tools/mcp_feedback.py` - MCP tools

**Documentation:**
- `FEEDBACK_SYSTEM_README.md` - Complete guide
- `FEEDBACK_TESTING_GUIDE.md` - Testing procedures
- `QUICK_SETUP_GUIDE.md` - 15-minute setup for other MCPs
- `FEEDBACK_DATABASE_SETUP.md` - This file

---

## Support

**Check logs:**
```bash
docker logs mcp_db_performance --tail 100 | grep -i feedback
```

**Verify database connection:**
```bash
docker exec omni_pg_db psql -U omni -d omni -c "SELECT version();"
```

**Test feedback tools:**
Via Claude Desktop, ask:
```
Can you help me report a bug?
```

---

**Status:** ✅ **READY FOR USE**

**Current Mode:** In-Memory (Perfect for Testing)

**Database:** Ready for Production Switch
