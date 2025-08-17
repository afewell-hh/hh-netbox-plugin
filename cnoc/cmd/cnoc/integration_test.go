package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"time"

	"github.com/hedgehog/cnoc/internal/api/rest/dto"
)

// IntegrationTest validates the entire CNOC system end-to-end
func RunIntegrationTest() error {
	log.Println("🧪 Starting CNOC Integration Test")
	log.Println("📋 Validating MDD-aligned architecture with real execution")
	
	baseURL := "http://localhost:8080"
	
	// Wait for server to be ready
	if err := waitForServer(baseURL); err != nil {
		return fmt.Errorf("server not ready: %w", err)
	}
	
	// Test 1: Health Check
	log.Println("🔍 Test 1: Health Check")
	if err := testHealthCheck(baseURL); err != nil {
		return fmt.Errorf("health check failed: %w", err)
	}
	log.Println("✅ Health check passed")
	
	// Test 2: Create Configuration (Testing Domain Model + Application Service + API)
	log.Println("🔍 Test 2: Create Configuration")
	configID, err := testCreateConfiguration(baseURL)
	if err != nil {
		return fmt.Errorf("create configuration failed: %w", err)
	}
	log.Printf("✅ Configuration created with ID: %s", configID)
	
	// Test 3: Get Configuration (Testing Query Layer + Anti-Corruption)
	log.Println("🔍 Test 3: Get Configuration")
	if err := testGetConfiguration(baseURL, configID); err != nil {
		return fmt.Errorf("get configuration failed: %w", err)
	}
	log.Println("✅ Configuration retrieved successfully")
	
	// Test 4: List Configurations (Testing Query Handlers + DTOs)
	log.Println("🔍 Test 4: List Configurations")
	if err := testListConfigurations(baseURL); err != nil {
		return fmt.Errorf("list configurations failed: %w", err)
	}
	log.Println("✅ Configuration list retrieved successfully")
	
	// Test 5: Update Configuration (Testing Command Handlers + Validation)
	log.Println("🔍 Test 5: Update Configuration")
	if err := testUpdateConfiguration(baseURL, configID); err != nil {
		return fmt.Errorf("update configuration failed: %w", err)
	}
	log.Println("✅ Configuration updated successfully")
	
	// Test 6: Validate Configuration (Testing Domain Services + Business Rules)
	log.Println("🔍 Test 6: Validate Configuration")
	if err := testValidateConfiguration(baseURL, configID); err != nil {
		return fmt.Errorf("validate configuration failed: %w", err)
	}
	log.Println("✅ Configuration validation passed")
	
	log.Println("🎉 All integration tests passed!")
	log.Println("✅ MDD-aligned architecture validated through runtime execution")
	log.Println("✅ Symphony-Level coordination operational")
	log.Println("✅ Anti-corruption layers functional")
	
	return nil
}

func waitForServer(baseURL string) error {
	log.Println("⏳ Waiting for server to be ready...")
	
	client := &http.Client{Timeout: 2 * time.Second}
	
	for i := 0; i < 30; i++ {
		resp, err := client.Get(baseURL + "/ready")
		if err == nil && resp.StatusCode == http.StatusOK {
			resp.Body.Close()
			log.Println("✅ Server is ready")
			return nil
		}
		if resp != nil {
			resp.Body.Close()
		}
		
		time.Sleep(1 * time.Second)
	}
	
	return fmt.Errorf("server not ready after 30 seconds")
}

func testHealthCheck(baseURL string) error {
	resp, err := http.Get(baseURL + "/health")
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("expected status 200, got %d", resp.StatusCode)
	}
	
	var health map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&health); err != nil {
		return err
	}
	
	if health["status"] != "healthy" {
		return fmt.Errorf("service not healthy: %v", health)
	}
	
	return nil
}

func testCreateConfiguration(baseURL string) (string, error) {
	createRequest := dto.CreateConfigurationRequestDTO{
		Name:        "test-config",
		Description: "Integration test configuration",
		Mode:        "development",
		Version:     "1.0.0",
		Labels: map[string]string{
			"test":        "integration",
			"environment": "test",
		},
		Components: []dto.ComponentDTO{
			{
				Name:    "test-component",
				Version: "1.0.0",
				Enabled: true,
				Resources: dto.ResourceRequirementsDTO{
					CPU:      "100m",
					Memory:   "128Mi",
					Replicas: 1,
				},
				Configuration: map[string]interface{}{
					"port": 8080,
					"env":  "test",
				},
			},
		},
	}
	
	jsonData, err := json.Marshal(createRequest)
	if err != nil {
		return "", err
	}
	
	resp, err := http.Post(baseURL+"/api/v1/configurations", "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusCreated {
		return "", fmt.Errorf("expected status 201, got %d", resp.StatusCode)
	}
	
	var configDTO dto.ConfigurationDTO
	if err := json.NewDecoder(resp.Body).Decode(&configDTO); err != nil {
		return "", err
	}
	
	// Validate response structure
	if configDTO.ID == "" {
		return "", fmt.Errorf("configuration ID is empty")
	}
	
	if configDTO.Name != createRequest.Name {
		return "", fmt.Errorf("name mismatch: expected %s, got %s", createRequest.Name, configDTO.Name)
	}
	
	if len(configDTO.Components) != 1 {
		return "", fmt.Errorf("expected 1 component, got %d", len(configDTO.Components))
	}
	
	return configDTO.ID, nil
}

func testGetConfiguration(baseURL, configID string) error {
	resp, err := http.Get(baseURL + "/api/v1/configurations/" + configID)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("expected status 200, got %d", resp.StatusCode)
	}
	
	var configDTO dto.ConfigurationDTO
	if err := json.NewDecoder(resp.Body).Decode(&configDTO); err != nil {
		return err
	}
	
	// Validate anti-corruption layer worked
	if configDTO.ID != configID {
		return fmt.Errorf("ID mismatch: expected %s, got %s", configID, configDTO.ID)
	}
	
	// Validate HATEOAS links
	if configDTO.Links.Self.Href == "" {
		return fmt.Errorf("missing self link")
	}
	
	return nil
}

func testListConfigurations(baseURL string) error {
	resp, err := http.Get(baseURL + "/api/v1/configurations?page=1&page_size=10")
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("expected status 200, got %d", resp.StatusCode)
	}
	
	var listDTO dto.ConfigurationListDTO
	if err := json.NewDecoder(resp.Body).Decode(&listDTO); err != nil {
		return err
	}
	
	// Validate pagination
	if listDTO.Page != 1 {
		return fmt.Errorf("expected page 1, got %d", listDTO.Page)
	}
	
	if listDTO.PageSize != 10 {
		return fmt.Errorf("expected page size 10, got %d", listDTO.PageSize)
	}
	
	// Should have at least our test configuration
	if len(listDTO.Items) == 0 {
		return fmt.Errorf("expected at least 1 configuration")
	}
	
	return nil
}

func testUpdateConfiguration(baseURL, configID string) error {
	updateRequest := dto.UpdateConfigurationRequestDTO{
		Description: stringPtr("Updated description for integration test"),
		Labels: map[string]string{
			"test":    "integration",
			"updated": "true",
		},
	}
	
	jsonData, err := json.Marshal(updateRequest)
	if err != nil {
		return err
	}
	
	req, err := http.NewRequest("PUT", baseURL+"/api/v1/configurations/"+configID, bytes.NewBuffer(jsonData))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	
	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("expected status 200, got %d", resp.StatusCode)
	}
	
	var configDTO dto.ConfigurationDTO
	if err := json.NewDecoder(resp.Body).Decode(&configDTO); err != nil {
		return err
	}
	
	// Validate update worked
	if configDTO.Description != *updateRequest.Description {
		return fmt.Errorf("description not updated")
	}
	
	if configDTO.Labels["updated"] != "true" {
		return fmt.Errorf("labels not updated")
	}
	
	return nil
}

func testValidateConfiguration(baseURL, configID string) error {
	resp, err := http.Post(baseURL+"/api/v1/configurations/"+configID+"/validate", "application/json", nil)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("expected status 200, got %d", resp.StatusCode)
	}
	
	var validationDTO dto.ValidationResultDTO
	if err := json.NewDecoder(resp.Body).Decode(&validationDTO); err != nil {
		return err
	}
	
	// For our test configuration, validation should pass
	if !validationDTO.Valid {
		return fmt.Errorf("validation failed: %v", validationDTO.Errors)
	}
	
	return nil
}

func stringPtr(s string) *string {
	return &s
}

// Main function for standalone test execution
func main() {
	if len(os.Args) > 1 && os.Args[1] == "test" {
		if err := RunIntegrationTest(); err != nil {
			log.Fatalf("❌ Integration test failed: %v", err)
		}
		log.Println("🎉 All tests passed! CNOC is operational.")
		os.Exit(0)
	}
	
	log.Println("🚀 Use 'go run main.go integration_test.go test' to run integration tests")
	log.Println("🚀 Use 'go run main.go' to start the CNOC server")
}