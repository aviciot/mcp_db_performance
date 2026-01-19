# Quick Setup Guide - Add Feedback System to Any MCP

## ⏱️ Time Required: 15 minutes

---

## Step 1: Generate GitHub Token (5 minutes)

### 1.1 Go to GitHub Settings
1. Open GitHub and log in
2. Click your profile picture (top right) → **Settings**
3. Scroll down to **Developer settings** (bottom of left sidebar)
4. Click **Personal access tokens** → **Tokens (classic)**
5. Click **Generate new token** → **Generate new token (classic)**

### 1.2 Configure Token
1. **Note:** "MCP Feedback System - [your MCP name]"
2. **Expiration:** Choose expiration (recommend: 90 days or 1 year)
3. **Scopes:** Select one of these:
   - ✅ **`repo`** (if your repository is **private**)
   - ✅ **`public_repo`** (if your repository is **public**)

   > **Note:** Only select `repo` or `public_repo`, not both!

4. Click **Generate token** (green button at bottom)
5. **COPY THE TOKEN IMMEDIATELY** - You won't see it again!
   - It looks like: `ghp_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8`

### 1.3 Save Token Securely
- **Don't commit to git!**
- Store in password manager or `.env` file (not tracked by git)

---

## Step 2: Copy Files to Your MCP (3 minutes)

### 2.1 Copy These 6 Files

**From `mcp_db_performance` to your MCP:**

```bash
# Copy tools (4 files)
cp mcp_db_peformance/server/tools/feedback_context.py your_mcp/server/tools/
cp mcp_db_peformance/server/tools/feedback_safety.py your_mcp/server/tools/
cp mcp_db_peformance/server/tools/feedback_quality.py your_mcp/server/tools/
cp mcp_db_peformance/server/tools/mcp_feedback.py your_mcp/server/tools/

# Copy prompt (1 file)
cp mcp_db_peformance/server/prompts/feedback_improvement.py your_mcp/server/prompts/

# Copy resource (1 file)
cp mcp_db_peformance/server/resources/mcp_welcome.py your_mcp/server/resources/
```

**Windows PowerShell:**
```powershell
Copy-Item "mcp_db_peformance\server\tools\feedback_*.py" "your_mcp\server\tools\"
Copy-Item "mcp_db_peformance\server\tools\mcp_feedback.py" "your_mcp\server\tools\"
Copy-Item "mcp_db_peformance\server\prompts\feedback_improvement.py" "your_mcp\server\prompts\"
Copy-Item "mcp_db_peformance\server\resources\mcp_welcome.py" "your_mcp\server\resources\"
```

---

## Step 3: Update Middleware (5 minutes)

### 3.1 Update `auth_middleware.py`

**Add at the top:**
```python
import hashlib  # Add this import
```

**Add this method to `AuthMiddleware` class:**
```python
def _extract_session_id(self, request: Request) -> str:
    """Extract or generate session ID from request."""
    # Check for explicit session header
    session_header = request.headers.get("x-session-id")
    if session_header:
        return session_header[:64]

    # Try MCP connection ID
    connection_id = request.headers.get("x-connection-id")
    if connection_id:
        return connection_id[:64]

    # Fallback: Create stable session from client fingerprint
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")
    fingerprint = f"{client_ip}:{user_agent}"
    session_hash = hashlib.sha256(fingerprint.encode()).hexdigest()[:32]
    return f"fp_{session_hash}"
```

**Update the `dispatch` method (before the final `return`):**
```python
# Find this line (near end of dispatch method):
# SUCCESS
logger.info(f"[AUTH] ✅ Authenticated client: {client_name} → {path}")
request.state.client_name = client_name

# ADD THESE 3 LINES:
session_id = self._extract_session_id(request)
request.state.client_id = client_name
request.state.session_id = session_id

return await call_next(request)
```

### 3.2 Update `server.py`

**Add imports at the top:**
```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request  # If not already imported
```

**Add this class (anywhere before `app = Starlette(...)`):**
```python
class SessionContextMiddleware(BaseHTTPMiddleware):
    """Sets session and client context variables for feedback tracking."""

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
```

**Update middleware registration (find the middleware section):**
```python
# BEFORE (your current code):
app.add_middleware(AuthMiddleware, config=config)

# AFTER (add SessionContextMiddleware):
app.add_middleware(AuthMiddleware, config=config)
app.add_middleware(SessionContextMiddleware)  # ADD THIS LINE

if config.auth_enabled:
    logger.info(f"🔐 Authentication ENABLED — {len(config.api_keys)} API key(s) configured")
else:
    logger.info("🔓 Authentication DISABLED")

logger.info("🔗 Session Context Middleware enabled for feedback tracking")  # ADD THIS LINE
```

---

## Step 4: Configure Settings (2 minutes)

### 4.1 Update `settings.yaml`

**Add this section (anywhere in the file, recommend after `server:` section):**

```yaml
# ============================================================================
# FEEDBACK SYSTEM CONFIGURATION
# ============================================================================
feedback:
  enabled: true

  # 👇 CHANGE THESE TWO VALUES:
  repo: "YOUR_GITHUB_USERNAME/YOUR_REPO_NAME"  # e.g., "johndoe/analytics_mcp"
  maintainer: "Your Name"                      # e.g., "John Doe"

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
    min_quality_score: 0
```

### 4.2 Update `.env`

**Add to your `.env` file:**

```bash
# GitHub Feedback System
GITHUB_TOKEN=ghp_paste_your_token_here_from_step_1
GITHUB_REPO=YOUR_USERNAME/YOUR_REPO  # Same as settings.yaml
```

**Important:** Make sure `.env` is in your `.gitignore`!

---

## Step 5: Install Dependencies (1 minute)

**Add to `requirements.txt` (if not already present):**
```
httpx>=0.24.0
pyyaml>=6.0
```

**Install:**
```bash
pip install httpx pyyaml
```

**Or rebuild Docker:**
```bash
docker-compose build
```

---

## Step 6: Test It! (5 minutes)

### 6.1 Restart Server
```bash
docker-compose restart
# OR
docker-compose down && docker-compose up -d
```

### 6.2 Check Logs
```bash
docker logs your_mcp_container --tail 50
```

**Look for these lines:**
```
📦 Auto-imported: tools.feedback_context
📦 Auto-imported: tools.feedback_safety
📦 Auto-imported: tools.feedback_quality
📦 Auto-imported: tools.mcp_feedback
📦 Auto-imported: prompts.feedback_improvement
📦 Auto-imported: resources.mcp_welcome
🔗 Session Context Middleware enabled for feedback tracking
```

**If you see errors:**
- Check file paths are correct
- Verify all 6 files were copied
- Check indentation in middleware code

### 6.3 Test via Claude Desktop

**Open Claude Desktop and connect to your MCP, then try:**

```
Can you help me report a bug in this MCP?
```

**Claude should use the `report_mcp_issue_interactive` tool.**

**Or test directly:**
```
Use the report_mcp_issue_interactive tool to report a test bug:
- Title: "Test feedback system"
- Description: "This is a test to verify the feedback system works"
- Type: bug
- Don't auto-submit, just preview
```

**Expected response:**
- Quality analysis (score 0-10)
- Preview of what will be posted
- Instructions to submit with `auto_submit=True`

### 6.4 Test Real Submission (Optional)

**⚠️ This creates a real GitHub issue!**

```
Now submit that test issue with auto_submit=True
```

**Check GitHub:**
1. Go to `https://github.com/YOUR_USERNAME/YOUR_REPO/issues`
2. You should see the new issue
3. Close it and add comment: "Test issue - closing"

---

## ✅ Done!

Your MCP now has a complete feedback system! 🎉

---

## Quick Reference Card

### For Your Users

**Report a Bug:**
```
"I found a bug - when I [describe action], [unexpected result] happens instead of [expected result]"
```

**Request a Feature:**
```
"Can you add support for [feature]? It would help with [use case]"
```

**Suggest Improvement:**
```
"The [current feature] could be better if [suggestion]"
```

**Search Issues:**
```
"Search for existing issues about [topic]"
```

**Claude will guide them through the interactive process!**

---

## Troubleshooting

### "GitHub token not configured"
- Check `.env` has `GITHUB_TOKEN=ghp_...`
- Verify token is valid (test at https://github.com/settings/tokens)
- Restart server after adding token

### "Feedback system is not enabled"
- Check `settings.yaml` has `feedback.enabled: true`
- Verify `feedback` section exists
- Restart server

### Tools not appearing
- Check logs for import errors
- Verify all 6 files were copied
- Check file names match exactly (case-sensitive)

### Session tracking not working
- Verify `SessionContextMiddleware` is added
- Check middleware order: Auth → Session Context → CORS
- Check logs for "Session context set" messages

---

## Configuration Examples

### Public MCP (More Permissive)
```yaml
feedback:
  safety:
    session_limits:
      per_hour: 5
      per_day: 20
```

### Internal MCP (More Restrictive)
```yaml
feedback:
  safety:
    session_limits:
      per_hour: 2
      per_day: 5
```

### Enforce Quality Standards
```yaml
feedback:
  quality:
    min_quality_score: 4  # Require at least 4/10
```

### Disable Team Limits
```yaml
feedback:
  safety:
    client_limits:
      per_hour: null  # No team limit
      per_day: null
```

---

## Security Notes

### Token Security
- ✅ Store in `.env` (not in git)
- ✅ Use minimal scopes (`public_repo` for public repos)
- ✅ Set expiration (rotate regularly)
- ✅ Revoke immediately if compromised

### Rate Limiting
- Prevents spam and abuse
- Fair for legitimate users
- Team limits prevent coordination attacks
- Auto-blocking for rapid submissions

### Privacy
- No personal information collected
- Only session/client IDs (hashed fingerprints)
- GitHub issues are public (users are warned)

---

## What to Customize

**Change repository:**
- `settings.yaml`: `feedback.repo`
- `.env`: `GITHUB_REPO`

**Adjust rate limits:**
- `settings.yaml`: `feedback.safety.session_limits`
- `settings.yaml`: `feedback.safety.client_limits`

**Change quality thresholds:**
- `settings.yaml`: `feedback.quality.min_quality_score`

**Customize validation:**
- Edit `server/tools/feedback_safety.py` → `validate_content()`

**Customize quality scoring:**
- Edit `server/tools/feedback_quality.py` → weights in `__init__`

---

## Next Steps

1. ✅ Test thoroughly with different scenarios
2. ✅ Monitor first issues for quality
3. ✅ Adjust rate limits based on usage
4. ✅ Add feedback system to your other MCPs!

---

**Total time: ~15 minutes** ⏱️

**Files changed: 4** 📝

**Files added: 6** ➕

**Lines of code added: ~50** 💻

**Result: Complete interactive feedback system!** 🎉
