-- ============================================================================
-- Feedback System Tables
-- ============================================================================
-- Purpose: Store rate limiting, submissions, and feedback metadata
-- Created: 2026-01-19
-- Schema: mcp_performance

-- ============================================================================
-- Table: feedback_submissions
-- Purpose: Track all feedback submissions for rate limiting and analytics
-- ============================================================================
CREATE TABLE IF NOT EXISTS mcp_performance.feedback_submissions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    client_id VARCHAR(64) NOT NULL,
    submission_type VARCHAR(20) NOT NULL CHECK (submission_type IN ('bug', 'feature', 'improvement')),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    content_hash VARCHAR(32) NOT NULL,  -- MD5 hash for duplicate detection
    quality_score NUMERIC(3,1),  -- 0.0 to 10.0
    github_issue_number INTEGER,
    github_issue_url TEXT,
    status VARCHAR(20) DEFAULT 'submitted' CHECK (status IN ('submitted', 'created', 'failed')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Indexes for fast lookups
    INDEX idx_feedback_session_created (session_id, created_at),
    INDEX idx_feedback_client_created (client_id, created_at),
    INDEX idx_feedback_content_hash (content_hash, created_at),
    INDEX idx_feedback_created_at (created_at)
);

COMMENT ON TABLE mcp_performance.feedback_submissions IS 'Tracks all feedback submissions for rate limiting and analytics';
COMMENT ON COLUMN mcp_performance.feedback_submissions.session_id IS 'Unique session identifier (individual user)';
COMMENT ON COLUMN mcp_performance.feedback_submissions.client_id IS 'Client/team identifier (from API key)';
COMMENT ON COLUMN mcp_performance.feedback_submissions.content_hash IS 'MD5 hash of title+description for duplicate detection';
COMMENT ON COLUMN mcp_performance.feedback_submissions.quality_score IS 'Automated quality analysis score (0-10)';

-- ============================================================================
-- Table: feedback_blocked_sessions
-- Purpose: Track blocked sessions/clients with auto-expiry
-- ============================================================================
CREATE TABLE IF NOT EXISTS mcp_performance.feedback_blocked_sessions (
    id SERIAL PRIMARY KEY,
    identifier VARCHAR(64) NOT NULL UNIQUE,  -- session_id or client_id
    identifier_type VARCHAR(10) NOT NULL CHECK (identifier_type IN ('session', 'client')),
    blocked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    unblock_at TIMESTAMP WITH TIME ZONE NOT NULL,
    reason TEXT,

    INDEX idx_blocked_identifier (identifier, unblock_at),
    INDEX idx_blocked_unblock_at (unblock_at)
);

COMMENT ON TABLE mcp_performance.feedback_blocked_sessions IS 'Tracks blocked sessions/clients with automatic expiry';
COMMENT ON COLUMN mcp_performance.feedback_blocked_sessions.identifier IS 'Session ID or Client ID that is blocked';
COMMENT ON COLUMN mcp_performance.feedback_blocked_sessions.unblock_at IS 'When the block expires (auto-unblock)';

-- ============================================================================
-- Function: Clean up old feedback data
-- Purpose: Remove submissions older than retention period
-- ============================================================================
CREATE OR REPLACE FUNCTION mcp_performance.cleanup_old_feedback()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Delete submissions older than 30 days
    DELETE FROM mcp_performance.feedback_submissions
    WHERE created_at < NOW() - INTERVAL '30 days';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    -- Delete expired blocks
    DELETE FROM mcp_performance.feedback_blocked_sessions
    WHERE unblock_at < NOW();

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION mcp_performance.cleanup_old_feedback() IS 'Removes feedback submissions older than 30 days and expired blocks';

-- ============================================================================
-- View: feedback_stats
-- Purpose: Quick stats for monitoring
-- ============================================================================
CREATE OR REPLACE VIEW mcp_performance.feedback_stats AS
SELECT
    COUNT(*) as total_submissions,
    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as last_24h,
    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as last_hour,
    COUNT(DISTINCT session_id) as unique_sessions,
    COUNT(DISTINCT client_id) as unique_clients,
    AVG(quality_score) as avg_quality_score,
    COUNT(*) FILTER (WHERE submission_type = 'bug') as bug_count,
    COUNT(*) FILTER (WHERE submission_type = 'feature') as feature_count,
    COUNT(*) FILTER (WHERE submission_type = 'improvement') as improvement_count,
    COUNT(*) FILTER (WHERE status = 'created') as successfully_created,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_submissions
FROM mcp_performance.feedback_submissions;

COMMENT ON VIEW mcp_performance.feedback_stats IS 'Real-time feedback system statistics';

-- ============================================================================
-- Initial Data / Configuration
-- ============================================================================

-- None needed - tables start empty

-- ============================================================================
-- Permissions (adjust as needed)
-- ============================================================================

-- Grant access to application user
GRANT SELECT, INSERT, UPDATE, DELETE ON mcp_performance.feedback_submissions TO omni;
GRANT SELECT, INSERT, UPDATE, DELETE ON mcp_performance.feedback_blocked_sessions TO omni;
GRANT USAGE, SELECT ON SEQUENCE mcp_performance.feedback_submissions_id_seq TO omni;
GRANT USAGE, SELECT ON SEQUENCE mcp_performance.feedback_blocked_sessions_id_seq TO omni;
GRANT SELECT ON mcp_performance.feedback_stats TO omni;

-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Check tables exist
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'mcp_performance' AND table_name LIKE 'feedback%';

-- Check view works
-- SELECT * FROM mcp_performance.feedback_stats;

-- Test cleanup function
-- SELECT mcp_performance.cleanup_old_feedback();
