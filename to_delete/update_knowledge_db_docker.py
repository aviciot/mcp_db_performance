#!/usr/bin/env python3
"""
Update knowledge_db.py to support schema-aware queries (Docker version)
"""

import os
import re

# Read the current knowledge_db.py (Docker container path)
knowledge_db_path = "knowledge_db.py"

print(f"Updating {knowledge_db_path}")

with open(knowledge_db_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update __init__ method to accept schema parameter
content = content.replace(
    "    def __init__(self):\n        self.pool = None\n        self._enabled = False",
    """    def __init__(self, schema: str = None):
        self.pool = None
        self._enabled = False
        # Schema support for multi-MCP deployment
        self.schema = schema or os.getenv("KNOWLEDGE_DB_SCHEMA", "mcp_performance")
        logger.info(f"Knowledge DB initialized with schema: {self.schema}")"""
)

# 2. Update connection settings
content = content.replace(
    """                server_settings={
                    'application_name': 'mcp_performance_server'
                }""",
    """                server_settings={
                    'application_name': f'mcp_performance_server_{self.schema}',
                    'search_path': f'{self.schema},public'
                }"""
)

# 3. Update connection success message
content = content.replace(
    'logger.info(f"✅ Knowledge DB connected successfully to {host}:{port}/{database}")',
    'logger.info(f"✅ Knowledge DB connected successfully to {host}:{port}/{database} (schema: {self.schema})")'
)

# 4. Update all table references to use schema prefix
tables_to_update = [
    "table_knowledge",
    "relationship_knowledge", 
    "query_explanations",
    "domain_glossary",
    "discovery_log"
]

for table in tables_to_update:
    # Replace FROM table_name with FROM {self.schema}.table_name
    content = re.sub(
        rf'\bFROM {table}\b',
        f'FROM {{self.schema}}.{table}',
        content
    )
    
    # Replace INSERT INTO table_name with INSERT INTO {self.schema}.table_name
    content = re.sub(
        rf'\bINSERT INTO {table}\b',
        f'INSERT INTO {{self.schema}}.{table}',
        content
    )
    
    # Replace UPDATE table_name with UPDATE {self.schema}.table_name
    content = re.sub(
        rf'\bUPDATE {table}\b',
        f'UPDATE {{self.schema}}.{table}',
        content
    )

# 5. Fix the f-strings - need to convert affected queries to f-strings
patterns_to_fix = [
    (r'"""(\s*SELECT \* FROM \{self\.schema\}\.table_knowledge.*?)"""', 
     r'f"""\1"""'),
    (r'"""(\s*SELECT \* FROM \{self\.schema\}\.relationship_knowledge.*?)"""',
     r'f"""\1"""'),
    (r'"""(\s*INSERT INTO \{self\.schema\}\..*?)"""',
     r'f"""\1"""'),
    (r'"""(\s*UPDATE \{self\.schema\}\..*?)"""',
     r'f"""\1"""'),
]

for pattern, replacement in patterns_to_fix:
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# 6. Update get_knowledge_db() function to support schema parameter
content = content.replace(
    """def get_knowledge_db() -> KnowledgeDBAsync:
    \"\"\"Get or create the global async knowledge DB instance.\"\"\"
    global _knowledge_db
    if _knowledge_db is None:
        _knowledge_db = KnowledgeDBAsync()
    return _knowledge_db""",
    """def get_knowledge_db(schema: str = None) -> KnowledgeDBAsync:
    \"\"\"Get or create the global async knowledge DB instance.\"\"\"
    global _knowledge_db
    if _knowledge_db is None:
        _knowledge_db = KnowledgeDBAsync(schema=schema)
    return _knowledge_db"""
)

# Write the updated content
with open(knowledge_db_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("SUCCESS: knowledge_db.py updated with schema support")
print(f"   - Schema parameter added to __init__")
print(f"   - All {len(tables_to_update)} tables now use schema prefix")
print(f"   - Connection settings updated for schema isolation")
print(f"   - get_knowledge_db() function supports schema parameter")