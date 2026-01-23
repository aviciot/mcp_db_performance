import logging

logger = logging.getLogger(__name__)

async def run_migrations(knowledge_db):
    """Run PostgreSQL schema migrations using KnowledgeDBAsync instance."""
    logger.info("🗄️ Running PostgreSQL migrations...")
    
    if not knowledge_db or not knowledge_db.is_enabled:
        logger.error("❌ Knowledge DB not available for migrations")
        return False

        # Run full schema migration from SQL file
    import os
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'migrations', '000_complete_schema_init.sql')
    
    if not os.path.exists(schema_path):
        logger.error(f"❌ Migration file not found: {schema_path}")
        return False
        
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    # Split and execute each statement safely (idempotent)
    statements = [s.strip() for s in schema_sql.split(';') if s.strip()]
    logger.info(f"📝 Executing {len(statements)} migration statements")
    
    success_count = 0
    for i, statement in enumerate(statements, 1):
        if statement:
            try:
                # Use the knowledge DB's execute method
                async with knowledge_db.pool.acquire() as conn:
                    await conn.execute(statement)
                success_count += 1
                logger.debug(f"✅ Statement {i}/{len(statements)} executed")
            except Exception as e:
                # Log warning but continue (table might already exist)
                logger.warning(f"⚠️ Statement {i} failed (may already exist): {e}")
                logger.debug(f"   Statement: {statement[:100]}...")

    logger.info(f"✅ Migrations completed: {success_count}/{len(statements)} statements successful")
    return True
