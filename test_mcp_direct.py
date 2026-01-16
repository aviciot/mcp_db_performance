#!/usr/bin/env python3
"""
Direct test of MCP business logic caching functionality
Tests the actual function flow to verify PostgreSQL cache is working
"""

import asyncio
import sys
import time
from datetime import datetime

# Add server directory to path
sys.path.insert(0, '/app')

from knowledge_db import get_knowledge_db
from config import config
import db_connector
from db_connector import oracle_connector

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(text):
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")


def print_success(text):
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text):
    print(f"{RED}✗ {text}{RESET}")


def print_info(text):
    print(f"{BLUE}ℹ {text}{RESET}")


async def test_postgresql_connection():
    """Test PostgreSQL connection and caching"""
    print_header("Test 1: PostgreSQL Connection & Caching")

    try:
        db = get_knowledge_db()
        print_info(f"KnowledgeDB instance created")
        print_info(f"Config loaded: {db.config is not None}")
        print_info(f"Initial state: enabled={db.is_enabled}, pool={db.pool is not None}")

        # Connect if not already connected
        if not db.is_enabled:
            print_info("Calling connect()...")
            await db.connect()
            print_success(f"Connected: enabled={db.is_enabled}, pool={db.pool is not None}")
        else:
            print_success("Already connected")

        # Test cache operations
        stats = await db.get_cache_stats()
        print_info(f"Cache stats: {stats.get('tables_cached', 0)} tables, {stats.get('relationships_cached', 0)} relationships")

        # Test saving a dummy table
        print_info("Testing cache write...")
        success = await db.save_table_knowledge(
            db_name="test_db",
            owner="TEST_OWNER",
            table_name="TEST_TABLE",
            table_data={
                "row_count": 100,
                "table_comment": "Test table for caching",
                "columns": [{"name": "ID", "type": "NUMBER"}]
            }
        )

        if success:
            print_success("Cache write successful")
        else:
            print_error("Cache write failed")
            return False

        # Test reading back
        print_info("Testing cache read...")
        cached = await db.get_table_knowledge("test_db", "TEST_OWNER", "TEST_TABLE")

        if cached:
            print_success("Cache read successful")
            print_info(f"Cached table comment: {cached.get('table_comment', 'N/A')}")
        else:
            print_error("Cache read returned no data")
            return False

        return True

    except Exception as e:
        print_error(f"Exception: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_oracle_connection():
    """Test Oracle database connection"""
    print_header("Test 2: Oracle Database Connection")

    # Find an Oracle database
    db_name = None
    for preset_name, preset_config in config.database_presets.items():
        if preset_config.get("type", "oracle").lower() == "oracle":
            db_name = preset_name
            break

    if not db_name:
        print_error("No Oracle database configured")
        return False

    print_info(f"Testing connection to: {db_name}")

    try:
        conn = oracle_connector.connect(db_name)
        cur = conn.cursor()

        # Test simple query
        cur.execute("SELECT 'Hello from Oracle' FROM DUAL")
        result = cur.fetchone()

        if result:
            print_success(f"Oracle query result: {result[0]}")

        # Get schema
        cur.execute("SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM DUAL")
        schema = cur.fetchone()[0]
        print_info(f"Current schema: {schema}")

        conn.close()
        return True

    except Exception as e:
        print_error(f"Oracle connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_full_workflow():
    """Test the full workflow: Oracle query + PostgreSQL caching"""
    print_header("Test 3: Full Workflow - Query Oracle & Cache in PostgreSQL")

    # Find Oracle database
    db_name = None
    for preset_name, preset_config in config.database_presets.items():
        if preset_config.get("type", "oracle").lower() == "oracle":
            db_name = preset_name
            break

    if not db_name:
        print_error("No Oracle database configured")
        return False

    try:
        # Get knowledge DB
        knowledge_db = get_knowledge_db()
        if not knowledge_db.is_enabled:
            await knowledge_db.connect()

        if not knowledge_db.is_enabled:
            print_error("Knowledge DB not enabled after connect()")
            return False

        print_success("Knowledge DB connected and ready")

        # Connect to Oracle
        conn = oracle_connector.connect(db_name)
        cur = conn.cursor()

        # Get a real table from Oracle
        cur.execute("""
            SELECT owner, table_name
            FROM all_tables
            WHERE owner NOT IN ('SYS', 'SYSTEM')
            AND rownum <= 1
        """)
        row = cur.fetchone()

        if not row:
            print_error("No tables found in Oracle")
            return False

        owner, table_name = row
        print_info(f"Testing with real table: {owner}.{table_name}")

        # Check if already in cache
        cached = await knowledge_db.get_table_knowledge(db_name, owner, table_name)
        was_cached = cached is not None

        print_info(f"Table in cache: {was_cached}")

        # Get table metadata from Oracle
        start_time = time.time()

        cur.execute("""
            SELECT comments
            FROM all_tab_comments
            WHERE owner = :owner AND table_name = :table_name
        """, {"owner": owner, "table_name": table_name})

        comment_row = cur.fetchone()
        table_comment = comment_row[0] if comment_row and comment_row[0] else "No comment"

        # Get row count
        try:
            cur.execute(f"SELECT COUNT(*) FROM {owner}.{table_name} WHERE rownum <= 10000")
            row_count = cur.fetchone()[0]
        except:
            row_count = None

        oracle_query_time = time.time() - start_time

        print_info(f"Oracle query time: {oracle_query_time:.2f}s")
        print_info(f"Table comment: {table_comment[:50]}...")
        print_info(f"Row count: {row_count}")

        # Save to cache
        print_info("Saving to PostgreSQL cache...")
        start_time = time.time()

        success = await knowledge_db.save_table_knowledge(
            db_name=db_name,
            owner=owner,
            table_name=table_name,
            table_data={
                "row_count": row_count,
                "table_comment": table_comment,
                "columns": []
            }
        )

        cache_save_time = time.time() - start_time

        if success:
            print_success(f"Cache save successful ({cache_save_time:.3f}s)")
        else:
            print_error("Cache save failed")
            return False

        # Read from cache
        print_info("Reading from PostgreSQL cache...")
        start_time = time.time()

        cached_data = await knowledge_db.get_table_knowledge(db_name, owner, table_name)

        cache_read_time = time.time() - start_time

        if cached_data:
            print_success(f"Cache read successful ({cache_read_time:.3f}s)")
            print_info(f"Cached comment: {cached_data.get('table_comment', 'N/A')[:50]}...")
        else:
            print_error("Cache read failed")
            return False

        print_success(f"Full workflow completed successfully!")
        print_info(f"Performance: Oracle query {oracle_query_time:.2f}s, Cache read {cache_read_time:.3f}s")

        conn.close()
        return True

    except Exception as e:
        print_error(f"Workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print_header(f"MCP Direct Test Suite - Cache Verification")
    print_info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    tests = [
        ("PostgreSQL Connection & Caching", test_postgresql_connection),
        ("Oracle Connection", test_oracle_connection),
        ("Full Workflow (Oracle + Cache)", test_full_workflow),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))

    # Summary
    print_header("Test Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = f"{GREEN}PASS{RESET}" if result else f"{RED}FAIL{RESET}"
        print(f"  {status}  {test_name}")

    print(f"\n{BLUE}Results: {passed}/{total} tests passed{RESET}")

    if passed == total:
        print_success("All tests passed! PostgreSQL caching is working correctly.")
        return 0
    else:
        print_error(f"{total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
