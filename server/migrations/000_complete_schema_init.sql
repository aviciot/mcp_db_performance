-- ============================================================
-- MCP Performance - Complete Schema Initialization
-- ============================================================
-- This file provides complete clean initialization for the MCP Performance system
-- 
-- Usage: Drop and recreate entire schema with all tables, indexes, triggers
-- Environment: PostgreSQL 14+ 
-- Schema: mcp_performance (configurable)
-- ============================================================

-- Clean slate - drop schema completely if exists
DROP SCHEMA IF EXISTS mcp_performance CASCADE;

-- Create fresh schema
CREATE SCHEMA mcp_performance;

-- Set search path for this session
SET search_path TO mcp_performance, public;

-- ============================================================
-- SECTION 1: Knowledge Base Tables (Business Context)
-- ============================================================

-- Table Knowledge Cache
-- Stores inferred business context for database tables
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
    inferred_entity_type VARCHAR(100),          -- 'transaction', 'lookup', 'audit', 'staging'
    inferred_domain VARCHAR(100),               -- 'finance', 'customer', 'inventory', 'hr'
    business_description TEXT,                  -- What this table represents
    business_purpose TEXT,                      -- Why this table exists
    confidence_score FLOAT DEFAULT 0.5,        -- How confident we are (0.0-1.0)
    
    -- Cache Management
    last_refreshed TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    refresh_count INTEGER DEFAULT 1,
    
    -- Constraints
    PRIMARY KEY (db_name, owner, table_name)
);

-- Relationship Knowledge Cache  
-- Stores foreign key relationships and business relationships
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
    relationship_type VARCHAR(20) DEFAULT 'FK',    -- 'FK', 'LOGICAL', 'HIERARCHY'
    constraint_name VARCHAR(128),
    cardinality VARCHAR(20),                       -- '1:1', '1:M', 'M:M'
    is_lookup BOOLEAN DEFAULT FALSE,               -- Is target table a lookup/dimension?
    
    -- Business Intelligence
    business_meaning TEXT,                         -- What this relationship represents
    relationship_role VARCHAR(100),               -- 'belongs_to', 'contains', 'references'
    
    -- Cache Management
    last_refreshed TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints  
    PRIMARY KEY (db_name, from_owner, from_table, to_owner, to_table, from_columns)
);

-- Query Explanation Cache
-- Stores business explanations for SQL queries
CREATE TABLE mcp_performance.query_explanations (
    -- Query Identification
    sql_fingerprint VARCHAR(64) PRIMARY KEY,       -- SHA256 hash of normalized SQL
    db_name VARCHAR(100) NOT NULL,
    sql_text TEXT NOT NULL,                        -- Original query
    sql_normalized TEXT NOT NULL,                  -- Normalized for matching
    
    -- Analysis Results
    tables_involved JSONB DEFAULT '[]',            -- [{"owner": "HR", "table": "EMPLOYEES", "role": "primary"}]
    business_explanation TEXT NOT NULL,            -- Human-readable explanation
    query_purpose VARCHAR(200),                    -- 'reporting', 'lookup', 'transaction'
    data_flow_description TEXT,                    -- How data flows through the query
    domain_tags TEXT[],                           -- ['hr', 'payroll', 'compliance']
    
    -- Cache Statistics
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_accessed TIMESTAMP WITH TIME ZONE DEFAULT NOW(), 
    hit_count INTEGER DEFAULT 1,
    
    -- Constraints
    UNIQUE (sql_fingerprint, db_name)
);

-- Domain Glossary
-- Business term definitions and examples
CREATE TABLE mcp_performance.domain_glossary (
    -- Term Definition
    term VARCHAR(200) NOT NULL,
    domain VARCHAR(100) NOT NULL,                 -- 'finance', 'hr', 'sales'
    definition TEXT NOT NULL,
    
    -- Examples and Usage
    examples TEXT[],                              -- Example values
    related_terms TEXT[],                         -- Synonyms, related concepts
    example_tables TEXT[],                        -- Tables that use this term
    example_columns TEXT[],                       -- Column names that use this term
    
    -- Usage Tracking
    occurrence_count INTEGER DEFAULT 1,
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    PRIMARY KEY (term, domain)
);

-- Discovery Operation Log
-- Tracks discovery operations and performance
CREATE TABLE mcp_performance.discovery_log (
    id SERIAL PRIMARY KEY,
    
    -- Operation Details
    operation_type VARCHAR(100) NOT NULL,         -- 'table_discovery', 'relationship_discovery'
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
-- Tracks individual query executions for performance analysis
CREATE TABLE mcp_performance.query_execution_history (
    id SERIAL PRIMARY KEY,
    
    -- Query Identification (from SQLite migration)
    fingerprint VARCHAR(64) NOT NULL,            -- MD5 hash of normalized SQL
    db_name VARCHAR(100) NOT NULL,               -- Database preset name
    
    -- MCP Instance Tracking (NEW - for multi-instance support)
    mcp_instance_id VARCHAR(100) NOT NULL DEFAULT 'performance_mcp',
    
    -- Execution Metadata (from SQLite)
    executed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    plan_hash VARCHAR(50),                       -- Oracle plan_hash_value or MySQL equivalent
    optimizer_cost INTEGER DEFAULT 0,           -- Query cost estimate
    
    -- Table Statistics at execution time (from SQLite)
    table_stats JSONB DEFAULT '{}',              -- {table_name: num_rows, ...}
    plan_operations JSONB DEFAULT '[]',          -- ["INDEX RANGE SCAN", "HASH JOIN", ...]
    
    -- Performance Tracking (NEW - enhanced from SQLite)
    execution_time_ms INTEGER,                   -- Actual execution time (if available)
    buffer_gets BIGINT,                         -- Oracle buffer gets / MySQL logical reads
    physical_reads BIGINT,                      -- I/O operations
    
    -- Query Normalization (from SQLite history_tracker.py logic)
    sql_text_sample TEXT,                       -- Original SQL snippet (first 500 chars)
    normalized_pattern TEXT,                    -- Normalized version for grouping
    
    -- Analysis Metadata (NEW)
    was_regression BOOLEAN DEFAULT FALSE,        -- Performance regression detected
    cost_change_pct FLOAT,                      -- Cost change vs previous execution
    plan_changed BOOLEAN DEFAULT FALSE,         -- Execution plan changed vs previous
    
    -- Indexing for performance
    CONSTRAINT uq_execution_tracking UNIQUE (fingerprint, db_name, mcp_instance_id, executed_at)
);

-- Query Performance Summary
-- Aggregated view of query performance for faster analysis
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
    cost_trend VARCHAR(20),                      -- 'stable', 'improving', 'degrading'
    plan_stability_pct FLOAT DEFAULT 100.0,     -- % of executions with same plan
    
    -- First seen
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Update tracking
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uq_query_summary UNIQUE (fingerprint, db_name, mcp_instance_id)
);

-- Migration Log
-- Tracks data migration operations from SQLite and other sources
CREATE TABLE mcp_performance.migration_log (
    id SERIAL PRIMARY KEY,
    
    -- Migration identification
    migration_type VARCHAR(50) NOT NULL,         -- 'sqlite_to_postgres', 'schema_upgrade'
    source_file VARCHAR(500),                    -- Path to source SQLite file
    mcp_instance_id VARCHAR(100) NOT NULL,
    
    -- Migration results
    records_migrated INTEGER DEFAULT 0,
    records_skipped INTEGER DEFAULT 0,
    migration_errors INTEGER DEFAULT 0,
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Details
    error_message TEXT,
    migration_notes TEXT,
    
    -- Unique constraint
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
RETURNS TRIGGER AS '
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
' LANGUAGE plpgsql;

-- Trigger: Automatically update summary on new executions
CREATE TRIGGER trg_update_query_summary
    AFTER INSERT ON mcp_performance.query_execution_history
    FOR EACH ROW EXECUTE FUNCTION mcp_performance.update_query_summary();

-- ============================================================
-- SECTION 5: Comments and Documentation
-- ============================================================

COMMENT ON SCHEMA mcp_performance IS 'MCP Performance Server - Unified PostgreSQL storage for business knowledge and query performance tracking';

-- Knowledge Base Comments
COMMENT ON TABLE mcp_performance.table_knowledge IS 'Business context cache for database tables with inferred meaning and purpose';
COMMENT ON TABLE mcp_performance.relationship_knowledge IS 'Foreign key and logical relationships between tables';
COMMENT ON TABLE mcp_performance.query_explanations IS 'Cached business explanations for SQL queries';
COMMENT ON TABLE mcp_performance.domain_glossary IS 'Business term definitions and domain vocabulary';
COMMENT ON TABLE mcp_performance.discovery_log IS 'Audit log of discovery operations and performance metrics';

-- Query History Comments  
COMMENT ON TABLE mcp_performance.query_execution_history IS 'Individual query execution tracking for performance analysis (migrated from SQLite)';
COMMENT ON TABLE mcp_performance.query_performance_summary IS 'Aggregated query performance metrics for quick analysis';
COMMENT ON TABLE mcp_performance.migration_log IS 'Data migration operations audit trail';

-- Function Comments
COMMENT ON FUNCTION mcp_performance.update_query_summary IS 'Automatically maintains query performance summaries when new executions are recorded';

-- ============================================================
-- SECTION 6: Initial Setup Complete
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
    RAISE NOTICE '🎉 MCP Performance Schema Initialization Complete!';
    RAISE NOTICE '   Schema: mcp_performance';
    RAISE NOTICE '   Tables Created: 9 (5 knowledge + 4 history)';
    RAISE NOTICE '   Indexes Created: 15';
    RAISE NOTICE '   Triggers Created: 1';
    RAISE NOTICE '   Status: Ready for production deployment';
END $$;