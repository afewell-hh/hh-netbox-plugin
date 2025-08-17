-- Migration 004: GitOps Integration Schema
-- Phase 4.1: Database Foundation for GitOps functionality
-- This migration implements the database schema for GitOps integration following HNP patterns

-- ================================================================================
-- Git Repositories Table - Centralized Git Repository Authentication
-- ================================================================================

CREATE TABLE git_repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    url TEXT NOT NULL,
    description TEXT,
    
    -- Authentication configuration
    authentication_type VARCHAR(50) NOT NULL DEFAULT 'personal_access_token',
    encrypted_credentials TEXT,
    credentials_key_version INTEGER DEFAULT 1,
    
    -- Connection status tracking
    connection_status VARCHAR(20) NOT NULL DEFAULT 'unknown',
    last_validated TIMESTAMP,
    validation_error TEXT,
    
    -- Repository metadata
    default_branch VARCHAR(100) DEFAULT 'main',
    last_commit_hash VARCHAR(64),
    last_fetched TIMESTAMP,
    
    -- Audit fields
    created TIMESTAMP DEFAULT NOW(),
    last_modified TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(100),
    modified_by VARCHAR(100),
    
    -- Constraints
    CONSTRAINT git_repositories_auth_type_check 
        CHECK (authentication_type IN ('personal_access_token', 'ssh_key', 'oauth_token', 'basic_auth')),
    CONSTRAINT git_repositories_connection_status_check
        CHECK (connection_status IN ('unknown', 'connected', 'failed', 'pending', 'expired')),
    CONSTRAINT git_repositories_name_length_check
        CHECK (char_length(name) > 0 AND char_length(name) <= 100),
    CONSTRAINT git_repositories_url_length_check
        CHECK (char_length(url) > 0)
);

-- Indexes for performance optimization
CREATE INDEX idx_git_repositories_connection_status ON git_repositories(connection_status);
CREATE INDEX idx_git_repositories_last_validated ON git_repositories(last_validated);
CREATE INDEX idx_git_repositories_created ON git_repositories(created);
CREATE INDEX idx_git_repositories_auth_type ON git_repositories(authentication_type);
CREATE INDEX idx_git_repositories_url_hash ON git_repositories USING hash(url);

-- Comments for documentation
COMMENT ON TABLE git_repositories IS 'Centralized git repository authentication and metadata storage for GitOps operations';
COMMENT ON COLUMN git_repositories.encrypted_credentials IS 'AES-256-GCM encrypted git credentials, never exposed in API responses';
COMMENT ON COLUMN git_repositories.credentials_key_version IS 'Version of encryption key used, supports key rotation';
COMMENT ON COLUMN git_repositories.connection_status IS 'Current connection status, updated by periodic validation';

-- ================================================================================
-- Enhanced Fabrics Table - GitOps Integration
-- ================================================================================

-- Add GitOps columns to existing fabrics table
ALTER TABLE fabrics 
    ADD COLUMN git_repository_id UUID REFERENCES git_repositories(id) ON DELETE SET NULL,
    ADD COLUMN gitops_branch VARCHAR(100) DEFAULT 'main',
    ADD COLUMN last_git_sync TIMESTAMP,
    ADD COLUMN last_git_commit_hash VARCHAR(64),
    ADD COLUMN git_sync_status VARCHAR(20) DEFAULT 'never_synced';

-- Add constraint for git sync status
ALTER TABLE fabrics ADD CONSTRAINT fabrics_git_sync_status_check
    CHECK (git_sync_status IN ('never_synced', 'in_sync', 'out_of_sync', 'syncing', 'error'));

-- Migrate existing git_repository data to new structure (if any exists)
-- This preserves any existing git repository URLs as repository names for backward compatibility
INSERT INTO git_repositories (name, url, authentication_type, connection_status, created, last_modified)
SELECT 
    DISTINCT 
    COALESCE(NULLIF(git_repository, ''), 'legacy-' || id) as name,
    COALESCE(NULLIF(git_repository, ''), 'https://github.com/example/repo') as url,
    'personal_access_token'::VARCHAR(50) as authentication_type,
    'unknown'::VARCHAR(20) as connection_status,
    NOW() as created,
    NOW() as last_modified
FROM fabrics 
WHERE git_repository IS NOT NULL AND git_repository != ''
ON CONFLICT (name) DO NOTHING;

-- Update fabrics to reference the new git_repositories
UPDATE fabrics 
SET git_repository_id = gr.id
FROM git_repositories gr
WHERE fabrics.git_repository = gr.name
AND fabrics.git_repository IS NOT NULL 
AND fabrics.git_repository != '';

-- Remove old git columns after migration
ALTER TABLE fabrics 
    DROP COLUMN IF EXISTS git_repository,
    DROP COLUMN IF EXISTS git_credentials;

-- Indexes for GitOps operations
CREATE INDEX idx_fabrics_git_repository_id ON fabrics(git_repository_id);
CREATE INDEX idx_fabrics_git_sync_status ON fabrics(git_sync_status);
CREATE INDEX idx_fabrics_last_git_sync ON fabrics(last_git_sync);
CREATE INDEX idx_fabrics_gitops_branch ON fabrics(gitops_branch);

-- Comments for documentation
COMMENT ON COLUMN fabrics.git_repository_id IS 'Foreign key reference to git_repositories table for GitOps authentication';
COMMENT ON COLUMN fabrics.git_sync_status IS 'GitOps synchronization status with git repository';
COMMENT ON COLUMN fabrics.last_git_sync IS 'Timestamp of last successful git synchronization';

-- ================================================================================
-- Enhanced CRD Resources Table - GitOps Tracking
-- ================================================================================

-- Add GitOps tracking columns to CRD resources
ALTER TABLE crd_resources
    ADD COLUMN git_file_path TEXT,
    ADD COLUMN git_commit_hash VARCHAR(64),
    ADD COLUMN last_synced_from VARCHAR(20) DEFAULT 'unknown',
    ADD COLUMN git_sync_timestamp TIMESTAMP;

-- Add constraint for sync source tracking
ALTER TABLE crd_resources ADD CONSTRAINT crd_resources_last_synced_from_check
    CHECK (last_synced_from IN ('git', 'kubernetes', 'manual', 'api', 'unknown'));

-- Indexes for GitOps tracking and performance
CREATE INDEX idx_crd_resources_git_file_path ON crd_resources(git_file_path);
CREATE INDEX idx_crd_resources_last_synced_from ON crd_resources(last_synced_from);
CREATE INDEX idx_crd_resources_git_commit_hash ON crd_resources(git_commit_hash);
CREATE INDEX idx_crd_resources_git_sync_timestamp ON crd_resources(git_sync_timestamp);

-- Composite index for fabric GitOps queries
CREATE INDEX idx_crd_resources_fabric_git_sync ON crd_resources(fabric_id, last_synced_from, git_sync_timestamp);

-- Comments for documentation
COMMENT ON COLUMN crd_resources.git_file_path IS 'Relative path to YAML file in git repository where this CRD originated';
COMMENT ON COLUMN crd_resources.git_commit_hash IS 'Git commit hash when this CRD was last synchronized from git';
COMMENT ON COLUMN crd_resources.last_synced_from IS 'Source of last synchronization: git, kubernetes, manual, api';

-- ================================================================================
-- GitOps Operations Audit Table - Operation Tracking
-- ================================================================================

CREATE TABLE gitops_operations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fabric_id UUID NOT NULL REFERENCES fabrics(id) ON DELETE CASCADE,
    git_repository_id UUID NOT NULL REFERENCES git_repositories(id) ON DELETE CASCADE,
    
    -- Operation details
    operation_type VARCHAR(50) NOT NULL, -- 'sync', 'test_connection', 'detect_drift'
    operation_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    
    -- Timing information
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_ms INTEGER,
    
    -- Operation context
    git_commit_hash VARCHAR(64),
    git_branch VARCHAR(100),
    gitops_directory TEXT,
    
    -- Results and metrics
    items_processed INTEGER DEFAULT 0,
    items_successful INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    
    -- Operation details (JSON)
    operation_details JSONB,
    error_details JSONB,
    
    -- Audit fields
    triggered_by VARCHAR(100),
    user_agent TEXT,
    
    CONSTRAINT gitops_operations_type_check
        CHECK (operation_type IN ('sync', 'test_connection', 'detect_drift', 'validate')),
    CONSTRAINT gitops_operations_status_check
        CHECK (operation_status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    CONSTRAINT gitops_operations_timing_check
        CHECK (completed_at IS NULL OR completed_at >= started_at),
    CONSTRAINT gitops_operations_metrics_check
        CHECK (items_processed >= 0 AND items_successful >= 0 AND items_failed >= 0)
);

-- Indexes for operation queries and monitoring
CREATE INDEX idx_gitops_operations_fabric_id ON gitops_operations(fabric_id);
CREATE INDEX idx_gitops_operations_git_repository_id ON gitops_operations(git_repository_id);
CREATE INDEX idx_gitops_operations_type_status ON gitops_operations(operation_type, operation_status);
CREATE INDEX idx_gitops_operations_started_at ON gitops_operations(started_at);
CREATE INDEX idx_gitops_operations_completed_at ON gitops_operations(completed_at);

-- Composite indexes for common queries
CREATE INDEX idx_gitops_operations_fabric_recent ON gitops_operations(fabric_id, started_at DESC);
CREATE INDEX idx_gitops_operations_status_timing ON gitops_operations(operation_status, started_at);

-- Comments for documentation
COMMENT ON TABLE gitops_operations IS 'Audit trail and monitoring for all GitOps operations';
COMMENT ON COLUMN gitops_operations.operation_details IS 'JSON details of operation results, varies by operation type';
COMMENT ON COLUMN gitops_operations.error_details IS 'JSON structure containing error information when operations fail';

-- ================================================================================
-- GitOps Drift Detection Table - Drift Tracking
-- ================================================================================

CREATE TABLE gitops_drift_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fabric_id UUID NOT NULL REFERENCES fabrics(id) ON DELETE CASCADE,
    git_repository_id UUID NOT NULL REFERENCES git_repositories(id) ON DELETE CASCADE,
    
    -- Report metadata
    report_timestamp TIMESTAMP DEFAULT NOW(),
    git_commit_hash VARCHAR(64) NOT NULL,
    
    -- Drift summary
    drift_detected BOOLEAN DEFAULT FALSE,
    drift_count INTEGER DEFAULT 0,
    overall_severity VARCHAR(20) DEFAULT 'info',
    
    -- Analysis details
    resources_in_git INTEGER DEFAULT 0,
    resources_in_database INTEGER DEFAULT 0,
    resources_missing INTEGER DEFAULT 0,
    resources_extra INTEGER DEFAULT 0,
    resources_modified INTEGER DEFAULT 0,
    
    -- Drift details (JSON array of drift items)
    drift_items JSONB,
    
    -- Analysis context
    gitops_directory TEXT,
    analysis_duration_ms INTEGER,
    
    -- Archive and retention
    archived BOOLEAN DEFAULT FALSE,
    archived_at TIMESTAMP,
    
    CONSTRAINT gitops_drift_severity_check
        CHECK (overall_severity IN ('info', 'warning', 'critical')),
    CONSTRAINT gitops_drift_counts_check
        CHECK (drift_count >= 0 AND resources_in_git >= 0 AND resources_in_database >= 0)
);

-- Indexes for drift report queries
CREATE INDEX idx_gitops_drift_reports_fabric_id ON gitops_drift_reports(fabric_id);
CREATE INDEX idx_gitops_drift_reports_timestamp ON gitops_drift_reports(report_timestamp);
CREATE INDEX idx_gitops_drift_reports_severity ON gitops_drift_reports(overall_severity);
CREATE INDEX idx_gitops_drift_reports_drift_detected ON gitops_drift_reports(drift_detected);

-- Composite index for recent drift reports by fabric
CREATE INDEX idx_gitops_drift_reports_fabric_recent ON gitops_drift_reports(fabric_id, report_timestamp DESC) 
    WHERE archived = FALSE;

-- Comments for documentation
COMMENT ON TABLE gitops_drift_reports IS 'Historical drift detection reports for GitOps monitoring';
COMMENT ON COLUMN gitops_drift_reports.drift_items IS 'JSON array of specific drift items with details and severity';

-- ================================================================================
-- Update trigger functions for audit fields
-- ================================================================================

-- Function to update last_modified timestamp
CREATE OR REPLACE FUNCTION update_last_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_modified = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add triggers for automatic timestamp updates
CREATE TRIGGER update_git_repositories_last_modified 
    BEFORE UPDATE ON git_repositories 
    FOR EACH ROW EXECUTE FUNCTION update_last_modified_column();

-- ================================================================================
-- Initial data and configuration
-- ================================================================================

-- Insert default configuration values (can be customized per deployment)
INSERT INTO git_repositories (id, name, url, description, authentication_type, connection_status)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'example-gitops-repo',
    'https://github.com/example/gitops-repo',
    'Example GitOps repository for initial configuration',
    'personal_access_token',
    'unknown'
) ON CONFLICT (id) DO NOTHING;

-- ================================================================================
-- Grants and permissions
-- ================================================================================

-- Grant appropriate permissions to cnoc application user
-- (Assumes cnoc user exists - adjust as needed for your deployment)
GRANT SELECT, INSERT, UPDATE, DELETE ON git_repositories TO cnoc;
GRANT SELECT, INSERT, UPDATE, DELETE ON gitops_operations TO cnoc;
GRANT SELECT, INSERT, UPDATE, DELETE ON gitops_drift_reports TO cnoc;

-- Grant sequence permissions if using serial columns
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO cnoc;

-- ================================================================================
-- Migration validation and verification
-- ================================================================================

-- Verify the migration completed successfully
DO $$
DECLARE
    git_repos_count INTEGER;
    fabric_columns_exist INTEGER;
    crd_columns_exist INTEGER;
BEGIN
    -- Check git_repositories table exists and has expected structure
    SELECT COUNT(*) INTO git_repos_count 
    FROM information_schema.tables 
    WHERE table_name = 'git_repositories' AND table_schema = 'public';
    
    IF git_repos_count != 1 THEN
        RAISE EXCEPTION 'GitOps migration failed: git_repositories table not created properly';
    END IF;
    
    -- Check fabrics table has new GitOps columns
    SELECT COUNT(*) INTO fabric_columns_exist
    FROM information_schema.columns
    WHERE table_name = 'fabrics' 
    AND column_name IN ('git_repository_id', 'git_sync_status', 'last_git_sync');
    
    IF fabric_columns_exist != 3 THEN
        RAISE EXCEPTION 'GitOps migration failed: fabrics table columns not added properly';
    END IF;
    
    -- Check crd_resources table has new GitOps columns
    SELECT COUNT(*) INTO crd_columns_exist
    FROM information_schema.columns
    WHERE table_name = 'crd_resources' 
    AND column_name IN ('git_file_path', 'git_commit_hash', 'last_synced_from');
    
    IF crd_columns_exist != 3 THEN
        RAISE EXCEPTION 'GitOps migration failed: crd_resources table columns not added properly';
    END IF;
    
    RAISE NOTICE 'GitOps migration 004 completed successfully';
    RAISE NOTICE 'Git repositories table: created with % expected structure', git_repos_count;
    RAISE NOTICE 'Fabrics table: enhanced with % GitOps columns', fabric_columns_exist;
    RAISE NOTICE 'CRD resources table: enhanced with % GitOps tracking columns', crd_columns_exist;
END $$;