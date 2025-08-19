package services

import (
	"context"
	"crypto/rand"
	"testing"
	"time"
)

// FORGE Movement 3: Git Authentication Service Integration Tests
// GREEN PHASE: These tests verify the real implementation works correctly
// Following FORGE methodology with real implementation validation

// TestGitAuthenticationServiceImpl_RealImplementation tests the actual implementation
func TestGitAuthenticationServiceImpl_RealImplementation(t *testing.T) {
	// Generate a test encryption key
	encryptionKey := make([]byte, 32)
	_, err := rand.Read(encryptionKey)
	if err != nil {
		t.Fatalf("Failed to generate encryption key: %v", err)
	}

	// Create real implementation
	authService := NewGitAuthenticationService(encryptionKey)

	ctx := context.Background()

	// Test 1: Encrypt and decrypt credentials round-trip
	t.Run("GitHub Token Round-trip", func(t *testing.T) {
		originalCreds := map[string]interface{}{
			"token": "ghp_test1234567890abcdef1234567890abcdef12",
		}

		// Encrypt
		start := time.Now()
		encrypted, err := authService.EncryptCredentials(ctx, "personal_access_auth", originalCreds)
		encryptTime := time.Since(start)

		if err != nil {
			t.Fatalf("❌ FORGE FAIL: Encryption failed: %v", err)
		}

		if encrypted == "" {
			t.Fatalf("❌ FORGE FAIL: Encrypted data is empty")
		}

		// Decrypt
		start = time.Now()
		decrypted, err := authService.DecryptCredentials(ctx, encrypted)
		decryptTime := time.Since(start)

		if err != nil {
			t.Fatalf("❌ FORGE FAIL: Decryption failed: %v", err)
		}

		// Verify round-trip integrity
		if decrypted["type"] != "personal_access_auth" {
			t.Errorf("❌ FORGE FAIL: Auth type mismatch: expected 'personal_access_auth', got '%v'", decrypted["type"])
		}

		if decrypted["token"] != originalCreds["token"] {
			t.Errorf("❌ FORGE FAIL: Token mismatch after round-trip")
		}

		// Performance validation
		maxEncryptTime := 100 * time.Millisecond
		maxDecryptTime := 100 * time.Millisecond

		if encryptTime > maxEncryptTime {
			t.Errorf("❌ FORGE FAIL: Encryption too slow: %v (max: %v)", encryptTime, maxEncryptTime)
		}

		if decryptTime > maxDecryptTime {
			t.Errorf("❌ FORGE FAIL: Decryption too slow: %v (max: %v)", decryptTime, maxDecryptTime)
		}

		// Security validation: ensure no plaintext in encrypted output
		if containsPlaintext(encrypted, originalCreds["token"].(string)) {
			t.Errorf("❌ FORGE SECURITY FAIL: Plaintext token found in encrypted output")
		}

		t.Logf("✅ FORGE EVIDENCE: GitHub Token Round-trip")
		t.Logf("🔐 Encrypt time: %v", encryptTime)
		t.Logf("🔓 Decrypt time: %v", decryptTime)
		t.Logf("📊 Encrypted data length: %d bytes", len(encrypted))
	})

	// Test 2: SSH Key credentials
	t.Run("SSH Key Round-trip", func(t *testing.T) {
		originalCreds := map[string]interface{}{
			"ssh_key":           "-----BEGIN OPENSSH PRIVATE KEY-----\ntest-ssh-key-content\n-----END OPENSSH PRIVATE KEY-----",
			"ssh_key_passphrase": "test-passphrase",
		}

		encrypted, err := authService.EncryptCredentials(ctx, "ssh_auth", originalCreds)
		if err != nil {
			t.Fatalf("❌ FORGE FAIL: SSH key encryption failed: %v", err)
		}

		decrypted, err := authService.DecryptCredentials(ctx, encrypted)
		if err != nil {
			t.Fatalf("❌ FORGE FAIL: SSH key decryption failed: %v", err)
		}

		if decrypted["type"] != "ssh_auth" {
			t.Errorf("❌ FORGE FAIL: SSH auth type mismatch")
		}

		if decrypted["ssh_key"] != originalCreds["ssh_key"] {
			t.Errorf("❌ FORGE FAIL: SSH key mismatch after round-trip")
		}

		if decrypted["ssh_key_passphrase"] != originalCreds["ssh_key_passphrase"] {
			t.Errorf("❌ FORGE FAIL: SSH passphrase mismatch after round-trip")
		}

		t.Logf("✅ FORGE EVIDENCE: SSH Key Round-trip successful")
	})

	// Test 3: Credential validation
	t.Run("Credential Validation", func(t *testing.T) {
		testCases := []struct {
			name          string
			repoURL       string
			credentials   map[string]interface{}
			expectError   bool
			errorContains string
		}{
			{
				name:    "Valid GitHub Token",
				repoURL: "https://github.com/enterprise/repo.git",
				credentials: map[string]interface{}{
					"type":  "personal_access_auth",
					"token": "test-valid-token-1234567890",
				},
				expectError: false,
			},
			{
				name:    "Valid SSH Key",
				repoURL: "git@github.com:enterprise/repo.git",
				credentials: map[string]interface{}{
					"type":    "ssh_auth",
					"ssh_key": "-----BEGIN OPENSSH PRIVATE KEY-----\ntest-content\n-----END OPENSSH PRIVATE KEY-----",
				},
				expectError: false,
			},
			{
				name:    "Invalid Token Format",
				repoURL: "https://github.com/enterprise/repo.git",
				credentials: map[string]interface{}{
					"type":  "personal_access_auth",
					"token": "short",
				},
				expectError:   true,
				errorContains: "invalid token format",
			},
			{
				name:    "Missing Token",
				repoURL: "https://github.com/enterprise/repo.git",
				credentials: map[string]interface{}{
					"type": "personal_access_auth",
				},
				expectError:   true,
				errorContains: "token missing or empty",
			},
			{
				name:    "Invalid SSH Key",
				repoURL: "git@github.com:enterprise/repo.git",
				credentials: map[string]interface{}{
					"type":    "ssh_auth",
					"ssh_key": "invalid-key-format",
				},
				expectError:   true,
				errorContains: "invalid SSH key format",
			},
		}

		for _, tc := range testCases {
			t.Run(tc.name, func(t *testing.T) {
				start := time.Now()
				err := authService.ValidateCredentials(ctx, tc.repoURL, tc.credentials)
				validateTime := time.Since(start)

				if tc.expectError && err == nil {
					t.Errorf("❌ FORGE FAIL: Expected validation error but got none")
				}

				if !tc.expectError && err != nil {
					t.Errorf("❌ FORGE FAIL: Unexpected validation error: %v", err)
				}

				if tc.expectError && err != nil && tc.errorContains != "" {
					if !containsString(err.Error(), tc.errorContains) {
						t.Errorf("❌ FORGE FAIL: Expected error to contain '%s', got '%s'", tc.errorContains, err.Error())
					}
				}

				// Performance validation
				maxValidateTime := 200 * time.Millisecond
				if validateTime > maxValidateTime {
					t.Errorf("❌ FORGE FAIL: Validation too slow: %v (max: %v)", validateTime, maxValidateTime)
				}

				t.Logf("✅ FORGE EVIDENCE: %s - Validation time: %v", tc.name, validateTime)
			})
		}
	})

	// Test 4: Token refresh
	t.Run("Token Refresh", func(t *testing.T) {
		testCases := []struct {
			name         string
			repoURL      string
			refreshToken string
			expectError  bool
			errorContains string
		}{
			{
				name:         "Valid Refresh Token",
				repoURL:      "https://github.com/enterprise/repo.git",
				refreshToken: "valid-refresh-token-12345",
				expectError:  false,
			},
			{
				name:         "Azure DevOps Refresh",
				repoURL:      "https://dev.azure.com/enterprise/project/_git/repo",
				refreshToken: "azure-refresh-token-67890",
				expectError:  false,
			},
			{
				name:          "Invalid Refresh Token",
				repoURL:       "https://github.com/enterprise/repo.git",
				refreshToken:  "invalid",
				expectError:   true,
				errorContains: "invalid refresh token",
			},
			{
				name:          "Empty Refresh Token",
				repoURL:       "https://github.com/enterprise/repo.git",
				refreshToken:  "",
				expectError:   true,
				errorContains: "refresh token is required",
			},
		}

		for _, tc := range testCases {
			t.Run(tc.name, func(t *testing.T) {
				start := time.Now()
				result, err := authService.RefreshToken(ctx, tc.repoURL, tc.refreshToken)
				refreshTime := time.Since(start)

				if tc.expectError && err == nil {
					t.Errorf("❌ FORGE FAIL: Expected refresh error but got none")
				}

				if !tc.expectError && err != nil {
					t.Errorf("❌ FORGE FAIL: Unexpected refresh error: %v", err)
				}

				if tc.expectError && err != nil && tc.errorContains != "" {
					if !containsString(err.Error(), tc.errorContains) {
						t.Errorf("❌ FORGE FAIL: Expected error to contain '%s', got '%s'", tc.errorContains, err.Error())
					}
				}

				if !tc.expectError && result != nil {
					// Validate token result structure
					if result.AccessToken == "" {
						t.Errorf("❌ FORGE FAIL: Access token is empty")
					}
					if result.TokenType != "Bearer" {
						t.Errorf("❌ FORGE FAIL: Expected token type 'Bearer', got '%s'", result.TokenType)
					}
					if result.ExpiresAt.Before(time.Now()) {
						t.Errorf("❌ FORGE FAIL: Token expires in the past")
					}
					if len(result.AccessToken) < 20 {
						t.Errorf("❌ FORGE FAIL: Access token seems too short")
					}
				}

				// Performance validation
				maxRefreshTime := 300 * time.Millisecond
				if refreshTime > maxRefreshTime {
					t.Errorf("❌ FORGE FAIL: Token refresh too slow: %v (max: %v)", refreshTime, maxRefreshTime)
				}

				t.Logf("✅ FORGE EVIDENCE: %s - Refresh time: %v", tc.name, refreshTime)
				if result != nil {
					t.Logf("🎫 Token type: %s", result.TokenType)
					t.Logf("⏰ Expires at: %v", result.ExpiresAt)
					t.Logf("🔐 Access token length: %d", len(result.AccessToken))
				}
			})
		}
	})
}

// Helper functions

func containsPlaintext(encrypted, plaintext string) bool {
	return len(plaintext) > 0 && containsString(encrypted, plaintext)
}

func containsString(haystack, needle string) bool {
	return len(needle) > 0 && indexOf(haystack, needle) >= 0
}

func indexOf(haystack, needle string) int {
	for i := 0; i <= len(haystack)-len(needle); i++ {
		if haystack[i:i+len(needle)] == needle {
			return i
		}
	}
	return -1
}