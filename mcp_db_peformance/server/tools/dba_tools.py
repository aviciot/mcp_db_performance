"""
DBA-focused tools for operational visibility.
============================================
Role-based access: Admin and DBA only
All tools are read-only - no writes or destructive operations.

Imported from mcp_db_peformance_v2 with role-based access control.
"""

import logging
from mcp_app import mcp
from config import config
from db_connector import oracle_connector
import mysql_connector
from tools.db_availability import ensure_db_available
from tools.tool_auth import require_roles

logger = logging.getLogger(__name__)


def _get_db_connector_and_type(db_name: str):
    """
    Get database connector and type for specified database.

    Args:
        db_name: Database preset name from configuration

    Returns:
        Tuple of (connector, db_type)

    Raises:
        ValueError: If database not found or connection failed
    """
    if db_name not in config.database_presets:
        raise ValueError(f"Database '{db_name}' not found in configuration")

    availability = ensure_db_available(db_name)
    if not availability.get("ok"):
        raise ValueError(availability.get("message", "Database connection failed"))

    db_config = config.database_presets[db_name]
    db_type = db_config.get("type", "oracle").lower()

    if db_type == "oracle":
        return oracle_connector, "oracle"
    if db_type in ("mysql", "mariadb"):
        return mysql_connector, "mysql"
    raise ValueError(f"Unsupported database type: {db_type}")


class ConnectorWrapper:
    """Wrapper to provide consistent async interface for both Oracle and MySQL."""

    def __init__(self, connection, db_type_val: str):
        self.connection = connection
        self.db_type = db_type_val

    async def execute(self, query, params=None):
        """
        Execute query and return results as list of dicts.

        Args:
            query: SQL query to execute
            params: Optional query parameters

        Returns:
            List of dicts with column names as keys
        """
        cursor = self.connection.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        # Handle non-SELECT queries (shouldn't happen in read-only tools)
        if not cursor.description:
            return []

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows] if rows else []


@mcp.tool(
    name="get_active_sessions",
    description=(
        "List active database sessions or connections. **Requires admin or dba role.**\n\n"
        "Use when:\n"
        "- Diagnosing database load\n"
        "- Checking who's connected\n"
        "- Investigating performance issues\n"
        "- Auditing current activity\n\n"
        "Returns list of active sessions with user, machine, program, and status.\n"
        "**Read-only**: This tool does not modify any data."
    ),
)
@require_roles(['admin', 'dba'])
async def get_active_sessions(db_name: str, limit: int = 50):
    """
    List active database sessions.

    Args:
        db_name: Database preset name (e.g., 'transformer_prod')
        limit: Maximum number of sessions to return (default: 50)

    Returns:
        Dict with db_type and list of active sessions

    Example:
        get_active_sessions(db_name='transformer_prod', limit=10)
    """
    logger.info(f"get_active_sessions(db={db_name}, limit={limit})")

    try:
        connector, db_type = _get_db_connector_and_type(db_name)
        conn = connector.connect(db_name)
        wrapped = ConnectorWrapper(conn, db_type)

        if db_type == "oracle":
            # Oracle: Query v$session
            query = """
                SELECT username, status, machine, program, module, logon_time
                FROM v$session
                WHERE type = 'USER'
                ORDER BY logon_time DESC
            """
        else:
            # MySQL: Query processlist
            query = """
                SELECT user, host, db, command, time, state, info
                FROM information_schema.processlist
                ORDER BY time DESC
            """

        rows = await wrapped.execute(query)
        conn.close()

        return {
            "db_type": db_type,
            "db_name": db_name,
            "sessions": rows[:limit],
            "total_returned": len(rows[:limit]),
            "note": "Read-only query - no data modified"
        }

    except Exception as exc:
        logger.error(f"Error in get_active_sessions: {exc}", exc_info=True)
        return {
            "error": str(exc),
            "db_name": db_name,
            "hint": "Check database connectivity and permissions"
        }


@mcp.tool(
    name="get_lock_info",
    description=(
        "Show blocking/locking information. **Requires admin or dba role.**\n\n"
        "Use when:\n"
        "- Queries hang or timeout\n"
        "- Investigating deadlocks\n"
        "- Diagnosing blocking sessions\n"
        "- Understanding lock contention\n\n"
        "Returns lock details including blocking sessions and lock types.\n"
        "**Read-only**: This tool does not modify any data."
    ),
)
@require_roles(['admin', 'dba'])
async def get_lock_info(db_name: str):
    """
    Show database locking information.

    Args:
        db_name: Database preset name (e.g., 'transformer_prod')

    Returns:
        Dict with db_type and list of locks/blocking sessions

    Example:
        get_lock_info(db_name='transformer_prod')
    """
    logger.info(f"get_lock_info(db={db_name})")

    try:
        connector, db_type = _get_db_connector_and_type(db_name)
        conn = connector.connect(db_name)
        wrapped = ConnectorWrapper(conn, db_type)

        if db_type == "oracle":
            # Oracle: Query v$lock and v$session
            query = """
                SELECT s.sid, s.serial#, s.username, s.status,
                       l.type, l.lmode, l.request, l.block
                FROM v$lock l
                JOIN v$session s ON l.sid = s.sid
                WHERE s.username IS NOT NULL
            """
            rows = await wrapped.execute(query)
        else:
            # MySQL: Query metadata_locks
            query = """
                SELECT object_type, object_schema, object_name, lock_type, lock_duration
                FROM performance_schema.metadata_locks
                WHERE lock_status = 'GRANTED'
            """
            rows = await wrapped.execute(query)

        conn.close()

        return {
            "db_type": db_type,
            "db_name": db_name,
            "locks": rows,
            "total_locks": len(rows),
            "note": "Read-only query - no data modified"
        }

    except Exception as exc:
        logger.error(f"Error in get_lock_info: {exc}", exc_info=True)
        return {
            "error": str(exc),
            "db_name": db_name,
            "hint": "Check database connectivity and permissions for lock views"
        }


@mcp.tool(
    name="get_db_users",
    description=(
        "List database users and permissions. **Requires admin or dba role.**\n\n"
        "Use when:\n"
        "- Auditing database access\n"
        "- Validating user ownership\n"
        "- Security review\n"
        "- Understanding privilege assignments\n\n"
        "Returns list of database users with account status and privileges.\n"
        "**Read-only**: This tool does not modify any data."
    ),
)
@require_roles(['admin', 'dba'])
async def get_db_users(db_name: str, limit: int = 200):
    """
    List database users and their permissions.

    Args:
        db_name: Database preset name (e.g., 'transformer_prod')
        limit: Maximum number of users to return (default: 200)

    Returns:
        Dict with db_type and list of users with permissions

    Example:
        get_db_users(db_name='transformer_prod', limit=50)
    """
    logger.info(f"get_db_users(db={db_name}, limit={limit})")

    try:
        connector, db_type = _get_db_connector_and_type(db_name)
        conn = connector.connect(db_name)
        wrapped = ConnectorWrapper(conn, db_type)

        if db_type == "oracle":
            # Oracle: Query dba_users
            query = "SELECT username, account_status, created FROM dba_users"
        else:
            # MySQL: Query user_privileges
            query = """
                SELECT grantee, privilege_type, is_grantable
                FROM information_schema.user_privileges
            """

        rows = await wrapped.execute(query)
        conn.close()

        return {
            "db_type": db_type,
            "db_name": db_name,
            "users": rows[:limit],
            "total_returned": len(rows[:limit]),
            "note": "Read-only query - no data modified"
        }

    except Exception as exc:
        logger.error(f"Error in get_db_users: {exc}", exc_info=True)
        return {
            "error": str(exc),
            "db_name": db_name,
            "hint": "Check database connectivity and DBA permissions"
        }


@mcp.tool(
    name="show_dba_tools",
    description=(
        "Show detailed documentation for DBA tools. **Requires admin or dba role.**\n\n"
        "Returns comprehensive guide including:\n"
        "- Tool descriptions and purposes\n"
        "- When to use each tool\n"
        "- Parameters and examples\n"
        "- Safety information\n\n"
        "Use this to understand all available DBA operational tools."
    )
)
@require_roles(['admin', 'dba'])
async def show_dba_tools():
    """
    Show comprehensive DBA tools documentation.

    Returns:
        Dict with tool descriptions, examples, and usage guidelines
    """
    logger.info("show_dba_tools called")

    return {
        "dba_tools_guide": {
            "overview": "DBA tools provide operational visibility into database systems",
            "access_control": "Restricted to admin and dba roles only",
            "safety": "All tools are read-only - no writes, deletes, or destructive operations"
        },

        "tools": [
            {
                "name": "get_active_sessions",
                "purpose": "List active database sessions/connections",
                "use_when": [
                    "Diagnosing database load",
                    "Checking who's connected",
                    "Investigating performance issues",
                    "Auditing current activity"
                ],
                "parameters": {
                    "db_name": "Database preset name (required)",
                    "limit": "Max sessions to return (default: 50)"
                },
                "returns": "List of active sessions with user, machine, program, status, logon_time",
                "example": "get_active_sessions(db_name='transformer_prod', limit=10)",
                "oracle_query": "SELECT * FROM v$session WHERE type = 'USER'",
                "mysql_query": "SELECT * FROM information_schema.processlist",
                "read_only": True
            },
            {
                "name": "get_lock_info",
                "purpose": "Show blocking/locking information",
                "use_when": [
                    "Queries hang or timeout",
                    "Investigating deadlocks",
                    "Diagnosing blocking sessions",
                    "Understanding lock contention"
                ],
                "parameters": {
                    "db_name": "Database preset name (required)"
                },
                "returns": "Lock details with blocking sessions, lock types, and durations",
                "example": "get_lock_info(db_name='transformer_prod')",
                "oracle_query": "SELECT * FROM v$lock JOIN v$session ON ...",
                "mysql_query": "SELECT * FROM performance_schema.metadata_locks",
                "read_only": True
            },
            {
                "name": "get_db_users",
                "purpose": "List database users and permissions",
                "use_when": [
                    "Auditing database access",
                    "Validating user ownership",
                    "Security review",
                    "Understanding privilege assignments"
                ],
                "parameters": {
                    "db_name": "Database preset name (required)",
                    "limit": "Max users to return (default: 200)"
                },
                "returns": "Database users with account status, privileges, and creation dates",
                "example": "get_db_users(db_name='transformer_prod', limit=50)",
                "oracle_query": "SELECT * FROM dba_users",
                "mysql_query": "SELECT * FROM information_schema.user_privileges",
                "read_only": True
            }
        ],

        "common_scenarios": [
            {
                "scenario": "Database is slow right now",
                "steps": [
                    "1. Check active sessions: get_active_sessions(db_name='prod', limit=20)",
                    "2. Look for unusual activity (many sessions, long-running queries)",
                    "3. Check for locks: get_lock_info(db_name='prod')",
                    "4. Identify blocking sessions",
                    "5. Coordinate with application teams to resolve"
                ]
            },
            {
                "scenario": "Query hangs indefinitely",
                "steps": [
                    "1. Check lock info: get_lock_info(db_name='prod')",
                    "2. Identify blocking session (block = 1 in Oracle)",
                    "3. Check what that session is doing: get_active_sessions()",
                    "4. Coordinate with session owner to resolve",
                    "5. Consider killing blocking session if necessary (manual DBA action)"
                ]
            },
            {
                "scenario": "Security audit",
                "steps": [
                    "1. List all users: get_db_users(db_name='prod', limit=500)",
                    "2. Review account_status (look for locked/expired accounts)",
                    "3. Verify expected users only",
                    "4. Check privilege assignments",
                    "5. Document findings for compliance"
                ]
            },
            {
                "scenario": "Performance investigation",
                "steps": [
                    "1. Check active sessions: get_active_sessions(db_name='prod')",
                    "2. Identify long-running or high-resource queries",
                    "3. Use analyze_oracle_query to optimize those queries",
                    "4. Check for lock contention: get_lock_info()",
                    "5. Implement optimizations"
                ]
            }
        ],

        "safety_notes": [
            "✅ All DBA tools are read-only (SELECT queries only)",
            "✅ No writes, updates, deletes, or DDL operations",
            "✅ Safe to run in production environments",
            "✅ All tool usage is logged for audit trail",
            "⚠️  Requires appropriate database view permissions (v$session, dba_users, etc.)",
            "⚠️  Access restricted to admin and dba roles only"
        ],

        "required_permissions": {
            "oracle": [
                "SELECT on v$session",
                "SELECT on v$lock",
                "SELECT on dba_users (or all_users for limited view)"
            ],
            "mysql": [
                "SELECT on information_schema.processlist",
                "SELECT on performance_schema.metadata_locks",
                "SELECT on information_schema.user_privileges"
            ]
        },

        "troubleshooting": {
            "insufficient_permissions": "If tool returns error about missing permissions, contact DBA to grant SELECT on required views",
            "connection_failed": "Verify database is available using analyze_oracle_query or analyze_mysql_query first",
            "access_denied": "If you get 'insufficient_permissions' error, your role (from API key) is not admin or dba. Contact administrator.",
            "no_results": "Empty results are normal if no active sessions, locks, or limited users. This is not an error."
        },

        "best_practices": [
            "Always specify a reasonable limit parameter to avoid overwhelming results",
            "Use get_active_sessions regularly to monitor database health",
            "Check get_lock_info immediately when queries hang",
            "Combine DBA tools with query analysis tools for complete picture",
            "Document findings and coordinate with application teams",
            "Remember: These tools show symptoms, not root causes. Use analyze_oracle_query to find actual query issues."
        ]
    }
