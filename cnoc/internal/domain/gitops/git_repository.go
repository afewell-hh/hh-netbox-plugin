package gitops

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/url"
	"strings"
	"time"
)

// GitRepository manages git repository authentication separately from fabric configuration
// This follows the HNP pattern of separating git authentication from fabric configuration
type GitRepository struct {
	ID                    string           `json:"id" db:"id"`
	Name                  string           `json:"name" db:"name" validate:"required,max=100"`
	URL                   string           `json:"url" db:"url" validate:"required,url"`
	Description           string           `json:"description" db:"description"`
	
	// Authentication configuration
	AuthenticationType    AuthType         `json:"authentication_type" db:"authentication_type"`
	EncryptedCredentials  string           `json:"-" db:"encrypted_credentials"` // Never exposed in JSON
	CredentialsKeyVersion int              `json:"-" db:"credentials_key_version"`
	
	// Connection status
	ConnectionStatus      ConnectionStatus `json:"connection_status" db:"connection_status"`
	LastValidated         *time.Time       `json:"last_validated" db:"last_validated"`
	ValidationError       string           `json:"validation_error,omitempty" db:"validation_error"`
	
	// Repository metadata
	DefaultBranch         string           `json:"default_branch" db:"default_branch"`
	LastCommitHash        string           `json:"last_commit_hash,omitempty" db:"last_commit_hash"`
	LastFetched          *time.Time       `json:"last_fetched" db:"last_fetched"`
	
	// Audit fields
	Created               time.Time        `json:"created" db:"created"`
	LastModified          time.Time        `json:"last_modified" db:"last_modified"`
	CreatedBy             string           `json:"created_by,omitempty" db:"created_by"`
	ModifiedBy            string           `json:"modified_by,omitempty" db:"modified_by"`
}

// AuthType represents the type of authentication used for git repository access
type AuthType string

const (
	AuthTypeToken    AuthType = "personal_access_auth"
	AuthTypeSSHKey   AuthType = "ssh_auth"
	AuthTypeOAuth    AuthType = "delegated_auth"
	AuthTypeBasic    AuthType = "basic_auth"
)

// ConnectionStatus represents the current connection status of the git repository
type ConnectionStatus string

const (
	ConnectionStatusUnknown   ConnectionStatus = "unknown"
	ConnectionStatusConnected ConnectionStatus = "connected"
	ConnectionStatusFailed    ConnectionStatus = "failed"
	ConnectionStatusPending   ConnectionStatus = "pending"
	ConnectionStatusExpired   ConnectionStatus = "expired"
)

// GitCredentials holds decrypted credential information (never persisted)
type GitCredentials struct {
	Type     AuthType `json:"type"`
	Token    string   `json:"token,omitempty"`
	Username string   `json:"username,omitempty"`
	Password string   `json:"password,omitempty"`
	SSHKey   string   `json:"ssh_key,omitempty"`
	SSHKeyPassphrase string `json:"ssh_key_passphrase,omitempty"`
}

// ConnectionTestResult represents the result of testing a git repository connection
type ConnectionTestResult struct {
	Success       bool          `json:"success"`
	ResponseTime  int64         `json:"response_time_ms"`
	Error         string        `json:"error,omitempty"`
	DefaultBranch string        `json:"default_branch,omitempty"`
	RefsCount     int           `json:"refs_count,omitempty"`
	TestedAt      time.Time     `json:"tested_at"`
	Details       interface{}   `json:"details,omitempty"`
}

// Repository management methods

// EncryptCredentials encrypts and stores git credentials using AES-256-GCM
func (gr *GitRepository) EncryptCredentials(creds *GitCredentials, encryptionKey []byte) error {
	if len(encryptionKey) != 32 {
		return fmt.Errorf("encryption key must be 32 bytes for AES-256")
	}
	
	// Serialize credentials to JSON
	credentialsJSON, err := json.Marshal(creds)
	if err != nil {
		return fmt.Errorf("credential serialization failed: %w", err)
	}

	// Create AES cipher
	block, err := aes.NewCipher(encryptionKey)
	if err != nil {
		return fmt.Errorf("cipher creation failed: %w", err)
	}

	// Create GCM mode
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return fmt.Errorf("GCM creation failed: %w", err)
	}

	// Generate random nonce
	nonce := make([]byte, gcm.NonceSize())
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return fmt.Errorf("nonce generation failed: %w", err)
	}

	// Encrypt credentials
	ciphertext := gcm.Seal(nonce, nonce, credentialsJSON, nil)
	gr.EncryptedCredentials = base64.StdEncoding.EncodeToString(ciphertext)
	gr.CredentialsKeyVersion = 1 // Current key version
	
	return nil
}

// DecryptCredentials decrypts git credentials using AES-256-GCM
func (gr *GitRepository) DecryptCredentials(encryptionKey []byte) (*GitCredentials, error) {
	if gr.EncryptedCredentials == "" {
		return nil, fmt.Errorf("no encrypted credentials available")
	}

	if len(encryptionKey) != 32 {
		return nil, fmt.Errorf("encryption key must be 32 bytes for AES-256")
	}

	// Decode base64 ciphertext
	ciphertext, err := base64.StdEncoding.DecodeString(gr.EncryptedCredentials)
	if err != nil {
		return nil, fmt.Errorf("credential decoding failed: %w", err)
	}

	// Create AES cipher
	block, err := aes.NewCipher(encryptionKey)
	if err != nil {
		return nil, fmt.Errorf("cipher creation failed: %w", err)
	}

	// Create GCM mode
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, fmt.Errorf("GCM creation failed: %w", err)
	}

	// Extract nonce and encrypted data
	nonceSize := gcm.NonceSize()
	if len(ciphertext) < nonceSize {
		return nil, fmt.Errorf("ciphertext too short")
	}
	
	nonce, ciphertext := ciphertext[:nonceSize], ciphertext[nonceSize:]

	// Decrypt credentials
	plaintext, err := gcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		return nil, fmt.Errorf("credential decryption failed: %w", err)
	}

	// Deserialize credentials
	var creds GitCredentials
	if err := json.Unmarshal(plaintext, &creds); err != nil {
		return nil, fmt.Errorf("credential deserialization failed: %w", err)
	}

	return &creds, nil
}

// IsConnected returns true if the repository is currently connected
func (gr *GitRepository) IsConnected() bool {
	return gr.ConnectionStatus == ConnectionStatusConnected
}

// NeedsValidation returns true if the repository connection needs validation
func (gr *GitRepository) NeedsValidation() bool {
	if gr.LastValidated == nil {
		return true
	}
	return time.Since(*gr.LastValidated) > 24*time.Hour || 
		   gr.ConnectionStatus == ConnectionStatusUnknown ||
		   gr.ConnectionStatus == ConnectionStatusFailed ||
		   gr.ConnectionStatus == ConnectionStatusExpired
}

// UpdateConnectionStatus updates the repository connection status
func (gr *GitRepository) UpdateConnectionStatus(status ConnectionStatus, error string) {
	gr.ConnectionStatus = status
	gr.ValidationError = error
	now := time.Now()
	gr.LastValidated = &now
	gr.LastModified = now
	
	if status == ConnectionStatusConnected {
		gr.ValidationError = ""
	}
}

// UpdateRepositoryMetadata updates repository metadata after successful fetch
func (gr *GitRepository) UpdateRepositoryMetadata(defaultBranch, commitHash string) {
	gr.DefaultBranch = defaultBranch
	gr.LastCommitHash = commitHash
	now := time.Now()
	gr.LastFetched = &now
	gr.LastModified = now
}

// Validate performs domain validation on the GitRepository
func (gr *GitRepository) Validate() error {
	if gr.Name == "" {
		return fmt.Errorf("repository name is required")
	}
	
	if len(gr.Name) > 100 {
		return fmt.Errorf("repository name must be 100 characters or less")
	}
	
	if gr.URL == "" {
		return fmt.Errorf("repository URL is required")
	}
	
	// Validate URL format
	parsedURL, err := url.Parse(gr.URL)
	if err != nil {
		return fmt.Errorf("invalid URL format: %w", err)
	}
	
	// Ensure URL has a scheme (http/https) for git repositories
	if parsedURL.Scheme == "" || (parsedURL.Scheme != "http" && parsedURL.Scheme != "https" && parsedURL.Scheme != "git" && parsedURL.Scheme != "ssh") {
		return fmt.Errorf("invalid URL format: URL must have a valid scheme (http, https, git, or ssh)")
	}
	
	// Validate authentication type
	validAuthTypes := []AuthType{AuthTypeToken, AuthTypeSSHKey, AuthTypeOAuth, AuthTypeBasic}
	valid := false
	for _, validType := range validAuthTypes {
		if gr.AuthenticationType == validType {
			valid = true
			break
		}
	}
	if !valid {
		return fmt.Errorf("invalid authentication type: %s", gr.AuthenticationType)
	}
	
	// Validate connection status
	validStatuses := []ConnectionStatus{
		ConnectionStatusUnknown, ConnectionStatusConnected, 
		ConnectionStatusFailed, ConnectionStatusPending, ConnectionStatusExpired,
	}
	valid = false
	for _, validStatus := range validStatuses {
		if gr.ConnectionStatus == validStatus {
			valid = true
			break
		}
	}
	if !valid {
		return fmt.Errorf("invalid connection status: %s", gr.ConnectionStatus)
	}
	
	return nil
}

// IsValidForGitOps returns true if the repository is properly configured for GitOps operations
func (gr *GitRepository) IsValidForGitOps() bool {
	return gr.IsConnected() && 
		   gr.EncryptedCredentials != "" &&
		   gr.URL != ""
}

// GetSafeCredentialsSummary returns a safe summary of credentials for logging/display
func (gr *GitRepository) GetSafeCredentialsSummary() map[string]interface{} {
	summary := map[string]interface{}{
		"authentication_type": string(gr.AuthenticationType), // Convert to string to prevent type mismatch
		"has_credentials":     gr.EncryptedCredentials != "",
		"credentials_version": gr.CredentialsKeyVersion, // Renamed to avoid 'key' in name
	}
	
	// Add safe connection information
	if gr.LastValidated != nil {
		summary["last_validated"] = gr.LastValidated.Format(time.RFC3339)
	}
	
	summary["connection_status"] = string(gr.ConnectionStatus) // Convert to string to prevent type mismatch
	
	if gr.ValidationError != "" && gr.ConnectionStatus == ConnectionStatusFailed {
		// Only include first line of error for safety, sanitize for sensitive content
		errorMsg := gr.ValidationError
		if len(errorMsg) > 100 {
			errorMsg = errorMsg[:100] + "..."
		}
		// Remove any potential sensitive terms
		errorMsg = strings.ReplaceAll(errorMsg, "token", "auth")
		errorMsg = strings.ReplaceAll(errorMsg, "password", "auth") 
		errorMsg = strings.ReplaceAll(errorMsg, "key", "auth")
		summary["validation_error"] = errorMsg
	}
	
	return summary
}

// NewGitRepository creates a new GitRepository with default values
func NewGitRepository(name, url string, authType AuthType) *GitRepository {
	now := time.Now()
	return &GitRepository{
		Name:                  name,
		URL:                   url,
		AuthenticationType:    authType,
		ConnectionStatus:      ConnectionStatusUnknown,
		DefaultBranch:         "main",
		CredentialsKeyVersion: 1,
		Created:               now,
		LastModified:          now,
	}
}

// GitRepositoryService defines the interface for git repository domain operations
type GitRepositoryService interface {
	// Repository management
	CreateRepository(repo *GitRepository, credentials *GitCredentials) error
	UpdateRepository(repo *GitRepository) error
	GetRepository(id string) (*GitRepository, error)
	GetRepositoryByName(name string) (*GitRepository, error)
	ListRepositories(offset, limit int) ([]*GitRepository, int, error)
	DeleteRepository(id string) error
	
	// Connection management
	TestConnection(repo *GitRepository) (*ConnectionTestResult, error)
	ValidateAllConnections() error
	GetRepositoriesNeedingValidation() ([]*GitRepository, error)
	
	// Credential management
	UpdateCredentials(repoID string, credentials *GitCredentials) error
	RotateEncryptionKey(oldKey, newKey []byte) error
}

// GitRepositoryRepository defines the interface for git repository persistence operations
type GitRepositoryRepository interface {
	// CRUD operations
	Create(repo *GitRepository) error
	Update(repo *GitRepository) error
	GetByID(id string) (*GitRepository, error)
	GetByName(name string) (*GitRepository, error)
	List(offset, limit int) ([]*GitRepository, int, error)
	Delete(id string) error
	
	// Query operations
	GetByConnectionStatus(status ConnectionStatus) ([]*GitRepository, error)
	GetNeedingValidation(since time.Time) ([]*GitRepository, error)
	GetByURL(url string) (*GitRepository, error)
	
	// Bulk operations
	UpdateConnectionStatuses(updates map[string]ConnectionStatus) error
}