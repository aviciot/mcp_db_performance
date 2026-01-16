#!/usr/bin/env python3
"""
Complete PostgreSQL Cache Fix for explain_business_logic
========================================================
This script completely reinitializes the PostgreSQL cache system.
"""

import asyncio
import sys
import os
import logging
import traceback

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("cache_fix")

logger.info("[fix_cache_complete.py] Script started. PID: %s", os.getpid())

async def connect_to_postgres():
    """Connect directly to PostgreSQL and test connection."""
    logger.info("[fix_cache_complete.py] Attempting to connect to Postgres for cache fix.")
    
    print("=" * 80)
    print("🔌 Testing PostgreSQL Connection")
    print("=" * 80)
    
    try:
        import asyncpg
        
        # Get connection parameters from environment
        host = os.getenv("KNOWLEDGE_DB_HOST", "pg")
        port = int(os.getenv("KNOWLEDGE_DB_PORT", "5432"))
        database = os.getenv("KNOWLEDGE_DB_NAME", "omni")
        user = os.getenv("KNOWLEDGE_DB_USER", "omni")
        password = os.getenv("KNOWLEDGE_DB_PASSWORD", "postgres")
        
        logger.info(f"[fix_cache_complete.py] Connecting to: {user}@{host}:{port}/{database}")
        print(f"[fix_cache_complete.py] [connect_to_postgres] Connecting to: {user}@{host}:{port}/{database}")
        # Test connection
        conn = await asyncpg.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            timeout=10
        )
        logger.info(f"[fix_cache_complete.py] Connected to Postgres: {user}@{host}:{port}/{database}")
        print(f"[fix_cache_complete.py] [connect_to_postgres] Connected to: {user}@{host}:{port}/{database}")
        # Test basic query
        version = await conn.fetchval("SELECT version()")
        print(f"✅ PostgreSQL Connection Successful")
        print(f"   Version: {version}")
        return conn
        
    except Exception as e:
        logger.error(f"[fix_cache_complete.py] Postgres connection failed: {e}")
        print(f"❌ PostgreSQL Connection Failed: {e}")
        print("\n💡 Troubleshooting:")
        print("   1. Ensure PostgreSQL container is running")
        print("   2. Check if 'pg' hostname resolves (docker network)")
        print("   3. Verify credentials in environment variables")
        return None

async def drop_and_recreate_schema(conn):
    """Drop and recreate the mcp_performance schema completely."""
    
    print("\n" + "=" * 80)
    print("🗑️ Dropping and Recreating Schema")
    print("=" * 80)
    
    schema = os.getenv("KNOWLEDGE_DB_SCHEMA", "mcp_performance")
    
    try:
        print(f"[fix_cache_complete.py] [drop_and_recreate_schema] Using connection: {conn}")
        # Drop schema completely
        print(f"🗑️ Dropping schema '{schema}' if exists...")
        await conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        print(f"✅ Schema '{schema}' dropped")
        # Create fresh schema
        print(f"🆕 Creating fresh schema '{schema}'...")
        await conn.execute(f"CREATE SCHEMA {schema}")
        print(f"✅ Schema '{schema}' created")
        return True
    except Exception as e:
        print(f"❌ Schema recreation failed: {e}")
        return False

async def initialize_schema_tables(conn):
    """Initialize all cache tables with the complete schema."""
    
    print("\n" + "=" * 80)
    print("🏗️ Initializing Cache Tables")
    print("=" * 80)
    
    schema = os.getenv("KNOWLEDGE_DB_SCHEMA", "mcp_performance")
    
    # Complete schema SQL - based on the migration file but fixed
    schema_sql = f"""
    -- Set search path
    SET search_path TO {schema}, public;
    
    -- Table Knowledge Cache
    CREATE TABLE {schema}.table_knowledge (
        -- Identification
        db_name VARCHAR(100) NOT NULL,
        owner VARCHAR(128) NOT NULL,
        table_name VARCHAR(128) NOT NULL,
        
        -- Oracle/MySQL Metadata
        oracle_comment TEXT,
        num_rows BIGINT DEFAULT 0,
        is_partitioned BOOLEAN DEFAULT FALSE,
        partition_type VARCHAR(50),
        partition_key_columns TEXT[],
        
        -- Schema Information
        columns JSONB DEFAULT '[]',
        primary_key_columns TEXT[],
        
        -- Business Intelligence (Inferred)
        inferred_entity_type VARCHAR(100),
        inferred_domain VARCHAR(100),
        business_description TEXT,
        business_purpose TEXT,
        confidence_score FLOAT DEFAULT 0.5,
        
        -- Cache Management
        last_refreshed TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        refresh_count INTEGER DEFAULT 1,
        
        -- Constraints
        PRIMARY KEY (db_name, owner, table_name)
    );

    -- Relationship Knowledge Cache  
    CREATE TABLE {schema}.relationship_knowledge (
        -- Identification
        db_name VARCHAR(100) NOT NULL,
        
        -- Source Table
        from_owner VARCHAR(128) NOT NULL,
        from_table VARCHAR(128) NOT NULL, 
        from_columns TEXT[] NOT NULL,
        
        -- Target Table
        to_owner VARCHAR(128) NOT NULL,
        to_table VARCHAR(128) NOT NULL,
        to_columns TEXT[] NOT NULL,
        
        -- Relationship Metadata
        relationship_type VARCHAR(20) DEFAULT 'FK',
        constraint_name VARCHAR(128),
        cardinality VARCHAR(20),
        is_lookup BOOLEAN DEFAULT FALSE,
        
        -- Business Intelligence
        business_meaning TEXT,
        relationship_role VARCHAR(100),
        
        -- Cache Management
        last_refreshed TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        
        -- Constraints  
        PRIMARY KEY (db_name, from_owner, from_table, to_owner, to_table, from_columns)
    );

    -- Query Explanation Cache
    CREATE TABLE {schema}.query_explanations (
        -- Query Identification
        sql_fingerprint VARCHAR(64) PRIMARY KEY,
        db_name VARCHAR(100) NOT NULL,
        sql_text TEXT NOT NULL,
        sql_normalized TEXT NOT NULL,
        
        -- Analysis Results
        tables_involved JSONB DEFAULT '[]',
        business_explanation TEXT NOT NULL,
        query_purpose VARCHAR(200),
        data_flow_description TEXT,
        domain_tags TEXT[],
        
        -- Cache Statistics
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        last_accessed TIMESTAMP WITH TIME ZONE DEFAULT NOW(), 
        hit_count INTEGER DEFAULT 1,
        
        -- Constraints
        UNIQUE (sql_fingerprint, db_name)
    );

    -- Domain Glossary
    CREATE TABLE {schema}.domain_glossary (
        -- Term Definition
        term VARCHAR(200) NOT NULL,
        domain VARCHAR(100) NOT NULL,
        definition TEXT NOT NULL,
        
        -- Examples and Usage
        examples TEXT[],
        related_terms TEXT[],
        example_tables TEXT[],
        example_columns TEXT[],
        
        -- Usage Tracking
        occurrence_count INTEGER DEFAULT 1,
        last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        
        -- Constraints
        PRIMARY KEY (term, domain)
    );

    -- Discovery Operation Log
    CREATE TABLE {schema}.discovery_log (
        id SERIAL PRIMARY KEY,
        
        -- Operation Details
        operation_type VARCHAR(100) NOT NULL,
        db_name VARCHAR(100) NOT NULL,
        
        -- Results
        tables_discovered INTEGER DEFAULT 0,
        relationships_discovered INTEGER DEFAULT 0,
        
        -- Performance Metrics
        cache_hits INTEGER DEFAULT 0,
        cache_misses INTEGER DEFAULT 0,
        duration_ms INTEGER,
        oracle_queries_executed INTEGER DEFAULT 0,
        
        -- Status
        success BOOLEAN DEFAULT TRUE,
        error_message TEXT,
        
        -- Timing
        started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    -- Create indexes for performance
    CREATE INDEX idx_table_knowledge_db_refresh ON {schema}.table_knowledge(db_name, last_refreshed);
    CREATE INDEX idx_table_knowledge_domain ON {schema}.table_knowledge(inferred_domain) WHERE inferred_domain IS NOT NULL;
    CREATE INDEX idx_relationship_knowledge_from ON {schema}.relationship_knowledge(db_name, from_owner, from_table);
    CREATE INDEX idx_relationship_knowledge_to ON {schema}.relationship_knowledge(db_name, to_owner, to_table);
    CREATE INDEX idx_query_explanations_db ON {schema}.query_explanations(db_name, last_accessed DESC);
    CREATE INDEX idx_domain_glossary_domain ON {schema}.domain_glossary(domain, occurrence_count DESC);
    CREATE INDEX idx_discovery_log_db_started ON {schema}.discovery_log(db_name, started_at DESC);
    """
    
    try:
        print(f"[fix_cache_complete.py] [initialize_schema_tables] Using connection: {conn}")
        # Execute the complete schema
        print("🏗️ Creating cache tables...")
        # Split into individual statements and execute
        statements = [s.strip() for s in schema_sql.split(';') if s.strip()]
        success_count = 0
        for i, statement in enumerate(statements, 1):
            if statement:
                try:
                    await conn.execute(statement)
                    success_count += 1
                    print(f"   ✅ Statement {i}/{len(statements)}")
                except Exception as e:
                    print(f"   ❌ Statement {i} failed: {e}")
        print(f"✅ Schema initialization complete: {success_count}/{len(statements)} statements executed")
        # Verify tables were created
        tables = await conn.fetch(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = $1",
            schema
        )
        print(f"📋 Created {len(tables)} tables:")
        for table in tables:
            print(f"   - {table['table_name']}")
        return len(tables) >= 5  # Should have at least 5 main tables
    except Exception as e:
        print(f"❌ Schema initialization failed: {e}")
        traceback.print_exc()
        return False

async def test_cache_operations(conn):
    """Test that cache operations work correctly."""
    
    print("\n" + "=" * 80)
    print("🧪 Testing Cache Operations")
    print("=" * 80)
    
    schema = os.getenv("KNOWLEDGE_DB_SCHEMA", "mcp_performance")
    
    try:
        print(f"[fix_cache_complete.py] [test_cache_operations] Using connection: {conn}")
        # Test 1: Insert table knowledge
        print("💾 Testing table knowledge insert...")
        await conn.execute(f"""
            INSERT INTO {schema}.table_knowledge (
                db_name, owner, table_name, oracle_comment, num_rows,
                columns, primary_key_columns, inferred_entity_type, inferred_domain
            ) VALUES (
                'test_db', 'TEST_SCHEMA', 'TEST_TABLE', 
                'Test table for cache verification',
                50000,
                '[{"name": "ID", "data_type": "NUMBER(10)", "position": 1, "nullable": false}]',
                ARRAY['ID'],
                'business_entity',
                'testing'
            )
        """)
        print("✅ Table knowledge insert successful")
        # Test 2: Retrieve table knowledge
        print("📦 Testing table knowledge retrieval...")
        row = await conn.fetchrow(f"""
            SELECT * FROM {schema}.table_knowledge 
            WHERE db_name = 'test_db' AND owner = 'TEST_SCHEMA' AND table_name = 'TEST_TABLE'
        """)
        if row:
            print("✅ Table knowledge retrieval successful")
            print(f"   Comment: {row['oracle_comment']}")
            print(f"   Domain: {row['inferred_domain']}")
            print(f"   Columns: {row['columns']}")
        else:
            print("❌ Table knowledge retrieval failed")
            return False
        # Test 3: Insert relationship
        print("🔗 Testing relationship insert...")
        await conn.execute(f"""
            INSERT INTO {schema}.relationship_knowledge (
                db_name, from_owner, from_table, from_columns,
                to_owner, to_table, to_columns, relationship_type
            ) VALUES (
                'test_db', 'TEST_SCHEMA', 'TEST_TABLE', ARRAY['STATUS'],
                'TEST_SCHEMA', 'STATUS_LOOKUP', ARRAY['CODE'], 'FK'
            )
        """)
        print("✅ Relationship insert successful")
        # Test 4: Retrieve relationships
        print("🔍 Testing relationship retrieval...")
        rels = await conn.fetch(f"""
            SELECT * FROM {schema}.relationship_knowledge 
            WHERE db_name = 'test_db' AND from_owner = 'TEST_SCHEMA'
        """)
        if rels:
            print(f"✅ Found {len(rels)} relationship(s)")
        else:
            print("⚠️ No relationships found")
        # Test 5: Cache statistics query
        print("📊 Testing cache statistics...")
        stats = await conn.fetchrow(f"""
            SELECT 
                (SELECT COUNT(*) FROM {schema}.table_knowledge) as tables_cached,
                (SELECT COUNT(*) FROM {schema}.relationship_knowledge) as relationships_cached,
                (SELECT COUNT(*) FROM {schema}.query_explanations) as queries_cached
        """)
        if stats:
            print("✅ Cache statistics working")
            print(f"   Tables: {stats['tables_cached']}")
            print(f"   Relationships: {stats['relationships_cached']}")
            print(f"   Queries: {stats['queries_cached']}")
        # Clean up test data
        print("🧹 Cleaning up test data...")
        await conn.execute(f"DELETE FROM {schema}.table_knowledge WHERE db_name = 'test_db'")
        await conn.execute(f"DELETE FROM {schema}.relationship_knowledge WHERE db_name = 'test_db'")
        print("✅ All cache operations working correctly!")
        return True
    except Exception as e:
        print(f"❌ Cache operations test failed: {e}")
        traceback.print_exc()
        return False

async def test_knowledge_db_wrapper():
    """Test the KnowledgeDBAsync wrapper class."""
    
    print("\n" + "=" * 80)
    print("📦 Testing KnowledgeDBAsync Wrapper")
    print("=" * 80)
    
    try:
        from knowledge_db import get_knowledge_db
        knowledge_db = get_knowledge_db()
        await knowledge_db.connect()
        print(f"[fix_cache_complete.py] [test_knowledge_db_wrapper] Connected to KnowledgeDBAsync (schema: {knowledge_db.schema})")
        # Test cache stats
        stats = await knowledge_db.get_cache_stats()
        print(f"📊 Cache stats: {stats}")
        # Test save operation
        print("💾 Testing save_table_knowledge...")
        success = await knowledge_db.save_table_knowledge(
            db_name="wrapper_test",
            owner="WRAPPER_SCHEMA",
            table_name="WRAPPER_TABLE",
            oracle_comment="Test from wrapper",
            columns=[{"name": "ID", "data_type": "NUMBER", "position": 1}],
            num_rows=12345,
            inferred_entity_type="test",
            inferred_domain="wrapper_test"
        )
        if success:
            print("✅ Wrapper save successful")
            # Test retrieve operation
            cached = await knowledge_db.get_table_knowledge("wrapper_test", "WRAPPER_SCHEMA", "WRAPPER_TABLE")
            if cached:
                print("✅ Wrapper retrieve successful")
                print(f"   Comment: {cached.get('oracle_comment')}")
            else:
                print("❌ Wrapper retrieve failed")
                return False
        else:
            print("❌ Wrapper save failed")
            return False
        # Clean up
        await knowledge_db.execute(
            f"DELETE FROM {knowledge_db.schema}.table_knowledge WHERE db_name = 'wrapper_test'"
        )
        await knowledge_db.close()
        print("✅ KnowledgeDBAsync wrapper working correctly!")
        return True
    except Exception as e:
        print(f"❌ KnowledgeDBAsync wrapper test failed: {e}")
        traceback.print_exc()
        return False

async def create_sample_data(conn):
    """Create some realistic sample data for testing."""
    
    print("\n" + "=" * 80)
    print("📋 Creating Sample Cache Data")
    print("=" * 80)
    
    schema = os.getenv("KNOWLEDGE_DB_SCHEMA", "mcp_performance")
    
    # Sample data for common tables
    sample_data = [
        {
            "db_name": "transformer_master",
            "owner": "GTW_ODS",
            "table_name": "GATEWAY_TRANSACTIONS",
            "oracle_comment": "Main transaction table storing all gateway payment transactions",
            "num_rows": 2500000,
            "columns": '[{"name": "TRANSACTION_ID", "data_type": "NUMBER(20)", "position": 1, "nullable": false}, {"name": "MERCHANT_ID", "data_type": "NUMBER(10)", "position": 2, "nullable": false}, {"name": "AMOUNT", "data_type": "NUMBER(15,2)", "position": 3, "nullable": false}, {"name": "STATUS", "data_type": "VARCHAR2(20)", "position": 4, "nullable": false}]',
            "primary_key_columns": ["TRANSACTION_ID"],
            "inferred_entity_type": "transaction",
            "inferred_domain": "payments"
        },
        {
            "db_name": "transformer_master",
            "owner": "GTW_ODS", 
            "table_name": "TRANSACTION_STATUS",
            "oracle_comment": "Lookup table for transaction status codes",
            "num_rows": 25,
            "columns": '[{"name": "STATUS_CODE", "data_type": "VARCHAR2(20)", "position": 1, "nullable": false}, {"name": "STATUS_NAME", "data_type": "VARCHAR2(100)", "position": 2, "nullable": false}]',
            "primary_key_columns": ["STATUS_CODE"],
            "inferred_entity_type": "lookup",
            "inferred_domain": "payments"
        }
    ]
    
    try:
        print(f"[fix_cache_complete.py] [create_sample_data] Using connection: {conn}")
        for data in sample_data:
            print(f"💾 Inserting sample data for {data['owner']}.{data['table_name']}...")
            await conn.execute(f"""
                INSERT INTO {schema}.table_knowledge (
                    db_name, owner, table_name, oracle_comment, num_rows,
                    columns, primary_key_columns, inferred_entity_type, inferred_domain
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (db_name, owner, table_name) DO UPDATE SET
                    oracle_comment = EXCLUDED.oracle_comment,
                    num_rows = EXCLUDED.num_rows,
                    columns = EXCLUDED.columns,
                    primary_key_columns = EXCLUDED.primary_key_columns,
                    inferred_entity_type = EXCLUDED.inferred_entity_type,
                    inferred_domain = EXCLUDED.inferred_domain,
                    last_refreshed = NOW()
            """, 
                data["db_name"], data["owner"], data["table_name"], 
                data["oracle_comment"], data["num_rows"], data["columns"],
                data["primary_key_columns"], data["inferred_entity_type"], 
                data["inferred_domain"]
            )
        # Add sample relationship
        print("🔗 Adding sample relationship...")
        await conn.execute(f"""
            INSERT INTO {schema}.relationship_knowledge (
                db_name, from_owner, from_table, from_columns,
                to_owner, to_table, to_columns, relationship_type
            ) VALUES (
                'transformer_master', 'GTW_ODS', 'GATEWAY_TRANSACTIONS', ARRAY['STATUS'],
                'GTW_ODS', 'TRANSACTION_STATUS', ARRAY['STATUS_CODE'], 'FK'
            )
            ON CONFLICT (db_name, from_owner, from_table, to_owner, to_table, from_columns) 
            DO UPDATE SET last_refreshed = NOW()
        """)
        print("✅ Sample data created successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to create sample data: {e}")
        return False

async def main():
    logger.info("[fix_cache_complete.py] main() called. Starting full cache fix.")
    
    """Complete cache fix and initialization."""
    
    print("🔧 Complete PostgreSQL Cache Fix & Initialization")
    print("🎯 Reinitializing explain_business_logic caching system")
    print("=" * 80)
    
    # Step 1: Connect to PostgreSQL
    conn = await connect_to_postgres()
    if not conn:
        logger.error("[fix_cache_complete.py] Could not connect to Postgres. Exiting main().")
        print("❌ Cannot proceed without PostgreSQL connection")
        return False
    try:
        # Step 2: Drop and recreate schema
        print("\nSTEP 2: Schema Reinitialization")
        if not await drop_and_recreate_schema(conn):
            return False
        
        # Step 3: Initialize tables
        print("\nSTEP 3: Table Creation") 
        if not await initialize_schema_tables(conn):
            return False
        
        # Step 4: Test cache operations
        print("\nSTEP 4: Cache Operations Test")
        if not await test_cache_operations(conn):
            return False
        
        # Step 5: Test wrapper class
        print("\nSTEP 5: Wrapper Class Test")
        if not await test_knowledge_db_wrapper():
            return False
        
        # Step 6: Create sample data
        print("\nSTEP 6: Sample Data Creation")
        await create_sample_data(conn)
        
        # Final verification
        schema = os.getenv("KNOWLEDGE_DB_SCHEMA", "mcp_performance")
        final_stats = await conn.fetchrow(f"""
            SELECT 
                (SELECT COUNT(*) FROM {schema}.table_knowledge) as tables,
                (SELECT COUNT(*) FROM {schema}.relationship_knowledge) as relationships,
                (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '{schema}') as schema_tables
        """)
        
        print("\n" + "=" * 80)
        print("🎉 CACHE FIX COMPLETE!")
        print("=" * 80)
        print("✅ PostgreSQL connection: Working")
        print("✅ Schema initialization: Complete")
        print("✅ Cache operations: Working")
        print("✅ Wrapper class: Working")
        print(f"✅ Schema tables: {final_stats['schema_tables']}")
        print(f"✅ Cached tables: {final_stats['tables']}")
        print(f"✅ Cached relationships: {final_stats['relationships']}")
        
        print("\n💡 Next Steps:")
        print("   1. Test explain_business_logic MCP tool")
        print("   2. Should see cache_hits > 0 in stats")
        print("   3. Performance should be significantly faster")
        
        print("\n📋 Test Command:")
        print("   SQL: SELECT * FROM GTW_ODS.GATEWAY_TRANSACTIONS WHERE ROWNUM <= 10")
        print("   Expected: cache_hits=2, oracle_queries=0")
        
        logger.info("[fix_cache_complete.py] Finished all steps in main().")
        return True
        
    except Exception as e:
        logger.error(f"[fix_cache_complete.py] Error in main(): {e}", exc_info=True)
        return False
        
    finally:
        try:
            await conn.close()
            print("\n🔌 PostgreSQL connection closed")
        except:
            pass

if __name__ == "__main__":
    logger.info("[fix_cache_complete.py] __main__ entry point.")
    try:
        success = asyncio.run(main())
        logger.info(f"[fix_cache_complete.py] Script finished. Success: {success}")
        print(f"\n{'🎉 SUCCESS' if success else '❌ FAILED'}: Cache fix {'completed' if success else 'failed'}")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("[fix_cache_complete.py] Interrupted by user.")
        print("\n⚠️ Fix interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"[fix_cache_complete.py] Script crashed: {e}", exc_info=True)
        print(f"\n💥 Fix crashed: {e}")
        traceback.print_exc()
        sys.exit(1)