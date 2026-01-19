# Quality Settings Explained - Feedback System

## Overview
The feedback system uses AI-powered quality analysis to ensure bug reports and feature requests are clear, actionable, and complete before creating GitHub issues.

## Quality Settings in `settings.yaml`

```yaml
feedback:
  quality:
    enabled: true                      # Enable/disable AI quality analysis
    auto_improve: true                 # Auto-suggest improvements for low-quality feedback
    auto_improve_threshold: 4.0        # Score below this triggers improvement suggestions
    good_quality_threshold: 7.0        # Score above this gets "good-quality" GitHub label
    min_quality_score: 0               # Minimum score to accept (0 = accept all with suggestions)
```

## How Quality Scoring Works

### 1. AI Quality Analysis (0-10 Scale)

When a user submits feedback, the system scores it based on:
- **Clarity** - Is the issue description clear and understandable?
- **Completeness** - Does it include all necessary details?
- **Actionability** - Can a developer act on this information?
- **Specificity** - Are concrete examples provided?

### 2. Quality Thresholds

#### `auto_improve_threshold: 4.0`
**Triggers when:** Score < 4.0
**What happens:** System responds with improvement suggestions

**Example:**
```
User submits: "Title: bug, Description: doesnt work"
Quality Score: 2.3/10

System Response:
"❌ Your feedback needs improvement before submission:

**Issues Found:**
- Title too vague - specify what component/feature is broken
- Description lacks details - what doesn't work? What did you expect?
- Missing steps to reproduce
- No error messages or symptoms provided

**How to Improve:**
1. Title: Be specific (e.g., "Database timeout on large table queries")
2. Description: Include what you tried, what happened, what you expected
3. Add steps to reproduce the issue
4. Include any error messages
```

#### `good_quality_threshold: 7.0`
**Triggers when:** Score >= 7.0
**What happens:** GitHub issue gets "good-quality" label automatically

**Example:**
```
User submits:
Title: "Database connection timeout when querying tables > 1M rows"
Description: "When I run SELECT * FROM large_table WHERE date > '2024-01-01',
             the query times out after 30 seconds. Expected: Query completes
             or shows progress. Database: Oracle 19c. Table size: 2.5M rows."

Quality Score: 8.1/10
→ Issue created with labels: ["bug", "user-submitted", "good-quality"]
```

#### `min_quality_score: 0`
**Current setting:** Accept all feedback regardless of score
**Purpose:** Suggestions only, not rejection
**Alternative:** Set to `3.0` to reject submissions below 3/10

## Real-World Examples

### Example 1: Poor Quality (Score 1.5/10)
```
Title: "help"
Description: "broken"

→ Feedback rejected with specific improvement guidance
```

### Example 2: Medium Quality (Score 5.2/10)
```
Title: "Query takes too long"
Description: "Some queries are slow when I search for data"

→ Feedback accepted but suggestions provided:
   - Which queries are slow?
   - What table/data size?
   - How long is "too long"?
   - What's acceptable performance?
```

### Example 3: High Quality (Score 8.7/10)
```
Title: "Oracle EXPLAIN PLAN fails for queries with table aliases"
Description: "When using table aliases in Oracle queries, the explain_oracle_query
             tool returns 'ORA-00942: table or view does not exist'. This happens
             because aliases aren't expanded before running EXPLAIN PLAN.

             Example query: SELECT * FROM users u WHERE u.id = 123
             Error: ORA-00942: table or view does not exist

             Expected: EXPLAIN PLAN should handle aliases correctly
             Database: Oracle 19c on transformer_prod
             MCP Version: 1.2.3"

→ Issue created immediately with "good-quality" label
```

## Configuration Recommendations

### Permissive (Current Settings)
```yaml
auto_improve_threshold: 4.0
good_quality_threshold: 7.0
min_quality_score: 0
```
- Accepts all feedback
- Provides suggestions for scores < 4
- Labels excellent feedback (>= 7)
- Best for: Open source projects wanting maximum user input

### Balanced
```yaml
auto_improve_threshold: 5.0
good_quality_threshold: 7.5
min_quality_score: 3.0
```
- Rejects very poor feedback (< 3)
- Suggests improvements for medium quality (3-5)
- Labels excellent feedback (>= 7.5)
- Best for: Production systems with limited review bandwidth

### Strict
```yaml
auto_improve_threshold: 6.0
good_quality_threshold: 8.0
min_quality_score: 5.0
```
- Only accepts well-written feedback (>= 5)
- Suggests improvements for anything < 6
- Only labels truly excellent feedback (>= 8)
- Best for: Enterprise systems requiring high-quality issue tracking

## How to Adjust Settings

1. **Edit settings.yaml:**
   ```bash
   vi mcp_db_peformance/server/config/settings.yaml
   ```

2. **Modify quality thresholds:**
   ```yaml
   quality:
     auto_improve_threshold: 5.0  # Your desired threshold
     good_quality_threshold: 8.0  # Your desired threshold
     min_quality_score: 3.0       # Your desired minimum
   ```

3. **Restart the server:**
   ```bash
   docker-compose restart
   ```

4. **No code changes needed!** Settings are loaded dynamically.

## Monitoring Quality

### View Quality Metrics (Admin Only)
Use the admin dashboard tool:
```
get_feedback_dashboard(limit=20)
```

Shows:
- Average quality score across all submissions
- Distribution of scores
- Most common quality issues
- Trend over time

### Quality Indicators
- **Average Score < 4:** Users need better guidance
- **Average Score 4-6:** Healthy mix of user levels
- **Average Score > 7:** Excellent user engagement

## Benefits of Quality System

1. **Reduces Noise** - Filters out "doesn't work" style reports
2. **Saves Time** - High-quality issues need less back-and-forth
3. **Educates Users** - Teaches good bug reporting through suggestions
4. **Automatic Triage** - Labels help prioritize which issues to review first
5. **No Manual Review** - AI handles initial quality check 24/7

## Technical Details

### Where Quality is Checked
- `tools/feedback_quality.py` - AI-powered quality analyzer
- `tools/mcp_feedback.py` - Main feedback submission tool
- `tools/feedback_safety.py` - Rate limiting and content validation

### Quality Analyzer Uses
- Claude API (Haiku model for speed/cost)
- Prompt engineering for consistent scoring
- Caching for repeated similar feedback
- <5 second analysis time typically

## Troubleshooting

**Q: All feedback scores 0/10**
A: Check `quality.enabled: true` in settings.yaml

**Q: No improvement suggestions showing**
A: Check `quality.auto_improve: true` in settings.yaml

**Q: Scores seem too harsh/lenient**
A: Adjust `auto_improve_threshold` up/down by 0.5-1.0

**Q: Want to disable quality checking**
A: Set `quality.enabled: false` - accepts all feedback without analysis
