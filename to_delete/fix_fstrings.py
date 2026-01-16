#!/usr/bin/env python3
"""
Fix f-string issues in knowledge_db.py
"""

import os
import re

# Read the current knowledge_db.py
knowledge_db_path = "knowledge_db.py"

print(f"Fixing f-string issues in {knowledge_db_path}")

with open(knowledge_db_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix specific f-string issues in get_cache_stats method
content = content.replace(
    'row = await self.fetchrow("SELECT COUNT(*) as count FROM {self.schema}.table_knowledge")',
    'row = await self.fetchrow(f"SELECT COUNT(*) as count FROM {self.schema}.table_knowledge")'
)

content = content.replace(
    'row = await self.fetchrow("SELECT COUNT(*) as count FROM {self.schema}.relationship_knowledge")',
    'row = await self.fetchrow(f"SELECT COUNT(*) as count FROM {self.schema}.relationship_knowledge")'
)

content = content.replace(
    'row = await self.fetchrow("SELECT COUNT(*) as count, SUM(hit_count) as total_hits FROM {self.schema}.query_explanations")',
    'row = await self.fetchrow(f"SELECT COUNT(*) as count, SUM(hit_count) as total_hits FROM {self.schema}.query_explanations")'
)

content = content.replace(
    'row = await self.fetchrow("SELECT COUNT(*) as count FROM {self.schema}.domain_glossary")',
    'row = await self.fetchrow(f"SELECT COUNT(*) as count FROM {self.schema}.domain_glossary")'
)

# Write the updated content
with open(knowledge_db_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCCESS: Fixed f-string issues in get_cache_stats method")