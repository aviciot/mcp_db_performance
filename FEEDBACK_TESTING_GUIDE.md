# Feedback System Testing Guide

## Pre-Testing Checklist

Before testing, ensure:

1. **GitHub Token is set:**
   ```bash
   # In .env file
   GITHUB_TOKEN=ghp_your_actual_token_here
   GITHUB_REPO=aviciot/mcp_db_performance
   ```

2. **Configuration is enabled:**
   ```yaml
   # In settings.yaml
   feedback:
     enabled: true
     repo: "aviciot/mcp_db_performance"
     maintainer: "Avi Cohen"
   ```

3. **Server is running:**
   ```bash
   docker-compose up -d
   docker logs mcp_db_performance --tail 50
   ```

4. **Check for import errors:**
   ```bash
   # Should see these lines in logs:
   # 📦 Auto-imported: tools.feedback_context
   # 📦 Auto-imported: tools.feedback_safety
   # 📦 Auto-imported: tools.feedback_quality
   # 📦 Auto-imported: tools.mcp_feedback
   # 📦 Auto-imported: prompts.feedback_improvement
   # 📦 Auto-imported: resources.mcp_welcome
   # 🔗 Session Context Middleware enabled for feedback tracking
   ```

---

## Testing Checklist

### Phase 1: Basic Functionality

#### Test 1: Tool Registration
**Goal:** Verify tools are registered with MCP

**Method:**
```bash
# Check MCP endpoint
curl http://localhost:8100/health/deep
```

**Expected Output:**
```json
{
  "status": "healthy",
  "checks": {
    "mcp": {
      "tools": 12,  # Should include feedback tools
      "resources": 8,  # Should include welcome resources
      "prompts": 2   # Should include improvement prompt
    }
  }
}
```

**Verification:**
- Tools count includes `report_mcp_issue_interactive`, `improve_my_feedback`, `search_mcp_issues`
- Resources include `welcome://feedback-system`
- Prompts include `improve_feedback`

---

#### Test 2: Context Tracking
**Goal:** Verify session and client IDs are extracted

**Method:**
1. Make authenticated request to MCP
2. Check logs for session tracking

**Expected Log Output:**
```
[AUTH] ✅ Authenticated client: client_1 | session: fp_a3b2c1d4e5f6... → /mcp
🔗 Session context set: client_1:fp_a3b2c1d4e5f6...
```

**Verification:**
- Session ID appears in auth logs
- Format is `fp_<hash>` or explicit session ID
- Client ID matches API key name

---

### Phase 2: Safety & Validation

#### Test 3: Content Validation
**Goal:** Test validation rules

**Test 3.1: Title too short**
```python
# Via Claude Desktop
report_mcp_issue_interactive(
    issue_type="bug",
    title="bug",  # Only 3 chars
    description="This is a valid description with enough details."
)
```

**Expected:**
```
❌ Title Too Short
Minimum: 5 characters
Please provide a descriptive title.
```

**Test 3.2: Description too short**
```python
report_mcp_issue_interactive(
    issue_type="bug",
    title="Valid title here",
    description="Too short"  # Only 9 chars
)
```

**Expected:**
```
❌ Description Too Short
Minimum: 10 characters
Please provide more details.
```

**Test 3.3: Valid content**
```python
report_mcp_issue_interactive(
    issue_type="bug",
    title="Query analysis fails for MERGE",
    description="When analyzing MERGE INTO statements, plan_details is empty."
)
```

**Expected:**
```
✅ Content validation passed
📊 Quality score: X.X/10
```

---

#### Test 4: Rate Limiting
**Goal:** Test per-user rate limits

**Test 4.1: Within limits**
```python
# Submission 1
report_mcp_issue_interactive(
    issue_type="bug",
    title="Test issue 1",
    description="First test submission",
    auto_submit=False
)
# Expected: Success

# Submission 2
report_mcp_issue_interactive(
    issue_type="bug",
    title="Test issue 2",
    description="Second test submission",
    auto_submit=False
)
# Expected: Success

# Submission 3
report_mcp_issue_interactive(
    issue_type="bug",
    title="Test issue 3",
    description="Third test submission",
    auto_submit=False
)
# Expected: Success
```

**Test 4.2: Exceed hourly limit**
```python
# Submission 4 (within same hour)
report_mcp_issue_interactive(
    issue_type="bug",
    title="Test issue 4",
    description="Fourth test submission",
    auto_submit=False
)
```

**Expected:**
```
⏱️ Hourly Rate Limit Reached

Your limit: 3 submissions per hour
Wait time: X minutes

💡 Tip: Search existing issues first!
Say: 'Search issues about [topic]'
```

---

#### Test 5: Duplicate Detection
**Goal:** Test duplicate prevention

**Test 5.1: Submit original**
```python
report_mcp_issue_interactive(
    issue_type="bug",
    title="Original issue",
    description="This is the original submission",
    auto_submit=False
)
```

**Test 5.2: Submit duplicate (within 30 minutes)**
```python
report_mcp_issue_interactive(
    issue_type="bug",
    title="Original issue",  # Same title
    description="This is the original submission",  # Same description
    auto_submit=False
)
```

**Expected:**
```
🔄 Duplicate Submission

You submitted identical feedback X minute(s) ago.
Wait time: Y minutes

💡 Did you mean to add more information?
```

---

### Phase 3: Quality Checking

#### Test 6: Quality Analysis
**Goal:** Test quality scoring

**Test 6.1: Good quality feedback**
```python
report_mcp_issue_interactive(
    issue_type="bug",
    title="analyze_oracle_query returns empty plan_details for MERGE",
    description="""
When analyzing a MERGE INTO statement using analyze_oracle_query,
the returned plan_details array is empty.

Steps to reproduce:
1. Call analyze_oracle_query with MERGE statement
2. Check plan_details in response
3. Observe empty array

Expected: plan_details should contain execution plan steps
Actual: plan_details is []

Environment: Oracle 19c
    """,
    auto_submit=False
)
```

**Expected:**
```
📊 Quality score: 8.5/10
✅ Feedback looks good!
Stage: preview
```

**Test 6.2: Low quality feedback**
```python
report_mcp_issue_interactive(
    issue_type="bug",
    title="something wrong",
    description="when i run query it not work maybe its slow or something",
    auto_submit=False
)
```

**Expected:**
```
📊 Quality score: 3.2/10

⚠️ Your feedback needs improvement:
• Contains 4 vague words (something, maybe, etc.)
• Description is very short
• Missing key information: what happened, expected behavior

Options:
1. Use improve_my_feedback tool
2. Edit and try again
3. Submit as-is with auto_submit=True
```

---

#### Test 7: Feedback Improvement
**Goal:** Test LLM-powered improvement

```python
improve_my_feedback(
    issue_type="bug",
    title="something wrong",
    description="when i run query it not work maybe its slow or something"
)
```

**Expected:**
```
📊 Current Quality: 3.2/10

Issues Found:
• Contains vague words
• Missing key information

Suggestions:
• Be more specific - avoid 'something', 'somehow', 'maybe'
• Add details about what happened vs expected

Next Step:
I can help rewrite this to be clearer. Would you like me to suggest improvements?
```

---

### Phase 4: GitHub Integration

#### Test 8: Issue Search
**Goal:** Test GitHub search

```python
search_mcp_issues(
    query="performance slow",
    issue_type="bug",
    state="open"
)
```

**Expected:**
```
🔍 Found X issue(s)

#15 [open] Performance degradation with tables >10M rows
   https://github.com/aviciot/mcp_db_performance/issues/15
   Labels: bug, performance

...
```

---

#### Test 9: Issue Creation (Preview Mode)
**Goal:** Test preview without submission

```python
report_mcp_issue_interactive(
    issue_type="bug",
    title="Test issue for feedback system",
    description="This is a test submission to verify the feedback system works correctly.",
    auto_submit=False  # Just preview
)
```

**Expected:**
```
📋 Preview Your Issue

Title: Test issue for feedback system
Type: bug
Quality Score: 7.8/10
Labels: bug, user-submitted, good-quality

Description:
This is a test submission to verify the feedback system works correctly.

---

To submit this issue:
Call this tool again with auto_submit=True
```

---

#### Test 10: Issue Creation (Full Submission)
**Goal:** Create actual GitHub issue

**⚠️ WARNING: This will create a real GitHub issue!**

```python
report_mcp_issue_interactive(
    issue_type="bug",
    title="[TEST] Feedback system test issue",
    description="This is a test issue to verify GitHub integration. Please close.",
    auto_submit=True  # Actually submit
)
```

**Expected:**
```
✅ Issue Created Successfully!

Issue #XX: https://github.com/aviciot/mcp_db_performance/issues/XX

Thank you for helping improve this MCP! 🎉

What's next:
• The maintainer (Avi Cohen) will review your submission
• You can track progress at the link above

Submissions remaining today: 9
```

**Verification:**
1. Visit the GitHub URL
2. Verify issue exists
3. Check labels: `bug`, `user-submitted`, `good-quality`
4. Close the test issue on GitHub

---

### Phase 5: Error Handling

#### Test 11: Missing GitHub Token
**Setup:**
1. Remove `GITHUB_TOKEN` from `.env`
2. Restart server

**Test:**
```python
report_mcp_issue_interactive(
    issue_type="bug",
    title="Test without token",
    description="Testing error handling",
    auto_submit=True
)
```

**Expected:**
```
❌ GitHub token not configured

The maintainer needs to set GITHUB_TOKEN in .env to enable issue creation.
```

---

#### Test 12: Disabled Feedback System
**Setup:**
1. Set `feedback.enabled: false` in `settings.yaml`
2. Restart server

**Test:**
```python
report_mcp_issue_interactive(
    issue_type="bug",
    title="Test with disabled system",
    description="Testing disabled state"
)
```

**Expected:**
```
❌ Feedback system is not enabled

The feedback system is currently disabled. Please contact the maintainer directly.
```

---

## Automated Testing Script

Create `test_feedback.py`:

```python
#!/usr/bin/env python3
"""
Automated test script for feedback system
"""

import asyncio
from tools.feedback_safety import get_safety_manager
from tools.feedback_quality import get_quality_analyzer, quick_quality_check
from tools.feedback_context import set_request_context, get_user_identifier

async def test_safety():
    """Test safety manager"""
    print("\\n=== Testing Safety Manager ===")

    # Setup test context
    set_request_context(
        session_id="test_session_123",
        user_id="test_user",
        client_id="test_client"
    )

    safety = get_safety_manager()
    user_id = get_user_identifier()

    # Test rate limit
    allowed, msg = safety.check_rate_limit(user_id, "test_client")
    print(f"Rate limit check: {'✅ PASS' if allowed else '❌ FAIL'}")
    print(f"Message: {msg if not allowed else 'Allowed'}")

    # Test content validation
    is_valid, msg = safety.validate_content(
        "Valid title here",
        "This is a valid description with enough content."
    )
    print(f"\\nContent validation: {'✅ PASS' if is_valid else '❌ FAIL'}")

    # Test duplicate detection
    is_dup, msg = safety.check_duplicate(user_id, "test content 123")
    print(f"Duplicate check: {'✅ PASS' if not is_dup else '❌ FAIL'}")

    # Get stats
    stats = safety.get_stats(user_id, "test_client")
    print(f"\\nStats: {stats}")

def test_quality():
    """Test quality analyzer"""
    print("\\n=== Testing Quality Analyzer ===")

    analyzer = get_quality_analyzer()

    # Test good quality
    is_good, msg, analysis = quick_quality_check(
        "bug",
        "Query analysis fails for MERGE statements",
        "When analyzing MERGE INTO statements, plan_details is empty. SELECT queries work fine."
    )
    print(f"Good quality test: {'✅ PASS' if is_good else '⚠️  NEEDS IMPROVEMENT'}")
    print(f"Score: {analysis['quality_score']}/10")

    # Test poor quality
    is_good, msg, analysis = quick_quality_check(
        "bug",
        "something wrong",
        "when i run query it not work maybe"
    )
    print(f"\\nPoor quality test: {'✅ PASS' if not is_good else '❌ FAIL'}")
    print(f"Score: {analysis['quality_score']}/10")
    print(f"Issues: {analysis['issues_found']}")

if __name__ == "__main__":
    print("🧪 Feedback System Test Suite")
    print("=" * 50)

    # Run tests
    asyncio.run(test_safety())
    test_quality()

    print("\\n" + "=" * 50)
    print("✅ All tests completed!")
```

**Run tests:**
```bash
cd /app
python test_feedback.py
```

---

## Post-Testing Cleanup

1. **Close test issues on GitHub:**
   - Go to your repository issues page
   - Close any test issues created during testing
   - Add comment: "Test issue - closing"

2. **Reset rate limits (if needed):**
   ```bash
   docker-compose restart
   ```

3. **Review logs for errors:**
   ```bash
   docker logs mcp_db_performance | grep -i "error\|warning"
   ```

---

## Success Criteria

✅ **All tools registered** - Check logs for imports
✅ **Session tracking works** - Session IDs in logs
✅ **Content validation works** - Rejects invalid input
✅ **Rate limiting works** - Blocks after 3/hour
✅ **Duplicate detection works** - Prevents duplicates within 30min
✅ **Quality checking works** - Scores feedback 0-10
✅ **Search works** - Finds existing issues
✅ **Preview works** - Shows preview before submit
✅ **GitHub integration works** - Creates real issues
✅ **Error handling works** - Graceful degradation

---

## Common Issues & Solutions

**Issue:** Tools not appearing in MCP
- **Solution:** Check for import errors in logs, verify file names match

**Issue:** Session IDs always "unknown"
- **Solution:** Verify SessionContextMiddleware is added and auth sets request.state

**Issue:** Rate limits not working
- **Solution:** Check context variables are set correctly

**Issue:** GitHub API returns 401
- **Solution:** Verify GITHUB_TOKEN is valid and has correct scopes

**Issue:** Quality scores always low
- **Solution:** Check for quality analyzer import errors

---

## Next Steps

After successful testing:

1. **Update GITHUB_TOKEN** with real token (not placeholder)
2. **Adjust rate limits** based on expected usage
3. **Enable in production** with `feedback.enabled: true`
4. **Monitor usage** via GitHub issues and logs
5. **Iterate** based on user feedback

---

**Testing Complete! 🎉**
