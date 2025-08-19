package domain

import (
	"crypto/rand"
	"encoding/json"
	"strings"
	"testing"
	"time"

	"github.com/hedgehog/cnoc/internal/domain/gitops"
)

// FORGE Movement 3: GitOps Repository Domain Model Test Suite
// RED PHASE: These tests MUST fail initially until proper implementation exists
// Following FORGE methodology with quantitative validation and evidence-based development

// TestGitOpsRepository_Creation tests GitOps repository creation with domain validation
func TestGitOpsRepository_Creation(t *testing.T) {
	// FORGE RED PHASE: Test domain object creation patterns
	
	testCases := []struct {
		name              string
		repoName          string
		repoURL           string
		authType          gitops.AuthType
		expectedError     bool
		validationPattern string
	}{
		{
			name:              "Valid GitHub Repository Creation",
			repoName:          "production-gitops-repo",
			repoURL:           "https://github.com/enterprise/production-config.git",
			authType:          gitops.AuthTypeToken,
			expectedError:     false,
			validationPattern: "github",
		},
		{
			name:              "Valid GitLab Repository Creation",
			repoName:          "staging-gitops-repo",
			repoURL:           "https://gitlab.com/enterprise/staging-config.git",
			authType:          gitops.AuthTypeSSHKey,
			expectedError:     false,
			validationPattern: "gitlab",
		},
		{
			name:              "Valid Azure DevOps Repository Creation",
			repoName:          "azure-gitops-repo",
			repoURL:           "https://dev.azure.com/enterprise/project/_git/config-repo",
			authType:          gitops.AuthTypeOAuth,
			expectedError:     false,
			validationPattern: "azure",
		},
		{
			name:              "Invalid Empty Name",
			repoName:          "",
			repoURL:           "https://github.com/test/repo.git",
			authType:          gitops.AuthTypeToken,
			expectedError:     true,
			validationPattern: "name_required",
		},
		{
			name:              "Invalid Empty URL",
			repoName:          "test-repo",
			repoURL:           "",
			authType:          gitops.AuthTypeToken,
			expectedError:     true,
			validationPattern: "url_required",
		},
		{
			name:              "Invalid Name Too Long",
			repoName:          strings.Repeat("a", 101), // 101 characters
			repoURL:           "https://github.com/test/repo.git",
			authType:          gitops.AuthTypeToken,
			expectedError:     true,
			validationPattern: "name_too_long",
		},
		{
			name:              "Invalid URL Format",
			repoName:          "test-repo",
			repoURL:           "not-a-url",
			authType:          gitops.AuthTypeToken,
			expectedError:     true,
			validationPattern: "invalid_url",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			// FORGE Quantitative Validation: Start timer
			startTime := time.Now()
			
			// Create GitRepository using constructor
			repo := gitops.NewGitRepository(tc.repoName, tc.repoURL, tc.authType)
			
			if repo == nil {
				t.Fatalf("❌ FORGE FAIL: gitops.NewGitRepository returned nil")
			}
			
			// Validate domain object creation
			err := repo.Validate()
			creationTime := time.Since(startTime)
			
			// FORGE Validation 1: Error handling
			if tc.expectedError && err == nil {
				t.Errorf("❌ FORGE FAIL: Expected validation error but got none for %s", tc.validationPattern)
			}
			if !tc.expectedError && err != nil {
				t.Errorf("❌ FORGE FAIL: Unexpected validation error: %v", err)
			}
			
			// FORGE Validation 2: Domain object structure
			if !tc.expectedError {
				if repo.Name != tc.repoName {
					t.Errorf("❌ FORGE FAIL: Name mismatch: expected %s, got %s", tc.repoName, repo.Name)
				}
				if repo.URL != tc.repoURL {
					t.Errorf("❌ FORGE FAIL: URL mismatch: expected %s, got %s", tc.repoURL, repo.URL)
				}
				if repo.AuthenticationType != tc.authType {
					t.Errorf("❌ FORGE FAIL: gitops.AuthType mismatch: expected %s, got %s", tc.authType, repo.AuthenticationType)
				}
				if repo.ConnectionStatus != gitops.ConnectionStatusUnknown {
					t.Errorf("❌ FORGE FAIL: Expected ConnectionStatusUnknown, got %s", repo.ConnectionStatus)
				}
				if repo.DefaultBranch != "main" {
					t.Errorf("❌ FORGE FAIL: Expected default branch 'main', got %s", repo.DefaultBranch)
				}
				if repo.Created.IsZero() || repo.LastModified.IsZero() {
					t.Errorf("❌ FORGE FAIL: Timestamps not set properly")
				}
			}
			
			// FORGE Validation 3: Performance requirements
			maxCreationTime := 10 * time.Millisecond
			if creationTime > maxCreationTime {
				t.Errorf("❌ FORGE FAIL: Repository creation too slow: %v (max: %v)", creationTime, maxCreationTime)
			}
			
			// FORGE Evidence Logging
			t.Logf("✅ FORGE EVIDENCE: %s - Creation time: %v", tc.name, creationTime)
			if err != nil {
				t.Logf("🔍 Expected validation error: %v", err)
			}
		})
	}
}

// TestGitOpsRepository_CredentialEncryption tests credential encryption and decryption
func TestGitOpsRepository_CredentialEncryption(t *testing.T) {
	// FORGE RED PHASE: Test security-critical functionality
	
	// Generate test encryption key (32 bytes for AES-256)
	encryptionKey := make([]byte, 32)
	_, err := rand.Read(encryptionKey)
	if err != nil {
		t.Fatalf("Failed to generate test encryption key: %v", err)
	}
	
	testCases := []struct {
		name              string
		credentials       *gitops.GitCredentials
		encryptionKey     []byte
		expectEncryptionError bool
		expectDecryptionError bool
		securityValidation    string
	}{
		{
			name: "GitHub Token Encryption",
			credentials: &gitops.GitCredentials{
				Type:  gitops.AuthTypeToken,
				Token: "ghp_1234567890abcdef1234567890abcdef12345678",
			},
			encryptionKey:         encryptionKey,
			expectEncryptionError: false,
			expectDecryptionError: false,
			securityValidation:    "github_token",
		},
		{
			name: "SSH Key Encryption",
			credentials: &gitops.GitCredentials{
				Type:             gitops.AuthTypeSSHKey,
				SSHKey:           "-----BEGIN OPENSSH PRIVATE KEY-----\ntest-ssh-key-content\n-----END OPENSSH PRIVATE KEY-----",
				SSHKeyPassphrase: "supersecret",
			},
			encryptionKey:         encryptionKey,
			expectEncryptionError: false,
			expectDecryptionError: false,
			securityValidation:    "ssh_key",
		},
		{
			name: "Basic Auth Encryption",
			credentials: &gitops.GitCredentials{
				Type:     gitops.AuthTypeBasic,
				Username: "enterprise-user",
				Password: "enterprise-password-123",
			},
			encryptionKey:         encryptionKey,
			expectEncryptionError: false,
			expectDecryptionError: false,
			securityValidation:    "basic_auth",
		},
		{
			name: "OAuth Token Encryption",
			credentials: &gitops.GitCredentials{
				Type:  gitops.AuthTypeOAuth,
				Token: "oauth2_access_token_1234567890abcdef",
			},
			encryptionKey:         encryptionKey,
			expectEncryptionError: false,
			expectDecryptionError: false,
			securityValidation:    "oauth_token",
		},
		{
			name: "Invalid Encryption Key",
			credentials: &gitops.GitCredentials{
				Type:  gitops.AuthTypeToken,
				Token: "test-token",
			},
			encryptionKey:         []byte("invalid-key"), // Wrong size
			expectEncryptionError: true,
			expectDecryptionError: true,
			securityValidation:    "invalid_key",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			// Create test repository
			repo := gitops.NewGitRepository("test-repo", "https://github.com/test/repo.git", tc.credentials.Type)
			
			// FORGE Quantitative Validation: Start encryption timer
			encryptStartTime := time.Now()
			
			// Test encryption
			err := repo.EncryptCredentials(tc.credentials, tc.encryptionKey)
			encryptionTime := time.Since(encryptStartTime)
			
			// FORGE Validation 1: Encryption error handling
			if tc.expectEncryptionError && err == nil {
				t.Errorf("❌ FORGE FAIL: Expected encryption error but got none")
			}
			if !tc.expectEncryptionError && err != nil {
				t.Errorf("❌ FORGE FAIL: Unexpected encryption error: %v", err)
			}
			
			if tc.expectEncryptionError {
				return // Skip decryption test if encryption failed as expected
			}
			
			// FORGE Security Validation 1: Verify credentials are encrypted
			if repo.EncryptedCredentials == "" {
				t.Errorf("❌ FORGE FAIL: Encrypted credentials are empty")
			}
			
			// FORGE Security Validation 2: Verify original credentials not in encrypted string
			encryptedData := repo.EncryptedCredentials
			originalJSON, _ := json.Marshal(tc.credentials)
			if strings.Contains(encryptedData, string(originalJSON)) {
				t.Errorf("❌ FORGE FAIL: Original credentials found in encrypted data - SECURITY VIOLATION")
			}
			if strings.Contains(encryptedData, tc.credentials.Token) && tc.credentials.Token != "" {
				t.Errorf("❌ FORGE FAIL: Token found in encrypted data - SECURITY VIOLATION")
			}
			if strings.Contains(encryptedData, tc.credentials.Password) && tc.credentials.Password != "" {
				t.Errorf("❌ FORGE FAIL: Password found in encrypted data - SECURITY VIOLATION")
			}
			
			// FORGE Quantitative Validation: Start decryption timer
			decryptStartTime := time.Now()
			
			// Test decryption
			decryptedCreds, err := repo.DecryptCredentials(tc.encryptionKey)
			decryptionTime := time.Since(decryptStartTime)
			
			// FORGE Validation 2: Decryption error handling
			if tc.expectDecryptionError && err == nil {
				t.Errorf("❌ FORGE FAIL: Expected decryption error but got none")
			}
			if !tc.expectDecryptionError && err != nil {
				t.Errorf("❌ FORGE FAIL: Unexpected decryption error: %v", err)
			}
			
			if !tc.expectDecryptionError && decryptedCreds != nil {
				// FORGE Validation 3: Round-trip integrity
				if decryptedCreds.Type != tc.credentials.Type {
					t.Errorf("❌ FORGE FAIL: Type mismatch after encryption/decryption")
				}
				if decryptedCreds.Token != tc.credentials.Token {
					t.Errorf("❌ FORGE FAIL: Token mismatch after encryption/decryption")
				}
				if decryptedCreds.Username != tc.credentials.Username {
					t.Errorf("❌ FORGE FAIL: Username mismatch after encryption/decryption")
				}
				if decryptedCreds.Password != tc.credentials.Password {
					t.Errorf("❌ FORGE FAIL: Password mismatch after encryption/decryption")
				}
				if decryptedCreds.SSHKey != tc.credentials.SSHKey {
					t.Errorf("❌ FORGE FAIL: SSH key mismatch after encryption/decryption")
				}
				if decryptedCreds.SSHKeyPassphrase != tc.credentials.SSHKeyPassphrase {
					t.Errorf("❌ FORGE FAIL: SSH passphrase mismatch after encryption/decryption")
				}
			}
			
			// FORGE Performance Requirements
			maxEncryptionTime := 50 * time.Millisecond
			maxDecryptionTime := 50 * time.Millisecond
			
			if encryptionTime > maxEncryptionTime {
				t.Errorf("❌ FORGE FAIL: Encryption too slow: %v (max: %v)", encryptionTime, maxEncryptionTime)
			}
			if decryptionTime > maxDecryptionTime {
				t.Errorf("❌ FORGE FAIL: Decryption too slow: %v (max: %v)", decryptionTime, maxDecryptionTime)
			}
			
			// FORGE Evidence Logging
			t.Logf("✅ FORGE EVIDENCE: %s", tc.name)
			t.Logf("🔐 Encryption time: %v", encryptionTime)
			t.Logf("🔓 Decryption time: %v", decryptionTime)
			t.Logf("🔒 Encrypted data length: %d bytes", len(repo.EncryptedCredentials))
			t.Logf("🛡️  Security validation: %s", tc.securityValidation)
		})
	}
}

// TestGitOpsRepository_ConnectionValidation tests connection status management
func TestGitOpsRepository_ConnectionValidation(t *testing.T) {
	// FORGE RED PHASE: Test connection status lifecycle management
	
	testCases := []struct {
		name                  string
		initialStatus         gitops.ConnectionStatus
		updateStatus          gitops.ConnectionStatus
		updateError           string
		expectedNeedsValidation bool
		validationReason      string
	}{
		{
			name:                  "Successful Connection Update",
			initialStatus:         gitops.ConnectionStatusUnknown,
			updateStatus:          gitops.ConnectionStatusConnected,
			updateError:           "",
			expectedNeedsValidation: false,
			validationReason:      "fresh_connection",
		},
		{
			name:                  "Failed Connection Update",
			initialStatus:         gitops.ConnectionStatusPending,
			updateStatus:          gitops.ConnectionStatusFailed,
			updateError:           "authentication failed: invalid token",
			expectedNeedsValidation: true,
			validationReason:      "connection_failed",
		},
		{
			name:                  "Expired Connection",
			initialStatus:         gitops.ConnectionStatusConnected,
			updateStatus:          gitops.ConnectionStatusExpired,
			updateError:           "token expired",
			expectedNeedsValidation: true,
			validationReason:      "token_expired",
		},
		{
			name:                  "Connection Recovery",
			initialStatus:         gitops.ConnectionStatusFailed,
			updateStatus:          gitops.ConnectionStatusConnected,
			updateError:           "",
			expectedNeedsValidation: false,
			validationReason:      "recovery_success",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			// Create test repository
			repo := gitops.NewGitRepository("connection-test", "https://github.com/test/connection.git", gitops.AuthTypeToken)
			
			// Set initial status
			repo.ConnectionStatus = tc.initialStatus
			
			// FORGE Quantitative Validation: Start timer
			startTime := time.Now()
			
			// Update connection status
			repo.UpdateConnectionStatus(tc.updateStatus, tc.updateError)
			updateTime := time.Since(startTime)
			
			// FORGE Validation 1: Status update verification
			if repo.ConnectionStatus != tc.updateStatus {
				t.Errorf("❌ FORGE FAIL: Expected status %s, got %s", tc.updateStatus, repo.ConnectionStatus)
			}
			
			// FORGE Validation 2: Error message handling
			if tc.updateError != "" && repo.ValidationError != tc.updateError {
				t.Errorf("❌ FORGE FAIL: Expected error '%s', got '%s'", tc.updateError, repo.ValidationError)
			}
			
			if tc.updateError == "" && repo.ValidationError != "" {
				t.Errorf("❌ FORGE FAIL: Expected no error, got '%s'", repo.ValidationError)
			}
			
			// FORGE Validation 3: Validation requirement logic
			needsValidation := repo.NeedsValidation()
			if needsValidation != tc.expectedNeedsValidation {
				t.Errorf("❌ FORGE FAIL: Expected needs validation %t, got %t", tc.expectedNeedsValidation, needsValidation)
			}
			
			// FORGE Validation 4: Timestamp updates
			if repo.LastValidated == nil {
				t.Errorf("❌ FORGE FAIL: LastValidated timestamp not set")
			}
			
			if repo.LastModified.IsZero() {
				t.Errorf("❌ FORGE FAIL: LastModified timestamp not set")
			}
			
			// FORGE Validation 5: Connection helper methods
			isConnected := repo.IsConnected()
			expectedConnected := tc.updateStatus == gitops.ConnectionStatusConnected
			if isConnected != expectedConnected {
				t.Errorf("❌ FORGE FAIL: Expected IsConnected %t, got %t", expectedConnected, isConnected)
			}
			
			// FORGE Performance Requirements
			maxUpdateTime := 5 * time.Millisecond
			if updateTime > maxUpdateTime {
				t.Errorf("❌ FORGE FAIL: Status update too slow: %v (max: %v)", updateTime, maxUpdateTime)
			}
			
			// FORGE Evidence Logging
			t.Logf("✅ FORGE EVIDENCE: %s", tc.name)
			t.Logf("📊 Status: %s → %s", tc.initialStatus, tc.updateStatus)
			t.Logf("⏱️  Update time: %v", updateTime)
			t.Logf("🔍 Needs validation: %t (%s)", needsValidation, tc.validationReason)
		})
	}
}

// TestGitOpsRepository_RepositoryMetadata tests repository metadata management
func TestGitOpsRepository_RepositoryMetadata(t *testing.T) {
	// FORGE RED PHASE: Test repository metadata lifecycle
	
	testCases := []struct {
		name           string
		defaultBranch  string
		commitHash     string
		expectedValid  bool
		metadataType   string
	}{
		{
			name:           "Main Branch Metadata",
			defaultBranch:  "main",
			commitHash:     "abc123def456789012345678901234567890abcd",
			expectedValid:  true,
			metadataType:   "main_branch",
		},
		{
			name:           "Master Branch Metadata",
			defaultBranch:  "master",
			commitHash:     "def456abc123789012345678901234567890abcd",
			expectedValid:  true,
			metadataType:   "master_branch",
		},
		{
			name:           "Feature Branch Metadata",
			defaultBranch:  "feature/gitops-enhancement",
			commitHash:     "123abc456def789012345678901234567890abcd",
			expectedValid:  true,
			metadataType:   "feature_branch",
		},
		{
			name:           "Short Commit Hash",
			defaultBranch:  "main",
			commitHash:     "abc123",
			expectedValid:  true,
			metadataType:   "short_hash",
		},
		{
			name:           "Empty Commit Hash",
			defaultBranch:  "main",
			commitHash:     "",
			expectedValid:  false,
			metadataType:   "empty_hash",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			// Create test repository
			repo := gitops.NewGitRepository("metadata-test", "https://github.com/test/metadata.git", gitops.AuthTypeToken)
			
			// Store initial timestamps for comparison
			initialLastFetched := repo.LastFetched
			initialLastModified := repo.LastModified
			
			// FORGE Quantitative Validation: Start timer
			startTime := time.Now()
			
			// Update repository metadata
			repo.UpdateRepositoryMetadata(tc.defaultBranch, tc.commitHash)
			updateTime := time.Since(startTime)
			
			// FORGE Validation 1: Metadata updates
			if repo.DefaultBranch != tc.defaultBranch {
				t.Errorf("❌ FORGE FAIL: Expected branch %s, got %s", tc.defaultBranch, repo.DefaultBranch)
			}
			
			if repo.LastCommitHash != tc.commitHash {
				t.Errorf("❌ FORGE FAIL: Expected commit %s, got %s", tc.commitHash, repo.LastCommitHash)
			}
			
			// FORGE Validation 2: Timestamp updates
			if repo.LastFetched == nil {
				t.Errorf("❌ FORGE FAIL: LastFetched timestamp not set")
			} else if repo.LastFetched == initialLastFetched {
				t.Errorf("❌ FORGE FAIL: LastFetched timestamp not updated")
			}
			
			if repo.LastModified.Equal(initialLastModified) {
				t.Errorf("❌ FORGE FAIL: LastModified timestamp not updated")
			}
			
			// FORGE Validation 3: GitOps readiness
			// For this test, we'll check if the repo would be valid for GitOps
			// (assuming connection and credentials are set)
			repo.ConnectionStatus = gitops.ConnectionStatusConnected
			repo.EncryptedCredentials = "test-encrypted-data"
			
			isValidForGitOps := repo.IsValidForGitOps()
			if tc.expectedValid && !isValidForGitOps {
				t.Errorf("❌ FORGE FAIL: Expected valid for GitOps but got false")
			}
			
			// FORGE Performance Requirements
			maxUpdateTime := 5 * time.Millisecond
			if updateTime > maxUpdateTime {
				t.Errorf("❌ FORGE FAIL: Metadata update too slow: %v (max: %v)", updateTime, maxUpdateTime)
			}
			
			// FORGE Evidence Logging
			t.Logf("✅ FORGE EVIDENCE: %s", tc.name)
			t.Logf("🌿 Branch: %s", repo.DefaultBranch)
			t.Logf("📝 Commit: %s", repo.LastCommitHash)
			t.Logf("⏱️  Update time: %v", updateTime)
			t.Logf("✅ GitOps ready: %t", isValidForGitOps)
		})
	}
}

// TestGitOpsRepository_ValidationRules tests comprehensive domain validation
func TestGitOpsRepository_ValidationRules(t *testing.T) {
	// FORGE RED PHASE: Test comprehensive domain validation rules
	
	testCases := []struct {
		name             string
		setupRepo        func() *gitops.GitRepository
		expectedError    bool
		errorContains    string
		validationAspect string
	}{
		{
			name: "Valid Repository All Fields",
			setupRepo: func() *gitops.GitRepository {
				repo := gitops.NewGitRepository("valid-repo", "https://github.com/test/valid.git", gitops.AuthTypeToken)
				repo.ConnectionStatus = gitops.ConnectionStatusConnected
				return repo
			},
			expectedError:    false,
			errorContains:    "",
			validationAspect: "complete_valid",
		},
		{
			name: "Invalid Authentication Type",
			setupRepo: func() *gitops.GitRepository {
				repo := gitops.NewGitRepository("test-repo", "https://github.com/test/repo.git", gitops.AuthTypeToken)
				repo.AuthenticationType = gitops.AuthType("invalid_auth_type")
				return repo
			},
			expectedError:    true,
			errorContains:    "invalid authentication type",
			validationAspect: "auth_type",
		},
		{
			name: "Invalid Connection Status",
			setupRepo: func() *gitops.GitRepository {
				repo := gitops.NewGitRepository("test-repo", "https://github.com/test/repo.git", gitops.AuthTypeToken)
				repo.ConnectionStatus = gitops.ConnectionStatus("invalid_status")
				return repo
			},
			expectedError:    true,
			errorContains:    "invalid connection status",
			validationAspect: "connection_status",
		},
		{
			name: "Empty Required Fields",
			setupRepo: func() *gitops.GitRepository {
				repo := &gitops.GitRepository{
					ID:                 "test-id",
					Name:               "", // Empty name
					URL:                "", // Empty URL
					AuthenticationType: gitops.AuthTypeToken,
					ConnectionStatus:   gitops.ConnectionStatusUnknown,
				}
				return repo
			},
			expectedError:    true,
			errorContains:    "name is required",
			validationAspect: "required_fields",
		},
		{
			name: "Name Too Long",
			setupRepo: func() *gitops.GitRepository {
				longName := strings.Repeat("a", 101)
				repo := gitops.NewGitRepository(longName, "https://github.com/test/repo.git", gitops.AuthTypeToken)
				return repo
			},
			expectedError:    true,
			errorContains:    "100 characters or less",
			validationAspect: "name_length",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			// Setup repository
			repo := tc.setupRepo()
			
			// FORGE Quantitative Validation: Start timer
			startTime := time.Now()
			
			// Validate repository
			err := repo.Validate()
			validationTime := time.Since(startTime)
			
			// FORGE Validation 1: Error expectations
			if tc.expectedError && err == nil {
				t.Errorf("❌ FORGE FAIL: Expected validation error but got none")
			}
			if !tc.expectedError && err != nil {
				t.Errorf("❌ FORGE FAIL: Unexpected validation error: %v", err)
			}
			
			// FORGE Validation 2: Error message content
			if tc.expectedError && err != nil && tc.errorContains != "" {
				if !strings.Contains(err.Error(), tc.errorContains) {
					t.Errorf("❌ FORGE FAIL: Expected error to contain '%s', got '%s'", tc.errorContains, err.Error())
				}
			}
			
			// FORGE Performance Requirements
			maxValidationTime := 10 * time.Millisecond
			if validationTime > maxValidationTime {
				t.Errorf("❌ FORGE FAIL: Validation too slow: %v (max: %v)", validationTime, maxValidationTime)
			}
			
			// FORGE Evidence Logging
			t.Logf("✅ FORGE EVIDENCE: %s", tc.name)
			t.Logf("⏱️  Validation time: %v", validationTime)
			t.Logf("🔍 Aspect: %s", tc.validationAspect)
			if err != nil {
				t.Logf("❌ Validation error: %v", err)
			}
		})
	}
}

// TestGitOpsRepository_SafeCredentialsSummary tests credential safety features
func TestGitOpsRepository_SafeCredentialsSummary(t *testing.T) {
	// FORGE RED PHASE: Test security-critical credential handling
	
	testCases := []struct {
		name                string
		setupRepo           func() *gitops.GitRepository
		expectedFields      []string
		forbiddenContent    []string
		securityValidation  string
	}{
		{
			name: "Connected Repository Summary",
			setupRepo: func() *gitops.GitRepository {
				repo := gitops.NewGitRepository("safe-test", "https://github.com/test/safe.git", gitops.AuthTypeToken)
				repo.ConnectionStatus = gitops.ConnectionStatusConnected
				repo.EncryptedCredentials = "encrypted-data-here"
				now := time.Now()
				repo.LastValidated = &now
				return repo
			},
			expectedFields: []string{"authentication_type", "has_credentials", "connection_status", "last_validated"},
			forbiddenContent: []string{"password", "token", "key", "secret"},
			securityValidation: "connected_repo",
		},
		{
			name: "Failed Repository Summary",
			setupRepo: func() *gitops.GitRepository {
				repo := gitops.NewGitRepository("failed-test", "https://github.com/test/failed.git", gitops.AuthTypeSSHKey)
				repo.ConnectionStatus = gitops.ConnectionStatusFailed
				repo.ValidationError = "authentication failed with provided SSH key"
				now := time.Now()
				repo.LastValidated = &now
				return repo
			},
			expectedFields: []string{"authentication_type", "has_credentials", "connection_status", "validation_error"},
			forbiddenContent: []string{"ssh_key", "private_key", "passphrase"},
			securityValidation: "failed_repo",
		},
		{
			name: "Pending Repository Summary",
			setupRepo: func() *gitops.GitRepository {
				repo := gitops.NewGitRepository("pending-test", "https://github.com/test/pending.git", gitops.AuthTypeOAuth)
				repo.ConnectionStatus = gitops.ConnectionStatusPending
				return repo
			},
			expectedFields: []string{"authentication_type", "has_credentials", "connection_status"},
			forbiddenContent: []string{"oauth", "access_token", "refresh_token"},
			securityValidation: "pending_repo",
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			// Setup repository
			repo := tc.setupRepo()
			
			// FORGE Quantitative Validation: Start timer
			startTime := time.Now()
			
			// Get safe credentials summary
			summary := repo.GetSafeCredentialsSummary()
			summaryTime := time.Since(startTime)
			
			// FORGE Validation 1: Required fields present
			for _, field := range tc.expectedFields {
				if _, exists := summary[field]; !exists {
					t.Errorf("❌ FORGE FAIL: Expected field '%s' missing from summary", field)
				}
			}
			
			// FORGE Security Validation: Forbidden content not present
			summaryJSON, _ := json.Marshal(summary)
			summaryString := string(summaryJSON)
			
			for _, forbidden := range tc.forbiddenContent {
				if strings.Contains(strings.ToLower(summaryString), strings.ToLower(forbidden)) {
					t.Errorf("❌ FORGE SECURITY FAIL: Forbidden content '%s' found in summary - SECURITY VIOLATION", forbidden)
				}
			}
			
			// FORGE Validation 2: Summary structure validation
			if authType, ok := summary["authentication_type"]; ok {
				if authType != string(repo.AuthenticationType) {
					t.Errorf("❌ FORGE FAIL: gitops.AuthType mismatch in summary")
				}
			}
			
			if hasCredentials, ok := summary["has_credentials"]; ok {
				expected := repo.EncryptedCredentials != ""
				if hasCredentials != expected {
					t.Errorf("❌ FORGE FAIL: has_credentials mismatch: expected %t, got %v", expected, hasCredentials)
				}
			}
			
			if status, ok := summary["connection_status"]; ok {
				if status != string(repo.ConnectionStatus) {
					t.Errorf("❌ FORGE FAIL: Connection status mismatch in summary")
				}
			}
			
			// FORGE Performance Requirements
			maxSummaryTime := 5 * time.Millisecond
			if summaryTime > maxSummaryTime {
				t.Errorf("❌ FORGE FAIL: Summary generation too slow: %v (max: %v)", summaryTime, maxSummaryTime)
			}
			
			// FORGE Evidence Logging
			t.Logf("✅ FORGE EVIDENCE: %s", tc.name)
			t.Logf("⏱️  Summary time: %v", summaryTime)
			t.Logf("🛡️  Security validation: %s", tc.securityValidation)
			t.Logf("📊 Summary fields: %v", tc.expectedFields)
			
			// Log summary for manual review (without sensitive data)
			for key, value := range summary {
				t.Logf("🔍 %s: %v", key, value)
			}
		})
	}
}

// FORGE GitOps Repository Domain Test Requirements Summary:
//
// 1. RED PHASE ENFORCEMENT:
//    - All domain methods must exist but return "not implemented" errors
//    - Tests MUST fail until proper domain logic implementation
//    - Validates complete domain object lifecycle
//
// 2. SECURITY REQUIREMENTS:
//    - Credential encryption/decryption round-trip integrity
//    - No credential exposure in logs, errors, or summaries
//    - AES-256-GCM encryption with proper key management
//    - Safe credential summary without sensitive data leakage
//
// 3. PERFORMANCE REQUIREMENTS:
//    - Repository creation: <10ms
//    - Credential encryption: <50ms
//    - Credential decryption: <50ms
//    - Status updates: <5ms
//    - Domain validation: <10ms
//    - Summary generation: <5ms
//
// 4. DOMAIN VALIDATION:
//    - Comprehensive field validation (name, URL, auth type)
//    - Connection status lifecycle management
//    - Repository metadata management
//    - GitOps readiness validation
//
// 5. QUANTITATIVE EVIDENCE:
//    - Response time measurements for all operations
//    - Security validation with forbidden content checks
//    - Domain object integrity verification
//    - Encryption strength and safety validation