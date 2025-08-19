package postgresql

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"

	"github.com/hedgehog/cnoc/internal/domain/gitops"
	"github.com/lib/pq"
	_ "github.com/lib/pq" // PostgreSQL driver
)

// GitRepositoryRepositoryImpl implements the GitRepositoryRepository interface
// following FORGE GREEN phase principles to make existing RED phase tests pass
type GitRepositoryRepositoryImpl struct {
	db *sql.DB
}

// NewGitRepositoryRepository creates a new PostgreSQL-based git repository repository
// This function is required by the test suite and must match the expected signature
func NewGitRepositoryRepository(db *sql.DB) gitops.GitRepositoryRepository {
	return &GitRepositoryRepositoryImpl{
		db: db,
	}
}

// Create persists a new git repository to the database
// FORGE REQUIREMENT: Must complete within 100ms and handle all error scenarios
func (r *GitRepositoryRepositoryImpl) Create(repo *gitops.GitRepository) error {
	if repo == nil {
		return fmt.Errorf("repository cannot be nil")
	}

	// Validate repository before persistence
	if err := repo.Validate(); err != nil {
		return fmt.Errorf("validation failed: %w", err)
	}

	// Generate ID if not set
	if repo.ID == "" {
		var id string
		err := r.db.QueryRow("SELECT gen_random_uuid()::text").Scan(&id)
		if err != nil {
			return fmt.Errorf("failed to generate ID: %w", err)
		}
		repo.ID = id
	}

	// Set timestamps if not already set
	now := time.Now()
	if repo.Created.IsZero() {
		repo.Created = now
	}
	if repo.LastModified.IsZero() {
		repo.LastModified = now
	}

	// Begin transaction for atomic operation
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	tx, err := r.db.BeginTx(ctx, &sql.TxOptions{
		Isolation: sql.LevelReadCommitted,
	})
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// Insert repository with all required fields
	query := `
		INSERT INTO git_repositories (
			id, name, url, description, authentication_type,
			encrypted_credentials, credentials_key_version,
			connection_status, last_validated, validation_error,
			default_branch, last_commit_hash, last_fetched,
			created, last_modified, created_by, modified_by
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
	`

	_, err = tx.ExecContext(ctx, query,
		repo.ID,
		repo.Name,
		repo.URL,
		repo.Description,
		string(repo.AuthenticationType),
		repo.EncryptedCredentials,
		repo.CredentialsKeyVersion,
		string(repo.ConnectionStatus),
		repo.LastValidated,
		repo.ValidationError,
		repo.DefaultBranch,
		repo.LastCommitHash,
		repo.LastFetched,
		repo.Created,
		repo.LastModified,
		repo.CreatedBy,
		repo.ModifiedBy,
	)

	if err != nil {
		// Handle specific constraint violations
		if pqErr, ok := err.(*pq.Error); ok {
			switch pqErr.Code {
			case "23505": // unique_violation
				if strings.Contains(pqErr.Message, "name") {
					return fmt.Errorf("repository name '%s' already exists", repo.Name)
				}
				return fmt.Errorf("duplicate repository detected")
			case "23514": // check_violation
				if strings.Contains(pqErr.Message, "authentication_type") {
					return fmt.Errorf("invalid authentication_type: %s", repo.AuthenticationType)
				}
				if strings.Contains(pqErr.Message, "name_length") {
					return fmt.Errorf("repository name exceeds maximum length")
				}
				if strings.Contains(pqErr.Message, "url_length") {
					return fmt.Errorf("repository url is required")
				}
				return fmt.Errorf("constraint violation: %s", pqErr.Message)
			case "23502": // not_null_violation
				return fmt.Errorf("required field missing: %s", pqErr.Column)
			}
		}
		return fmt.Errorf("failed to create repository: %w", err)
	}

	// Commit transaction
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	return nil
}

// GetByID retrieves a git repository by its ID
// FORGE REQUIREMENT: Must complete within 100ms and handle not found scenarios
func (r *GitRepositoryRepositoryImpl) GetByID(id string) (*gitops.GitRepository, error) {
	if id == "" {
		return nil, fmt.Errorf("repository ID cannot be empty")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	query := `
		SELECT 
			id, name, url, description, authentication_type,
			encrypted_credentials, credentials_key_version,
			connection_status, last_validated, validation_error,
			default_branch, last_commit_hash, last_fetched,
			created, last_modified, created_by, modified_by
		FROM git_repositories 
		WHERE id = $1
	`

	row := r.db.QueryRowContext(ctx, query, id)

	repo := &gitops.GitRepository{}
	var authType, connStatus string
	
	err := row.Scan(
		&repo.ID,
		&repo.Name,
		&repo.URL,
		&repo.Description,
		&authType,
		&repo.EncryptedCredentials,
		&repo.CredentialsKeyVersion,
		&connStatus,
		&repo.LastValidated,
		&repo.ValidationError,
		&repo.DefaultBranch,
		&repo.LastCommitHash,
		&repo.LastFetched,
		&repo.Created,
		&repo.LastModified,
		&repo.CreatedBy,
		&repo.ModifiedBy,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("repository with ID %s not found", id)
		}
		return nil, fmt.Errorf("failed to retrieve repository: %w", err)
	}

	// Convert string types to domain types
	repo.AuthenticationType = gitops.AuthType(authType)
	repo.ConnectionStatus = gitops.ConnectionStatus(connStatus)

	return repo, nil
}

// List retrieves repositories with pagination
// FORGE REQUIREMENT: Must complete within 500ms and support pagination
func (r *GitRepositoryRepositoryImpl) List(offset, limit int) ([]*gitops.GitRepository, int, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// Get total count
	var totalCount int
	countQuery := "SELECT COUNT(*) FROM git_repositories"
	err := r.db.QueryRowContext(ctx, countQuery).Scan(&totalCount)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to get total count: %w", err)
	}

	// Get paginated results
	query := `
		SELECT 
			id, name, url, description, authentication_type,
			encrypted_credentials, credentials_key_version,
			connection_status, last_validated, validation_error,
			default_branch, last_commit_hash, last_fetched,
			created, last_modified, created_by, modified_by
		FROM git_repositories 
		ORDER BY created DESC
		LIMIT $1 OFFSET $2
	`

	rows, err := r.db.QueryContext(ctx, query, limit, offset)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to query repositories: %w", err)
	}
	defer rows.Close()

	var repositories []*gitops.GitRepository
	for rows.Next() {
		repo := &gitops.GitRepository{}
		var authType, connStatus string

		err := rows.Scan(
			&repo.ID,
			&repo.Name,
			&repo.URL,
			&repo.Description,
			&authType,
			&repo.EncryptedCredentials,
			&repo.CredentialsKeyVersion,
			&connStatus,
			&repo.LastValidated,
			&repo.ValidationError,
			&repo.DefaultBranch,
			&repo.LastCommitHash,
			&repo.LastFetched,
			&repo.Created,
			&repo.LastModified,
			&repo.CreatedBy,
			&repo.ModifiedBy,
		)

		if err != nil {
			return nil, 0, fmt.Errorf("failed to scan repository: %w", err)
		}

		// Convert string types to domain types
		repo.AuthenticationType = gitops.AuthType(authType)
		repo.ConnectionStatus = gitops.ConnectionStatus(connStatus)

		repositories = append(repositories, repo)
	}

	if err = rows.Err(); err != nil {
		return nil, 0, fmt.Errorf("error iterating rows: %w", err)
	}

	return repositories, totalCount, nil
}

// Update modifies an existing git repository
// FORGE REQUIREMENT: Must complete within 100ms and handle not found scenarios
func (r *GitRepositoryRepositoryImpl) Update(repo *gitops.GitRepository) error {
	if repo == nil {
		return fmt.Errorf("repository cannot be nil")
	}

	if repo.ID == "" {
		return fmt.Errorf("repository ID cannot be empty")
	}

	// Validate repository before update
	if err := repo.Validate(); err != nil {
		return fmt.Errorf("validation failed: %w", err)
	}

	// Update last modified timestamp
	repo.LastModified = time.Now()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	tx, err := r.db.BeginTx(ctx, &sql.TxOptions{
		Isolation: sql.LevelReadCommitted,
	})
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	query := `
		UPDATE git_repositories SET
			name = $2,
			url = $3,
			description = $4,
			authentication_type = $5,
			encrypted_credentials = $6,
			credentials_key_version = $7,
			connection_status = $8,
			last_validated = $9,
			validation_error = $10,
			default_branch = $11,
			last_commit_hash = $12,
			last_fetched = $13,
			last_modified = $14,
			modified_by = $15
		WHERE id = $1
	`

	result, err := tx.ExecContext(ctx, query,
		repo.ID,
		repo.Name,
		repo.URL,
		repo.Description,
		string(repo.AuthenticationType),
		repo.EncryptedCredentials,
		repo.CredentialsKeyVersion,
		string(repo.ConnectionStatus),
		repo.LastValidated,
		repo.ValidationError,
		repo.DefaultBranch,
		repo.LastCommitHash,
		repo.LastFetched,
		repo.LastModified,
		repo.ModifiedBy,
	)

	if err != nil {
		return fmt.Errorf("failed to update repository: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("repository with ID %s not found", repo.ID)
	}

	// Commit transaction
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	return nil
}

// Delete removes a git repository by ID
// FORGE REQUIREMENT: Must complete within 100ms and handle not found scenarios
func (r *GitRepositoryRepositoryImpl) Delete(id string) error {
	if id == "" {
		return fmt.Errorf("repository ID cannot be empty")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	tx, err := r.db.BeginTx(ctx, &sql.TxOptions{
		Isolation: sql.LevelReadCommitted,
	})
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	query := "DELETE FROM git_repositories WHERE id = $1"
	
	result, err := tx.ExecContext(ctx, query, id)
	if err != nil {
		return fmt.Errorf("failed to delete repository: %w", err)
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rowsAffected == 0 {
		return fmt.Errorf("repository with ID %s not found", id)
	}

	// Commit transaction
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	return nil
}

// GetByName retrieves a git repository by its name
func (r *GitRepositoryRepositoryImpl) GetByName(name string) (*gitops.GitRepository, error) {
	if name == "" {
		return nil, fmt.Errorf("repository name cannot be empty")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	query := `
		SELECT 
			id, name, url, description, authentication_type,
			encrypted_credentials, credentials_key_version,
			connection_status, last_validated, validation_error,
			default_branch, last_commit_hash, last_fetched,
			created, last_modified, created_by, modified_by
		FROM git_repositories 
		WHERE name = $1
	`

	row := r.db.QueryRowContext(ctx, query, name)

	repo := &gitops.GitRepository{}
	var authType, connStatus string
	
	err := row.Scan(
		&repo.ID,
		&repo.Name,
		&repo.URL,
		&repo.Description,
		&authType,
		&repo.EncryptedCredentials,
		&repo.CredentialsKeyVersion,
		&connStatus,
		&repo.LastValidated,
		&repo.ValidationError,
		&repo.DefaultBranch,
		&repo.LastCommitHash,
		&repo.LastFetched,
		&repo.Created,
		&repo.LastModified,
		&repo.CreatedBy,
		&repo.ModifiedBy,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("repository with name %s not found", name)
		}
		return nil, fmt.Errorf("failed to retrieve repository: %w", err)
	}

	// Convert string types to domain types
	repo.AuthenticationType = gitops.AuthType(authType)
	repo.ConnectionStatus = gitops.ConnectionStatus(connStatus)

	return repo, nil
}

// GetByConnectionStatus retrieves repositories by connection status
func (r *GitRepositoryRepositoryImpl) GetByConnectionStatus(status gitops.ConnectionStatus) ([]*gitops.GitRepository, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	query := `
		SELECT 
			id, name, url, description, authentication_type,
			encrypted_credentials, credentials_key_version,
			connection_status, last_validated, validation_error,
			default_branch, last_commit_hash, last_fetched,
			created, last_modified, created_by, modified_by
		FROM git_repositories 
		WHERE connection_status = $1
		ORDER BY last_modified DESC
	`

	rows, err := r.db.QueryContext(ctx, query, string(status))
	if err != nil {
		return nil, fmt.Errorf("failed to query repositories by status: %w", err)
	}
	defer rows.Close()

	var repositories []*gitops.GitRepository
	for rows.Next() {
		repo := &gitops.GitRepository{}
		var authType, connStatus string

		err := rows.Scan(
			&repo.ID,
			&repo.Name,
			&repo.URL,
			&repo.Description,
			&authType,
			&repo.EncryptedCredentials,
			&repo.CredentialsKeyVersion,
			&connStatus,
			&repo.LastValidated,
			&repo.ValidationError,
			&repo.DefaultBranch,
			&repo.LastCommitHash,
			&repo.LastFetched,
			&repo.Created,
			&repo.LastModified,
			&repo.CreatedBy,
			&repo.ModifiedBy,
		)

		if err != nil {
			return nil, fmt.Errorf("failed to scan repository: %w", err)
		}

		// Convert string types to domain types
		repo.AuthenticationType = gitops.AuthType(authType)
		repo.ConnectionStatus = gitops.ConnectionStatus(connStatus)

		repositories = append(repositories, repo)
	}

	if err = rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating rows: %w", err)
	}

	return repositories, nil
}

// GetNeedingValidation retrieves repositories that need validation since the given time
func (r *GitRepositoryRepositoryImpl) GetNeedingValidation(since time.Time) ([]*gitops.GitRepository, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	query := `
		SELECT 
			id, name, url, description, authentication_type,
			encrypted_credentials, credentials_key_version,
			connection_status, last_validated, validation_error,
			default_branch, last_commit_hash, last_fetched,
			created, last_modified, created_by, modified_by
		FROM git_repositories 
		WHERE last_validated IS NULL OR last_validated < $1
		ORDER BY last_validated ASC NULLS FIRST
	`

	rows, err := r.db.QueryContext(ctx, query, since)
	if err != nil {
		return nil, fmt.Errorf("failed to query repositories needing validation: %w", err)
	}
	defer rows.Close()

	var repositories []*gitops.GitRepository
	for rows.Next() {
		repo := &gitops.GitRepository{}
		var authType, connStatus string

		err := rows.Scan(
			&repo.ID,
			&repo.Name,
			&repo.URL,
			&repo.Description,
			&authType,
			&repo.EncryptedCredentials,
			&repo.CredentialsKeyVersion,
			&connStatus,
			&repo.LastValidated,
			&repo.ValidationError,
			&repo.DefaultBranch,
			&repo.LastCommitHash,
			&repo.LastFetched,
			&repo.Created,
			&repo.LastModified,
			&repo.CreatedBy,
			&repo.ModifiedBy,
		)

		if err != nil {
			return nil, fmt.Errorf("failed to scan repository: %w", err)
		}

		// Convert string types to domain types
		repo.AuthenticationType = gitops.AuthType(authType)
		repo.ConnectionStatus = gitops.ConnectionStatus(connStatus)

		repositories = append(repositories, repo)
	}

	if err = rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating rows: %w", err)
	}

	return repositories, nil
}

// GetByURL retrieves a repository by its URL
func (r *GitRepositoryRepositoryImpl) GetByURL(url string) (*gitops.GitRepository, error) {
	if url == "" {
		return nil, fmt.Errorf("repository URL cannot be empty")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	query := `
		SELECT 
			id, name, url, description, authentication_type,
			encrypted_credentials, credentials_key_version,
			connection_status, last_validated, validation_error,
			default_branch, last_commit_hash, last_fetched,
			created, last_modified, created_by, modified_by
		FROM git_repositories 
		WHERE url = $1
	`

	row := r.db.QueryRowContext(ctx, query, url)

	repo := &gitops.GitRepository{}
	var authType, connStatus string
	
	err := row.Scan(
		&repo.ID,
		&repo.Name,
		&repo.URL,
		&repo.Description,
		&authType,
		&repo.EncryptedCredentials,
		&repo.CredentialsKeyVersion,
		&connStatus,
		&repo.LastValidated,
		&repo.ValidationError,
		&repo.DefaultBranch,
		&repo.LastCommitHash,
		&repo.LastFetched,
		&repo.Created,
		&repo.LastModified,
		&repo.CreatedBy,
		&repo.ModifiedBy,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("repository with URL %s not found", url)
		}
		return nil, fmt.Errorf("failed to retrieve repository: %w", err)
	}

	// Convert string types to domain types
	repo.AuthenticationType = gitops.AuthType(authType)
	repo.ConnectionStatus = gitops.ConnectionStatus(connStatus)

	return repo, nil
}

// UpdateConnectionStatuses updates multiple repositories' connection statuses in a single transaction
func (r *GitRepositoryRepositoryImpl) UpdateConnectionStatuses(updates map[string]gitops.ConnectionStatus) error {
	if len(updates) == 0 {
		return nil
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	tx, err := r.db.BeginTx(ctx, &sql.TxOptions{
		Isolation: sql.LevelReadCommitted,
	})
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	query := `
		UPDATE git_repositories 
		SET connection_status = $2, last_modified = NOW()
		WHERE id = $1
	`

	for id, status := range updates {
		_, err := tx.ExecContext(ctx, query, id, string(status))
		if err != nil {
			return fmt.Errorf("failed to update repository %s: %w", id, err)
		}
	}

	// Commit transaction
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	return nil
}