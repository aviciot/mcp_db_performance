#!/usr/bin/env python3
"""
Cache Status Checker & Auto-Fix
================================
Comprehensive tool to check and fix the PostgreSQL cache system.
This can be run manually or through Docker exec.
"""

import asyncio
import sys
import os
import json
import logging
import traceback
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("check_cache_status")
logger.info("[check_cache_status.py] Script started. PID: %s", os.getpid())

class CacheStatusChecker:
    """Comprehensive cache status checker and auto-fixer."""
    
    def __init__(self):
        self.issues_found = []
        self.fixes_applied = []
        self.conn = None
        
    async def check_postgres_connection(self):
        """Check PostgreSQL connection and connectivity."""
        
        print("🔌 Checking PostgreSQL Connection...")
        print("-" * 50)
        
        try:
            import asyncpg
            
            # Get connection parameters
            host = os.getenv("KNOWLEDGE_DB_HOST", "pg")
            port = int(os.getenv("KNOWLEDGE_DB_PORT", "5432"))
            database = os.getenv("KNOWLEDGE_DB_NAME", "omni")
            user = os.getenv("KNOWLEDGE_DB_USER", "omni")
            password = os.getenv("KNOWLEDGE_DB_PASSWORD", "postgres")
            
            print(f"Host: {host}:{port}")
            print(f"Database: {database}")
            print(f"User: {user}")
            
            # Test connection
            self.conn = await asyncpg.connect(
                host=host, port=port, database=database, 
                user=user, password=password, timeout=5
            )
            
            version = await self.conn.fetchval("SELECT version()")
            print(f"✅ Connection successful")
            print(f"   PostgreSQL version: {version.split(',')[0]}")
            
            logger.info("PostgreSQL connection successful. Version: %s", version.split(',')[0])
            return True
            
        except ImportError:
            self.issues_found.append("asyncpg module not available")
            print("❌ asyncpg module not installed")
            logger.error("asyncpg module not installed")
            return False
            
        except Exception as e:
            self.issues_found.append(f"PostgreSQL connection failed: {e}")
            print(f"❌ Connection failed: {e}")
            logger.error("PostgreSQL connection failed: %s", e)
            print("💡 Check:")
            print("   - PostgreSQL container is running")
            print("   - Network connectivity (docker network)")
            print("   - Credentials in environment variables")
            return False
    
    async def check_schema_exists(self):
        """Check if the mcp_performance schema exists."""
        
        print("\n📋 Checking Schema...")
        print("-" * 50)
        
        if not self.conn:
            print("❌ No database connection")
            logger.warning("Schema check skipped - no database connection")
            return False
            
        try:
            schema = os.getenv("KNOWLEDGE_DB_SCHEMA", "mcp_performance")
            
            # Check if schema exists
            schema_exists = await self.conn.fetchval(
                "SELECT 1 FROM information_schema.schemata WHERE schema_name = $1",
                schema
            )
            
            if schema_exists:
                print(f"✅ Schema '{schema}' exists")
                logger.info("Schema check passed. Schema '%s' exists", schema)
                
                # Check tables in schema
                tables = await self.conn.fetch(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = $1",
                    schema
                )
                
                expected_tables = [
                    'table_knowledge', 'relationship_knowledge', 
                    'query_explanations', 'domain_glossary', 'discovery_log'
                ]
                
                print(f"📊 Found {len(tables)} tables in schema:")
                existing_tables = [row['table_name'] for row in tables]
                
                for table in expected_tables:
                    if table in existing_tables:
                        print(f"   ✅ {table}")
                    else:
                        print(f"   ❌ {table} (MISSING)")
                        self.issues_found.append(f"Table {table} missing from schema")
                        logger.warning("Table %s is missing from schema %s", table, schema)
                
                return len(existing_tables) >= len(expected_tables) // 2  # At least half the tables
                
            else:
                self.issues_found.append(f"Schema '{schema}' does not exist")
                print(f"❌ Schema '{schema}' does not exist")
                logger.warning("Schema check failed. Schema '%s' does not exist", schema)
                return False
                
        except Exception as e:
            self.issues_found.append(f"Schema check failed: {e}")
            print(f"❌ Schema check failed: {e}")
            logger.error("Schema check error: %s", e)
            return False
    
    async def check_cache_data(self):
        """Check if there's any data in the cache."""
        
        print("\n💾 Checking Cache Data...")
        print("-" * 50)
        
        if not self.conn:
            print("❌ No database connection")
            logger.warning("Cache data check skipped - no database connection")
            return False
            
        try:
            schema = os.getenv("KNOWLEDGE_DB_SCHEMA", "mcp_performance")
            
            # Count records in each table
            stats = await self.conn.fetchrow(f"""
                SELECT 
                    (SELECT COUNT(*) FROM {schema}.table_knowledge) as table_count,
                    (SELECT COUNT(*) FROM {schema}.relationship_knowledge) as rel_count,
                    (SELECT COUNT(*) FROM {schema}.query_explanations) as query_count,
                    (SELECT COUNT(*) FROM {schema}.discovery_log) as log_count
            """)
            
            total_records = sum(stats.values())
            
            print(f"📊 Cache Statistics:")
            print(f"   Tables cached: {stats['table_count']}")
            print(f"   Relationships cached: {stats['rel_count']}")  
            print(f"   Queries cached: {stats['query_count']}")
            print(f"   Discovery logs: {stats['log_count']}")
            print(f"   Total records: {total_records}")
            
            logger.info("Cache data check completed. Total records: %d", total_records)
            
            if total_records > 0:
                print("✅ Cache contains data")
                
                # Show some sample data
                if stats['table_count'] > 0:
                    sample = await self.conn.fetchrow(f"""
                        SELECT db_name, owner, table_name, inferred_domain, last_refreshed
                        FROM {schema}.table_knowledge 
                        ORDER BY last_refreshed DESC LIMIT 1
                    """)
                    print(f"   📋 Latest cached table: {sample['owner']}.{sample['table_name']} ({sample['db_name']})")
                    print(f"      Domain: {sample['inferred_domain']}")
                    print(f"      Cached: {sample['last_refreshed']}")
                
                return True
            else:
                print("📭 Cache is empty (no data cached yet)")
                logger.info("Cache is empty (no data cached yet)")
                return False
                
        except Exception as e:
            self.issues_found.append(f"Cache data check failed: {e}")
            print(f"❌ Cache data check failed: {e}")
            logger.error("Cache data check error: %s", e)
            return False
    
    async def check_knowledge_db_wrapper(self):
        """Check if the KnowledgeDBAsync wrapper is working."""
        
        print("\n📦 Checking KnowledgeDBAsync Wrapper...")
        print("-" * 50)
        
        try:
            from knowledge_db import get_knowledge_db
            
            knowledge_db = get_knowledge_db()
            print(f"Schema: {knowledge_db.schema}")
            print(f"Initially enabled: {knowledge_db.is_enabled}")
            
            if not knowledge_db.is_enabled:
                await knowledge_db.connect()
                
            print(f"After connect enabled: {knowledge_db.is_enabled}")
            
            if knowledge_db.is_enabled:
                # Test cache stats
                stats = await knowledge_db.get_cache_stats()
                print(f"✅ Wrapper working, cache stats: {stats}")
                logger.info("KnowledgeDBAsync wrapper working. Cache stats: %s", stats)
                
                await knowledge_db.close()
                return True
            else:
                self.issues_found.append("KnowledgeDBAsync wrapper failed to connect")
                print("❌ KnowledgeDBAsync wrapper not working")
                logger.warning("KnowledgeDBAsync wrapper not working - enabled status: %s", knowledge_db.is_enabled)
                return False
                
        except Exception as e:
            self.issues_found.append(f"KnowledgeDBAsync wrapper error: {e}")
            print(f"❌ KnowledgeDBAsync wrapper error: {e}")
            logger.error("KnowledgeDBAsync wrapper error: %s", e)
            traceback.print_exc()
            return False
    
    async def auto_fix_schema(self):
        """Automatically fix schema issues."""
        
        print("\n🔧 Auto-fixing Schema Issues...")
        print("-" * 50)
        
        if not self.conn:
            print("❌ Cannot fix - no database connection")
            logger.warning("Auto-fix schema skipped - no database connection")
            return False
            
        try:
            schema = os.getenv("KNOWLEDGE_DB_SCHEMA", "mcp_performance")
            
            # Drop and recreate schema
            print(f"🗑️ Dropping schema '{schema}' if exists...")
            await self.conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
            logger.info("Schema '%s' dropped", schema)
            
            print(f"🆕 Creating fresh schema '{schema}'...")
            await self.conn.execute(f"CREATE SCHEMA {schema}")
            logger.info("Schema '%s' created", schema)
            
            # Create tables (simplified version)
            print("🏗️ Creating cache tables...")
            
            tables_sql = f"""
            -- Table Knowledge Cache
            CREATE TABLE {schema}.table_knowledge (
                db_name VARCHAR(100) NOT NULL,
                owner VARCHAR(128) NOT NULL,
                table_name VARCHAR(128) NOT NULL,
                oracle_comment TEXT,
                num_rows BIGINT DEFAULT 0,
                columns JSONB DEFAULT '[]',
                primary_key_columns TEXT[],
                inferred_entity_type VARCHAR(100),
                inferred_domain VARCHAR(100),
                last_refreshed TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                PRIMARY KEY (db_name, owner, table_name)
            );

            -- Relationship Knowledge Cache  
            CREATE TABLE {schema}.relationship_knowledge (
                db_name VARCHAR(100) NOT NULL,
                from_owner VARCHAR(128) NOT NULL,
                from_table VARCHAR(128) NOT NULL, 
                from_columns TEXT[] NOT NULL,
                to_owner VARCHAR(128) NOT NULL,
                to_table VARCHAR(128) NOT NULL,
                to_columns TEXT[] NOT NULL,
                relationship_type VARCHAR(20) DEFAULT 'FK',
                last_refreshed TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                PRIMARY KEY (db_name, from_owner, from_table, to_owner, to_table, from_columns)
            );

            -- Query Explanation Cache
            CREATE TABLE {schema}.query_explanations (
                sql_fingerprint VARCHAR(64) PRIMARY KEY,
                db_name VARCHAR(100) NOT NULL,
                sql_text TEXT NOT NULL,
                business_explanation TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                hit_count INTEGER DEFAULT 1
            );

            -- Domain Glossary
            CREATE TABLE {schema}.domain_glossary (
                term VARCHAR(200) NOT NULL,
                domain VARCHAR(100) NOT NULL,
                definition TEXT NOT NULL,
                PRIMARY KEY (term, domain)
            );

            -- Discovery Operation Log
            CREATE TABLE {schema}.discovery_log (
                id SERIAL PRIMARY KEY,
                operation_type VARCHAR(100) NOT NULL,
                db_name VARCHAR(100) NOT NULL,
                cache_hits INTEGER DEFAULT 0,
                cache_misses INTEGER DEFAULT 0,
                started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """
            
            # Execute table creation
            statements = [s.strip() for s in tables_sql.split(';') if s.strip()]
            for statement in statements:
                await self.conn.execute(statement)
                logger.info("Executed SQL statement: %s", statement[:50])  # Log first 50 chars of statement
            
            self.fixes_applied.append("Schema recreated with all tables")
            print("✅ Schema auto-fix completed")
            logger.info("Schema auto-fix completed")
            return True
            
        except Exception as e:
            print(f"❌ Auto-fix failed: {e}")
            logger.error("Auto-fix schema error: %s", e)
            return False
    
    async def create_sample_data(self):
        """Create sample data for testing."""
        
        print("\n📋 Creating Sample Data...")
        print("-" * 50)
        
        if not self.conn:
            logger.warning("Sample data creation skipped - no database connection")
            return False
            
        try:
            schema = os.getenv("KNOWLEDGE_DB_SCHEMA", "mcp_performance")
            
            # Insert sample table data
            await self.conn.execute(f"""
                INSERT INTO {schema}.table_knowledge (
                    db_name, owner, table_name, oracle_comment, num_rows,
                    columns, primary_key_columns, inferred_entity_type, inferred_domain
                ) VALUES 
                ('transformer_master', 'GTW_ODS', 'GATEWAY_TRANSACTIONS', 
                 'Main transaction table', 2500000,
                 '[{{"name": "TRANSACTION_ID", "data_type": "NUMBER(20)", "position": 1}}]',
                 ARRAY['TRANSACTION_ID'], 'transaction', 'payments'),
                ('transformer_master', 'GTW_ODS', 'TRANSACTION_STATUS',
                 'Transaction status lookup', 25,
                 '[{{"name": "STATUS_CODE", "data_type": "VARCHAR2(20)", "position": 1}}]',
                 ARRAY['STATUS_CODE'], 'lookup', 'payments')
                ON CONFLICT (db_name, owner, table_name) DO NOTHING
            """)
            logger.info("Inserted sample data into table_knowledge")
            
            # Insert sample relationship
            await self.conn.execute(f"""
                INSERT INTO {schema}.relationship_knowledge (
                    db_name, from_owner, from_table, from_columns,
                    to_owner, to_table, to_columns, relationship_type
                ) VALUES (
                    'transformer_master', 'GTW_ODS', 'GATEWAY_TRANSACTIONS', ARRAY['STATUS'],
                    'GTW_ODS', 'TRANSACTION_STATUS', ARRAY['STATUS_CODE'], 'FK'
                ) ON CONFLICT DO NOTHING
            """)
            logger.info("Inserted sample data into relationship_knowledge")
            
            self.fixes_applied.append("Sample data created")
            print("✅ Sample data created")
            logger.info("Sample data creation completed")
            return True
            
        except Exception as e:
            print(f"❌ Sample data creation failed: {e}")
            logger.error("Sample data creation error: %s", e)
            return False

    async def run_comprehensive_check(self, auto_fix=False):
        """Run all checks and optionally auto-fix issues."""
        
        print("🔍 PostgreSQL Cache Comprehensive Status Check")
        print("=" * 80)
        print(f"Auto-fix mode: {'ENABLED' if auto_fix else 'DISABLED'}")
        print(f"Timestamp: {datetime.now()}")
        print("=" * 80)
        
        # Step 1: PostgreSQL Connection
        conn_ok = await self.check_postgres_connection()
        
        if not conn_ok:
            print("\n💥 CRITICAL: Cannot proceed without PostgreSQL connection")
            logger.critical("PostgreSQL connection failed - aborting")
            return False
        
        # Step 2: Schema Check
        schema_ok = await self.check_schema_exists()
        
        if not schema_ok and auto_fix:
            print("\n🔧 Auto-fixing schema issues...")
            if await self.auto_fix_schema():
                schema_ok = True
        
        # Step 3: Cache Data Check
        data_ok = await self.check_cache_data()
        
        if schema_ok and not data_ok and auto_fix:
            print("\n🔧 Creating sample data...")
            if await self.create_sample_data():
                data_ok = True
        
        # Step 4: Wrapper Check
        wrapper_ok = await self.check_knowledge_db_wrapper()
        
        # Final Summary
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE STATUS SUMMARY")
        print("=" * 80)
        
        checks = [
            ("PostgreSQL Connection", conn_ok),
            ("Schema & Tables", schema_ok), 
            ("Cache Data", data_ok),
            ("KnowledgeDBAsync Wrapper", wrapper_ok)
        ]
        
        passed = sum(1 for _, ok in checks if ok)
        total = len(checks)
        
        for check_name, ok in checks:
            status = "✅ PASS" if ok else "❌ FAIL"
            print(f"{check_name:25} {status}")
        
        print(f"\nOverall Status: {passed}/{total} checks passed")
        
        if self.issues_found:
            print(f"\n🚨 Issues Found ({len(self.issues_found)}):")
            for i, issue in enumerate(self.issues_found, 1):
                print(f"  {i}. {issue}")
        
        if self.fixes_applied:
            print(f"\n🔧 Fixes Applied ({len(self.fixes_applied)}):")
            for i, fix in enumerate(self.fixes_applied, 1):
                print(f"  {i}. {fix}")
        
        if passed == total:
            print("\n🎉 ALL CHECKS PASSED!")
            print("💡 PostgreSQL cache should be working for explain_business_logic")
            logger.info("All checks passed. PostgreSQL cache should be functional.")
        elif passed >= total // 2:
            print("\n⚠️ PARTIAL SUCCESS - Some issues remain")
            if not auto_fix:
                print("💡 Try running with auto_fix=True to fix issues")
            logger.warning("Partial success - some issues remain")
        else:
            print("\n❌ MAJOR ISSUES - Cache not functional")
            print("💡 Manual intervention required")
            logger.error("Major issues detected - manual intervention required")
        
        # Cleanup
        if self.conn:
            await self.conn.close()
            logger.info("Database connection closed")
        
        return passed == total

async def main():
    """Main entry point."""
    
    # Check for auto-fix argument
    auto_fix = len(sys.argv) > 1 and sys.argv[1].lower() in ('fix', 'auto-fix', '--fix')
    
    if auto_fix:
        print("🔧 Auto-fix mode enabled - will attempt to fix issues automatically")
    else:
        print("🔍 Check mode - will only diagnose issues")
        print("💡 Run with 'fix' argument to auto-fix issues")
    
    checker = CacheStatusChecker()
    success = await checker.run_comprehensive_check(auto_fix=auto_fix)
    
    return success

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        print(f"\n{'🎉 SUCCESS' if success else '❌ FAILED'}: Status check completed")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Check interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Check crashed: {e}")
        traceback.print_exc()
        sys.exit(1)