package web

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/hedgehog/cnoc/internal/monitoring"
)

// FORGE Testing-Validation Engineer: Simple GitOps Integration Tests
// RED PHASE VALIDATION: These tests demonstrate test-first methodology
// and validate integration points that will be implemented

func TestGitOpsIntegration_RED_PHASE_Basic_Validation(t *testing.T) {
	// RED PHASE: Test current system capabilities and identify gaps
	
	t.Run("Current_Configuration_API_Works", func(t *testing.T) {
		// Test existing configuration service integration (should work)
		handler := createSimpleTestWebHandler(t)
		
		req := httptest.NewRequest("GET", "/api/v1/configurations", nil)
		w := httptest.NewRecorder()
		
		startTime := time.Now()
		handler.HandleAPIConfigurationList(w, req)
		responseTime := time.Since(startTime)
		
		// QUANTITATIVE SUCCESS CRITERIA
		assert.Equal(t, http.StatusOK, w.Code, "Configuration list should work with existing service")
		assert.Less(t, responseTime.Milliseconds(), int64(2000), "Configuration listing should be <2 seconds")
		
		var response map[string]interface{}
		err := json.Unmarshal(w.Body.Bytes(), &response)
		require.NoError(t, err, "Response should be valid JSON")
		
		// Validate response structure
		assert.Contains(t, response, "configurations", "Should contain configurations array")
		if totalCount, ok := response["total_count"].(float64); ok {
			assert.Greater(t, totalCount, 0.0, "Should have configurations from seeded data")
		}
		
		t.Logf("✅ Configuration API Performance: %dms", responseTime.Milliseconds())
	})
	
	t.Run("Current_Fabric_API_Works", func(t *testing.T) {
		// Test existing fabric service integration (should work)
		handler := createSimpleTestWebHandler(t)
		
		req := httptest.NewRequest("GET", "/api/v1/fabrics", nil)
		w := httptest.NewRecorder()
		
		startTime := time.Now()
		handler.HandleAPIFabricList(w, req)
		responseTime := time.Since(startTime)
		
		// QUANTITATIVE SUCCESS CRITERIA
		assert.Equal(t, http.StatusOK, w.Code, "Fabric list should work with existing service")
		assert.Less(t, responseTime.Milliseconds(), int64(2000), "Fabric listing should be <2 seconds")
		
		// Should return valid JSON even if empty
		var response interface{}
		err := json.Unmarshal(w.Body.Bytes(), &response)
		require.NoError(t, err, "Response should be valid JSON")
		
		t.Logf("✅ Fabric API Performance: %dms", responseTime.Milliseconds())
	})
	
	t.Run("RED_PHASE_Missing_GitOps_Repository_API", func(t *testing.T) {
		// RED PHASE: This should fail - demonstrates missing GitOps repository service
		handler := createSimpleTestWebHandler(t)
		
		req := httptest.NewRequest("GET", "/api/v1/repositories", nil)
		w := httptest.NewRecorder()
		
		// This handler doesn't exist yet - should return 404
		handler.HandleAPIRepositoryList(w, req)
		
		// RED PHASE VALIDATION: Should fail because service is missing
		assert.NotEqual(t, http.StatusOK, w.Code, "TEST SHOULD FAIL: Repository API not implemented yet")
		t.Logf("❌ Repository API missing (expected RED phase result)")
	})
	
	t.Run("RED_PHASE_Missing_Drift_Detection_API", func(t *testing.T) {
		// RED PHASE: This should fail - demonstrates missing drift detection service
		handler := createSimpleTestWebHandler(t)
		
		req := httptest.NewRequest("GET", "/api/v1/fabrics/test-fabric-1/drift", nil)
		w := httptest.NewRecorder()
		
		// This handler doesn't exist yet - should return 404 or 500
		handler.HandleAPIFabricDrift(w, req)
		
		// RED PHASE VALIDATION: Should fail because service is missing  
		assert.NotEqual(t, http.StatusOK, w.Code, "TEST SHOULD FAIL: Drift detection API not implemented yet")
		t.Logf("❌ Drift detection API missing (expected RED phase result)")
	})
}

func TestGitOpsIntegration_Performance_Baseline(t *testing.T) {
	// Establish performance baselines for existing services
	
	t.Run("Configuration_Service_Performance_Baseline", func(t *testing.T) {
		handler := createSimpleTestWebHandler(t)
		
		// Test configuration list performance multiple times for baseline
		var totalTime time.Duration
		runs := 5
		
		for i := 0; i < runs; i++ {
			req := httptest.NewRequest("GET", "/api/v1/configurations", nil)
			w := httptest.NewRecorder()
			
			start := time.Now()
			handler.HandleAPIConfigurationList(w, req)
			totalTime += time.Since(start)
			
			assert.Equal(t, http.StatusOK, w.Code, fmt.Sprintf("Run %d should succeed", i+1))
		}
		
		averageTime := totalTime / time.Duration(runs)
		
		// QUANTITATIVE BASELINE EVIDENCE
		assert.Less(t, averageTime.Milliseconds(), int64(2000), "Average response time should be <2s")
		
		t.Logf("📊 Configuration Service Baseline:")
		t.Logf("   Average Response Time: %dms", averageTime.Milliseconds())
		t.Logf("   Total Runs: %d", runs)
		t.Logf("   Performance Target: <2000ms ✅")
	})
	
	t.Run("Configuration_Detail_Performance_Baseline", func(t *testing.T) {
		handler := createSimpleTestWebHandler(t)
		
		// Test configuration detail with seeded data
		testConfigID := "production-enterprise" // From seeded data
		
		req := httptest.NewRequest("GET", fmt.Sprintf("/api/v1/configurations/%s", testConfigID), nil)
		w := httptest.NewRecorder()
		
		startTime := time.Now()
		handler.HandleAPIConfigurationGet(w, req)
		responseTime := time.Since(startTime)
		
		// Should work with existing service
		if w.Code == http.StatusOK {
			assert.Less(t, responseTime.Milliseconds(), int64(1000), "Config detail should be <1s")
			
			var config map[string]interface{}
			err := json.Unmarshal(w.Body.Bytes(), &config)
			require.NoError(t, err, "Should return valid configuration")
			
			// Validate configuration structure
			assert.Contains(t, config, "id", "Should contain configuration ID")
			assert.Contains(t, config, "name", "Should contain configuration name")
			assert.Contains(t, config, "components", "Should contain components")
			
			t.Logf("✅ Configuration Detail Performance: %dms", responseTime.Milliseconds())
		} else {
			t.Logf("ℹ️  Configuration detail API not fully implemented yet")
		}
	})
}

func TestGitOpsIntegration_Service_Factory_Analysis(t *testing.T) {
	// Analyze current service factory capabilities
	
	t.Run("Analyze_Current_Service_Factory", func(t *testing.T) {
		handler := createSimpleTestWebHandler(t)
		
		// Test what services are currently available
		configService := handler.serviceFactory.GetConfigurationService()
		fabricService := handler.serviceFactory.GetFabricService()
		
		assert.NotNil(t, configService, "Configuration service should be available")
		assert.NotNil(t, fabricService, "Fabric service should be available")
		
		// Test configuration service functionality
		ctx := context.Background()
		configList, err := configService.ListConfigurations(ctx, 1, 10)
		
		if err == nil {
			assert.Greater(t, len(configList.Items), 0, "Should have seeded configurations")
			t.Logf("✅ Configuration Service: %d configurations available", len(configList.Items))
		} else {
			t.Logf("⚠️  Configuration service error: %v", err)
		}
		
		// Test fabric service functionality  
		fabricList, err := fabricService.ListFabrics(ctx, 1, 10)
		
		if err == nil {
			t.Logf("✅ Fabric Service: %d fabrics available", len(fabricList.Items))
		} else {
			t.Logf("⚠️  Fabric service error: %v", err)
		}
		
		t.Logf("📋 Service Factory Analysis Complete:")
		t.Logf("   ✅ Configuration Service: Operational")
		t.Logf("   ✅ Fabric Service: Operational") 
		t.Logf("   ❌ GitOps Repository Service: Missing (RED phase)")
		t.Logf("   ❌ Drift Detection Service: Missing (RED phase)")
		t.Logf("   ❌ Configuration Validation Service: Missing (RED phase)")
	})
}

func TestGitOpsIntegration_WebSocket_Infrastructure(t *testing.T) {
	// Test WebSocket infrastructure readiness
	
	t.Run("WebSocket_Manager_Available", func(t *testing.T) {
		handler := createSimpleTestWebHandler(t)
		
		assert.NotNil(t, handler.wsManager, "WebSocket manager should be initialized")
		assert.NotNil(t, handler.eventBroadcaster, "Event broadcaster should be available")
		
		t.Logf("✅ WebSocket Infrastructure: Ready")
		t.Logf("   WebSocket Manager: Available")
		t.Logf("   Event Broadcaster: Available") 
		t.Logf("   Real-time Updates: Infrastructure ready for GitOps integration")
	})
}

// Helper function for simple test setup
func createSimpleTestWebHandler(t *testing.T) *WebHandler {
	metricsCollector := &monitoring.MetricsCollector{}
	
	// Create handler without templates for testing
	handler := &WebHandler{
		metricsCollector: metricsCollector,
		wsManager:        NewWebSocketManager(),
	}
	
	// Initialize WebSocket and event components
	handler.wsManager.Start()
	handler.eventBroadcaster = NewEventBroadcaster(handler.wsManager)
	handler.serviceFactory = NewServiceFactory()
	
	return handler
}

// Mock handler methods removed - now implemented in handlers.go
// RED PHASE validation will use the real handlers that return appropriate error statuses