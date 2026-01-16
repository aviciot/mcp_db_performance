#!/usr/bin/env python3
"""
Run query history migration
"""
import asyncio
from knowledge_db import get_knowledge_db

async def run_query_history_migration():
    print('🚀 Running query history migration...')
    knowledge_db = get_knowledge_db()
    await knowledge_db.connect()
    
    # Read and execute the query history migration
    with open('migrations/002_query_history.sql', 'r') as f:
        history_sql = f.read()
    
    statements = [s.strip() for s in history_sql.split(';') if s.strip()]
    print(f'📝 Executing {len(statements)} query history statements...')
    
    success_count = 0
    for i, statement in enumerate(statements, 1):
        if statement:
            try:
                async with knowledge_db.pool.acquire() as conn:
                    await conn.execute(statement)
                success_count += 1
                if i % 5 == 0:
                    print(f'   ✅ Completed {i}/{len(statements)} statements')
            except Exception as e:
                print(f'   ⚠️ Statement {i}: {str(e)[:50]}...')
    
    print(f'✅ Query history migration completed: {success_count}/{len(statements)} successful')
    
    # Verify new tables
    async with knowledge_db.pool.acquire() as conn:
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'mcp_performance' 
            AND table_name LIKE '%history%'
            ORDER BY table_name
        """)
        print(f'📊 Query history tables: {[t["table_name"] for t in tables]}')
    
    await knowledge_db.close()

if __name__ == "__main__":
    asyncio.run(run_query_history_migration())