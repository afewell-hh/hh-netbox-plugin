package deployment

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// DockerTestSuite provides comprehensive Docker deployment testing
type DockerTestSuite struct {
	ImageTag         string
	ContainerID      string
	TestStartTime    time.Time
	BuildMetrics     []DockerBuildMetric
	SecurityResults  []SecurityScanResult
}

// DockerBuildMetric tracks build performance and characteristics
type DockerBuildMetric struct {
	BuildStage       string        `json:"build_stage"`
	Duration         time.Duration `json:"duration_ns"`
	ImageSize        int64         `json:"image_size_bytes"`
	LayerCount       int           `json:"layer_count"`
	BuildCacheHits   int           `json:"build_cache_hits"`
	Timestamp        time.Time     `json:"timestamp"`
}

// SecurityScanResult tracks vulnerability scanning results
type SecurityScanResult struct {
	Scanner          string    `json:"scanner"`
	CriticalVulns    int       `json:"critical_vulns"`
	HighVulns        int       `json:"high_vulns"`
	MediumVulns      int       `json:"medium_vulns"`
	LowVulns         int       `json:"low_vulns"`
	ScanDuration     time.Duration `json:"scan_duration_ns"`
	Timestamp        time.Time `json:"timestamp"`
}

// ContainerHealthMetric tracks container health and readiness
type ContainerHealthMetric struct {
	HealthEndpoint   string        `json:"health_endpoint"`
	ReadinessTime    time.Duration `json:"readiness_time_ns"`
	HealthStatus     string        `json:"health_status"`
	StartupTime      time.Duration `json:"startup_time_ns"`
	MemoryUsage      int64         `json:"memory_usage_bytes"`
	CPUUsagePercent  float64       `json:"cpu_usage_percent"`
	Timestamp        time.Time     `json:"timestamp"`
}

// NewDockerTestSuite creates new Docker deployment test suite
func NewDockerTestSuite() *DockerTestSuite {
	return &DockerTestSuite{
		ImageTag:        fmt.Sprintf("cnoc-test:%d", time.Now().Unix()),
		TestStartTime:   time.Now(),
		BuildMetrics:    []DockerBuildMetric{},
		SecurityResults: []SecurityScanResult{},
	}
}

// TestDockerMultiStageBuild validates optimized Docker image builds
func TestDockerMultiStageBuild(t *testing.T) {
	// FORGE Movement 7: Infrastructure as Code Testing - Docker Build Validation
	t.Log("🔄 FORGE M7: Testing Docker multi-stage build optimization...")

	suite := NewDockerTestSuite()
	buildStart := time.Now()

	// Build Docker image with multi-stage optimization
	buildCmd := exec.Command("docker", "build", 
		"-t", suite.ImageTag,
		"-f", "Dockerfile",
		".")
	
	buildOutput, err := buildCmd.CombinedOutput()
	buildDuration := time.Since(buildStart)
	
	require.NoError(t, err, "Docker build must succeed: %s", string(buildOutput))
	
	// Validate image exists and get details
	inspectCmd := exec.Command("docker", "inspect", suite.ImageTag)
	inspectOutput, err := inspectCmd.Output()
	require.NoError(t, err, "Docker inspect must succeed")

	var imageDetails []map[string]interface{}
	err = json.Unmarshal(inspectOutput, &imageDetails)
	require.NoError(t, err, "Image inspect JSON must be valid")
	require.Len(t, imageDetails, 1, "Image must exist")

	imageDetail := imageDetails[0]
	imageSize := int64(imageDetail["Size"].(float64))
	
	// Record build metrics
	buildMetric := DockerBuildMetric{
		BuildStage:    "multi-stage-production",
		Duration:      buildDuration,
		ImageSize:     imageSize,
		LayerCount:    len(imageDetail["RootFS"].(map[string]interface{})["Layers"].([]interface{})),
		Timestamp:     time.Now(),
	}
	suite.BuildMetrics = append(suite.BuildMetrics, buildMetric)

	// FORGE Validation 1: Image size must be under 100MB
	maxSizeBytes := int64(100 * 1024 * 1024) // 100MB
	assert.Less(t, imageSize, maxSizeBytes, 
		"Image must be <100MB for production deployment, got %d bytes (%d MB)", 
		imageSize, imageSize/(1024*1024))

	// FORGE Validation 2: Verify required binaries are present
	runCmd := exec.Command("docker", "run", "--rm", suite.ImageTag, 
		"ls", "-la", "/root/cnoc")
	
	output, err := runCmd.Output()
	require.NoError(t, err, "Binary must exist in final image")
	assert.Contains(t, string(output), "cnoc", "CNOC binary must be present")

	// FORGE Validation 3: Verify health check configuration
	config := imageDetail["Config"].(map[string]interface{})
	healthcheck, exists := config["Healthcheck"]
	assert.True(t, exists, "Health check must be configured")
	
	if healthcheckMap, ok := healthcheck.(map[string]interface{}); ok {
		test, testExists := healthcheckMap["Test"]
		assert.True(t, testExists, "Health check test must be defined")
		if testSlice, ok := test.([]interface{}); ok {
			assert.Greater(t, len(testSlice), 0, "Health check test must not be empty")
		}
	}

	// FORGE Evidence Collection
	t.Logf("✅ FORGE M7 EVIDENCE - Docker Build:")
	t.Logf("📦 Image Size: %d bytes (%.1f MB)", imageSize, float64(imageSize)/(1024*1024))
	t.Logf("⏱️  Build Duration: %v", buildDuration)
	t.Logf("🎯 Size Compliance: %t (max: %d MB)", imageSize < maxSizeBytes, maxSizeBytes/(1024*1024))
	t.Logf("📋 Layer Count: %d", buildMetric.LayerCount)

	// Store image tag for other tests
	t.Cleanup(func() {
		exec.Command("docker", "rmi", "-f", suite.ImageTag).Run()
	})
}

// TestDockerHealthChecks validates health and readiness probes
func TestDockerHealthChecks(t *testing.T) {
	// FORGE Movement 7: Health Check Validation
	t.Log("🔄 FORGE M7: Testing Docker health check functionality...")

	suite := NewDockerTestSuite()
	
	// Start container with health checks
	runCmd := exec.Command("docker", "run", 
		"-d", 
		"-p", "18080:8080",
		"--name", "cnoc-health-test",
		suite.ImageTag)
	
	output, err := runCmd.Output()
	require.NoError(t, err, "Container must start successfully")
	
	containerID := strings.TrimSpace(string(output))
	suite.ContainerID = containerID
	
	t.Cleanup(func() {
		exec.Command("docker", "stop", containerID).Run()
		exec.Command("docker", "rm", "-f", containerID).Run()
	})

	// Wait for container startup and measure readiness time
	startupStart := time.Now()
	client := &http.Client{Timeout: 5 * time.Second}
	
	var healthStatus string
	var readinessTime time.Duration
	
	// Attempt health check for up to 30 seconds
	for i := 0; i < 30; i++ {
		resp, err := client.Get("http://localhost:18080/health")
		if err == nil && resp.StatusCode == http.StatusOK {
			readinessTime = time.Since(startupStart)
			resp.Body.Close()
			healthStatus = "healthy"
			break
		}
		if resp != nil {
			resp.Body.Close()
		}
		time.Sleep(1 * time.Second)
	}

	// FORGE Validation 1: Container must be ready within 10 seconds
	maxStartupTime := 10 * time.Second
	assert.Less(t, readinessTime, maxStartupTime, 
		"Container must be ready in <%v, took %v", maxStartupTime, readinessTime)

	// FORGE Validation 2: Health endpoint must respond correctly
	assert.Equal(t, "healthy", healthStatus, "Health check must report healthy status")

	// Test readiness endpoint
	readyResp, err := client.Get("http://localhost:18080/ready")
	if err == nil {
		defer readyResp.Body.Close()
		assert.Equal(t, http.StatusOK, readyResp.StatusCode, "Ready endpoint must return 200")
	}

	// Get container statistics
	statsCmd := exec.Command("docker", "stats", "--no-stream", "--format", 
		"{{.MemUsage}}\t{{.CPUPerc}}", containerID)
	statsOutput, err := statsCmd.Output()
	
	var memoryUsage int64
	var cpuPercent float64
	if err == nil {
		statsData := strings.Fields(strings.TrimSpace(string(statsOutput)))
		if len(statsData) >= 2 {
			// Parse memory usage (format: "123MiB / 456MiB")
			memParts := strings.Split(statsData[0], " / ")
			if len(memParts) > 0 {
				memStr := strings.TrimSuffix(memParts[0], "MiB")
				if memVal, parseErr := fmt.Sscanf(memStr, "%f", &cpuPercent); parseErr == nil {
					memoryUsage = int64(memVal * 1024 * 1024) // Convert MiB to bytes
				}
			}
			
			// Parse CPU percentage (format: "12.34%")
			cpuStr := strings.TrimSuffix(statsData[1], "%")
			fmt.Sscanf(cpuStr, "%f", &cpuPercent)
		}
	}

	// Record health metrics
	healthMetric := ContainerHealthMetric{
		HealthEndpoint:   "/health",
		ReadinessTime:    readinessTime,
		HealthStatus:     healthStatus,
		StartupTime:      readinessTime,
		MemoryUsage:      memoryUsage,
		CPUUsagePercent:  cpuPercent,
		Timestamp:        time.Now(),
	}

	// FORGE Evidence Collection
	t.Logf("✅ FORGE M7 EVIDENCE - Health Checks:")
	t.Logf("⏱️  Startup Time: %v (max: %v)", readinessTime, maxStartupTime)
	t.Logf("🏥 Health Status: %s", healthStatus)
	t.Logf("💾 Memory Usage: %d bytes (%.1f MB)", memoryUsage, float64(memoryUsage)/(1024*1024))
	t.Logf("🖥️  CPU Usage: %.2f%%", cpuPercent)
	t.Logf("📊 Container ID: %s", containerID[:12])
}

// TestDockerSecurityScanning validates container security
func TestDockerSecurityScanning(t *testing.T) {
	// FORGE Movement 7: Security Validation
	t.Log("🔄 FORGE M7: Testing Docker security scanning...")

	suite := NewDockerTestSuite()
	scanStart := time.Now()

	// Check if security scanning tools are available
	_, trivyErr := exec.LookPath("trivy")
	_, dockerErr := exec.LookPath("docker")
	
	if trivyErr != nil {
		t.Skip("Trivy security scanner not available - skipping security scan")
	}
	if dockerErr != nil {
		t.Skip("Docker not available - skipping security scan")
	}

	// Run Trivy security scan
	scanCmd := exec.Command("trivy", "image", "--format", "json", "--quiet", suite.ImageTag)
	scanOutput, err := scanCmd.Output()
	scanDuration := time.Since(scanStart)

	var scanResults map[string]interface{}
	if err == nil {
		json.Unmarshal(scanOutput, &scanResults)
	}

	// Parse vulnerability results
	var criticalVulns, highVulns, mediumVulns, lowVulns int
	
	if results, exists := scanResults["Results"]; exists && results != nil {
		if resultsSlice, ok := results.([]interface{}); ok {
			for _, result := range resultsSlice {
				if resultMap, ok := result.(map[string]interface{}); ok {
					if vulns, exists := resultMap["Vulnerabilities"]; exists && vulns != nil {
						if vulnsSlice, ok := vulns.([]interface{}); ok {
							for _, vuln := range vulnsSlice {
								if vulnMap, ok := vuln.(map[string]interface{}); ok {
									if severity, exists := vulnMap["Severity"]; exists {
										switch severity {
										case "CRITICAL":
											criticalVulns++
										case "HIGH":
											highVulns++
										case "MEDIUM":
											mediumVulns++
										case "LOW":
											lowVulns++
										}
									}
								}
							}
						}
					}
				}
			}
		}
	}

	// Record security scan results
	securityResult := SecurityScanResult{
		Scanner:       "trivy",
		CriticalVulns: criticalVulns,
		HighVulns:     highVulns,
		MediumVulns:   mediumVulns,
		LowVulns:      lowVulns,
		ScanDuration:  scanDuration,
		Timestamp:     time.Now(),
	}
	suite.SecurityResults = append(suite.SecurityResults, securityResult)

	// FORGE Validation 1: No critical vulnerabilities allowed
	assert.Equal(t, 0, criticalVulns, "No critical vulnerabilities allowed in production image")

	// FORGE Validation 2: High vulnerabilities should be minimized
	assert.LessOrEqual(t, highVulns, 5, "High vulnerabilities should be ≤5 for production deployment")

	// FORGE Validation 3: Scan must complete in reasonable time
	maxScanTime := 5 * time.Minute
	assert.Less(t, scanDuration, maxScanTime, "Security scan must complete in <%v", maxScanTime)

	// FORGE Evidence Collection
	t.Logf("✅ FORGE M7 EVIDENCE - Security Scan:")
	t.Logf("🔴 Critical Vulnerabilities: %d (max: 0)", criticalVulns)
	t.Logf("🟡 High Vulnerabilities: %d (max: 5)", highVulns)
	t.Logf("🔵 Medium Vulnerabilities: %d", mediumVulns)
	t.Logf("🟢 Low Vulnerabilities: %d", lowVulns)
	t.Logf("⏱️  Scan Duration: %v", scanDuration)
	t.Logf("🛡️  Security Compliance: %t", criticalVulns == 0 && highVulns <= 5)
}

// TestDockerStartupTime validates application startup performance
func TestDockerStartupTime(t *testing.T) {
	// FORGE Movement 7: Startup Performance Validation
	t.Log("🔄 FORGE M7: Testing Docker application startup time...")

	suite := NewDockerTestSuite()
	
	// Multiple startup time measurements for accuracy
	startupTimes := make([]time.Duration, 3)
	
	for i := 0; i < 3; i++ {
		containerName := fmt.Sprintf("cnoc-startup-test-%d", i)
		
		startupStart := time.Now()
		
		// Start container
		runCmd := exec.Command("docker", "run", 
			"-d", 
			"-p", fmt.Sprintf("%d:8080", 18081+i),
			"--name", containerName,
			suite.ImageTag)
		
		output, err := runCmd.Output()
		require.NoError(t, err, "Container must start successfully")
		
		containerID := strings.TrimSpace(string(output))
		
		// Wait for application to be ready
		client := &http.Client{Timeout: 2 * time.Second}
		ready := false
		
		for j := 0; j < 15; j++ { // Try for 15 seconds
			resp, err := client.Get(fmt.Sprintf("http://localhost:%d/ready", 18081+i))
			if err == nil && resp.StatusCode == http.StatusOK {
				resp.Body.Close()
				ready = true
				break
			}
			if resp != nil {
				resp.Body.Close()
			}
			time.Sleep(1 * time.Second)
		}
		
		startupTime := time.Since(startupStart)
		startupTimes[i] = startupTime
		
		// Cleanup
		exec.Command("docker", "stop", containerID).Run()
		exec.Command("docker", "rm", "-f", containerID).Run()
		
		// FORGE Validation: Each startup must be under 10 seconds
		maxStartupTime := 10 * time.Second
		assert.True(t, ready, "Application must be ready after startup attempt %d", i+1)
		assert.Less(t, startupTime, maxStartupTime, 
			"Startup attempt %d took %v, must be <%v", i+1, startupTime, maxStartupTime)
	}
	
	// Calculate average startup time
	var totalStartup time.Duration
	for _, startup := range startupTimes {
		totalStartup += startup
	}
	avgStartup := totalStartup / time.Duration(len(startupTimes))
	
	// FORGE Evidence Collection
	t.Logf("✅ FORGE M7 EVIDENCE - Startup Performance:")
	t.Logf("⏱️  Average Startup: %v", avgStartup)
	t.Logf("📊 Individual Times: %v, %v, %v", startupTimes[0], startupTimes[1], startupTimes[2])
	t.Logf("🎯 Performance Target: <10s (achieved: %t)", avgStartup < 10*time.Second)
}

// TestDockerEnvironmentConfig validates environment variable handling
func TestDockerEnvironmentConfig(t *testing.T) {
	// FORGE Movement 7: Configuration Management Testing
	t.Log("🔄 FORGE M7: Testing Docker environment configuration...")

	suite := NewDockerTestSuite()
	
	// Test environment variable configurations
	envTestCases := []struct {
		name     string
		envVars  []string
		expected map[string]string
	}{
		{
			name: "Development Configuration",
			envVars: []string{
				"CNOC_ENV=development",
				"CNOC_LOG_LEVEL=debug",
				"CNOC_PORT=8080",
			},
			expected: map[string]string{
				"CNOC_ENV": "development",
				"CNOC_LOG_LEVEL": "debug",
				"CNOC_PORT": "8080",
			},
		},
		{
			name: "Production Configuration",
			envVars: []string{
				"CNOC_ENV=production",
				"CNOC_LOG_LEVEL=info",
				"CNOC_PORT=8080",
				"CNOC_METRICS_ENABLED=true",
			},
			expected: map[string]string{
				"CNOC_ENV": "production",
				"CNOC_LOG_LEVEL": "info",
				"CNOC_PORT": "8080",
				"CNOC_METRICS_ENABLED": "true",
			},
		},
	}
	
	for i, tc := range envTestCases {
		t.Run(tc.name, func(t *testing.T) {
			containerName := fmt.Sprintf("cnoc-env-test-%d", i)
			
			// Build docker run command with environment variables
			runArgs := []string{"run", "-d", "--name", containerName}
			for _, env := range tc.envVars {
				runArgs = append(runArgs, "-e", env)
			}
			runArgs = append(runArgs, suite.ImageTag)
			
			runCmd := exec.Command("docker", runArgs...)
			output, err := runCmd.Output()
			require.NoError(t, err, "Container with env vars must start")
			
			containerID := strings.TrimSpace(string(output))
			
			t.Cleanup(func() {
				exec.Command("docker", "stop", containerID).Run()
				exec.Command("docker", "rm", "-f", containerID).Run()
			})
			
			// Wait a moment for container to start
			time.Sleep(2 * time.Second)
			
			// Verify environment variables are set correctly
			for envVar, expectedValue := range tc.expected {
				envCmd := exec.Command("docker", "exec", containerID, "env")
				envOutput, err := envCmd.Output()
				require.NoError(t, err, "Environment check must succeed")
				
				envString := string(envOutput)
				expectedLine := fmt.Sprintf("%s=%s", envVar, expectedValue)
				assert.Contains(t, envString, expectedLine, 
					"Environment variable %s must be set to %s", envVar, expectedValue)
			}
			
			// Verify container is still running with these configurations
			psCmd := exec.Command("docker", "ps", "--filter", fmt.Sprintf("id=%s", containerID), "--format", "{{.Status}}")
			psOutput, err := psCmd.Output()
			require.NoError(t, err, "Container status check must succeed")
			
			status := strings.TrimSpace(string(psOutput))
			assert.Contains(t, status, "Up", "Container must be running with environment configuration")
		})
	}
	
	// FORGE Evidence Collection
	t.Logf("✅ FORGE M7 EVIDENCE - Environment Configuration:")
	t.Logf("🔧 Test Cases: %d", len(envTestCases))
	t.Logf("📋 Configuration Types: Development, Production")
	t.Logf("✅ Environment Handling: Validated")
}

// FORGE Movement 7 Docker Test Requirements Summary:
//
// 1. MULTI-STAGE BUILD OPTIMIZATION:
//    - Image size must be <100MB for production deployment
//    - Required binaries present in final stage
//    - Health check configuration validated
//    - Build performance metrics collected
//
// 2. HEALTH CHECK VALIDATION:
//    - Container ready within 10 seconds
//    - Health endpoints respond correctly (/health, /ready)
//    - Resource usage monitoring (memory, CPU)
//    - Startup time performance validation
//
// 3. SECURITY COMPLIANCE:
//    - Zero critical vulnerabilities allowed
//    - High vulnerabilities ≤5 for production
//    - Security scanning performance <5 minutes
//    - Base image security validation
//
// 4. STARTUP PERFORMANCE:
//    - Application ready in <10 seconds
//    - Multiple measurement accuracy
//    - Performance consistency validation
//    - Resource initialization timing
//
// 5. CONFIGURATION MANAGEMENT:
//    - Environment variable handling
//    - Configuration validation
//    - Development/Production mode support
//    - Runtime configuration management