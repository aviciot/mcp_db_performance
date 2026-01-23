#!/usr/bin/env python3
"""
Add fetchval method to KnowledgeDBAsync class
"""

knowledge_db_path = "knowledge_db.py"

print(f"Adding fetchval method to {knowledge_db_path}")

with open(knowledge_db_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add fetchval method after the existing fetch method
fetchval_method = '''
    async def fetchval(self, query, *args):
        """Execute query and return single value."""
        if not self.is_enabled:
            return None
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)
'''

# Insert the method after the fetch method
content = content.replace(
    """    async def execute(self, query, *args):
        \"\"\"Execute query (INSERT/UPDATE/DELETE).\"\"\"
        if not self.is_enabled:
            return None
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)""",
    
    fetchval_method + """
    async def execute(self, query, *args):
        \"\"\"Execute query (INSERT/UPDATE/DELETE).\"\"\"
        if not self.is_enabled:
            return None
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)"""
)

# Write the updated content
with open(knowledge_db_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCCESS: Added fetchval method to KnowledgeDBAsync")