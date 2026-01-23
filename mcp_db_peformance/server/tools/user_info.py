"""
User Identity and Capabilities Tool
===================================
Shows current user identity, role, and available tool categories.

Provides a welcome message showing what the user can access.
"""

import logging
from mcp_app import mcp
from tools.tool_auth import get_user_info

logger = logging.getLogger(__name__)


@mcp.tool(
    name="who_am_i",
    description=(
        "Show your current identity, role, and available tool categories.\n\n"
        "Returns:\n"
        "- Your client ID and session ID\n"
        "- Your role (admin, dba, user, or anonymous)\n"
        "- Capabilities based on your role\n"
        "- List of tool categories you can access\n\n"
        "Use this to understand what tools are available to you."
    )
)
async def who_am_i():
    """
    Display user identity and permissions.

    Shows:
    - User identity (client_id, session_id, role)
    - Capabilities (what you can access)
    - Available tool categories
    - Hints for accessing restricted tools
    """
    logger.info("who_am_i tool called")

    user_info = get_user_info()
    client_id = user_info.get("client_id", "anonymous")
    session_id = user_info.get("session_id", "unknown")
    role = user_info.get("role", "anonymous")

    # Determine capabilities based on role
    is_admin = role == "admin"
    is_dba = role in ["admin", "dba"]
    is_user = role not in ["anonymous"]

    capabilities = {
        "query_analysis": is_user,  # Requires authentication
        "feedback_system": is_user,  # Requires authentication
        "dba_tools": is_dba,         # Only admin/dba
        "admin_tools": is_admin      # Only admin
    }

    # Build list of available tool categories
    available_categories = []

    if capabilities["query_analysis"]:
        available_categories.append({
            "category": "🔍 Query Analysis",
            "tools": [
                "analyze_oracle_query - Analyze Oracle query performance",
                "analyze_mysql_query - Analyze MySQL query performance",
                "compare_oracle_plans - Compare execution plans",
                "check_oracle_access - Verify database permissions",
                "check_mysql_access - Verify MySQL permissions"
            ],
            "description": "Performance analysis and optimization tools"
        })

    if capabilities["feedback_system"]:
        available_categories.append({
            "category": "💬 Feedback System",
            "tools": [
                "report_mcp_issue_interactive - Report bugs or request features",
                "search_mcp_issues - Search existing issues",
                "improve_my_feedback - Get help improving feedback quality"
            ],
            "description": "Help improve this MCP by reporting issues"
        })

    if capabilities["dba_tools"]:
        available_categories.append({
            "category": "🔧 DBA Tools",
            "tools": [
                "get_active_sessions - List active database sessions",
                "get_lock_info - Show blocking/locking information",
                "get_db_users - List database users and permissions",
                "show_dba_tools - Detailed DBA tools documentation"
            ],
            "description": "Operational database administration tools"
        })

    if capabilities["admin_tools"]:
        available_categories.append({
            "category": "👨‍💼 Admin Tools",
            "tools": [
                "get_feedback_dashboard - View feedback analytics",
                "moderate_feedback - Review and manage feedback",
                "manage_rate_limits - Configure rate limiting"
            ],
            "description": "Administrative and moderation tools"
        })

    # Generate welcome message
    if is_admin:
        welcome_msg = f"👋 Welcome back, {client_id}! You have full admin access to all tools."
    elif is_dba:
        welcome_msg = f"👋 Welcome, {client_id}! You have DBA access including operational tools."
    elif is_user:
        welcome_msg = f"👋 Welcome, {client_id}! You have access to query analysis and feedback tools."
    else:
        welcome_msg = "🔒 Anonymous access. Please authenticate to use tools."

    # Add hints based on role
    hints = []
    if not capabilities["dba_tools"] and is_user:
        hints.append("💡 For DBA tools access, contact your administrator")
    if capabilities["dba_tools"]:
        hints.append("💡 Use 'show_dba_tools' to see detailed DBA tools documentation")
    if capabilities["feedback_system"]:
        hints.append("💡 Use 'report_mcp_issue_interactive' to report bugs or request features")

    result = {
        "welcome": welcome_msg,
        "identity": {
            "client_id": client_id,
            "session_id": session_id[:8] + "...",  # First 8 chars only for privacy
            "role": role,
            "authenticated": is_user
        },
        "capabilities": capabilities,
        "available_tool_categories": available_categories,
        "total_tool_categories": len(available_categories),
        "hints": hints
    }

    logger.info(f"User identity check: {client_id} (role: {role})")
    return result


@mcp.tool(
    name="list_my_tools",
    description=(
        "List all tools available to your current role.\n\n"
        "Returns a comprehensive list of tools you can use, organized by category.\n"
        "Each tool includes its name, description, and usage examples."
    )
)
async def list_my_tools():
    """
    List all tools available to current user based on role.

    Provides detailed information about each accessible tool including:
    - Tool name
    - Purpose
    - Parameters
    - Examples
    """
    logger.info("list_my_tools tool called")

    user_info = get_user_info()
    role = user_info.get("role", "anonymous")
    client_id = user_info.get("client_id", "anonymous")

    is_admin = role == "admin"
    is_dba = role in ["admin", "dba"]
    is_user = role not in ["anonymous"]

    tools_by_category = {}

    # Query Analysis Tools (all authenticated users)
    if is_user:
        tools_by_category["Query Analysis"] = [
            {
                "name": "analyze_oracle_query",
                "purpose": "Analyze Oracle query performance and get optimization recommendations",
                "access": "All users",
                "example": "analyze_oracle_query(db_name='transformer_prod', sql_text='SELECT ...', depth='standard')"
            },
            {
                "name": "analyze_mysql_query",
                "purpose": "Analyze MySQL query performance and get optimization recommendations",
                "access": "All users",
                "example": "analyze_mysql_query(db_name='mysql_devdb03_avi', sql_text='SELECT ...', depth='standard')"
            },
            {
                "name": "compare_oracle_plans",
                "purpose": "Compare execution plans before and after optimization",
                "access": "All users",
                "example": "compare_oracle_plans(db_name='transformer_prod', original_sql='...', optimized_sql='...')"
            }
        ]

        tools_by_category["Database Access Verification"] = [
            {
                "name": "check_oracle_access",
                "purpose": "Verify Oracle database permissions and capabilities",
                "access": "All users",
                "example": "check_oracle_access(db_preset='transformer_prod')"
            },
            {
                "name": "check_mysql_access",
                "purpose": "Verify MySQL database permissions and capabilities",
                "access": "All users",
                "example": "check_mysql_access(db_preset='mysql_devdb03_avi')"
            }
        ]

    # Feedback Tools (all authenticated users)
    if is_user:
        tools_by_category["Feedback System"] = [
            {
                "name": "report_mcp_issue_interactive",
                "purpose": "Report bugs, request features, or suggest improvements",
                "access": "All users",
                "example": "report_mcp_issue_interactive(issue_type='bug', title='...', description='...', auto_submit=False)"
            },
            {
                "name": "search_mcp_issues",
                "purpose": "Search existing GitHub issues to avoid duplicates",
                "access": "All users",
                "example": "search_mcp_issues(query='performance slow', state='open')"
            },
            {
                "name": "improve_my_feedback",
                "purpose": "Get AI assistance to improve feedback clarity",
                "access": "All users",
                "example": "improve_my_feedback(issue_type='bug', title='...', description='...')"
            }
        ]

    # DBA Tools (admin and dba only)
    if is_dba:
        tools_by_category["DBA Operations"] = [
            {
                "name": "get_active_sessions",
                "purpose": "List active database sessions/connections",
                "access": "Admin, DBA",
                "example": "get_active_sessions(db_name='transformer_prod', limit=50)",
                "read_only": True
            },
            {
                "name": "get_lock_info",
                "purpose": "Show blocking/locking information",
                "access": "Admin, DBA",
                "example": "get_lock_info(db_name='transformer_prod')",
                "read_only": True
            },
            {
                "name": "get_db_users",
                "purpose": "List database users and permissions",
                "access": "Admin, DBA",
                "example": "get_db_users(db_name='transformer_prod', limit=200)",
                "read_only": True
            },
            {
                "name": "show_dba_tools",
                "purpose": "Detailed documentation for DBA tools",
                "access": "Admin, DBA",
                "example": "show_dba_tools()"
            }
        ]

    # Admin Tools (admin only)
    if is_admin:
        tools_by_category["Administration"] = [
            {
                "name": "get_feedback_dashboard",
                "purpose": "View feedback analytics and statistics",
                "access": "Admin only",
                "example": "get_feedback_dashboard()"
            }
        ]

    # Identity Tools (everyone)
    tools_by_category["User Identity"] = [
        {
            "name": "who_am_i",
            "purpose": "Show your identity, role, and capabilities",
            "access": "Everyone",
            "example": "who_am_i()"
        },
        {
            "name": "list_my_tools",
            "purpose": "List all tools available to your role",
            "access": "Everyone",
            "example": "list_my_tools()"
        }
    ]

    result = {
        "user": {
            "client_id": client_id,
            "role": role
        },
        "tools_by_category": tools_by_category,
        "total_categories": len(tools_by_category),
        "total_tools": sum(len(tools) for tools in tools_by_category.values()),
        "note": "All DBA tools are read-only and safe to use"
    }

    logger.info(f"Tools list generated for: {client_id} (role: {role})")
    return result
