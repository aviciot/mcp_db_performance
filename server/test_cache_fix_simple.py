#!/usr/bin/env python3
"""
Simple direct test to verify PostgreSQL caching works after bug fix
"""

import asyncio
import sys
import time

sys.path.insert(0, '/app')

from knowledge_db import get_knowledge_db
from config import config
from db_connector import oracle_connector
from tools.oracle_business_context import collect_oracle_business_context

GREEN = '\033[92m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'


async def test_cache_workflow():
    """Test the actual caching workflow used by the tools"""
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BLUE}PostgreSQL Cache Fix Verification{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")

    # Find Oracle database
    db_name = None
    for preset_name, preset_config in config.database_presets.items():
        if preset_config.get("type", "oracle").lower() == "oracle":
            db_name = preset_name
            break

    if not db_name:
        print(f"{RED}✗ No Oracle database configured{RESET}")
        return False

    print(f"{BLUE}ℹ Using database: {db_name}{RESET}")

    try:
        # Step 1: Test PostgreSQL connection
        print(f"\n{BLUE}Step 1: Testing PostgreSQL connection...{RESET}")
        knowledge_db = get_knowledge_db()
        print(f"  Initial state: enabled={knowledge_db.is_enabled}")

        if not knowledge_db.is_enabled:
            print(f"  Calling connect()...")
            await knowledge_db.connect()
            print(f"  After connect: enabled={knowledge_db.is_enabled}, pool={knowledge_db.pool is not None}")

        if not knowledge_db.is_enabled:
            print(f"{RED}✗ PostgreSQL connection failed{RESET}")
            return False

        print(f"{GREEN}✓ PostgreSQL connection working{RESET}")

        # Step 2: Get a real table from Oracle
        print(f"\n{BLUE}Step 2: Getting test table from Oracle...{RESET}")
        conn = oracle_connector.connect(db_name)
        cur = conn.cursor()

        cur.execute("""
            SELECT owner, table_name
            FROM all_tables
            WHERE owner NOT IN ('SYS', 'SYSTEM')
            AND rownum <= 1
        """)
        row = cur.fetchone()

        if not row:
            print(f"{RED}✗ No tables found{RESET}")
            conn.close()
            return False

        owner, table_name = row
        print(f"  Test table: {owner}.{table_name}")
        print(f"{GREEN}✓ Oracle connection working{RESET}")

        # Step 3: Check if table is in cache
        print(f"\n{BLUE}Step 3: Checking cache...{RESET}")
        cached = await knowledge_db.get_table_knowledge(db_name, owner, table_name)
        if cached:
            print(f"  Table already in cache")
        else:
            print(f"  Table not in cache (will populate)")

        # Step 4: Collect metadata from Oracle
        print(f"\n{BLUE}Step 4: Collecting metadata from Oracle...{RESET}")
        start_time = time.time()

        context = collect_oracle_business_context(
            cur,
            [(owner, table_name)],
            follow_relationships=False,
            max_depth=1
        )

        oracle_time = time.time() - start_time
        print(f"  Oracle query time: {oracle_time:.2f}s")

        table_key = (owner, table_name)
        if table_key not in context.get("table_context", {}):
            print(f"{RED}✗ Failed to collect table metadata{RESET}")
            conn.close()
            return False

        table_data = context["table_context"][table_key]
        print(f"  Collected: {len(table_data.get('columns', []))} columns")
        print(f"{GREEN}✓ Oracle metadata collection working{RESET}")

        # Step 5: Save to cache
        print(f"\n{BLUE}Step 5: Saving to PostgreSQL cache...{RESET}")
        start_time = time.time()

        success = await knowledge_db.save_table_knowledge(
            db_name=db_name,
            owner=owner,
            table_name=table_name,
            oracle_comment=table_data.get("table_comment"),
            num_rows=table_data.get("row_count"),
            is_partitioned=table_data.get("is_partitioned", False),
            columns=table_data.get("columns", []),
            primary_key_columns=table_data.get("primary_key_columns", [])
        )

        cache_save_time = time.time() - start_time

        if not success:
            print(f"{RED}✗ Failed to save to cache{RESET}")
            conn.close()
            return False

        print(f"  Cache save time: {cache_save_time:.3f}s")
        print(f"{GREEN}✓ Cache save working{RESET}")

        # Step 6: Read from cache
        print(f"\n{BLUE}Step 6: Reading from PostgreSQL cache...{RESET}")
        start_time = time.time()

        cached_data = await knowledge_db.get_table_knowledge(db_name, owner, table_name)

        cache_read_time = time.time() - start_time

        if not cached_data:
            print(f"{RED}✗ Failed to read from cache{RESET}")
            conn.close()
            return False

        print(f"  Cache read time: {cache_read_time:.3f}s")
        print(f"  Cached columns: {len(cached_data.get('columns', []))}")
        print(f"{GREEN}✓ Cache read working{RESET}")

        # Step 7: Performance summary
        print(f"\n{BLUE}{'=' * 70}{RESET}")
        print(f"{GREEN}✓ ALL TESTS PASSED - PostgreSQL caching is fully functional{RESET}")
        print(f"{BLUE}{'=' * 70}{RESET}")
        print(f"\nPerformance:")
        print(f"  Oracle metadata query: {oracle_time:.2f}s")
        print(f"  Cache save:            {cache_save_time:.3f}s")
        print(f"  Cache read:            {cache_read_time:.3f}s")
        print(f"\nCache speedup: {(oracle_time / cache_read_time):.1f}x faster than Oracle query")

        conn.close()
        return True

    except Exception as e:
        print(f"\n{RED}✗ Test failed: {e}{RESET}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_cache_workflow())
    sys.exit(0 if result else 1)
