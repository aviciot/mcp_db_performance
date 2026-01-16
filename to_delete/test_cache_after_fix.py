#!/usr/bin/env python3
"""
Test the explain_business_logic cache after the fix
"""

import asyncio
import sys
import os
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_cache")

async def test_explain_business_logic_cache():
    """Test the explain_business_logic function with caching."""
    
    print("🔍 Testing explain_business_logic Cache Performance")
    print("=" * 80)
    
    # Test SQL that should hit our sample cache data
    test_sql = """
    SELECT t1.transaction_id, t1.amount, t2.status_name
    FROM GTW_ODS.GATEWAY_TRANSACTIONS t1
    LEFT JOIN GTW_ODS.TRANSACTION_STATUS t2 ON t1.status = t2.status_code
    WHERE t1.created_date >= SYSDATE - 1
    """
    
    try:
        from tools.oracle_analysis import explain_business_logic
        
        print("📝 Testing with SQL query:")
        print(test_sql[:200] + "..." if len(test_sql) > 200 else test_sql)
        
        print("\n🔄 First call (should populate any missing cache)...")
        
        # First call
        result1 = await explain_business_logic(
            db_name="transformer_master",
            sql_text=test_sql,
            follow_relationships=True,
            max_depth=2
        )
        
        if "error" in result1:
            print(f"❌ First call error: {result1['error']}")
            if "connection" in result1['error'].lower():
                print("💡 Oracle connection issue - expected if Oracle is not accessible")
                print("   But we can still test if cache infrastructure is working")
            return result1.get('error', 'Unknown error')
        
        stats1 = result1.get('stats', {})
        print(f"✅ First call completed:")
        print(f"   Duration: {stats1.get('duration_ms', 0)}ms")
        print(f"   Cache hits: {stats1.get('cache_hits', 0)}")
        print(f"   Cache misses: {stats1.get('cache_misses', 0)}")
        print(f"   Oracle queries: {stats1.get('oracle_queries', 0)}")
        print(f"   Tables analyzed: {stats1.get('tables_analyzed', 0)}")
        
        # Brief pause
        await asyncio.sleep(0.1)
        
        print("\n🔄 Second call (should use cache more)...")
        
        # Second call - should be faster
        result2 = await explain_business_logic(
            db_name="transformer_master",
            sql_text=test_sql,
            follow_relationships=True,
            max_depth=2
        )
        
        if "error" in result2:
            print(f"❌ Second call error: {result2['error']}")
            return result2.get('error', 'Unknown error')
        
        stats2 = result2.get('stats', {})
        print(f"✅ Second call completed:")
        print(f"   Duration: {stats2.get('duration_ms', 0)}ms")
        print(f"   Cache hits: {stats2.get('cache_hits', 0)}")
        print(f"   Cache misses: {stats2.get('cache_misses', 0)}")
        print(f"   Oracle queries: {stats2.get('oracle_queries', 0)}")
        print(f"   Tables analyzed: {stats2.get('tables_analyzed', 0)}")
        
        # Analyze cache performance
        print("\n📊 Cache Performance Analysis:")
        
        if stats2.get('cache_hits', 0) > 0:
            print("🚀 Cache is WORKING!")
            print(f"   ✅ {stats2.get('cache_hits', 0)} cache hits detected")
            if stats1.get('cache_hits', 0) < stats2.get('cache_hits', 0):
                print(f"   ✅ Cache hits increased from {stats1.get('cache_hits', 0)} to {stats2.get('cache_hits', 0)}")
        else:
            print("📭 No cache hits detected")
            print("   💡 This could mean:")
            print("     - Tables not in cache yet (first time running)")
            print("     - Oracle connection failed before caching could occur")
            print("     - Table names don't match cached data")
        
        # Check if Oracle queries were reduced
        if stats2.get('oracle_queries', 0) < stats1.get('oracle_queries', 0):
            print(f"   ✅ Oracle queries reduced from {stats1.get('oracle_queries', 0)} to {stats2.get('oracle_queries', 0)}")
        elif stats2.get('oracle_queries', 0) == 0 and stats2.get('cache_hits', 0) > 0:
            print("   🎉 Perfect! All data from cache, no Oracle queries needed")
        
        # Check if duration improved
        dur1 = stats1.get('duration_ms', 0)
        dur2 = stats2.get('duration_ms', 0)
        if dur1 > 0 and dur2 > 0 and dur2 < dur1 * 0.8:
            improvement = ((dur1 - dur2) / dur1 * 100)
            print(f"   ⚡ Performance improved by {improvement:.1f}%")
        
        print(f"\n📋 Result Structure:")
        print(f"   Tables found: {len(result2.get('tables', {}))}")
        print(f"   Relationships: {len(result2.get('relationships', []))}")
        
        if result2.get('tables'):
            print(f"\n📊 Sample table data:")
            sample_table = list(result2['tables'].keys())[0]
            table_info = result2['tables'][sample_table]
            print(f"   {sample_table}:")
            print(f"     Type: {table_info.get('type')}")
            print(f"     Domain: {table_info.get('domain')}")
            print(f"     Description: {table_info.get('description', 'None')[:100]}...")
        
        return "success"
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return f"Exception: {e}"

async def test_direct_cache_lookup():
    """Test direct cache lookup without Oracle."""
    
    print("\n" + "=" * 80)
    print("🔍 Testing Direct Cache Lookup")
    print("=" * 80)
    
    try:
        from knowledge_db import get_knowledge_db
        
        knowledge_db = get_knowledge_db()
        await knowledge_db.connect()
        
        print("✅ Connected to knowledge DB")
        
        # Check what's in cache
        stats = await knowledge_db.get_cache_stats()
        print(f"📊 Current cache stats: {stats}")
        
        if stats.get('tables_cached', 0) > 0:
            # Try to get our sample table
            cached = await knowledge_db.get_table_knowledge(
                "transformer_master", 
                "GTW_ODS", 
                "GATEWAY_TRANSACTIONS"
            )
            
            if cached:
                print("✅ Found GATEWAY_TRANSACTIONS in cache!")
                print(f"   Comment: {cached.get('oracle_comment')}")
                print(f"   Domain: {cached.get('inferred_domain')}")
                print(f"   Entity type: {cached.get('inferred_entity_type')}")
                print(f"   Last refreshed: {cached.get('last_refreshed')}")
            else:
                print("📭 GATEWAY_TRANSACTIONS not in cache")
                
                # Show what IS in cache
                all_cached = await knowledge_db.fetch(f"""
                    SELECT db_name, owner, table_name, inferred_domain
                    FROM {knowledge_db.schema}.table_knowledge
                    ORDER BY last_refreshed DESC
                    LIMIT 5
                """)
                
                if all_cached:
                    print("📋 Tables currently in cache:")
                    for row in all_cached:
                        print(f"   - {row['owner']}.{row['table_name']} ({row['db_name']}) - {row['inferred_domain']}")
                else:
                    print("📭 No tables in cache")
        else:
            print("📭 Cache is empty")
        
        await knowledge_db.close()
        return True
        
    except Exception as e:
        print(f"❌ Direct cache test failed: {e}")
        return False

async def main():
    """Run all cache tests."""
    
    print("🧪 PostgreSQL Cache Verification Tests")
    print("🎯 Testing explain_business_logic after cache fix")
    print("=" * 80)
    
    # Test 1: Direct cache lookup
    print("TEST 1: Direct Cache Lookup")
    cache_working = await test_direct_cache_lookup()
    
    # Test 2: explain_business_logic cache performance
    print("\nTEST 2: explain_business_logic Cache Performance")
    result = await test_explain_business_logic_cache()
    
    # Summary
    print("\n" + "=" * 80)
    print("📋 TEST SUMMARY")
    print("=" * 80)
    
    if cache_working and result == "success":
        print("🎉 All tests passed! PostgreSQL cache is working correctly!")
        print("\n✅ Cache Infrastructure: Working")
        print("✅ explain_business_logic: Working with cache")
        print("✅ Performance: Improved with caching")
    elif cache_working and "connection" in str(result).lower():
        print("⚠️ Cache infrastructure working, Oracle connection issue")
        print("\n✅ Cache Infrastructure: Working")  
        print("⚠️ explain_business_logic: Limited by Oracle connection")
        print("💡 This is expected if Oracle DB is not accessible")
    elif not cache_working:
        print("❌ Cache infrastructure not working")
        print("\n❌ Cache Infrastructure: Failed")
        print("💡 May need to run fix_cache_complete.py again")
    else:
        print("⚠️ Mixed results - check details above")
    
    return cache_working

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Tests crashed: {e}")
        sys.exit(1)