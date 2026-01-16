#!/usr/bin/env python3
"""
Comprehensive PostgreSQL Testing Script
========================================
Tests all PostgreSQL operations including:
- Connection establishment
- Table knowledge CRUD
- Relationship CRUD
- Query explanation cache
- Batch operations
- Error handling
- Performance metrics

Usage: docker exec mcp_db_performance python test-scripts/test_postgresql_comprehensive.py
"""

import asyncio
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Add server directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from knowledge_db import get_knowledge_db
from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test results tracking
test_results = {
    "passed": [],
    "failed": [],
    "warnings": [],
    "start_time": None,
    "end_time": None
}

def log_test(test_name: str, passed: bool, message: str = ""):
    """Log test result."""
    status = "✅ PASS" if passed else "❌ FAIL"
    logger.info(f"{status}: {test_name}")
    if message:
        logger.info(f"  └─ {message}")

    if passed:
        test_results["passed"].append({"test": test_name, "message": message})
    else:
        test_results["failed"].append({"test": test_name, "message": message})

def log_warning(message: str):
    """Log a warning."""
    logger.warning(f"⚠️  {message}")
    test_results["warnings"].append(message)

async def test_1_connection():
    """Test 1: Database Connection"""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Database Connection")
    logger.info("="*60)

    try:
        # Test configuration loading
        pg_config = config.get_postgresql_config()
        log_test("Configuration Loading", True, f"Host: {pg_config['host']}, DB: {pg_config['database']}")

        # Create knowledge DB instance
        db = get_knowledge_db(schema="mcp_performance")
        log_test("KnowledgeDB Instance Creation", True)

        # Test connection
        success = await db.connect()
        log_test("PostgreSQL Connection", success,
                f"Enabled: {db.is_enabled}, Pool: {db.pool is not None}")

        if not success:
            return None

        # Get connection status
        status = db.get_connection_status()
        logger.info(f"\n📊 Connection Status:")
        for key, value in status.items():
            logger.info(f"  {key}: {value}")

        return db

    except Exception as e:
        log_test("Connection Test", False, str(e))
        return None

async def test_2_basic_operations(db):
    """Test 2: Basic CRUD Operations"""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Basic CRUD Operations")
    logger.info("="*60)

    if not db or not db.is_enabled:
        log_warning("Skipping basic operations - DB not connected")
        return

    test_data = {
        "db_name": "test_db",
        "owner": "TEST_SCHEMA",
        "table_name": "TEST_TABLE_001",
        "oracle_comment": "Test table for comprehensive testing",
        "num_rows": 12345,
        "columns": [
            {"name": "ID", "data_type": "NUMBER", "nullable": False},
            {"name": "NAME", "data_type": "VARCHAR2(100)", "nullable": True},
            {"name": "CREATED_DATE", "data_type": "DATE", "nullable": True}
        ],
        "primary_key_columns": ["ID"],
        "inferred_entity_type": "Transaction",
        "inferred_domain": "Testing",
        "business_description": "Test table for validation"
    }

    try:
        # Test INSERT
        logger.info("\n🔹 Testing INSERT operation...")
        success = await db.save_table_knowledge(**test_data)
        log_test("INSERT Table Knowledge", success)

        # Test SELECT
        logger.info("\n🔹 Testing SELECT operation...")
        result = await db.get_table_knowledge(
            test_data["db_name"],
            test_data["owner"],
            test_data["table_name"]
        )

        if result:
            log_test("SELECT Table Knowledge", True,
                    f"Found: {result['owner']}.{result['table_name']}")

            # Verify data integrity
            checks = [
                ("Owner", result['owner'] == test_data['owner'].upper()),
                ("Table Name", result['table_name'] == test_data['table_name'].upper()),
                ("Row Count", result['num_rows'] == test_data['num_rows']),
                ("Columns", len(result['columns']) == len(test_data['columns'])),
                ("Entity Type", result['inferred_entity_type'] == test_data['inferred_entity_type'])
            ]

            for check_name, check_result in checks:
                log_test(f"Data Integrity: {check_name}", check_result)
        else:
            log_test("SELECT Table Knowledge", False, "No data returned")

        # Test UPDATE (save again with different data)
        logger.info("\n🔹 Testing UPDATE operation...")
        test_data["num_rows"] = 54321
        test_data["business_description"] = "Updated description"
        success = await db.save_table_knowledge(**test_data)
        log_test("UPDATE Table Knowledge", success)

        # Verify update
        result = await db.get_table_knowledge(
            test_data["db_name"],
            test_data["owner"],
            test_data["table_name"]
        )
        log_test("UPDATE Verification",
                result and result['num_rows'] == 54321,
                f"New row count: {result['num_rows'] if result else 'N/A'}")

    except Exception as e:
        log_test("Basic Operations", False, str(e))
        logger.error(f"Exception details:", exc_info=True)

async def test_3_batch_operations(db):
    """Test 3: Batch Operations"""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Batch Operations")
    logger.info("="*60)

    if not db or not db.is_enabled:
        log_warning("Skipping batch operations - DB not connected")
        return

    try:
        # Create test data for batch insert
        batch_data = []
        for i in range(1, 6):
            batch_data.append({
                "db_name": "test_db",
                "owner": "BATCH_TEST",
                "table_name": f"BATCH_TABLE_{i:03d}",
                "oracle_comment": f"Batch test table {i}",
                "num_rows": i * 1000,
                "columns": [
                    {"name": "ID", "data_type": "NUMBER", "nullable": False},
                    {"name": f"FIELD_{i}", "data_type": "VARCHAR2(50)", "nullable": True}
                ],
                "primary_key_columns": ["ID"],
                "inferred_entity_type": "Test",
                "inferred_domain": "Batch Testing"
            })

        logger.info(f"\n🔹 Testing batch INSERT of {len(batch_data)} tables...")
        saved_count = await db.save_tables_knowledge_batch(batch_data)
        log_test("Batch INSERT", saved_count == len(batch_data),
                f"Saved {saved_count}/{len(batch_data)} tables")

        # Test batch retrieval
        logger.info(f"\n🔹 Testing batch SELECT...")
        tables_list = [(d["owner"], d["table_name"]) for d in batch_data]
        result = await db.get_tables_knowledge_batch("test_db", tables_list)
        log_test("Batch SELECT", len(result) == len(batch_data),
                f"Retrieved {len(result)}/{len(batch_data)} tables")

    except Exception as e:
        log_test("Batch Operations", False, str(e))
        logger.error(f"Exception details:", exc_info=True)

async def test_4_relationships(db):
    """Test 4: Relationship Operations"""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Relationship Operations")
    logger.info("="*60)

    if not db or not db.is_enabled:
        log_warning("Skipping relationship operations - DB not connected")
        return

    try:
        # Create relationship
        logger.info("\n🔹 Testing relationship INSERT...")
        success = await db.save_relationship(
            db_name="test_db",
            from_owner="ORDERS",
            from_table="ORDER_ITEMS",
            from_columns=["ORDER_ID"],
            to_owner="ORDERS",
            to_table="ORDERS",
            to_columns=["ORDER_ID"],
            relationship_type="FK",
            constraint_name="FK_ORDER_ITEMS_ORDERS"
        )
        log_test("INSERT Relationship", success)

        # Retrieve relationships
        logger.info("\n🔹 Testing relationship SELECT...")
        relationships = await db.get_relationships_for_table("test_db", "ORDERS", "ORDER_ITEMS")
        log_test("SELECT Relationships", len(relationships) > 0,
                f"Found {len(relationships)} relationship(s)")

    except Exception as e:
        log_test("Relationship Operations", False, str(e))
        logger.error(f"Exception details:", exc_info=True)

async def test_5_cache_ttl(db):
    """Test 5: Cache TTL Behavior"""
    logger.info("\n" + "="*60)
    logger.info("TEST 5: Cache TTL Behavior")
    logger.info("="*60)

    if not db or not db.is_enabled:
        log_warning("Skipping TTL test - DB not connected")
        return

    try:
        # Insert old data (will be filtered by TTL)
        logger.info("\n🔹 Testing TTL filtering...")
        async with db.pool.acquire() as conn:
            await conn.execute(f"""
                INSERT INTO {db.schema}.table_knowledge (
                    db_name, owner, table_name,
                    last_refreshed
                ) VALUES (
                    'test_db', 'TTL_TEST', 'OLD_TABLE',
                    NOW() - INTERVAL '8 days'
                )
                ON CONFLICT (db_name, owner, table_name) DO UPDATE SET
                    last_refreshed = EXCLUDED.last_refreshed
            """)

        # Try to retrieve (should return None due to TTL)
        result = await db.get_table_knowledge("test_db", "TTL_TEST", "OLD_TABLE")
        log_test("TTL Filtering", result is None,
                "Old data correctly filtered by TTL")

    except Exception as e:
        log_test("Cache TTL", False, str(e))
        logger.error(f"Exception details:", exc_info=True)

async def test_6_error_handling(db):
    """Test 6: Error Handling"""
    logger.info("\n" + "="*60)
    logger.info("TEST 6: Error Handling")
    logger.info("="*60)

    if not db or not db.is_enabled:
        log_warning("Skipping error handling test - DB not connected")
        return

    try:
        # Test invalid data
        logger.info("\n🔹 Testing error handling with invalid data...")
        success = await db.save_table_knowledge(
            db_name="test_db",
            owner="ERROR_TEST",
            table_name="",  # Empty table name should fail
            columns=[]
        )
        log_test("Error Handling: Empty Table Name", not success,
                "Empty table name handled gracefully")

    except Exception as e:
        # Exception is expected, this is good
        log_test("Error Handling: Exception Caught", True,
                "Exception properly raised and caught")

async def test_7_performance(db):
    """Test 7: Performance Metrics"""
    logger.info("\n" + "="*60)
    logger.info("TEST 7: Performance Metrics")
    logger.info("="*60)

    if not db or not db.is_enabled:
        log_warning("Skipping performance test - DB not connected")
        return

    try:
        import time

        # Test single insert performance
        logger.info("\n🔹 Testing single INSERT performance...")
        start = time.time()
        for i in range(10):
            await db.save_table_knowledge(
                db_name="test_db",
                owner="PERF_TEST",
                table_name=f"PERF_TABLE_{i:03d}",
                num_rows=1000
            )
        single_duration = time.time() - start
        logger.info(f"  10 single inserts: {single_duration:.2f}s ({single_duration/10:.3f}s each)")

        # Test batch insert performance
        logger.info("\n🔹 Testing batch INSERT performance...")
        batch_data = [
            {
                "db_name": "test_db",
                "owner": "PERF_BATCH",
                "table_name": f"BATCH_PERF_{i:03d}",
                "num_rows": 1000
            }
            for i in range(10)
        ]
        start = time.time()
        await db.save_tables_knowledge_batch(batch_data)
        batch_duration = time.time() - start
        logger.info(f"  10 batch inserts: {batch_duration:.2f}s ({batch_duration/10:.3f}s each)")

        speedup = single_duration / batch_duration if batch_duration > 0 else 0
        log_test("Performance: Batch vs Single", speedup > 1.5,
                f"Batch is {speedup:.1f}x faster")

    except Exception as e:
        log_test("Performance Metrics", False, str(e))
        logger.error(f"Exception details:", exc_info=True)

async def test_8_connection_pooling(db):
    """Test 8: Connection Pool Management"""
    logger.info("\n" + "="*60)
    logger.info("TEST 8: Connection Pool Management")
    logger.info("="*60)

    if not db or not db.is_enabled:
        log_warning("Skipping pool test - DB not connected")
        return

    try:
        # Test concurrent operations
        logger.info("\n🔹 Testing concurrent database operations...")

        async def concurrent_operation(i):
            await db.save_table_knowledge(
                db_name="test_db",
                owner="POOL_TEST",
                table_name=f"CONCURRENT_{i:03d}",
                num_rows=i
            )
            return await db.get_table_knowledge("test_db", "POOL_TEST", f"CONCURRENT_{i:03d}")

        tasks = [concurrent_operation(i) for i in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r and not isinstance(r, Exception))
        log_test("Concurrent Operations", success_count == len(tasks),
                f"{success_count}/{len(tasks)} operations succeeded")

    except Exception as e:
        log_test("Connection Pooling", False, str(e))
        logger.error(f"Exception details:", exc_info=True)

async def cleanup_test_data(db):
    """Clean up test data"""
    logger.info("\n" + "="*60)
    logger.info("CLEANUP: Removing Test Data")
    logger.info("="*60)

    if not db or not db.is_enabled:
        return

    try:
        async with db.pool.acquire() as conn:
            # Delete test table knowledge
            result = await conn.execute(f"""
                DELETE FROM {db.schema}.table_knowledge
                WHERE db_name = 'test_db'
            """)
            logger.info(f"✅ Cleaned up table_knowledge: {result}")

            # Delete test relationships
            result = await conn.execute(f"""
                DELETE FROM {db.schema}.relationship_knowledge
                WHERE db_name = 'test_db'
            """)
            logger.info(f"✅ Cleaned up relationship_knowledge: {result}")

    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")

async def main():
    """Main test execution"""
    test_results["start_time"] = datetime.now()

    logger.info("\n" + "🧪"*30)
    logger.info("PostgreSQL Comprehensive Testing Suite")
    logger.info("🧪"*30 + "\n")

    # Run all tests
    db = await test_1_connection()

    if db and db.is_enabled:
        await test_2_basic_operations(db)
        await test_3_batch_operations(db)
        await test_4_relationships(db)
        await test_5_cache_ttl(db)
        await test_6_error_handling(db)
        await test_7_performance(db)
        await test_8_connection_pooling(db)
        await cleanup_test_data(db)
    else:
        logger.error("❌ Database connection failed - skipping all tests")

    # Print summary
    test_results["end_time"] = datetime.now()
    duration = (test_results["end_time"] - test_results["start_time"]).total_seconds()

    logger.info("\n" + "="*60)
    logger.info("TEST SUMMARY")
    logger.info("="*60)
    logger.info(f"✅ Passed: {len(test_results['passed'])}")
    logger.info(f"❌ Failed: {len(test_results['failed'])}")
    logger.info(f"⚠️  Warnings: {len(test_results['warnings'])}")
    logger.info(f"⏱️  Duration: {duration:.2f}s")

    if test_results['failed']:
        logger.info("\n❌ FAILED TESTS:")
        for failed in test_results['failed']:
            logger.info(f"  • {failed['test']}: {failed['message']}")

    if test_results['warnings']:
        logger.info("\n⚠️  WARNINGS:")
        for warning in test_results['warnings']:
            logger.info(f"  • {warning}")

    logger.info("="*60 + "\n")

    # Return exit code
    return 0 if not test_results['failed'] else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
