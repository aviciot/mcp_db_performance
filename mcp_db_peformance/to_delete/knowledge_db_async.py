import os
import asyncpg
import logging
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger("knowledge_db_async")

class AsyncKnowledgeDB:
    def __init__(self):
        self.pool = None
        self._enabled = False

    async def connect(self):
        self.pool = await asyncpg.create_pool(
            host=os.getenv("KNOWLEDGE_DB_HOST", "postgres"),
            port=int(os.getenv("KNOWLEDGE_DB_PORT", "5432")),
            database=os.getenv("KNOWLEDGE_DB_NAME", "omni"),
            user=os.getenv("KNOWLEDGE_DB_USER", "postgres"),
            password=os.getenv("KNOWLEDGE_DB_PASSWORD", "postgres"),
            min_size=1,
            max_size=10
        )
        self._enabled = True
        logger.info("✅ Connected to async knowledge DB")

    @property
    def is_enabled(self) -> bool:
        return self._enabled and self.pool is not None

    async def fetchrow(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetch(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def execute(self, query, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    # Example: async get_table_knowledge
    async def get_table_knowledge(self, db_name: str, owner: str, table_name: str) -> Optional[Dict[str, Any]]:
        if not self.is_enabled:
            return None
        row = await self.fetchrow(
            """
            SELECT * FROM table_knowledge
            WHERE db_name = $1 AND owner = $2 AND table_name = $3
              AND last_refreshed > NOW() - INTERVAL '7 days'
            """, db_name, owner.upper(), table_name.upper()
        )
        return dict(row) if row else None

    # Add more async methods for save, update, etc.

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None
            self._enabled = False
            logger.info("🔌 Async knowledge DB connection closed")
