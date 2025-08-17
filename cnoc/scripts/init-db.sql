-- CNOC Database Initialization Script
-- MDD-aligned schema for Configuration Management

-- Create configurations table
CREATE TABLE IF NOT EXISTS configurations (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    mode VARCHAR(20) NOT NULL CHECK (mode IN ('development', 'staging', 'production')),
    version VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'deprecated', 'archived')),
    labels JSONB,
    annotations JSONB,
    enterprise_config JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(name, version)
);

-- Create components table
CREATE TABLE IF NOT EXISTS components (
    id UUID PRIMARY KEY,
    configuration_id UUID NOT NULL REFERENCES configurations(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    configuration JSONB,
    resources JSONB NOT NULL,
    dependencies TEXT[],
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create events table for event sourcing
CREATE TABLE IF NOT EXISTS domain_events (
    id UUID PRIMARY KEY,
    aggregate_id UUID NOT NULL,
    aggregate_type VARCHAR(100) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB NOT NULL,
    event_version INTEGER NOT NULL,
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    correlation_id UUID,
    causation_id UUID,
    metadata JSONB
);

-- Create validation_results table
CREATE TABLE IF NOT EXISTS validation_results (
    id UUID PRIMARY KEY,
    configuration_id UUID NOT NULL REFERENCES configurations(id) ON DELETE CASCADE,
    validation_type VARCHAR(50) NOT NULL,
    is_valid BOOLEAN NOT NULL,
    errors JSONB,
    warnings JSONB,
    validated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    validator_version VARCHAR(50)
);

-- Create deployment_history table
CREATE TABLE IF NOT EXISTS deployment_history (
    id UUID PRIMARY KEY,
    configuration_id UUID NOT NULL REFERENCES configurations(id) ON DELETE CASCADE,
    deployment_id VARCHAR(100) NOT NULL,
    environment VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    strategy VARCHAR(50),
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    details JSONB,
    error_message TEXT
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_configurations_name ON configurations(name);
CREATE INDEX IF NOT EXISTS idx_configurations_mode ON configurations(mode);
CREATE INDEX IF NOT EXISTS idx_configurations_status ON configurations(status);
CREATE INDEX IF NOT EXISTS idx_configurations_created_at ON configurations(created_at);

CREATE INDEX IF NOT EXISTS idx_components_configuration_id ON components(configuration_id);
CREATE INDEX IF NOT EXISTS idx_components_name ON components(name);
CREATE INDEX IF NOT EXISTS idx_components_enabled ON components(enabled);

CREATE INDEX IF NOT EXISTS idx_domain_events_aggregate_id ON domain_events(aggregate_id);
CREATE INDEX IF NOT EXISTS idx_domain_events_aggregate_type ON domain_events(aggregate_type);
CREATE INDEX IF NOT EXISTS idx_domain_events_event_type ON domain_events(event_type);
CREATE INDEX IF NOT EXISTS idx_domain_events_occurred_at ON domain_events(occurred_at);

CREATE INDEX IF NOT EXISTS idx_validation_results_configuration_id ON validation_results(configuration_id);
CREATE INDEX IF NOT EXISTS idx_validation_results_validated_at ON validation_results(validated_at);

CREATE INDEX IF NOT EXISTS idx_deployment_history_configuration_id ON deployment_history(configuration_id);
CREATE INDEX IF NOT EXISTS idx_deployment_history_environment ON deployment_history(environment);
CREATE INDEX IF NOT EXISTS idx_deployment_history_started_at ON deployment_history(started_at);

-- Insert sample data for testing
INSERT INTO configurations (
    id,
    name,
    description,
    mode,
    version,
    status,
    labels,
    annotations
) VALUES (
    '550e8400-e29b-41d4-a716-446655440000',
    'sample-config',
    'Sample configuration for MDD validation',
    'development',
    '1.0.0',
    'active',
    '{"environment": "development", "team": "platform"}',
    '{"created_by": "system", "purpose": "mdd-validation"}'
) ON CONFLICT (name, version) DO NOTHING;

-- Insert sample component
INSERT INTO components (
    id,
    configuration_id,
    name,
    version,
    enabled,
    configuration,
    resources,
    dependencies
) VALUES (
    '550e8400-e29b-41d4-a716-446655440001',
    '550e8400-e29b-41d4-a716-446655440000',
    'sample-component',
    '1.0.0',
    true,
    '{"port": 8080, "env": "development"}',
    '{"cpu": "100m", "memory": "128Mi", "replicas": 1, "namespace": "default"}',
    ARRAY[]::TEXT[]
);

-- Functions for updated_at triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_configurations_updated_at BEFORE UPDATE ON configurations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_components_updated_at BEFORE UPDATE ON components
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Print success message
DO $$
BEGIN
    RAISE NOTICE '✅ CNOC database initialized successfully with MDD-aligned schema';
    RAISE NOTICE '📊 Sample configuration created: sample-config v1.0.0';
    RAISE NOTICE '🔧 Sample component created: sample-component v1.0.0';
END $$;