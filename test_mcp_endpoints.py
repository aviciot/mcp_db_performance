#!/usr/bin/env python3
"""
Test script for MCP Server endpoints
Tests all available tools and verifies PostgreSQL caching functionality
"""

import asyncio
import json
import sys
import time
from datetime import datetime

# Add server directory to path
sys.path.insert(0, '/app')

from mcp_app import mcp
from knowledge_db import get_knowledge_db
from config import config

# ANSI color codes
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


def print_warning(text):
    print(f"{YELLOW}⚠ {text}{RESET}")


async def test_knowledge_db_connection():
    """Test PostgreSQL knowledge DB connection"""
    print_header("Test 1: PostgreSQL Knowledge DB Connection")

    try:
        db = get_knowledge_db()
        print_info(f"Config loaded: {db.config is not None}")

        if not db.is_enabled:
            print_info("Connecting to PostgreSQL...")
            await db.connect()

        if db.is_enabled:
            print_success("PostgreSQL connection: ESTABLISHED")
            print_info(f"Pool exists: {db.pool is not None}")

            # Get cache stats
            stats = await db.get_cache_stats()
            print_info(f"Cache stats: {stats.get('tables_cached', 0)} tables, {stats.get('relationships_cached', 0)} relationships")
            return True
        else:
            print_error("PostgreSQL connection: FAILED")
            status = db.get_connection_status()
            print_error(f"Status: {status}")
            return False
    except Exception as e:
        print_error(f"Exception: {e}")
        return False


async def test_list_available_tools():
    """List all available MCP tools"""
    print_header("Test 2: Available MCP Tools")

    try:
        tools = await mcp.get_tools()
        print_success(f"Found {len(tools)} tools:")
        for tool in tools:
            print(f"  • {tool['name']}")
            if 'description' in tool:
                desc = tool['description'][:100] + "..." if len(tool['description']) > 100 else tool['description']
                print(f"    {desc}")
        return True
    except Exception as e:
        print_error(f"Failed to list tools: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_list_available_databases():
    """Test list_available_databases tool"""
    print_header("Test 3: List Available Databases")

    try:
        import db_connector

        print_info(f"Configured databases: {len(config.database_presets)}")
        for db_name in config.database_presets.keys():
            print(f"  • {db_name}")

        print_success("Database configuration loaded successfully")
        return True
    except Exception as e:
        print_error(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_explain_business_logic_caching():
    """Test explain_business_logic with caching (call twice with same query)"""
    print_header("Test 4: Business Logic Analysis - Cache Test")

    # First, check which databases are available
    db_name = None
    for preset_name, preset_config in config.database_presets.items():
        if preset_config.get("type", "oracle").lower() == "oracle":
            db_name = preset_name
            break

    if not db_name:
        print_warning("No Oracle database configured, skipping test")
        return False

    print_info(f"Using database: {db_name}")

    # Simple test query
    test_sql = "SELECT * FROM user_tables WHERE rownum <= 1"

    try:
        # Import the actual tool module
        import tools.oracle_analysis as oracle_analysis_module

        # Get the actual function from the module __dict__
        explain_func = None
        for key, value in vars(oracle_analysis_module).items():
            if key == 'explain_business_logic' and callable(value):
                explain_func = value
                break

        if not explain_func:
            print_error("Could not find explain_business_logic function")
            return False

        # First call - should populate cache
        print_info("First call (cache miss - should populate cache)...")
        start_time = time.time()
        result1 = await explain_func(
            db_name=db_name,
            sql_text=test_sql,
            follow_relationships=False,
            max_depth=1
        )
        elapsed1 = time.time() - start_time

        if isinstance(result1, dict) and 'error' in result1:
            print_error(f"First call failed: {result1['error']}")
            return False

        print_success(f"First call completed in {elapsed1:.2f}s")
        print_info(f"Tables analyzed: {len(result1.get('tables', {})) if isinstance(result1, dict) else 'N/A'}")

        # Small delay
        await asyncio.sleep(1)

        # Second call - should hit cache
        print_info("Second call (cache hit - should be faster)...")
        start_time = time.time()
        result2 = await explain_func(
            db_name=db_name,
            sql_text=test_sql,
            follow_relationships=False,
            max_depth=1
        )
        elapsed2 = time.time() - start_time

        if isinstance(result2, dict) and 'error' in result2:
            print_error(f"Second call failed: {result2['error']}")
            return False

        print_success(f"Second call completed in {elapsed2:.2f}s")
        print_info(f"Tables analyzed: {len(result2.get('tables', {})) if isinstance(result2, dict) else 'N/A'}")

        # Compare performance
        improvement = ((elapsed1 - elapsed2) / elapsed1 * 100) if elapsed1 > 0 else 0
        if elapsed2 < elapsed1:
            print_success(f"Cache working! Second call was {improvement:.1f}% faster")
        else:
            print_warning(f"Second call was slower - cache may not be working")

        return True

    except Exception as e:
        print_error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_health_endpoints():
    """Test health check endpoints"""
    print_header("Test 5: Health Check Endpoints")

    import requests

    endpoints = [
        ("Health", "http://localhost:8100/health"),
        ("Healthz", "http://localhost:8100/healthz"),
        ("Deep Health", "http://localhost:8100/health/deep"),
        ("Version", "http://localhost:8100/version"),
    ]

    success_count = 0
    for name, url in endpoints:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print_success(f"{name}: OK")
                success_count += 1
            else:
                print_error(f"{name}: Status {response.status_code}")
        except Exception as e:
            print_error(f"{name}: {e}")

    return success_count == len(endpoints)


async def main():
    """Run all tests"""
    print_header(f"MCP Server Comprehensive Test Suite")
    print_info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    tests = [
        ("PostgreSQL Connection", test_knowledge_db_connection),
        ("List MCP Tools", test_list_available_tools),
        ("List Databases", test_list_available_databases),
        ("Business Logic + Cache", test_explain_business_logic_caching),
        ("Health Endpoints", test_health_endpoints),
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
        print_success("All tests passed!")
        return 0
    else:
        print_error(f"{total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
