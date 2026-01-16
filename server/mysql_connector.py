"""
MySQL Database Connection Manager
Handles connections to MySQL databases defined in settings.yaml
"""

import mysql.connector
from mysql.connector import pooling
import logging
from config import config

logger = logging.getLogger(__name__)

# Connection pools by database name
_pools = {}

def _get_or_create_pool(db_name: str):
    """Get existing pool or create new one for the database"""
    if db_name in _pools:
        return _pools[db_name]
    
    db_config = config.get_db_preset(db_name)
    
    if not db_config:
        raise ValueError(f"Database '{db_name}' not found in settings.yaml")
    
    if db_config.get("type") != "mysql":
        raise ValueError(f"Database '{db_name}' is not a MySQL database (type: {db_config.get('type')})")
    
    logger.debug(f"🔗 Creating MySQL connection pool for '{db_name}'")
    logger.debug(f"   Host: {db_config['host']}:{db_config['port']}")
    logger.debug(f"   Database: {db_config['database']}")
    logger.debug(f"   User: {db_config['user']}")
    
    try:
        pool = pooling.MySQLConnectionPool(
            pool_name=f"pool_{db_name}",
            pool_size=5,
            pool_reset_session=True,
            host=db_config["host"],
            port=db_config.get("port", 3306),
            user=db_config["user"],
            password=db_config["password"],
            database=db_config["database"],
            autocommit=True,
            # Performance settings
            use_pure=False,  # Use C extension for better performance
            connection_timeout=10,
            # Charset
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        
        _pools[db_name] = pool
        logger.debug(f"✅ MySQL pool created successfully for '{db_name}'")
        return pool
        
    except mysql.connector.Error as e:
        logger.error(f"❌ Failed to create MySQL pool for '{db_name}': {e}")
        raise


def connect(db_name: str):
    """
    Get a connection to the specified MySQL database.
    
    Args:
        db_name: Name of database from settings.yaml
    
    Returns:
        MySQL connection object
    
    Raises:
        ValueError: If database not found or not MySQL type
        mysql.connector.Error: If connection fails
    """
    pool = _get_or_create_pool(db_name)
    
    try:
        conn = pool.get_connection()
        logger.debug(f"📡 Acquired MySQL connection for '{db_name}'")
        return conn
    except mysql.connector.Error as e:
        logger.error(f"❌ Failed to get connection from pool for '{db_name}': {e}")
        raise


def test_connection(db_name: str) -> tuple[bool, str]:
    """
    Test if connection to database works.
    
    Args:
        db_name: Name of database from settings.yaml
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        conn = connect(db_name)
        cur = conn.cursor()
        cur.execute("SELECT VERSION()")
        version = cur.fetchone()[0]
        cur.close()
        conn.close()
        
        # Compact one-line output
        logger.info(f"   ✅ {db_name} (MySQL {version})")
        return True, f"Connected successfully. MySQL version: {version}"
        
    except Exception as e:
        logger.error(f"   ❌ {db_name}: {e}")
        return False, str(e)


def close_all_pools():
    """Close all connection pools (for cleanup)"""
    for db_name, pool in _pools.items():
        try:
            # MySQL connector doesn't have a direct pool.close()
            # Connections will be cleaned up when pool goes out of scope
            logger.info(f"🔒 Releasing pool for '{db_name}'")
        except Exception as e:
            logger.warning(f"⚠️  Error closing pool for '{db_name}': {e}")
    
    _pools.clear()
