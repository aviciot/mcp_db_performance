# server/db_connector.py

import os
import oracledb
import logging
from config import config

logger = logging.getLogger("db-check")

# Ensure UTF-8 handling for Oracle Thin mode
os.environ["NLS_LANG"] = ".AL32UTF8"


class OracleConnector:
    def connect(self, preset_name: str):
        p = config.get_db_preset(preset_name)

        # Thin mode → cannot use encoding=
        return oracledb.connect(
            user=p["user"],
            password=p["password"],
            dsn=p["dsn"]
        )

    def test_connection(self, preset_name: str) -> bool:
        try:
            conn = self.connect(preset_name)
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM dual")
            cur.fetchone()
            cur.close()
            conn.close()
            logger.info(f"   ✅ {preset_name} (Oracle)")
            return True
        except Exception as e:
            logger.error(f"   ❌ {preset_name}: {e}")
            return False

oracle_connector = OracleConnector()


# =============================================================================
# UNIFIED DATABASE CONNECTOR - Routes to Oracle or MySQL based on config
# =============================================================================

def connect(db_name: str):
    """
    Universal connection function - routes to appropriate database connector.
    
    Args:
        db_name: Name of database from settings.yaml
    
    Returns:
        Database connection object (Oracle or MySQL)
    
    Raises:
        ValueError: If database not found or unsupported type
    """
    db_config = config.get_db_preset(db_name)
    db_type = db_config.get("type", "oracle")  # Default to oracle for backward compatibility
    
    if db_type == "oracle":
        return oracle_connector.connect(db_name)
    elif db_type == "mysql":
        import mysql_connector
        return mysql_connector.connect(db_name)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def test_connection(db_name: str) -> bool:
    """
    Test connection to any database type.
    
    Args:
        db_name: Name of database from settings.yaml
    
    Returns:
        True if connection successful, False otherwise
    """
    db_config = config.get_db_preset(db_name)
    db_type = db_config.get("type", "oracle")
    
    if db_type == "oracle":
        return oracle_connector.test_connection(db_name)
    elif db_type == "mysql":
        import mysql_connector
        success, _ = mysql_connector.test_connection(db_name)
        return success
    else:
        logger.error(f"❌ Unsupported database type: {db_type}")
        return False
