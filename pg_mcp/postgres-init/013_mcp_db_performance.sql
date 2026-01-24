-- ============================================================
-- MCP DB Performance - User and Schema Initialization
-- ============================================================
-- Creates dedicated user and initializes knowledge/performance schema
-- User: mcp_db_performance / Password: mcp_db_performance
-- Schema: mcp_performance
-- Database: omni
-- ============================================================

-- Step 1: Create dedicated user for mcp_db_performance
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mcp_db_performance') THEN
        CREATE USER mcp_db_performance WITH PASSWORD 'mcp_db_performance';
        RAISE NOTICE 'Created user: mcp_db_performance';
    ELSE
        RAISE NOTICE 'User mcp_db_performance already exists';
    END IF;
END $$;

-- Step 2: Grant database connection privileges
GRANT CONNECT ON DATABASE omni TO mcp_db_performance;

-- Step 3: Clean slate - drop schema if exists and recreate
DROP SCHEMA IF EXISTS mcp_performance CASCADE;
CREATE SCHEMA mcp_performance AUTHORIZATION mcp_db_performance;

-- Step 4: Grant schema usage to the user
GRANT ALL ON SCHEMA mcp_performance TO mcp_db_performance;

-- Set search path for this session
SET search_path TO mcp_performance, public;

-- ============================================================
-- SECTION 1: Knowledge Base Tables (Business Context)
-- ============================================================

-- Table Knowledge Cache
CREATE TABLE mcp_performance.table_knowledge (
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

    PRIMARY KEY (db_name, owner, table_name)
);

-- Relationship Knowledge Cache
CREATE TABLE mcp_performance.relationship_knowledge (
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

    PRIMARY KEY (db_name, from_owner, from_table, to_owner, to_table, from_columns)
);

-- Query Explanation Cache
CREATE TABLE mcp_performance.query_explanations (
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

    UNIQUE (sql_fingerprint, db_name)
);

-- Domain Glossary
CREATE TABLE mcp_performance.domain_glossary (
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

    PRIMARY KEY (term, domain)
);

-- Discovery Operation Log
CREATE TABLE mcp_performance.discovery_log (
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

-- ============================================================
-- SECTION 2: Query Performance History Tables
-- ============================================================

-- Query Execution History
CREATE TABLE mcp_performance.query_execution_history (
    id SERIAL PRIMARY KEY,

    -- Query Identification
    fingerprint VARCHAR(64) NOT NULL,
    db_name VARCHAR(100) NOT NULL,

    -- MCP Instance Tracking
    mcp_instance_id VARCHAR(100) NOT NULL DEFAULT 'performance_mcp',

    -- Execution Metadata
    executed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    plan_hash VARCHAR(50),
    optimizer_cost INTEGER DEFAULT 0,

    -- Table Statistics at execution time
    table_stats JSONB DEFAULT '{}',
    plan_operations JSONB DEFAULT '[]',

    -- Performance Tracking
    execution_time_ms INTEGER,
    buffer_gets BIGINT,
    physical_reads BIGINT,

    -- Query Normalization
    sql_text_sample TEXT,
    normalized_pattern TEXT,

    -- Analysis Metadata
    was_regression BOOLEAN DEFAULT FALSE,
    cost_change_pct FLOAT,
    plan_changed BOOLEAN DEFAULT FALSE,

    CONSTRAINT uq_execution_tracking UNIQUE (fingerprint, db_name, mcp_instance_id, executed_at)
);

-- Query Performance Summary
CREATE TABLE mcp_performance.query_performance_summary (
    id SERIAL PRIMARY KEY,

    -- Query identification
    fingerprint VARCHAR(64) NOT NULL,
    db_name VARCHAR(100) NOT NULL,
    mcp_instance_id VARCHAR(100) NOT NULL,

    -- Performance aggregates
    total_executions INTEGER DEFAULT 1,
    avg_cost FLOAT,
    min_cost INTEGER,
    max_cost INTEGER,

    -- Latest execution
    last_executed TIMESTAMP WITH TIME ZONE NOT NULL,
    latest_plan_hash VARCHAR(50),

    -- Trend analysis
    cost_trend VARCHAR(20),
    plan_stability_pct FLOAT DEFAULT 100.0,

    -- First seen
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Update tracking
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT uq_query_summary UNIQUE (fingerprint, db_name, mcp_instance_id)
);

-- Migration Log
CREATE TABLE mcp_performance.migration_log (
    id SERIAL PRIMARY KEY,

    -- Migration identification
    migration_type VARCHAR(50) NOT NULL,
    source_file VARCHAR(500),
    mcp_instance_id VARCHAR(100) NOT NULL,

    -- Migration results
    records_migrated INTEGER DEFAULT 0,
    records_skipped INTEGER DEFAULT 0,
    migration_errors INTEGER DEFAULT 0,

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Details
    error_message TEXT,
    migration_notes TEXT,

    CONSTRAINT uq_migration_log UNIQUE (migration_type, source_file, mcp_instance_id)
);

-- ============================================================
-- SECTION 3: Indexes for Performance
-- ============================================================

-- Knowledge Base Indexes
CREATE INDEX idx_table_knowledge_db_refresh ON mcp_performance.table_knowledge(db_name, last_refreshed);
CREATE INDEX idx_table_knowledge_domain ON mcp_performance.table_knowledge(inferred_domain) WHERE inferred_domain IS NOT NULL;
CREATE INDEX idx_relationship_knowledge_from ON mcp_performance.relationship_knowledge(db_name, from_owner, from_table);
CREATE INDEX idx_relationship_knowledge_to ON mcp_performance.relationship_knowledge(db_name, to_owner, to_table);
CREATE INDEX idx_query_explanations_db ON mcp_performance.query_explanations(db_name, last_accessed DESC);
CREATE INDEX idx_domain_glossary_domain ON mcp_performance.domain_glossary(domain, occurrence_count DESC);
CREATE INDEX idx_discovery_log_db_started ON mcp_performance.discovery_log(db_name, started_at DESC);

-- Query History Indexes
CREATE INDEX idx_query_history_fingerprint ON mcp_performance.query_execution_history(fingerprint);
CREATE INDEX idx_query_history_db_instance ON mcp_performance.query_execution_history(db_name, mcp_instance_id);
CREATE INDEX idx_query_history_executed ON mcp_performance.query_execution_history(executed_at DESC);
CREATE INDEX idx_query_history_plan_hash ON mcp_performance.query_execution_history(plan_hash);
CREATE INDEX idx_query_history_regression ON mcp_performance.query_execution_history(was_regression) WHERE was_regression = TRUE;

-- Query Summary Indexes
CREATE INDEX idx_query_summary_db_instance ON mcp_performance.query_performance_summary(db_name, mcp_instance_id);
CREATE INDEX idx_query_summary_last_executed ON mcp_performance.query_performance_summary(last_executed DESC);
CREATE INDEX idx_query_summary_trend ON mcp_performance.query_performance_summary(cost_trend);

-- Migration Log Indexes
CREATE INDEX idx_migration_log_status ON mcp_performance.migration_log(status);
CREATE INDEX idx_migration_log_started ON mcp_performance.migration_log(started_at DESC);

-- ============================================================
-- SECTION 4: Triggers and Functions
-- ============================================================

-- Function: Update query performance summary on new execution
CREATE OR REPLACE FUNCTION mcp_performance.update_query_summary()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO mcp_performance.query_performance_summary (
        fingerprint, db_name, mcp_instance_id, total_executions,
        avg_cost, min_cost, max_cost, last_executed, latest_plan_hash, first_seen
    )
    VALUES (
        NEW.fingerprint,
        NEW.db_name,
        NEW.mcp_instance_id,
        1,
        NEW.optimizer_cost::FLOAT,
        NEW.optimizer_cost,
        NEW.optimizer_cost,
        NEW.executed_at,
        NEW.plan_hash,
        NEW.executed_at
    )
    ON CONFLICT (fingerprint, db_name, mcp_instance_id) DO UPDATE SET
        total_executions = query_performance_summary.total_executions + 1,
        avg_cost = (query_performance_summary.avg_cost * query_performance_summary.total_executions + NEW.optimizer_cost) / (query_performance_summary.total_executions + 1),
        min_cost = LEAST(query_performance_summary.min_cost, NEW.optimizer_cost),
        max_cost = GREATEST(query_performance_summary.max_cost, NEW.optimizer_cost),
        last_executed = NEW.executed_at,
        latest_plan_hash = NEW.plan_hash,
        last_updated = NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: Automatically update summary on new executions
CREATE TRIGGER trg_update_query_summary
    AFTER INSERT ON mcp_performance.query_execution_history
    FOR EACH ROW EXECUTE FUNCTION mcp_performance.update_query_summary();

-- ============================================================
-- SECTION 5: Grant Permissions to mcp_db_performance User
-- ============================================================

-- Grant all privileges on all tables in the schema
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA mcp_performance TO mcp_db_performance;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA mcp_performance TO mcp_db_performance;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA mcp_performance TO mcp_db_performance;

-- Grant default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA mcp_performance GRANT ALL ON TABLES TO mcp_db_performance;
ALTER DEFAULT PRIVILEGES IN SCHEMA mcp_performance GRANT ALL ON SEQUENCES TO mcp_db_performance;
ALTER DEFAULT PRIVILEGES IN SCHEMA mcp_performance GRANT ALL ON FUNCTIONS TO mcp_db_performance;

-- ============================================================
-- SECTION 6: Comments and Documentation
-- ============================================================

COMMENT ON SCHEMA mcp_performance IS 'MCP Performance Server - Unified PostgreSQL storage for business knowledge and query performance tracking';
COMMENT ON TABLE mcp_performance.table_knowledge IS 'Business context cache for database tables with inferred meaning and purpose';
COMMENT ON TABLE mcp_performance.relationship_knowledge IS 'Foreign key and logical relationships between tables';
COMMENT ON TABLE mcp_performance.query_explanations IS 'Cached business explanations for SQL queries';
COMMENT ON TABLE mcp_performance.domain_glossary IS 'Business term definitions and domain vocabulary';
COMMENT ON TABLE mcp_performance.discovery_log IS 'Audit log of discovery operations and performance metrics';
COMMENT ON TABLE mcp_performance.query_execution_history IS 'Individual query execution tracking for performance analysis';
COMMENT ON TABLE mcp_performance.query_performance_summary IS 'Aggregated query performance metrics for quick analysis';
COMMENT ON TABLE mcp_performance.migration_log IS 'Data migration operations audit trail';
COMMENT ON FUNCTION mcp_performance.update_query_summary IS 'Automatically maintains query performance summaries when new executions are recorded';

-- ============================================================
-- SECTION 7: Initial Setup Complete
-- ============================================================

-- Log the schema initialization
INSERT INTO mcp_performance.discovery_log (
    operation_type, db_name, tables_discovered, success, duration_ms
) VALUES (
    'schema_initialization', 'system', 9, TRUE, 0
);

-- Success message
DO $$
BEGIN
    RAISE NOTICE '🎉 MCP DB Performance - Schema Initialization Complete!';
    RAISE NOTICE '   User: mcp_db_performance (created)';
    RAISE NOTICE '   Schema: mcp_performance (owned by mcp_db_performance)';
    RAISE NOTICE '   Database: omni';
    RAISE NOTICE '   Tables Created: 9 (5 knowledge + 4 history)';
    RAISE NOTICE '   Indexes Created: 15';
    RAISE NOTICE '   Triggers Created: 1';
    RAISE NOTICE '   Permissions: GRANTED';
    RAISE NOTICE '   Status: Ready for use';
END $$;
