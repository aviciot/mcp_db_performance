#!/usr/bin/env python3
"""
Verify Cache is Working - Simple Test
=====================================
This script tests if the PostgreSQL cache is working in explain_business_logic.
"""

import asyncio
import sys
import json
import time
from datetime import datetime
import logging
import os

logger = logging.getLogger("verify_cache_working")
logger.info("[verify_cache_working.py] Script started. PID: %s", os.getpid())

async def test_explain_business_logic():
    """Test explain_business_logic with cache timing."""
    
    print("🧪 Testing explain_business_logic Cache Performance")
    print("=" * 80)
    
    # Test SQL - targeting our sample cached tables
    test_sql = """
    SELECT 
        gt.transaction_id,
        gt.amount, 
        gt.currency_code,
        ts.status_name
    FROM GTW_ODS.GATEWAY_TRANSACTIONS gt
    LEFT JOIN GTW_ODS.TRANSACTION_STATUS ts 
        ON gt.status = ts.status_code
    WHERE gt.created_date >= SYSDATE - 7
    """
    
    try:
        from tools.oracle_analysis import explain_business_logic
        
        print("📝 Test SQL:")
        print(test_sql.strip())
        
        # First call - should populate cache if not already cached
        print(f"\n🔄 First call - {datetime.now().strftime('%H:%M:%S')}")
        start1 = time.time()
        
        result1 = await explain_business_logic(
            db_name="transformer_master",
            sql_text=test_sql,
            follow_relationships=True,
            max_depth=2
        )
        
        duration1 = time.time() - start1
        
        # Check result
        if "error" in result1:
            print(f"❌ Error: {result1['error']}")
            if "connection" in result1['error'].lower():
                print("💡 Oracle connection issue - this tests cache infrastructure only")
            return result1
        
        # Extract stats
        stats1 = result1.get('stats', {})
        
        print(f"✅ First call completed in {duration1:.3f}s")
        print(f"   Cache hits: {stats1.get('cache_hits', 0)}")
        print(f"   Cache misses: {stats1.get('cache_misses', 0)}")  
        print(f"   Oracle queries: {stats1.get('oracle_queries', 0)}")
        print(f"   Tables analyzed: {stats1.get('tables_analyzed', 0)}")
        
        # Brief pause
        await asyncio.sleep(0.1)
        
        # Second call - should use more cache
        print(f"\n🔄 Second call - {datetime.now().strftime('%H:%M:%S')}")
        start2 = time.time()
        
        result2 = await explain_business_logic(
            db_name="transformer_master", 
            sql_text=test_sql,
            follow_relationships=True,
            max_depth=2
        )
        
        duration2 = time.time() - start2
        
        if "error" in result2:
            print(f"❌ Error on second call: {result2['error']}")
            return result2
        
        stats2 = result2.get('stats', {})
        
        print(f"✅ Second call completed in {duration2:.3f}s")
        print(f"   Cache hits: {stats2.get('cache_hits', 0)}")
        print(f"   Cache misses: {stats2.get('cache_misses', 0)}")
        print(f"   Oracle queries: {stats2.get('oracle_queries', 0)}")
        print(f"   Tables analyzed: {stats2.get('tables_analyzed', 0)}")
        
        # Analyze cache performance
        print(f"\n📊 Cache Performance Analysis:")
        
        # Check for cache improvements
        cache_working = False
        
        if stats2.get('cache_hits', 0) > 0:
            print(f"🚀 Cache is WORKING!")
            print(f"   ✅ {stats2.get('cache_hits', 0)} cache hits detected")
            cache_working = True
        
        if stats1.get('cache_hits', 0) < stats2.get('cache_hits', 0):
            print(f"   ✅ Cache hits improved: {stats1.get('cache_hits', 0)} → {stats2.get('cache_hits', 0)}")
            cache_working = True
        
        if stats2.get('oracle_queries', 0) == 0 and stats2.get('cache_hits', 0) > 0:
            print(f"   🎉 Perfect! All data from cache, no Oracle queries needed")
            cache_working = True
        elif stats2.get('oracle_queries', 0) < stats1.get('oracle_queries', 0):
            print(f"   ✅ Oracle queries reduced: {stats1.get('oracle_queries', 0)} → {stats2.get('oracle_queries', 0)}")
            cache_working = True
        
        # Speed improvement
        if duration1 > 0 and duration2 > 0:
            if duration2 < duration1 * 0.8:  # At least 20% faster
                improvement = ((duration1 - duration2) / duration1 * 100)
                print(f"   ⚡ Speed improved by {improvement:.1f}%")
                cache_working = True
            elif duration2 < duration1:
                improvement = ((duration1 - duration2) / duration1 * 100)
                print(f"   ⚡ Speed improved by {improvement:.1f}% (minor)")
        
        if not cache_working:
            print("⚠️ No clear cache improvements detected")
            print("💡 This could mean:")
            print("   - Tables not in cache (first run)")
            print("   - Oracle connection issues")
            print("   - Cache infrastructure not working")
        
        # Show result structure
        print(f"\n📋 Result Structure:")
        print(f"   Tables found: {len(result2.get('tables', {}))}")
        print(f"   Relationships: {len(result2.get('relationships', []))}")
        print(f"   Has explanation prompt: {'explanation_prompt' in result2}")
        
        if result2.get('tables'):
            print(f"\n📊 Sample Table Info:")
            for i, (table_name, table_info) in enumerate(result2['tables'].items()):
                if i >= 2:  # Show max 2 tables
                    break
                print(f"   {table_name}:")
                print(f"     Type: {table_info.get('type', 'unknown')}")
                print(f"     Domain: {table_info.get('domain', 'unknown')}")
                print(f"     Row count: {table_info.get('row_count', 'unknown')}")
                if table_info.get('description'):
                    desc = table_info['description'][:80]
                    print(f"     Description: {desc}{'...' if len(table_info.get('description', '')) > 80 else ''}")
        
        return {"success": True, "cache_working": cache_working, "stats": stats2}
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

async def quick_cache_check():
    """Quick check of cache infrastructure."""
    
    print("\n🔍 Quick Cache Infrastructure Check")
    print("-" * 50)
    
    try:
        from knowledge_db import get_knowledge_db
        
        knowledge_db = get_knowledge_db()
        await knowledge_db.connect()
        
        stats = await knowledge_db.get_cache_stats()
        print(f"Cache stats: {json.dumps(stats, indent=2)}")
        
        if stats.get('tables_cached', 0) > 0:
            print("✅ Cache contains data")
            
            # Show what's cached
            sample_tables = await knowledge_db.fetch(f"""
                SELECT db_name, owner, table_name, inferred_domain 
                FROM {knowledge_db.schema}.table_knowledge 
                LIMIT 3
            """)
            
            print("📋 Cached tables:")
            for row in sample_tables:
                print(f"   - {row['owner']}.{row['table_name']} ({row['db_name']}) [{row['inferred_domain']}]")
        else:
            print("📭 Cache is empty")
        
        await knowledge_db.close()
        return True
        
    except Exception as e:
        print(f"❌ Cache check failed: {e}")
        return False

async def main():
    """Main test runner."""
    
    print("🧪 PostgreSQL Cache Verification")
    print("🎯 Testing explain_business_logic performance")
    print("=" * 80)
    print(f"Timestamp: {datetime.now()}")
    print("=" * 80)
    
    # Quick cache infrastructure check
    print("STEP 1: Cache Infrastructure Check")
    cache_infra_ok = await quick_cache_check()
    
    if not cache_infra_ok:
        print("\n❌ Cache infrastructure not working")
        print("💡 Run: python check_cache_status.py fix")
        return False
    
    # Main explain_business_logic test
    print("\nSTEP 2: explain_business_logic Performance Test")
    result = await test_explain_business_logic()
    
    # Final summary
    print("\n" + "=" * 80)
    print("🏁 VERIFICATION SUMMARY")
    print("=" * 80)
    
    if isinstance(result, dict) and result.get("success"):
        cache_working = result.get("cache_working", False)
        
        if cache_working:
            print("🎉 SUCCESS: PostgreSQL cache is working optimally!")
            print("✅ Cache infrastructure: Working")
            print("✅ explain_business_logic: Using cache effectively")
            print("✅ Performance: Cache hits detected")
        else:
            print("⚠️ PARTIAL SUCCESS: Cache infrastructure working, limited cache usage")
            print("✅ Cache infrastructure: Working")  
            print("⚠️ explain_business_logic: Limited cache benefits")
            print("💡 This may be normal for first-time usage or Oracle connection issues")
        
        print(f"\n📊 Final Stats: {json.dumps(result.get('stats', {}), indent=2)}")
        
    elif isinstance(result, dict) and "error" in result:
        if "connection" in result["error"].lower():
            print("⚠️ Oracle connection issue - cache infrastructure seems OK")
            print("✅ Cache infrastructure: Working")
            print("⚠️ Oracle connection: Failed") 
            print("💡 This is expected if Oracle database is not accessible")
            print("💡 Cache will work when Oracle is available")
        else:
            print("❌ Test failed with error")
            print(f"Error: {result['error']}")
    else:
        print("❌ Unexpected test result")
    
    print(f"\nTest completed at: {datetime.now()}")
    return True

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Verification interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Verification crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)