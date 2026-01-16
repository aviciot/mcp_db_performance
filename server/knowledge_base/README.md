# Performance MCP - Knowledge Base

This knowledge base contains comprehensive documentation for the Performance MCP Server, its tools, and how to use them effectively.

## Documentation Structure

- **overview.md** - MCP purpose, capabilities, and when to use it
- **workflows.md** - Common usage patterns and step-by-step guides
- **tools/** - Detailed documentation for each tool
- **troubleshooting.md** - Common errors and solutions
- **architecture.md** - How the MCP works internally

## Quick Navigation

### Getting Started
- [What is Performance MCP?](overview.md#what-is-performance-mcp)
- [When to use this MCP](overview.md#when-to-use)
- [What this MCP does NOT do](overview.md#what-this-mcp-does-not-do)

### Common Workflows
- [Analyzing a slow query](workflows.md#slow-query-analysis)
- [Comparing query plans](workflows.md#query-plan-comparison)
- [Checking database permissions](workflows.md#permission-verification)

### Tools by Category

**Oracle Analysis:**
- [analyze_oracle_query](tools/analyze_oracle_query.md) - Main Oracle performance analysis
- [compare_oracle_plans](tools/compare_oracle_plans.md) - Before/after comparison
- [check_oracle_access](tools/check_oracle_access.md) - Verify permissions

**MySQL Analysis:**
- [analyze_mysql_query](tools/analyze_mysql_query.md) - Main MySQL performance analysis
- [check_mysql_access](tools/check_mysql_access.md) - Verify permissions

**Monitoring:**
- [collect_oracle_system_health](tools/collect_oracle_system_health.md) - Real-time metrics
- [get_oracle_top_queries](tools/get_oracle_top_queries.md) - Most expensive queries

### Troubleshooting
- [Common errors](troubleshooting.md#common-errors)
- [Permission issues](troubleshooting.md#permission-issues)
- [Connection problems](troubleshooting.md#connection-problems)

## For Maintainers

When adding a new tool, create:
1. Tool documentation in `tools/{tool_name}.md`
2. Update this README with link
3. Add examples to `workflows.md` if applicable
4. Update troubleshooting.md with common errors

Template: See `tools/_template.md`
