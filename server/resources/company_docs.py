from mcp_app import mcp

@mcp.resource("company://docs/welcome")
def get_welcome_doc() -> str:
    """
    Company welcome document resource.
    """
    return """
# Welcome to Our Company!

## Mission
We build amazing AI-powered tools to help developers create better software.

## Values
- Innovation: Always push boundaries
- Collaboration: Work together effectively
- Quality: Never compromise on excellence

## Getting Started
1. Complete your onboarding tasks
2. Meet your team members
3. Set up your development environment
4. Read our engineering guidelines
"""

@mcp.resource("company://policies/vacation")
def get_vacation_policy() -> str:
    """
    Company vacation policy resource.
    """
    return """
# Vacation Policy

## Allowance
- New employees: 15 days/year
- After 2 years: 20 days/year
- After 5 years: 25 days/year

## Request Process
1. Submit request 2 weeks in advance
2. Get manager approval
3. Update team calendar
4. Log in HR system

## Blackout Periods
- End of quarter (last week)
- Major product launches
"""

@mcp.resource("oracle://tuning/rules")
def oracle_rules() -> str:
    return """# Oracle Tuning Rules
- Avoid SELECT *
- Avoid leading wildcard in LIKE ('%abc')
- Prefer explicit JOIN over implicit comma joins
- Check full table scans; add indexes if needed
- Provide actionable SQL rewrites and DDL when possible
"""