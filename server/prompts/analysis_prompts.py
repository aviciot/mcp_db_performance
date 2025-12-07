from mcp_app import mcp

@mcp.prompt()
def oracle_query_tuning_prompt(query: str, execution_plan: str = "", error_message: str = ""):
    """
    Oracle query performance tuning prompt.
    
    IMPORTANT: MCP prompts should return a STRING, not a list of messages.
    The client will handle wrapping it in messages for the LLM.
    
    Args:
        query: The SQL query to analyze
        execution_plan: Execution plan from EXPLAIN PLAN or DBMS_XPLAN (optional)
        error_message: Any error message if query failed (optional)
        
    Returns:
        Formatted string prompt for query tuning analysis
    """
    
    plan = execution_plan or "❌ No execution plan provided"
    err  = error_message  or "✅ No errors"

    # Return a single string that combines everything
    return f"""
# 🔍 Oracle Query Performance Analysis

## 📋 INSTRUCTIONS:
1. **FIRST**: Read the tuning rules from resource: oracle://tuning/rules
2. **FOLLOW**: Apply those rules strictly during your analysis
3. **OUTPUT**: Provide recommendations in the specified format below

---

## 🗄️ Query to Analyze:
```sql
{query}
```

## 📊 Execution Plan:
{plan}

## ⚠️ Error Message:
{err}

---

## 🎯 Analysis Required:

### 1. Quick Assessment (⏱️ 10 seconds scan)
- Is this query efficient or problematic?
- Severity: LOW / MEDIUM / HIGH / CRITICAL

### 2. Issues Found
List each issue with:
- **Issue**: What's wrong
- **Impact**: Performance impact (1-10 scale)
- **Evidence**: What in the plan shows this

### 3. Recommendations (Apply rules from oracle://tuning/rules!)
For each issue, provide:
- **Fix**: Specific action to take
- **Priority**: HIGH / MEDIUM / LOW
- **Example**: Show the improved query/index

### 4. Quick Wins
List 1-3 immediate actions that give biggest impact.

---

## 📏 Output Format:
Use clear sections with emojis for readability.
Be specific - no generic advice!
Reference line numbers from execution plan when relevant.

## 👨‍💼 Role:
You are an expert Oracle SQL performance tuning specialist. Analyze the SQL and plan, identify concrete issues, and give specific fixes.
"""


# Alternative: If you want to use the messages format, use this pattern:
@mcp.prompt()
def oracle_query_tuning_prompt_v2(query: str, execution_plan: str = "", error_message: str = ""):
    """
    Alternative version using the messages format.
    This returns the prompt content but FastMCP will wrap it properly.
    """
    
    plan = execution_plan or "❌ No execution plan provided"
    err  = error_message  or "✅ No errors"

    # Create the main prompt content
    prompt_content = f"""
# 🔍 Oracle Query Performance Analysis

## 📋 INSTRUCTIONS:
1. **FIRST**: Read the tuning rules from resource: oracle://tuning/rules
2. **FOLLOW**: Apply those rules strictly during your analysis
3. **OUTPUT**: Provide recommendations in the specified format below

---

## 🗄️ Query to Analyze:
```sql
{query}
```

## 📊 Execution Plan:
{plan}

## ⚠️ Error Message:
{err}

---

## 🎯 Analysis Required:

### 1. Quick Assessment (⏱️ 10 seconds scan)
- Is this query efficient or problematic?
- Severity: LOW / MEDIUM / HIGH / CRITICAL

### 2. Issues Found
List each issue with:
- **Issue**: What's wrong
- **Impact**: Performance impact (1-10 scale)
- **Evidence**: What in the plan shows this

### 3. Recommendations (Apply rules from oracle://tuning/rules!)
For each issue, provide:
- **Fix**: Specific action to take
- **Priority**: HIGH / MEDIUM / LOW
- **Example**: Show the improved query/index

### 4. Quick Wins
List 1-3 immediate actions that give biggest impact.

---

## 📏 Output Format:
Use clear sections with emojis for readability.
Be specific - no generic advice!
Reference line numbers from execution plan when relevant.
"""
    
    # Return just the string - FastMCP handles the message wrapping
    return prompt_content






@mcp.prompt()
def oracle_query_tuning_prompt_v3(query: str, execution_plan: str = "", error_message: str = "") -> str:
    """
    Oracle query tuning prompt with structured output.

    Args:
        query: The SQL query to analyze
        execution_plan: Execution plan as plain text from EXPLAIN PLAN or DBMS_XPLAN.DISPLAY (optional)
        error_message: Any error message if query failed (optional)

    Returns:
        Structured prompt for query tuning analysis
    """
    plan = execution_plan or "❌ No execution plan provided"
    err = error_message or "✅ No errors"

    return f"""
# 🔍 Oracle Query Performance Analysis

## 📋 INSTRUCTIONS:
1. **Read**: Load tuning rules from resource: oracle://tuning/rules
2. **Apply**: Strictly follow rules for analysis
3. **Output**: Use exact format below, starting with SEVERITY and ISSUE_COUNT

---

## 🗄️ Query to Analyze:
```sql
{query}
```

## 📊 Execution Plan:
{plan}

## ⚠️ Error Message:
{err}

---

## 🎯 Required Analysis Format:
### STEP 1: Summary Header (REQUIRED - EXACT FORMAT)
SEVERITY: [LOW|MEDIUM|HIGH|CRITICAL]
ISSUE_COUNT: [number]

### STEP 2: Issues
For each issue, use:
ISSUE_[n]: Brief title
Description: Specific issue details
Impact: [1-10]/10
Fix: Actionable solution with SQL/DDL if applicable

### STEP 3: Quick Wins
List 1-3 high-impact actions:
QUICKWIN_[n]: Specific action (e.g., "Create index on table.column")

### STEP 4: Detailed Recommendations
- Full analysis with executable SQL/DDL
- Reference execution plan line numbers
- Use table/column names from query

---

## 📏 Rules:
- Follow oracle://tuning/rules strictly
- Use exact format (SEVERITY:, ISSUE_COUNT:, ISSUE_[n]:, QUICKWIN_[n]:)
- Provide specific, executable SQL
- Classify severity per rules
- Assume execution_plan is plain text from DBMS_XPLAN.DISPLAY
"""