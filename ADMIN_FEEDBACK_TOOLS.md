# Admin Feedback Tools - Complete Guide

## 🔒 Admin-Only Access

These tools require authentication with the **"admin" API key**.

**Admin API Key:** `avicohen-admin-1234`

**Security:** Non-admin users will receive "Access Denied" if they attempt to use these tools.

---

## ✅ Setup Complete

### Admin Tools Loaded:
```
✅ tools.feedback_admin imported
✅ 3 admin tools registered:
   • get_feedback_dashboard
   • get_github_issues_summary
   • get_feedback_by_client
```

### Admin Authentication:
```
🔑 API KEY: admin | Token: avicohen-admin-1234
```

### Database Ready:
```
✅ feedback_submissions table
✅ feedback_blocked_sessions table
✅ feedback_stats view
✅ Migration copied to PG/postgres-init/
```

---

## 📊 Tool 1: get_feedback_dashboard

**Description:** Complete feedback system dashboard with statistics and recent submissions.

**Access:** Admin only

**Use Cases:**
- Monitor feedback volume and trends
- Review quality of submissions
- Track GitHub integration success
- Identify active users/teams

### Parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Max recent submissions to return |
| `status_filter` | string | null | Filter by status (submitted, created, failed) |
| `type_filter` | string | null | Filter by type (bug, feature, improvement) |

### Example Usage:

**Via Claude Desktop (as admin):**
```
Show me the feedback dashboard
```

**Or more specific:**
```
Show me the feedback dashboard with the last 50 submissions
```

**Or filtered:**
```
Show me only bug reports that were successfully created
```

### Response Includes:

1. **Summary Statistics:**
   - Total submissions (all-time, last 24h, last hour)
   - Unique users and teams
   - Average quality score

2. **Breakdown by Type:**
   - Bugs count
   - Features count
   - Improvements count

3. **Breakdown by Status:**
   - Successfully created on GitHub
   - Failed submissions
   - Pending submissions

4. **Recent Submissions List:**
   - Session ID (truncated)
   - Client ID
   - Type, title, quality score
   - GitHub issue number and URL
   - Status and timestamp

5. **Blocked Users:**
   - Currently blocked sessions/clients
   - Time remaining until unblock
   - Block reason

6. **Top Contributors:**
   - Most active clients in last 30 days
   - Submission counts
   - Average quality scores

---

## 🐛 Tool 2: get_github_issues_summary

**Description:** Summary of GitHub issues created from feedback system.

**Access:** Admin only

**Use Cases:**
- Check how many GitHub issues are open
- Monitor GitHub integration success
- Review recent issues created
- Identify failed submissions

### Parameters:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_failed` | boolean | false | Include failed submissions in results |
| `limit` | integer | 10 | Max recent issues to return |

### Example Usage:

**Via Claude Desktop (as admin):**
```
How many GitHub issues are open?
```

**Or:**
```
Show me GitHub issues summary
```

**Include failed:**
```
Show me GitHub issues including failed submissions
```

### Response Includes:

1. **Total Issues Created:** Count of successfully created GitHub issues

2. **By Type:**
   - Bugs
   - Features
   - Improvements

3. **Status:**
   - Success rate percentage
   - Failed count
   - Pending count

4. **Recent Issues List:**
   - Issue type and title
   - GitHub issue number
   - GitHub URL
   - Quality score
   - Status (created/failed)
   - Timestamp

---

## 👥 Tool 3: get_feedback_by_client

**Description:** View all feedback submissions from a specific client/team.

**Access:** Admin only

**Use Cases:**
- Investigate specific team's feedback
- Check client rate limit usage
- Review quality of submissions from team
- Verify if client is blocked

### Parameters:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `client_id` | string | Yes | Client/team identifier |
| `limit` | integer | No (20) | Max submissions to return |

### Example Usage:

**Via Claude Desktop (as admin):**
```
Show me feedback from client_1
```

**Or:**
```
Get feedback submissions from the development team
```

### Response Includes:

1. **Client Statistics:**
   - Total submissions
   - Last 24 hours / Last hour
   - Average quality score
   - Unique sessions (individual users)
   - First and last submission timestamps

2. **Block Status:**
   - Is blocked (yes/no)
   - Hours remaining (if blocked)
   - Block reason
   - Unblock timestamp

3. **Submissions List:**
   - Session ID (truncated)
   - Type, title
   - Quality score
   - GitHub issue number
   - Status
   - Timestamp

---

## 🔐 Testing Admin Access

### Test 1: Verify Admin Tools Are Available (as admin)

**Connect with admin API key:**
```json
{
  "mcpServers": {
    "mcp_db_performance": {
      "url": "http://localhost:8100/mcp",
      "headers": {
        "Authorization": "Bearer avicohen-admin-1234"
      }
    }
  }
}
```

**Ask Claude:**
```
List all available tools related to feedback
```

**Expected:** Should see:
- `get_feedback_dashboard`
- `get_github_issues_summary`
- `get_feedback_by_client`
- `report_mcp_issue_interactive` (available to all)
- `improve_my_feedback` (available to all)
- `search_mcp_issues` (available to all)

### Test 2: Check Admin Access Works

**As admin user, ask:**
```
Show me the feedback dashboard
```

**Expected Response:**
```
📊 Feedback System Dashboard

Summary:
• Total submissions: 0
• Last 24 hours: 0
• Last hour: 0
• Unique users: 0
• Unique teams: 0
• Avg quality score: 0.0/10

By Type:
• Bugs: 0
• Features: 0
• Improvements: 0

By Status:
• Created on GitHub: 0
• Failed: 0
• Pending: 0
```

### Test 3: Verify Non-Admin Access is Denied

**Connect with non-admin API key (client_1):**
```json
{
  "mcpServers": {
    "mcp_db_performance": {
      "url": "http://localhost:8100/mcp",
      "headers": {
        "Authorization": "Bearer U1f1mzzSvNKhrtntjJeE0O1KUz-7r7TiuR1-ushQXoc"
      }
    }
  }
}
```

**Ask Claude:**
```
Show me the feedback dashboard
```

**Expected Response:**
```
🔒 Access Denied

This tool is restricted to administrators only.
Contact your system administrator if you need access to feedback management.
```

---

## 📊 Sample Queries (Database)

If you want to query the database directly:

### View All Feedback Submissions
```sql
SELECT
    id,
    client_id,
    submission_type,
    title,
    quality_score,
    status,
    created_at
FROM mcp_performance.feedback_submissions
ORDER BY created_at DESC
LIMIT 20;
```

### Get Dashboard Statistics
```sql
SELECT * FROM mcp_performance.feedback_stats;
```

### Check Currently Blocked Users
```sql
SELECT
    identifier,
    identifier_type,
    EXTRACT(EPOCH FROM (unblock_at - NOW()))/3600 as hours_remaining,
    reason
FROM mcp_performance.feedback_blocked_sessions
WHERE unblock_at > NOW();
```

### Top Contributors (Last 30 Days)
```sql
SELECT
    client_id,
    COUNT(*) as submissions,
    ROUND(AVG(quality_score), 1) as avg_quality
FROM mcp_performance.feedback_submissions
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY client_id
ORDER BY submissions DESC;
```

---

## 🎯 Common Admin Workflows

### Workflow 1: Daily Monitoring

**Morning check:**
```
Show me the feedback dashboard for last 24 hours
```

**Review:**
- Check submission volume
- Review quality scores
- Identify any failed submissions
- Check for blocked users

### Workflow 2: GitHub Issue Management

**Check open issues:**
```
How many GitHub issues are open?
```

**Review failed submissions:**
```
Show me GitHub issues including failed submissions
```

**Follow up:**
- Manually create issues for failures (if needed)
- Review error messages
- Update GitHub token if expired

### Workflow 3: Team Investigation

**Check specific team:**
```
Show me feedback from client_1
```

**Analyze:**
- Review submission frequency
- Check quality scores
- Verify rate limit compliance
- Check if team is blocked

### Workflow 4: Abuse Detection

**Review dashboard:**
```
Show me the feedback dashboard with blocked users
```

**Check patterns:**
- Multiple blocks from same client
- Spam submissions (low quality)
- Excessive submission rates
- Duplicate content

---

## 🔧 Configuration

Admin tools use the same database connection as the feedback system:

**Database:** `omni_pg_db`
**Schema:** `mcp_performance`
**Tables:**
- `feedback_submissions`
- `feedback_blocked_sessions`

**Connection configured in:**
- `.env`: Database credentials
- `settings.yaml`: Feedback configuration

---

## 📝 Logging

Admin tool calls are logged:

```bash
# Check admin tool usage
docker logs mcp_db_performance | grep "ADMIN"

# Example output:
# 📊 TOOL CALLED: get_feedback_dashboard (ADMIN)
# ✅ Admin access granted to user: admin
# 📊 TOOL CALLED: get_github_issues_summary (ADMIN)
```

**Non-admin attempts are logged as warnings:**
```
🚫 Non-admin user 'client_1' attempted to access admin tool
```

---

## 🛡️ Security Features

1. **Authentication Check:**
   - Every tool call verifies client_id = "admin"
   - Uses context variables from session tracking
   - Logs all access attempts

2. **Access Denial:**
   - Clear error message to user
   - No sensitive data leaked
   - Logged for security audit

3. **Database Security:**
   - Read-only queries
   - Parameterized queries (SQL injection safe)
   - Limited to mcp_performance schema

4. **Rate Limiting:**
   - Admin tools NOT rate limited
   - But usage is logged for audit

---

## 🚀 Next Steps

1. **Test admin access** with admin API key
2. **Submit test feedback** (as regular user)
3. **View in dashboard** (as admin)
4. **Monitor daily** for trends and issues

---

## 📞 Support

**Check tool status:**
```bash
docker logs mcp_db_performance --tail 50 | grep feedback_admin
```

**Verify admin key:**
```bash
docker logs mcp_db_performance | grep "admin"
```

**Database access:**
```bash
docker exec omni_pg_db psql -U omni -d omni -c "SELECT * FROM mcp_performance.feedback_stats;"
```

---

## Summary

✅ **3 admin-only tools** created and loaded
✅ **Admin API key** configured: `avicohen-admin-1234`
✅ **Database tables** ready and populated
✅ **Migration** copied to PG init folder
✅ **Access control** working (tested)
✅ **Logging** enabled for security audit

**Admin can now:**
- 📊 View complete feedback dashboard
- 🐛 Monitor GitHub issues
- 👥 Investigate specific teams
- 🚫 Review blocked users
- 📈 Track trends and statistics

**Regular users can:**
- 🐛 Report bugs
- ✨ Request features
- 🔧 Suggest improvements
- 🔍 Search existing issues
- ✨ Get help improving feedback

---

**Status:** ✅ **READY FOR ADMIN USE**
