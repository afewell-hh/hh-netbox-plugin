package postgresql

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/lib/pq"
	
	"github.com/hedgehog/cnoc/internal/domain/configuration"
	"github.com/hedgehog/cnoc/internal/domain/configuration/repositories"
	"github.com/hedgehog/cnoc/internal/domain/events"
)

// PostgreSQLConfigurationRepository implements the configuration repository
// following hexagonal architecture with anti-corruption layer patterns
type PostgreSQLConfigurationRepository struct {
	db              *sql.DB
	transactionCtx  context.Context
	transaction     *sql.Tx
	eventBus        events.EventBus
	domainMapper    *ConfigurationDomainMapper
	metricsCollector *RepositoryMetricsCollector
}

// NewPostgreSQLConfigurationRepository creates a new PostgreSQL configuration repository
func NewPostgreSQLConfigurationRepository(
	db *sql.DB,
	eventBus events.EventBus,
	metricsCollector *RepositoryMetricsCollector,
) *PostgreSQLConfigurationRepository {
	return &PostgreSQLConfigurationRepository{
		db:              db,
		eventBus:        eventBus,
		domainMapper:    NewConfigurationDomainMapper(),
		metricsCollector: metricsCollector,
	}
}

// Save persists a configuration aggregate with its domain events
func (r *PostgreSQLConfigurationRepository) Save(
	ctx context.Context,
	config *configuration.Configuration,
) error {
	startTime := time.Now()
	defer r.recordMetrics("save", startTime, nil)

	tx, err := r.getTransaction(ctx)
	if err != nil {
		return r.wrapError("transaction_failed", err)
	}

	// Convert domain model to persistence model with anti-corruption layer
	persistenceModel, err := r.domainMapper.ToDatabaseModel(config)
	if err != nil {
		return r.wrapError("domain_mapping_failed", err)
	}

	// Check if configuration exists
	exists, err := r.configurationExists(ctx, tx, config.ID())
	if err != nil {
		return r.wrapError("existence_check_failed", err)
	}

	if exists {
		err = r.updateConfiguration(ctx, tx, persistenceModel)
	} else {
		err = r.insertConfiguration(ctx, tx, persistenceModel)
	}

	if err != nil {
		return r.wrapError("persistence_failed", err)
	}

	// Save components with proper referential integrity
	if err := r.saveComponents(ctx, tx, persistenceModel); err != nil {
		return r.wrapError("component_persistence_failed", err)
	}

	// Save enterprise configuration if present
	if persistenceModel.EnterpriseConfig != nil {
		if err := r.saveEnterpriseConfig(ctx, tx, persistenceModel); err != nil {
			return r.wrapError("enterprise_config_persistence_failed", err)
		}
	}

	// Update metadata
	if err := r.saveMetadata(ctx, tx, persistenceModel); err != nil {
		return r.wrapError("metadata_persistence_failed", err)
	}

	return nil
}

// FindByID retrieves a configuration by its unique identifier
func (r *PostgreSQLConfigurationRepository) FindByID(
	ctx context.Context,
	id configuration.ConfigurationID,
) (*configuration.Configuration, error) {
	startTime := time.Now()
	defer r.recordMetrics("find_by_id", startTime, nil)

	tx, err := r.getTransaction(ctx)
	if err != nil {
		return nil, r.wrapError("transaction_failed", err)
	}

	// Query configuration with optimized joins
	query := `
		SELECT 
			c.id, c.name, c.description, c.mode, c.version, c.status,
			c.labels, c.annotations, c.created_at, c.updated_at,
			c.metadata, c.cached_component_count,
			ec.compliance_framework, ec.security_level, ec.audit_enabled,
			ec.encryption_required, ec.backup_required, ec.policy_templates,
			ec.metadata as enterprise_metadata
		FROM configurations c
		LEFT JOIN enterprise_configurations ec ON c.id = ec.configuration_id
		WHERE c.id = $1 AND c.deleted_at IS NULL
	`

	var persistenceModel ConfigurationPersistenceModel
	var enterpriseConfig *EnterpriseConfigPersistenceModel

	row := tx.QueryRowContext(ctx, query, id.String())
	err = r.scanConfigurationRow(row, &persistenceModel, &enterpriseConfig)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, repositories.ErrConfigurationNotFound
		}
		return nil, r.wrapError("scan_failed", err)
	}

	// Load components
	components, err := r.loadComponents(ctx, tx, id.String())
	if err != nil {
		return nil, r.wrapError("component_load_failed", err)
	}
	persistenceModel.Components = components

	// Set enterprise config if loaded
	if enterpriseConfig != nil {
		persistenceModel.EnterpriseConfig = enterpriseConfig
	}

	// Convert persistence model back to domain model through anti-corruption layer
	domainModel, err := r.domainMapper.ToDomainModel(persistenceModel)
	if err != nil {
		return nil, r.wrapError("domain_mapping_failed", err)
	}

	return domainModel, nil
}

// FindByName retrieves a configuration by its name
func (r *PostgreSQLConfigurationRepository) FindByName(
	ctx context.Context,
	name configuration.ConfigurationName,
) (*configuration.Configuration, error) {
	startTime := time.Now()
	defer r.recordMetrics("find_by_name", startTime, nil)

	tx, err := r.getTransaction(ctx)
	if err != nil {
		return nil, r.wrapError("transaction_failed", err)
	}

	// Query by name with case-insensitive matching
	query := `
		SELECT id FROM configurations 
		WHERE LOWER(name) = LOWER($1) AND deleted_at IS NULL
		LIMIT 1
	`

	var configID string
	err = tx.QueryRowContext(ctx, query, name.String()).Scan(&configID)
	if err != nil {
		if err == sql.ErrNoRows {
			return nil, repositories.ErrConfigurationNotFound
		}
		return nil, r.wrapError("query_failed", err)
	}

	// Convert to ConfigurationID and use FindByID
	id, err := configuration.NewConfigurationID(configID)
	if err != nil {
		return nil, r.wrapError("id_conversion_failed", err)
	}

	return r.FindByID(ctx, id)
}

// FindAll retrieves configurations with optional filtering
func (r *PostgreSQLConfigurationRepository) FindAll(
	ctx context.Context,
	filter repositories.ConfigurationFilter,
) ([]*configuration.Configuration, error) {
	startTime := time.Now()
	defer r.recordMetrics("find_all", startTime, nil)

	tx, err := r.getTransaction(ctx)
	if err != nil {
		return nil, r.wrapError("transaction_failed", err)
	}

	// Build dynamic query with filters
	queryBuilder := &PostgreSQLQueryBuilder{}
	query, args := queryBuilder.BuildConfigurationQuery(filter)

	rows, err := tx.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, r.wrapError("query_execution_failed", err)
	}
	defer rows.Close()

	configurations := make([]*configuration.Configuration, 0)
	
	for rows.Next() {
		var persistenceModel ConfigurationPersistenceModel
		var enterpriseConfig *EnterpriseConfigPersistenceModel

		err := r.scanConfigurationRow(rows, &persistenceModel, &enterpriseConfig)
		if err != nil {
			return nil, r.wrapError("scan_failed", err)
		}

		// Load components for each configuration
		components, err := r.loadComponents(ctx, tx, persistenceModel.ID)
		if err != nil {
			return nil, r.wrapError("component_load_failed", err)
		}
		persistenceModel.Components = components

		if enterpriseConfig != nil {
			persistenceModel.EnterpriseConfig = enterpriseConfig
		}

		// Convert to domain model
		domainModel, err := r.domainMapper.ToDomainModel(persistenceModel)
		if err != nil {
			return nil, r.wrapError("domain_mapping_failed", err)
		}

		configurations = append(configurations, domainModel)
	}

	if err = rows.Err(); err != nil {
		return nil, r.wrapError("rows_iteration_failed", err)
	}

	return configurations, nil
}

// Delete removes a configuration from persistence (soft delete)
func (r *PostgreSQLConfigurationRepository) Delete(
	ctx context.Context,
	id configuration.ConfigurationID,
) error {
	startTime := time.Now()
	defer r.recordMetrics("delete", startTime, nil)

	tx, err := r.getTransaction(ctx)
	if err != nil {
		return r.wrapError("transaction_failed", err)
	}

	// Soft delete configuration
	query := `
		UPDATE configurations 
		SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
		WHERE id = $1 AND deleted_at IS NULL
	`

	result, err := tx.ExecContext(ctx, query, id.String())
	if err != nil {
		return r.wrapError("delete_execution_failed", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return r.wrapError("rows_affected_check_failed", err)
	}

	if rowsAffected == 0 {
		return repositories.ErrConfigurationNotFound
	}

	// Soft delete related components
	componentQuery := `
		UPDATE configuration_components 
		SET deleted_at = CURRENT_TIMESTAMP
		WHERE configuration_id = $1 AND deleted_at IS NULL
	`

	_, err = tx.ExecContext(ctx, componentQuery, id.String())
	if err != nil {
		return r.wrapError("component_delete_failed", err)
	}

	return nil
}

// Exists checks if a configuration exists by ID
func (r *PostgreSQLConfigurationRepository) Exists(
	ctx context.Context,
	id configuration.ConfigurationID,
) (bool, error) {
	startTime := time.Now()
	defer r.recordMetrics("exists", startTime, nil)

	tx, err := r.getTransaction(ctx)
	if err != nil {
		return false, r.wrapError("transaction_failed", err)
	}

	return r.configurationExists(ctx, tx, id)
}

// Count returns the total number of configurations matching filter
func (r *PostgreSQLConfigurationRepository) Count(
	ctx context.Context,
	filter repositories.ConfigurationFilter,
) (int64, error) {
	startTime := time.Now()
	defer r.recordMetrics("count", startTime, nil)

	tx, err := r.getTransaction(ctx)
	if err != nil {
		return 0, r.wrapError("transaction_failed", err)
	}

	// Build count query
	queryBuilder := &PostgreSQLQueryBuilder{}
	query, args := queryBuilder.BuildCountQuery(filter)

	var count int64
	err = tx.QueryRowContext(ctx, query, args...).Scan(&count)
	if err != nil {
		return 0, r.wrapError("count_query_failed", err)
	}

	return count, nil
}

// SaveWithTransaction saves configuration within a transaction context
func (r *PostgreSQLConfigurationRepository) SaveWithTransaction(
	ctx context.Context,
	config *configuration.Configuration,
	transaction repositories.Transaction,
) error {
	// Cast transaction to our PostgreSQL implementation
	pgTx, ok := transaction.(*PostgreSQLTransaction)
	if !ok {
		return r.wrapError("invalid_transaction_type", fmt.Errorf("expected PostgreSQLTransaction"))
	}

	// Temporarily set transaction context
	originalTx := r.transaction
	originalCtx := r.transactionCtx
	
	r.transaction = pgTx.tx
	r.transactionCtx = ctx
	
	defer func() {
		r.transaction = originalTx
		r.transactionCtx = originalCtx
	}()

	return r.Save(ctx, config)
}

// GetNextID generates the next available configuration ID
func (r *PostgreSQLConfigurationRepository) GetNextID(
	ctx context.Context,
) (configuration.ConfigurationID, error) {
	// Generate UUID using PostgreSQL function
	tx, err := r.getTransaction(ctx)
	if err != nil {
		return configuration.ConfigurationID{}, r.wrapError("transaction_failed", err)
	}

	var id string
	err = tx.QueryRowContext(ctx, "SELECT gen_random_uuid()").Scan(&id)
	if err != nil {
		return configuration.ConfigurationID{}, r.wrapError("id_generation_failed", err)
	}

	return configuration.NewConfigurationID(id)
}

// Helper methods for database operations

func (r *PostgreSQLConfigurationRepository) getTransaction(ctx context.Context) (*sql.Tx, error) {
	if r.transaction != nil && r.transactionCtx == ctx {
		return r.transaction, nil
	}

	// Create new transaction
	tx, err := r.db.BeginTx(ctx, &sql.TxOptions{
		Isolation: sql.LevelReadCommitted,
		ReadOnly:  false,
	})
	if err != nil {
		return nil, err
	}

	return tx, nil
}

func (r *PostgreSQLConfigurationRepository) configurationExists(
	ctx context.Context,
	tx *sql.Tx,
	id configuration.ConfigurationID,
) (bool, error) {
	query := `SELECT 1 FROM configurations WHERE id = $1 AND deleted_at IS NULL LIMIT 1`
	
	var exists int
	err := tx.QueryRowContext(ctx, query, id.String()).Scan(&exists)
	if err != nil {
		if err == sql.ErrNoRows {
			return false, nil
		}
		return false, err
	}
	
	return true, nil
}

func (r *PostgreSQLConfigurationRepository) insertConfiguration(
	ctx context.Context,
	tx *sql.Tx,
	model ConfigurationPersistenceModel,
) error {
	query := `
		INSERT INTO configurations (
			id, name, description, mode, version, status,
			labels, annotations, cached_component_count,
			metadata, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
	`

	_, err := tx.ExecContext(ctx, query,
		model.ID,
		model.Name,
		model.Description,
		model.Mode,
		model.Version,
		model.Status,
		model.Labels,
		model.Annotations,
		model.CachedComponentCount,
		model.Metadata,
		model.CreatedAt,
		model.UpdatedAt,
	)

	return err
}

func (r *PostgreSQLConfigurationRepository) updateConfiguration(
	ctx context.Context,
	tx *sql.Tx,
	model ConfigurationPersistenceModel,
) error {
	query := `
		UPDATE configurations SET
			name = $2,
			description = $3,
			mode = $4,
			version = $5,
			status = $6,
			labels = $7,
			annotations = $8,
			cached_component_count = $9,
			metadata = $10,
			updated_at = $11
		WHERE id = $1 AND deleted_at IS NULL
	`

	result, err := tx.ExecContext(ctx, query,
		model.ID,
		model.Name,
		model.Description,
		model.Mode,
		model.Version,
		model.Status,
		model.Labels,
		model.Annotations,
		model.CachedComponentCount,
		model.Metadata,
		model.UpdatedAt,
	)

	if err != nil {
		return err
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return err
	}

	if rowsAffected == 0 {
		return repositories.ErrConfigurationNotFound
	}

	return nil
}

func (r *PostgreSQLConfigurationRepository) saveComponents(
	ctx context.Context,
	tx *sql.Tx,
	model ConfigurationPersistenceModel,
) error {
	// First, mark existing components as deleted
	deleteQuery := `
		UPDATE configuration_components 
		SET deleted_at = CURRENT_TIMESTAMP
		WHERE configuration_id = $1 AND deleted_at IS NULL
	`

	_, err := tx.ExecContext(ctx, deleteQuery, model.ID)
	if err != nil {
		return err
	}

	// Insert new components
	if len(model.Components) == 0 {
		return nil
	}

	insertQuery := `
		INSERT INTO configuration_components (
			id, configuration_id, name, version, enabled,
			configuration_data, cpu_requirement, memory_requirement,
			storage_requirement, replicas, namespace, dependencies,
			created_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
	`

	for _, component := range model.Components {
		_, err := tx.ExecContext(ctx, insertQuery,
			component.ID,
			model.ID,
			component.Name,
			component.Version,
			component.Enabled,
			component.ConfigurationData,
			component.CPURequirement,
			component.MemoryRequirement,
			component.StorageRequirement,
			component.Replicas,
			component.Namespace,
			pq.Array(component.Dependencies),
			component.CreatedAt,
		)
		if err != nil {
			return err
		}
	}

	return nil
}

func (r *PostgreSQLConfigurationRepository) saveEnterpriseConfig(
	ctx context.Context,
	tx *sql.Tx,
	model ConfigurationPersistenceModel,
) error {
	// Upsert enterprise configuration
	query := `
		INSERT INTO enterprise_configurations (
			configuration_id, compliance_framework, security_level,
			audit_enabled, encryption_required, backup_required,
			policy_templates, metadata, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
		ON CONFLICT (configuration_id) DO UPDATE SET
			compliance_framework = EXCLUDED.compliance_framework,
			security_level = EXCLUDED.security_level,
			audit_enabled = EXCLUDED.audit_enabled,
			encryption_required = EXCLUDED.encryption_required,
			backup_required = EXCLUDED.backup_required,
			policy_templates = EXCLUDED.policy_templates,
			metadata = EXCLUDED.metadata,
			updated_at = EXCLUDED.updated_at
	`

	_, err := tx.ExecContext(ctx, query,
		model.ID,
		model.EnterpriseConfig.ComplianceFramework,
		model.EnterpriseConfig.SecurityLevel,
		model.EnterpriseConfig.AuditEnabled,
		model.EnterpriseConfig.EncryptionRequired,
		model.EnterpriseConfig.BackupRequired,
		pq.Array(model.EnterpriseConfig.PolicyTemplates),
		model.EnterpriseConfig.Metadata,
		model.EnterpriseConfig.CreatedAt,
		model.EnterpriseConfig.UpdatedAt,
	)

	return err
}

func (r *PostgreSQLConfigurationRepository) saveMetadata(
	ctx context.Context,
	tx *sql.Tx,
	model ConfigurationPersistenceModel,
) error {
	// Update metadata timestamp
	query := `UPDATE configurations SET updated_at = CURRENT_TIMESTAMP WHERE id = $1`
	_, err := tx.ExecContext(ctx, query, model.ID)
	return err
}

func (r *PostgreSQLConfigurationRepository) loadComponents(
	ctx context.Context,
	tx *sql.Tx,
	configurationID string,
) ([]ComponentPersistenceModel, error) {
	query := `
		SELECT 
			id, name, version, enabled, configuration_data,
			cpu_requirement, memory_requirement, storage_requirement,
			replicas, namespace, dependencies, created_at
		FROM configuration_components 
		WHERE configuration_id = $1 AND deleted_at IS NULL
		ORDER BY name
	`

	rows, err := tx.QueryContext(ctx, query, configurationID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	components := make([]ComponentPersistenceModel, 0)
	
	for rows.Next() {
		var component ComponentPersistenceModel
		var deps pq.StringArray

		err := rows.Scan(
			&component.ID,
			&component.Name,
			&component.Version,
			&component.Enabled,
			&component.ConfigurationData,
			&component.CPURequirement,
			&component.MemoryRequirement,
			&component.StorageRequirement,
			&component.Replicas,
			&component.Namespace,
			&deps,
			&component.CreatedAt,
		)
		if err != nil {
			return nil, err
		}

		component.Dependencies = []string(deps)
		components = append(components, component)
	}

	return components, rows.Err()
}

func (r *PostgreSQLConfigurationRepository) scanConfigurationRow(
	scanner RowScanner,
	model *ConfigurationPersistenceModel,
	enterpriseConfig **EnterpriseConfigPersistenceModel,
) error {
	var enterpriseFramework sql.NullString
	var enterpriseSecurityLevel sql.NullString
	var enterpriseAuditEnabled sql.NullBool
	var enterpriseEncryptionRequired sql.NullBool
	var enterpriseBackupRequired sql.NullBool
	var enterprisePolicyTemplates pq.StringArray
	var enterpriseMetadata sql.NullString

	err := scanner.Scan(
		&model.ID,
		&model.Name,
		&model.Description,
		&model.Mode,
		&model.Version,
		&model.Status,
		&model.Labels,
		&model.Annotations,
		&model.CreatedAt,
		&model.UpdatedAt,
		&model.Metadata,
		&model.CachedComponentCount,
		&enterpriseFramework,
		&enterpriseSecurityLevel,
		&enterpriseAuditEnabled,
		&enterpriseEncryptionRequired,
		&enterpriseBackupRequired,
		&enterprisePolicyTemplates,
		&enterpriseMetadata,
	)

	if err != nil {
		return err
	}

	// Build enterprise config if data exists
	if enterpriseFramework.Valid {
		*enterpriseConfig = &EnterpriseConfigPersistenceModel{
			ComplianceFramework:  enterpriseFramework.String,
			SecurityLevel:       enterpriseSecurityLevel.String,
			AuditEnabled:        enterpriseAuditEnabled.Bool,
			EncryptionRequired:  enterpriseEncryptionRequired.Bool,
			BackupRequired:      enterpriseBackupRequired.Bool,
			PolicyTemplates:     []string(enterprisePolicyTemplates),
			Metadata:           enterpriseMetadata.String,
			CreatedAt:          model.CreatedAt,
			UpdatedAt:          model.UpdatedAt,
		}
	}

	return nil
}

func (r *PostgreSQLConfigurationRepository) recordMetrics(operation string, startTime time.Time, err error) {
	if r.metricsCollector != nil {
		duration := time.Since(startTime)
		r.metricsCollector.RecordOperation(operation, duration, err)
	}
}

func (r *PostgreSQLConfigurationRepository) wrapError(operation string, err error) error {
	return repositories.NewRepositoryError(
		repositories.ErrorTypeUnknown,
		fmt.Sprintf("PostgreSQL repository %s failed: %v", operation, err),
		err,
	)
}

// RowScanner interface for abstraction over sql.Row and sql.Rows
type RowScanner interface {
	Scan(dest ...interface{}) error
}

// PostgreSQLTransaction implements the Transaction interface
type PostgreSQLTransaction struct {
	tx     *sql.Tx
	ctx    context.Context
	active bool
}

// NewPostgreSQLTransaction creates a new PostgreSQL transaction
func NewPostgreSQLTransaction(ctx context.Context, db *sql.DB) (*PostgreSQLTransaction, error) {
	tx, err := db.BeginTx(ctx, &sql.TxOptions{
		Isolation: sql.LevelReadCommitted,
		ReadOnly:  false,
	})
	if err != nil {
		return nil, err
	}

	return &PostgreSQLTransaction{
		tx:     tx,
		ctx:    ctx,
		active: true,
	}, nil
}

// Commit commits the transaction
func (t *PostgreSQLTransaction) Commit() error {
	if !t.active {
		return fmt.Errorf("transaction is not active")
	}
	
	err := t.tx.Commit()
	t.active = false
	return err
}

// Rollback rolls back the transaction
func (t *PostgreSQLTransaction) Rollback() error {
	if !t.active {
		return nil // Already rolled back or committed
	}
	
	err := t.tx.Rollback()
	t.active = false
	return err
}

// IsActive returns true if transaction is active
func (t *PostgreSQLTransaction) IsActive() bool {
	return t.active
}

// Context returns the transaction context
func (t *PostgreSQLTransaction) Context() context.Context {
	return t.ctx
}

// Supporting types for persistence models

type ConfigurationPersistenceModel struct {
	ID                    string                         `json:"id"`
	Name                  string                         `json:"name"`
	Description           string                         `json:"description"`
	Mode                  string                         `json:"mode"`
	Version               string                         `json:"version"`
	Status                string                         `json:"status"`
	Labels                string                         `json:"labels"`    // JSON serialized
	Annotations           string                         `json:"annotations"` // JSON serialized
	CachedComponentCount  int                            `json:"cached_component_count"`
	Metadata              string                         `json:"metadata"`   // JSON serialized
	CreatedAt             time.Time                      `json:"created_at"`
	UpdatedAt             time.Time                      `json:"updated_at"`
	Components            []ComponentPersistenceModel    `json:"components"`
	EnterpriseConfig      *EnterpriseConfigPersistenceModel `json:"enterprise_config,omitempty"`
}

type ComponentPersistenceModel struct {
	ID                   string    `json:"id"`
	Name                 string    `json:"name"`
	Version              string    `json:"version"`
	Enabled              bool      `json:"enabled"`
	ConfigurationData    string    `json:"configuration_data"` // JSON serialized
	CPURequirement       string    `json:"cpu_requirement"`
	MemoryRequirement    string    `json:"memory_requirement"`
	StorageRequirement   string    `json:"storage_requirement"`
	Replicas             int       `json:"replicas"`
	Namespace            string    `json:"namespace"`
	Dependencies         []string  `json:"dependencies"`
	CreatedAt            time.Time `json:"created_at"`
}

type EnterpriseConfigPersistenceModel struct {
	ComplianceFramework  string    `json:"compliance_framework"`
	SecurityLevel        string    `json:"security_level"`
	AuditEnabled         bool      `json:"audit_enabled"`
	EncryptionRequired   bool      `json:"encryption_required"`
	BackupRequired       bool      `json:"backup_required"`
	PolicyTemplates      []string  `json:"policy_templates"`
	Metadata             string    `json:"metadata"` // JSON serialized
	CreatedAt            time.Time `json:"created_at"`
	UpdatedAt            time.Time `json:"updated_at"`
}

// RepositoryMetricsCollector for performance monitoring
type RepositoryMetricsCollector struct {
	// Implementation would collect metrics about repository operations
}

func (rmc *RepositoryMetricsCollector) RecordOperation(operation string, duration time.Duration, err error) {
	// Implementation would record operation metrics
}

// PostgreSQLQueryBuilder for dynamic query construction
type PostgreSQLQueryBuilder struct {
	// Implementation would build dynamic queries based on filters
}

func (qb *PostgreSQLQueryBuilder) BuildConfigurationQuery(filter repositories.ConfigurationFilter) (string, []interface{}) {
	// Implementation would build dynamic SQL queries with proper parameterization
	baseQuery := `
		SELECT 
			c.id, c.name, c.description, c.mode, c.version, c.status,
			c.labels, c.annotations, c.created_at, c.updated_at,
			c.metadata, c.cached_component_count,
			ec.compliance_framework, ec.security_level, ec.audit_enabled,
			ec.encryption_required, ec.backup_required, ec.policy_templates,
			ec.metadata as enterprise_metadata
		FROM configurations c
		LEFT JOIN enterprise_configurations ec ON c.id = ec.configuration_id
		WHERE c.deleted_at IS NULL
	`
	
	// Add filters dynamically...
	// This would be a comprehensive implementation for building filtered queries
	
	return baseQuery + " ORDER BY c.created_at DESC", []interface{}{}
}

func (qb *PostgreSQLQueryBuilder) BuildCountQuery(filter repositories.ConfigurationFilter) (string, []interface{}) {
	baseQuery := `SELECT COUNT(*) FROM configurations c WHERE c.deleted_at IS NULL`
	
	// Add filters dynamically...
	
	return baseQuery, []interface{}{}
}