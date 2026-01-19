# Interactive Feedback System for MCP

## Overview

The **Interactive Feedback System** enables users to report bugs, request features, and suggest improvements directly through the MCP, with LLM-powered quality checking and GitHub integration.

### Key Features

- **Interactive Quality Checking**: LLM analyzes feedback and suggests improvements
- **Multi-level Rate Limiting**: Per-user and per-team limits prevent abuse
- **Session Tracking**: Proper tracking even when API tokens are shared
- **Search Before Submit**: Find existing issues to avoid duplicates
- **Preview Before Post**: Review feedback before creating GitHub issues
- **Generic & Reusable**: Copy to any MCP with minimal configuration

---

## Architecture

### Components

1. **feedback_context.py** - Session and client identifier tracking
2. **feedback_safety.py** - Rate limiting, validation, duplicate detection
3. **feedback_quality.py** - LLM-powered quality analysis
4. **mcp_feedback.py** - MCP tools for interactive feedback
5. **feedback_improvement.py** - Prompt for improving unclear feedback
6. **mcp_welcome.py** - Resources explaining the feedback system

### Middleware Integration

1. **AuthMiddleware** - Extracts client_id and session_id from requests
2. **SessionContextMiddleware** - Sets context variables for request lifecycle

### Data Flow

```
User → MCP Tool Call → Auth Middleware → Session Context Middleware
  ↓
Context Variables Set (client_id, session_id)
  ↓
Feedback Tool → Safety Check → Quality Check → GitHub API
  ↓
GitHub Issue Created → User Gets Link
```

---

## Installation & Setup

### Step 1: Copy Files

Copy these files to your MCP project:

```
server/tools/
  ├── feedback_context.py
  ├── feedback_safety.py
  ├── feedback_quality.py
  └── mcp_feedback.py

server/prompts/
  └── feedback_improvement.py

server/resources/
  └── mcp_welcome.py
```

### Step 2: Update Middleware

**In `auth_middleware.py`**, add session tracking:

```python
import hashlib

def _extract_session_id(self, request: Request) -> str:
    """Extract or generate session ID from request."""
    session_header = request.headers.get("x-session-id")
    if session_header:
        return session_header[:64]

    connection_id = request.headers.get("x-connection-id")
    if connection_id:
        return connection_id[:64]

    # Fallback: fingerprint
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    fingerprint = f"{client_ip}:{user_agent}"
    session_hash = hashlib.sha256(fingerprint.encode()).hexdigest()[:32]
    return f"fp_{session_hash}"

# In dispatch method, after authentication:
session_id = self._extract_session_id(request)
request.state.client_id = client_name
request.state.session_id = session_id
```

**In `server.py`**, add SessionContextMiddleware:

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class SessionContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        from tools.feedback_context import set_request_context

        session_id = getattr(request.state, "session_id", None)
        client_id = getattr(request.state, "client_id", None)
        user_id = getattr(request.state, "client_name", None)

        if session_id and client_id:
            set_request_context(
                session_id=session_id,
                user_id=user_id or client_id,
                client_id=client_id
            )

        return await call_next(request)

# Add middleware (order matters!)
app.add_middleware(AuthMiddleware, config=config)
app.add_middleware(SessionContextMiddleware)
```

### Step 3: Configure Settings

**In `settings.yaml`**, add feedback configuration:

```yaml
feedback:
  enabled: true
  repo: "your-username/your-repo"  # Change this!
  maintainer: "Your Name"          # Change this!

  safety:
    session_limits:
      per_hour: 3
      per_day: 10
    client_limits:
      per_hour: 20
      per_day: 50
    validation:
      min_title_length: 5
      max_title_length: 200
      min_description_length: 10
      max_description_length: 5000
    duplicate_window_minutes: 30
    block_duration_hours: 24

  quality:
    enabled: true
    auto_improve: true
    min_quality_score: 0  # 0 = suggestions only, no enforcement
```

### Step 4: Set GitHub Token

**In `.env`**, add your GitHub token:

```bash
# Generate token at: https://github.com/settings/tokens
# Required scopes: repo (private) or public_repo (public)
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_REPO=your-username/your-repo
```

### Step 5: Install Dependencies

```bash
pip install httpx pyyaml
```

---

## Usage

### For Users

**Report a Bug:**
```python
report_mcp_issue_interactive(
    issue_type="bug",
    title="Query analysis fails for MERGE statements",
    description="When analyzing MERGE INTO statements, plan_details is empty. SELECT queries work fine.",
    auto_submit=False  # Preview first
)
```

**Request a Feature:**
```python
report_mcp_issue_interactive(
    issue_type="feature",
    title="Add PostgreSQL support",
    description="Would like to analyze PostgreSQL queries like Oracle/MySQL",
    auto_submit=False
)
```

**Suggest an Improvement:**
```python
report_mcp_issue_interactive(
    issue_type="improvement",
    title="Better error messages",
    description="Error messages are too technical. Add plain-language explanations.",
    auto_submit=False
)
```

**Search Existing Issues:**
```python
search_mcp_issues(
    query="performance slow",
    issue_type="bug",
    state="open"
)
```

**Improve Unclear Feedback:**
```python
improve_my_feedback(
    issue_type="bug",
    title="something wrong with query",
    description="when i run query it not work maybe its slow or something"
)
```

### Interactive Workflow

1. **User calls `report_mcp_issue_interactive`**
   - Rate limit check (3/hour, 10/day per user)
   - Content validation (length, spam, duplicates)
   - Quality analysis (score 0-10)

2. **If quality is low (<7/10):**
   - User gets suggestions for improvement
   - Can use `improve_my_feedback` to get LLM help
   - Can submit anyway with `auto_submit=True`

3. **Preview:**
   - User sees exactly what will be posted
   - Can edit and try again
   - Can confirm with `auto_submit=True`

4. **Submission:**
   - GitHub issue created
   - User gets direct link
   - Rate limit recorded

---

## Rate Limiting

### Per-Session (Individual User)

- **3 submissions per hour**
- **10 submissions per day**
- Tracks individual users even when sharing API token

### Per-Client (Team/Organization)

- **20 submissions per hour**
- **50 submissions per day**
- Prevents one team from overwhelming the system

### Auto-Blocking

- **6+ submissions in 1 hour = 24-hour block**
- Automatic unblock after duration
- Helps prevent abuse and spam

### Rate Limit Example

```
User A (team "acme"):
  - Hour 1: 3 submissions → OK
  - Hour 1: 4th submission → "Wait 30 minutes"

User B (same team "acme"):
  - Hour 1: 3 submissions → OK (separate session)

Team "acme" (both users combined):
  - Hour 1: 6 submissions → OK
  - Hour 1: 21st submission → "Team limit reached"
```

---

## Quality Checking

### Scoring (0-10)

**Positive Signals (+points):**
- Clear structure (bullets, numbers)
- Specific examples
- Steps to reproduce
- Expected vs actual behavior

**Negative Signals (-points):**
- Vague words ("something", "somehow", "maybe")
- Missing key information
- Too short (<50 chars)
- Grammar issues

### Quality Thresholds

- **7-10**: Good quality, submit as-is
- **4-6**: Medium quality, suggestions provided
- **0-3**: Low quality, improvement strongly recommended

### Interactive Improvement

LLM can rewrite unclear feedback while preserving meaning:

**Before:**
```
Title: something wrong with query
Description: when i run query it not work maybe its slow or something
```

**After (LLM-improved):**
```
Title: Query execution fails or runs very slowly
Description: When executing database queries, the query either fails
to complete or runs significantly slower than expected.

Actual behavior: Query does not complete successfully or takes much
longer than usual.

Expected behavior: Query should execute and return results promptly.

Additional context needed:
- Which specific query is affected?
- What error message appears (if any)?
- How long does it take vs. expected time?
```

---

## Configuration Reference

### Safety Settings

```yaml
feedback:
  safety:
    session_limits:
      per_hour: 3          # Max per user per hour
      per_day: 10          # Max per user per day

    client_limits:
      per_hour: 20         # Max per team per hour
      per_day: 50          # Max per team per day
      # Set to null to disable

    validation:
      min_title_length: 5
      max_title_length: 200
      min_description_length: 10
      max_description_length: 5000

    duplicate_window_minutes: 30  # Duplicate detection window
    block_duration_hours: 24      # Auto-block duration
```

### Quality Settings

```yaml
feedback:
  quality:
    enabled: true              # Enable quality checking
    auto_improve: true         # Suggest improvements
    min_quality_score: 0       # 0 = suggestions only
                               # 4 = require minimum quality
                               # 7 = require good quality
```

### GitHub Settings

```yaml
feedback:
  repo: "owner/repo"           # GitHub repository
  maintainer: "Name"           # Maintainer shown to users
```

---

## Customization

### Adjust Rate Limits

**More Permissive (public MCP):**
```yaml
session_limits:
  per_hour: 5
  per_day: 20
client_limits:
  per_hour: 50
  per_day: 200
```

**More Restrictive (private/internal):**
```yaml
session_limits:
  per_hour: 2
  per_day: 5
client_limits:
  per_hour: 10
  per_day: 25
```

### Disable Team Limits

```yaml
client_limits:
  per_hour: null  # No team limit
  per_day: null   # No team limit
```

### Enforce Quality Standards

```yaml
quality:
  min_quality_score: 4  # Require at least 4/10
```

### Custom Validation

**In `feedback_safety.py`**, edit `validate_content()`:

```python
# Add custom spam patterns
spam_patterns = [
    (r'(.)\\1{20,}', "repeated characters"),
    (r'\\b(urgent|asap|critical)\\b', "urgency spam"),
    # Add your patterns here
]
```

---

## Monitoring & Maintenance

### Check Rate Limit Stats

```python
from tools.feedback_safety import get_safety_manager

safety = get_safety_manager()
stats = safety.get_stats(session_identifier, client_identifier)

print(stats)
# {
#   "session": {
#     "submissions_today": 3,
#     "submissions_this_hour": 1,
#     "remaining_today": 7,
#     "remaining_this_hour": 2,
#     "is_blocked": False
#   },
#   "client": {
#     "submissions_today": 12,
#     "submissions_this_hour": 5,
#     "remaining_today": 38,
#     "remaining_this_hour": 15,
#     "is_blocked": False
#   }
# }
```

### Clear Rate Limit Data

Rate limit data is stored in memory and cleared on server restart. For persistent tracking, add database storage:

```python
# In feedback_safety.py, modify __init__:
def __init__(self, db_connection=None):
    if db_connection:
        # Load from database
        self._load_from_db(db_connection)
    else:
        # In-memory (current behavior)
        self._session_submissions = {}
```

### Monitor Blocked Users

```python
safety = get_safety_manager()

# Check blocked sessions
print(f"Blocked sessions: {len(safety._blocked_sessions)}")
print(f"Blocked clients: {len(safety._blocked_clients)}")
```

---

## Troubleshooting

### "GitHub token not configured"

**Solution:**
1. Generate token at https://github.com/settings/tokens
2. Required scopes: `repo` (private) or `public_repo` (public)
3. Add to `.env`: `GITHUB_TOKEN=ghp_xxxx`
4. Restart server

### "Feedback system is not enabled"

**Solution:**
1. Check `settings.yaml`: `feedback.enabled: true`
2. Verify `feedback` section exists
3. Restart server

### "Rate limit exceeded"

**Solution:**
1. Wait for limit to reset (hourly/daily)
2. Or adjust limits in `settings.yaml`
3. Or clear in-memory data (restart server)

### "Session tracking not working"

**Solution:**
1. Verify `SessionContextMiddleware` is added to server.py
2. Check middleware order: `AuthMiddleware` → `SessionContextMiddleware`
3. Check logs for session IDs in auth messages

### Quality checking not working

**Solution:**
1. Check `feedback.quality.enabled: true` in settings.yaml
2. Verify `feedback_quality.py` is imported
3. Check logs for quality analysis output

---

## Security Considerations

### Data Privacy

- **Session IDs**: Hashed fingerprints, not personally identifiable
- **Client IDs**: From API keys, tracks teams/organizations
- **No PII**: System doesn't collect names, emails, or personal data

### Content Sanitization

Feedback is sanitized before posting to GitHub:

- Passwords, tokens, API keys removed
- IP addresses redacted
- Sensitive environment variables masked

**To customize sanitization**, edit `mcp_feedback.py`:

```python
def sanitize_content(text: str) -> str:
    # Remove passwords
    text = re.sub(r'password[=:]\s*\S+', 'password=***', text, flags=re.IGNORECASE)
    # Remove tokens
    text = re.sub(r'token[=:]\s*\S+', 'token=***', text, flags=re.IGNORECASE)
    # Add your rules here
    return text
```

### Rate Limit Bypass Protection

- Multiple detection layers (session, client, abuse patterns)
- Auto-blocking for rapid submissions
- Duplicate detection prevents spam
- Content validation blocks malicious input

---

## Migration to Other MCPs

### Checklist

1. **Copy files:**
   - `server/tools/feedback_*.py` (4 files)
   - `server/prompts/feedback_improvement.py`
   - `server/resources/mcp_welcome.py`

2. **Update middleware:**
   - Enhance `auth_middleware.py` with session tracking
   - Add `SessionContextMiddleware` to `server.py`

3. **Configure:**
   - Add `feedback` section to `settings.yaml`
   - Change `repo` and `maintainer` values
   - Add `GITHUB_TOKEN` to `.env`

4. **Install dependencies:**
   ```bash
   pip install httpx pyyaml
   ```

5. **Test:**
   - Verify tools are registered: Check MCP logs
   - Test rate limiting: Submit multiple issues
   - Test quality checking: Submit vague feedback
   - Test GitHub integration: Create real issue

### Customization per MCP

**Change repository:**
```yaml
feedback:
  repo: "your-org/your-mcp"
  maintainer: "Your Name"
```

**Adjust rate limits for MCP audience:**
- Public MCP: More permissive
- Internal MCP: More restrictive

**Customize quality standards:**
- Technical MCP: Higher quality standards
- User-facing MCP: More lenient

---

## FAQ

**Q: Can users submit anonymously?**
A: Yes, submissions use session IDs (not personal info). GitHub issues are public but don't reveal user identity.

**Q: What if I don't have a GitHub token?**
A: System will work in "preview mode" - users get feedback analysis but can't auto-create issues. They can copy the preview and create manually.

**Q: Can I integrate with GitLab/Jira instead?**
A: Yes! Modify `create_github_issue()` in `mcp_feedback.py` to call your issue tracker's API.

**Q: How do I disable for specific MCP instances?**
A: Set `feedback.enabled: false` in `settings.yaml` for that instance.

**Q: Do rate limits persist across restarts?**
A: No, in-memory by default. Add database storage for persistence.

**Q: Can I customize quality scoring?**
A: Yes! Edit weights in `feedback_quality.py`:
```python
self.weights = {
    "vague_language": -2,  # Change these
    "missing_details": -3,
    "good_structure": +2,
}
```

---

## Contributing

Contributions welcome! To add features:

1. **New validation rule:** Edit `feedback_safety.py` → `validate_content()`
2. **New quality check:** Edit `feedback_quality.py` → `analyze_feedback_quality()`
3. **New tool:** Add to `mcp_feedback.py` with `@mcp.tool()` decorator
4. **New resource:** Add to `mcp_welcome.py` with `@mcp.resource()` decorator

---

## License

This feedback system is designed to be generic and reusable. Copy freely to any MCP project.

---

## Support

**Issues with the feedback system itself?**
Use the feedback system! Report bugs/request features through the MCP.

**Questions?**
Check the welcome resources in the MCP or contact the maintainer.

---

**Built with ❤️ for the MCP community**
