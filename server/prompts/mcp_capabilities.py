"""MCP capabilities description - helps LLM understand scope."""

from mcp_app import mcp


@mcp.prompt(
    name="mcp_capabilities",
    description="Describes what this MCP does - use before reporting issues"
)
async def get_mcp_capabilities():
    """
    Returns a clear description of MCP capabilities.
    LLM should read this to understand scope before validating feedback.
    """
    return """
# Database Query Analysis MCP - Capabilities

## What This MCP Does

### Core Features
1. **SQL Query Performance Analysis**
   - Oracle and MySQL support
   - Execution plan generation and explanation
   - Cost analysis and optimization recommendations
   - Index usage tracking

2. **Business Logic Explanation**
   - Table relationship discovery
   - Column meaning inference from database comments
   - Query intent analysis (what it does in business terms)

3. **Performance Monitoring**
   - Query execution history tracking
   - Performance degradation detection
   - Cache-based metadata optimization

4. **Optimization Recommendations**
   - Index suggestions
   - Query rewrite proposals
   - Join order optimization
   - Predicate pushdown analysis

## What This MCP Does NOT Do

❌ General software development
❌ Non-database functionality
❌ Entertainment or unrelated features
❌ Data modification or schema changes (read-only analysis)

## When to Report Issues

### ✅ Valid Bug Reports
- Query analysis tools returning errors
- Execution plans not displaying correctly
- Performance recommendations missing
- Business logic explanation failures
- Caching or connection issues

### ✅ Valid Feature Requests
- Support for additional database types
- New optimization recommendations
- Better execution plan visualization
- Enhanced metadata collection

### ❌ Invalid Requests
- Features unrelated to database analysis
- Jokes or test submissions
- Requests for non-database functionality
- Off-topic suggestions

## Example Valid Feedback

- "analyze_oracle_query times out on queries with 10+ joins"
- "Add support for PostgreSQL execution plans"
- "Include index cardinality in recommendations"
- "Business logic explanation doesn't follow foreign keys"

## Example Invalid Feedback

- "Add lyrics to query results" (not database-related)
- "Order pizza when analysis fails" (joke/absurd)
- "Make it faster" (too vague, no context)
- "Doesn't work" (no details about what/how)
"""
