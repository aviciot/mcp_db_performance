"""
Universal Database Tools
Contains database-agnostic tools that work across all database types (Oracle, MySQL, etc.)
"""

import logging
from mcp_app import mcp
from config import config
from db_connector import oracle_connector

logger = logging.getLogger(__name__)


@mcp.tool(
    name="list_available_databases",
    description=(
        "Lists all configured database presets grouped by type (Oracle, MySQL, etc.) and tests their connectivity. "
        "Returns databases organized by database type with connection status, version info, and accessibility. "
        "Use this to see which databases are available for analysis before running queries."
    ),
)
def list_available_databases():
    """
    Returns list of configured database presets with accessibility status.
    Tests connection to each database to verify availability.
    Supports multiple database types: Oracle, MySQL, and extensible to others.
    """
    logger.info("🔍 list_available_databases() called")
    
    databases = []
    
    for db_name, db_config in config.database_presets.items():
        db_type = db_config.get("type", "oracle")
        
        # Build database info based on type
        db_info = {
            "name": db_name,
            "type": db_type,
            "user": db_config.get("user", ""),
            "status": "unknown",
            "message": ""
        }
        
        # Add type-specific connection info
        if db_type == "oracle":
            db_info["dsn"] = db_config.get("dsn", "")
        elif db_type == "mysql":
            db_info["host"] = db_config.get("host", "")
            db_info["port"] = db_config.get("port", 3306)
            db_info["database"] = db_config.get("database", "")
        
        # Test connection using type-specific connector
        try:
            if db_type == "oracle":
                conn = oracle_connector.connect(db_name)
                cur = conn.cursor()
                
                version = "Unknown"
                db_instance = "Unknown"
                
                # Try to get database version and name (requires V$ access)
                try:
                    cur.execute("SELECT banner FROM v$version WHERE ROWNUM = 1")
                    row = cur.fetchone()
                    if row:
                        version = row[0]
                    
                    cur.execute("SELECT name FROM v$database")
                    row = cur.fetchone()
                    if row:
                        db_instance = row[0]
                except Exception as v_error:
                    # User doesn't have V$ access, but connection is valid
                    if "ORA-00942" in str(v_error):
                        logger.info(f"⚠️  {db_name}: Connected but no V$ view access")
                    else:
                        raise  # Re-raise if it's not a permission issue
                
                db_info["status"] = "accessible"
                db_info["message"] = "Connected successfully" if version != "Unknown" else "Connected (limited V$ access)"
                db_info["version"] = version
                db_info["instance"] = db_instance
                
                conn.close()
                logger.info(f"✅ {db_name}: accessible")
                
            elif db_type == "mysql":
                import mysql_connector
                success, message = mysql_connector.test_connection(db_name)
                
                if success:
                    db_info["status"] = "accessible"
                    db_info["message"] = message
                    # Extract version from message (format: "Connected successfully. MySQL version: X.X.X")
                    if "MySQL version:" in message:
                        db_info["version"] = message.split("MySQL version:")[-1].strip()
                    logger.info(f"✅ {db_name}: accessible")
                else:
                    db_info["status"] = "error"
                    db_info["message"] = message
                    logger.warning(f"❌ {db_name}: {message}")
            else:
                db_info["status"] = "error"
                db_info["message"] = f"Unsupported database type: {db_type}"
                logger.warning(f"❌ {db_name}: Unsupported type {db_type}")
            
        except Exception as e:
            db_info["status"] = "error"
            db_info["message"] = str(e)
            logger.warning(f"❌ {db_name}: {e}")
        
        databases.append(db_info)
    
    # Group databases by type
    oracle_dbs = [db for db in databases if db.get("type") == "oracle"]
    mysql_dbs = [db for db in databases if db.get("type") == "mysql"]
    other_dbs = [db for db in databases if db.get("type") not in ["oracle", "mysql"]]
    
    result = {
        "oracle_databases": {
            "databases": oracle_dbs,
            "count": len(oracle_dbs),
            "accessible": sum(1 for db in oracle_dbs if db["status"] == "accessible"),
            "errors": sum(1 for db in oracle_dbs if db["status"] == "error")
        },
        "mysql_databases": {
            "databases": mysql_dbs,
            "count": len(mysql_dbs),
            "accessible": sum(1 for db in mysql_dbs if db["status"] == "accessible"),
            "errors": sum(1 for db in mysql_dbs if db["status"] == "error")
        },
        "summary": {
            "total_databases": len(databases),
            "total_accessible": sum(1 for db in databases if db["status"] == "accessible"),
            "total_errors": sum(1 for db in databases if db["status"] == "error"),
            "database_types": {
                "oracle": len(oracle_dbs),
                "mysql": len(mysql_dbs),
                "other": len(other_dbs)
            }
        }
    }
    
    # Add other databases section if any exist
    if other_dbs:
        result["other_databases"] = {
            "databases": other_dbs,
            "count": len(other_dbs),
            "accessible": sum(1 for db in other_dbs if db["status"] == "accessible"),
            "errors": sum(1 for db in other_dbs if db["status"] == "error")
        }
    
    # Return dict directly - no JSON serialization
    return result
