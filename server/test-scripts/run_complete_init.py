#!/usr/bin/env python3
"""
Complete Schema Initialization - Clean Slate Deployment
========================================================
Runs the complete schema initialization SQL file for a clean deployment.

Command: docker exec -it mcp_performance python /app/test-scripts/run_complete_init.py
"""

import asyncio
import sys
from pathlib import Path
import logging

# Add server directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from knowledge_db import get_knowledge_db

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_complete_initialization():
    """Run complete schema initialization from SQL file."""
    
    logger.info("🚀 Starting Complete Schema Initialization")
    logger.info("=" * 60)
    
    schema = "mcp_performance"
    db = get_knowledge_db(schema=schema)
    
    try:
        # Connect to PostgreSQL
        await db.connect()
        logger.info(f"✅ Connected to PostgreSQL")
        
        # Read the complete initialization SQL
        sql_file = Path(__file__).parent.parent / "migrations" / "000_complete_schema_init.sql"
        
        if not sql_file.exists():
            raise FileNotFoundError(f"SQL file not found: {sql_file}")
        
        logger.info(f"📁 Reading SQL file: {sql_file.name}")
        sql_content = sql_file.read_text(encoding='utf-8')
        
        # Execute the complete SQL as one transaction
        logger.info("🔧 Executing complete schema initialization...")
        
        async with db.pool.acquire() as conn:
            # Execute the entire SQL file in one go
            await conn.execute(sql_content)
        
        logger.info("✅ Schema initialization completed successfully!")
        
        # Verify the installation
        logger.info("🔍 Verifying installation...")
        
        # Check tables created
        tables = await db.fetch("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = $1 
            ORDER BY tablename
        """, schema)
        
        logger.info(f"📋 Tables created: {len(tables)}")
        for table in tables:
            logger.info(f"   ✓ {schema}.{table['tablename']}")
        
        # Check indexes
        indexes = await db.fetch("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE schemaname = $1 
            ORDER BY indexname
        """, schema)
        
        logger.info(f"🔗 Indexes created: {len(indexes)}")
        
        # Check triggers
        triggers = await db.fetch("""
            SELECT trigger_name 
            FROM information_schema.triggers 
            WHERE trigger_schema = $1
            ORDER BY trigger_name
        """, schema)
        
        logger.info(f"⚡ Triggers created: {len(triggers)}")
        for trigger in triggers:
            logger.info(f"   ✓ {trigger['trigger_name']}")
        
        # Check discovery log entry
        log_entry = await db.fetchrow(
            f"SELECT * FROM {schema}.discovery_log WHERE operation_type = 'schema_initialization'"
        )
        
        if log_entry:
            logger.info("✅ Schema initialization logged successfully")
        
        logger.info("=" * 60)
        logger.info("🎉 COMPLETE SCHEMA INITIALIZATION SUCCESSFUL!")
        logger.info(f"   Schema: {schema}")
        logger.info(f"   Tables: {len(tables)}")
        logger.info(f"   Indexes: {len(indexes)}")
        logger.info(f"   Triggers: {len(triggers)}")
        logger.info("   Status: ✅ Ready for E2E testing")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Schema initialization failed: {e}")
        return False

async def main():
    """Main execution."""
    success = await run_complete_initialization()
    
    if success:
        print("\n🚀 DEPLOYMENT READY - Run E2E test now!")
        return 0
    else:
        print("\n💥 DEPLOYMENT FAILED - Check errors above")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)