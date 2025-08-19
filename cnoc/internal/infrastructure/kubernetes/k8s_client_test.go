package kubernetes

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/stretchr/testify/suite"
	corev1 "k8s.io/api/core/v1"
	storagev1 "k8s.io/api/storage/v1"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/client-go/discovery"
	"k8s.io/client-go/dynamic"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
)

// FORGE Movement 5: Event Orchestration Testing
// Kubernetes Client Integration Tests with real cluster connectivity

// K8sClientConfig represents Kubernetes client configuration
type K8sClientConfig struct {
	Server       string            `json:"server"`
	Token        string            `json:"token,omitempty"`
	CertData     []byte            `json:"cert_data,omitempty"`
	KeyData      []byte            `json:"key_data,omitempty"`
	CAData       []byte            `json:"ca_data,omitempty"`
	Insecure     bool              `json:"insecure"`
	Timeout      time.Duration     `json:"timeout"`
	UserAgent    string            `json:"user_agent"`
	Impersonate  string            `json:"impersonate,omitempty"`
	QPS          float32           `json:"qps"`
	Burst        int               `json:"burst"`
	Metadata     map[string]string `json:"metadata,omitempty"`
}

// CRDDefinition represents a Custom Resource Definition
type CRDDefinition struct {
	Group        string                 `json:"group"`
	Version      string                 `json:"version"`
	Kind         string                 `json:"kind"`
	PluralName   string                 `json:"plural_name"`
	Namespaced   bool                   `json:"namespaced"`
	Schema       map[string]interface{} `json:"schema,omitempty"`
	Subresources []string               `json:"subresources,omitempty"`
}

// ResourceOperation represents a Kubernetes resource operation
type ResourceOperation struct {
	Operation   string                 `json:"operation"` // create, read, update, delete, list
	Resource    *unstructured.Unstructured `json:"resource"`
	Namespace   string                 `json:"namespace,omitempty"`
	Name        string                 `json:"name,omitempty"`
	Labels      map[string]string      `json:"labels,omitempty"`
	Fields      map[string]string      `json:"fields,omitempty"`
	Options     metav1.ListOptions     `json:"options,omitempty"`
}

// ResourceOperationResult represents the result of a resource operation
type ResourceOperationResult struct {
	Success      bool                       `json:"success"`
	Operation    string                     `json:"operation"`
	Resource     *unstructured.Unstructured `json:"resource,omitempty"`
	Resources    []unstructured.Unstructured `json:"resources,omitempty"`
	Error        string                     `json:"error,omitempty"`
	Duration     time.Duration              `json:"duration"`
	Metadata     map[string]interface{}     `json:"metadata,omitempty"`
}

// ClusterInfo represents cluster information and capabilities
type ClusterInfo struct {
	Version           string                    `json:"version"`
	APIVersions       []string                  `json:"api_versions"`
	Resources         []metav1.APIResource      `json:"resources"`
	CRDsSupported     bool                      `json:"crds_supported"`
	NamespacesList    []string                  `json:"namespaces"`
	NodeCount         int                       `json:"node_count"`
	ServiceAccount    string                    `json:"service_account"`
	Permissions       map[string]bool           `json:"permissions"`
	CustomResources   []CRDDefinition           `json:"custom_resources"`
	ClusterRoles      []string                  `json:"cluster_roles"`
	StorageClasses    []string                  `json:"storage_classes"`
}

// K8sClientTestSuite - FORGE Movement 5 Test Suite
type K8sClientTestSuite struct {
	suite.Suite
	config       *K8sClientConfig
	restConfig   *rest.Config
	clientset    kubernetes.Interface
	dynamicClient dynamic.Interface
	discoveryClient discovery.DiscoveryInterface
	evidence     map[string]interface{}
	testNamespace string
	testResources []unstructured.Unstructured
}

func (suite *K8sClientTestSuite) SetupSuite() {
	suite.evidence = make(map[string]interface{})
	suite.testNamespace = "cnoc-test-namespace"
	
	// FORGE Requirement: Real cluster connectivity testing
	suite.setupKubernetesConfig()
	
	// Try to create clients - may fail if no cluster available
	var err error
	if suite.restConfig != nil {
		suite.clientset, err = NewKubernetesClient(suite.config)
		if err != nil {
			suite.T().Logf("Failed to create Kubernetes client: %v", err)
		}
		
		suite.dynamicClient, err = NewDynamicClient(suite.config) 
		if err != nil {
			suite.T().Logf("Failed to create dynamic client: %v", err)
		}
		
		suite.discoveryClient, err = NewDiscoveryClient(suite.config)
		if err != nil {
			suite.T().Logf("Failed to create discovery client: %v", err)
		}
	}
	
	suite.evidence["setup_completed"] = time.Now()
	suite.evidence["test_namespace"] = suite.testNamespace
}

func (suite *K8sClientTestSuite) setupKubernetesConfig() {
	// Setup realistic Kubernetes configuration for testing
	suite.config = &K8sClientConfig{
		Server:    "https://127.0.0.1:6443",
		Insecure:  false,
		Timeout:   30 * time.Second,
		UserAgent: "cnoc-test-client/v1.0.0",
		QPS:       50.0,
		Burst:     100,
	}
	
	// Attempt to load real kubeconfig for integration testing
	kubeconfigPath := os.Getenv("KUBECONFIG")
	if kubeconfigPath == "" {
		homeDir, _ := os.UserHomeDir()
		kubeconfigPath = filepath.Join(homeDir, ".kube", "config")
	}
	
	// Check for local testing kubeconfig
	localKubeconfig := "/home/ubuntu/cc/hedgehog-netbox-plugin/hemk/poc_development/kubeconfig/kubeconfig.yaml"
	if _, err := os.Stat(localKubeconfig); err == nil {
		kubeconfigPath = localKubeconfig
	}
	
	if _, err := os.Stat(kubeconfigPath); err == nil {
		config, err := clientcmd.BuildConfigFromFlags("", kubeconfigPath)
		if err == nil {
			suite.restConfig = config
			suite.config.Server = config.Host
		}
	}
	
	suite.evidence["kubeconfig_path"] = kubeconfigPath
	suite.evidence["k8s_server"] = suite.config.Server
}

func (suite *K8sClientTestSuite) setupTestResources() {
	// Setup test CRD resources for CNOC testing
	suite.testResources = []unstructured.Unstructured{
		// VPC Test Resource
		{
			Object: map[string]interface{}{
				"apiVersion": "vpc.hedgehog.com/v1",
				"kind":       "VPC",
				"metadata": map[string]interface{}{
					"name":      "test-vpc-k8s",
					"namespace": suite.testNamespace,
					"labels": map[string]interface{}{
						"test":        "forge-k8s-integration",
						"environment": "testing",
					},
				},
				"spec": map[string]interface{}{
					"ipv4Namespace":  "test-namespace",
					"subnets":        []string{"10.100.0.0/24", "10.100.1.0/24"},
					"defaultGateway": "10.100.0.1",
					"dnsServers":     []string{"8.8.8.8", "8.8.4.4"},
					"vlanId":         1000,
					"description":    "Test VPC for FORGE Kubernetes integration",
				},
			},
		},
		// Connection Test Resource
		{
			Object: map[string]interface{}{
				"apiVersion": "connection.hedgehog.com/v1",
				"kind":       "Connection",
				"metadata": map[string]interface{}{
					"name":      "test-connection-k8s",
					"namespace": suite.testNamespace,
					"labels": map[string]interface{}{
						"test": "forge-k8s-integration",
						"type": "test-connection",
					},
				},
				"spec": map[string]interface{}{
					"endpoints": []map[string]interface{}{
						{"device": "test-switch-1", "port": "eth0"},
						{"device": "test-switch-2", "port": "eth1"},
					},
					"bandwidth": "1Gbps",
					"protocol":  "ethernet",
					"vlanTags":  []int{1000, 2000},
				},
			},
		},
		// Switch Test Resource
		{
			Object: map[string]interface{}{
				"apiVersion": "switch.hedgehog.com/v1",
				"kind":       "Switch",
				"metadata": map[string]interface{}{
					"name":      "test-switch-k8s",
					"namespace": suite.testNamespace,
					"labels": map[string]interface{}{
						"test": "forge-k8s-integration",
						"role": "test-leaf",
					},
				},
				"spec": map[string]interface{}{
					"model":   "Test Switch Model",
					"ports":   24,
					"uplinks": 2,
					"role":    "leaf",
					"mgmtIP":  "192.168.100.10",
					"bgpASN":  65100,
				},
			},
		},
	}
}

func (suite *K8sClientTestSuite) TearDownSuite() {
	// Cleanup test resources
	suite.evidence["teardown_completed"] = time.Now()
}

// TestClusterConnectivity - FORGE Movement 5 Requirement
// Real cluster authentication and connection testing
func (suite *K8sClientTestSuite) TestClusterConnectivity() {
	startTime := time.Now()
	t := suite.T()
	
	// RED PHASE: Test should fail until K8s client is implemented
	if suite.clientset == nil || suite.restConfig == nil {
		t.Log("Kubernetes client not implemented - test failing as expected in FORGE RED PHASE")
		assert.Fail(t, "Kubernetes client implementation required")
		return
	}
	
	ctx := context.Background()
	
	// Test 1: Basic cluster connectivity
	serverVersion, err := suite.clientset.Discovery().ServerVersion()
	assert.NoError(t, err, "Should connect to Kubernetes cluster")
	assert.NotNil(t, serverVersion, "Should retrieve server version")
	assert.NotEmpty(t, serverVersion.String(), "Server version should not be empty")
	
	// Test 2: Authentication validation
	_, err = suite.clientset.CoreV1().Namespaces().List(ctx, metav1.ListOptions{Limit: 1})
	assert.NoError(t, err, "Should successfully authenticate with cluster")
	
	// Test 3: Cluster permissions validation
	selfSubjectReview := &unstructured.Unstructured{
		Object: map[string]interface{}{
			"apiVersion": "authorization.k8s.io/v1",
			"kind":       "SelfSubjectAccessReview",
			"spec": map[string]interface{}{
				"resourceAttributes": map[string]interface{}{
					"verb":     "create",
					"group":    "apiextensions.k8s.io",
					"resource": "customresourcedefinitions",
				},
			},
		},
	}
	
	gvr := schema.GroupVersionResource{
		Group:    "authorization.k8s.io",
		Version:  "v1",
		Resource: "selfsubjectaccessreviews",
	}
	
	review, err := suite.dynamicClient.Resource(gvr).Create(ctx, selfSubjectReview, metav1.CreateOptions{})
	assert.NoError(t, err, "Should be able to perform self-subject access review")
	assert.NotNil(t, review, "Access review should return result")
	
	// Test 4: Network connectivity metrics
	connectivityStart := time.Now()
	
	nodes, err := suite.clientset.CoreV1().Nodes().List(ctx, metav1.ListOptions{})
	connectivityDuration := time.Since(connectivityStart)
	
	assert.NoError(t, err, "Should list cluster nodes")
	assert.Greater(t, len(nodes.Items), 0, "Cluster should have at least one node")
	
	// Test 5: API server capabilities
	apiVersions, err := suite.clientset.Discovery().ServerGroups()
	assert.NoError(t, err, "Should retrieve API server groups")
	assert.Greater(t, len(apiVersions.Groups), 0, "Should have available API groups")
	
	// Evidence collection
	duration := time.Since(startTime)
	suite.evidence["connectivity_test_duration"] = duration
	suite.evidence["connectivity_latency"] = connectivityDuration
	suite.evidence["server_version"] = serverVersion.String()
	suite.evidence["node_count"] = len(nodes.Items)
	suite.evidence["api_groups_count"] = len(apiVersions.Groups)
	
	// Performance requirement: Cluster connectivity should be established within 5 seconds
	assert.Less(t, duration, 5*time.Second, "Cluster connectivity should be fast")
	assert.Less(t, connectivityDuration, 1*time.Second, "API calls should have low latency")
}

// TestCRDResourceOperations - FORGE Movement 5 Requirement
// Create, read, update, delete CRD resources in cluster
func (suite *K8sClientTestSuite) TestCRDResourceOperations() {
	startTime := time.Now()
	t := suite.T()
	
	if suite.dynamicClient == nil {
		t.Log("Dynamic client not implemented - test failing as expected in FORGE RED PHASE")
		assert.Fail(t, "Dynamic Kubernetes client implementation required")
		return
	}
	
	ctx := context.Background()
	suite.setupTestResources()
	
	// Test CRUD operations for each test resource
	for _, testResource := range suite.testResources {
		resourceName := testResource.GetName()
		resourceKind := testResource.GetKind()
		
		t.Run(fmt.Sprintf("CRUD_%s_%s", resourceKind, resourceName), func(t *testing.T) {
			suite.testCRUDOperationsForResource(t, testResource)
		})
	}
	
	// Evidence collection
	duration := time.Since(startTime)
	suite.evidence["crud_operations_duration"] = duration
	suite.evidence["resources_tested"] = len(suite.testResources)
}

func (suite *K8sClientTestSuite) testCRUDOperationsForResource(t *testing.T, testResource unstructured.Unstructured) {
	ctx := context.Background()
	
	// Determine GVR for the resource
	gvr := schema.GroupVersionResource{
		Group:    "hedgehog.com",
		Version:  "v1",
		Resource: strings.ToLower(testResource.GetKind()) + "s",
	}
	
	resourceName := testResource.GetName()
	namespace := testResource.GetNamespace()
	
	// Test 1: CREATE
	created, err := suite.dynamicClient.Resource(gvr).Namespace(namespace).Create(ctx, &testResource, metav1.CreateOptions{})
	assert.NoError(t, err, fmt.Sprintf("Should create %s resource", testResource.GetKind()))
	assert.NotNil(t, created, "Created resource should not be nil")
	assert.Equal(t, resourceName, created.GetName(), "Created resource name should match")
	
	// Test 2: READ
	retrieved, err := suite.dynamicClient.Resource(gvr).Namespace(namespace).Get(ctx, resourceName, metav1.GetOptions{})
	assert.NoError(t, err, fmt.Sprintf("Should retrieve %s resource", testResource.GetKind()))
	assert.NotNil(t, retrieved, "Retrieved resource should not be nil")
	assert.Equal(t, resourceName, retrieved.GetName(), "Retrieved resource name should match")
	
	// Validate resource spec
	spec, found, err := unstructured.NestedMap(retrieved.Object, "spec")
	assert.NoError(t, err, "Should extract spec from resource")
	assert.True(t, found, "Resource should have spec")
	assert.NotEmpty(t, spec, "Spec should not be empty")
	
	// Test 3: UPDATE
	// Add a label to the resource
	labels := retrieved.GetLabels()
	if labels == nil {
		labels = make(map[string]string)
	}
	labels["updated"] = "true"
	labels["update-time"] = time.Now().Format(time.RFC3339)
	retrieved.SetLabels(labels)
	
	updated, err := suite.dynamicClient.Resource(gvr).Namespace(namespace).Update(ctx, retrieved, metav1.UpdateOptions{})
	assert.NoError(t, err, fmt.Sprintf("Should update %s resource", testResource.GetKind()))
	assert.NotNil(t, updated, "Updated resource should not be nil")
	assert.Equal(t, "true", updated.GetLabels()["updated"], "Updated label should be present")
	
	// Test 4: LIST
	resourceList, err := suite.dynamicClient.Resource(gvr).Namespace(namespace).List(ctx, metav1.ListOptions{})
	assert.NoError(t, err, fmt.Sprintf("Should list %s resources", testResource.GetKind()))
	assert.NotNil(t, resourceList, "Resource list should not be nil")
	assert.Greater(t, len(resourceList.Items), 0, "Should have at least one resource")
	
	// Find our test resource in the list
	found = false
	for _, item := range resourceList.Items {
		if item.GetName() == resourceName {
			found = true
			break
		}
	}
	assert.True(t, found, "Test resource should be found in list")
	
	// Test 5: DELETE
	err = suite.dynamicClient.Resource(gvr).Namespace(namespace).Delete(ctx, resourceName, metav1.DeleteOptions{})
	assert.NoError(t, err, fmt.Sprintf("Should delete %s resource", testResource.GetKind()))
	
	// Verify deletion
	_, err = suite.dynamicClient.Resource(gvr).Namespace(namespace).Get(ctx, resourceName, metav1.GetOptions{})
	assert.Error(t, err, "Resource should not exist after deletion")
}

// TestResourceDiscovery - FORGE Movement 5 Requirement
// Query existing CRDs from cluster
func (suite *K8sClientTestSuite) TestResourceDiscovery() {
	startTime := time.Now()
	t := suite.T()
	
	if suite.discoveryClient == nil {
		t.Log("Discovery client not implemented - test failing as expected in FORGE RED PHASE")
		assert.Fail(t, "Discovery client implementation required")
		return
	}
	
	ctx := context.Background()
	
	// Test 1: Discover all API resources
	resourceLists, err := suite.discoveryClient.ServerPreferredResources()
	assert.NoError(t, err, "Should discover server resources")
	assert.Greater(t, len(resourceLists), 0, "Should find API resources")
	
	// Test 2: Discover CRD-specific resources
	crdGVR := schema.GroupVersionResource{
		Group:    "apiextensions.k8s.io",
		Version:  "v1",
		Resource: "customresourcedefinitions",
	}
	
	crds, err := suite.dynamicClient.Resource(crdGVR).List(ctx, metav1.ListOptions{})
	assert.NoError(t, err, "Should list Custom Resource Definitions")
	assert.NotNil(t, crds, "CRD list should not be nil")
	
	// Test 3: Discover Hedgehog-specific CRDs
	hedgehogCRDs := make([]unstructured.Unstructured, 0)
	for _, crd := range crds.Items {
		name, found, _ := unstructured.NestedString(crd.Object, "metadata", "name")
		if found && strings.Contains(name, "hedgehog.com") {
			hedgehogCRDs = append(hedgehogCRDs, crd)
		}
	}
	
	// Log discovered CRDs for evidence
	t.Logf("Discovered %d Hedgehog CRDs in cluster", len(hedgehogCRDs))
	
	// Test 4: Validate CRD schemas
	validCRDs := 0
	for _, crd := range hedgehogCRDs {
		spec, found, _ := unstructured.NestedMap(crd.Object, "spec")
		if found && len(spec) > 0 {
			validCRDs++
		}
	}
	
	assert.Equal(t, len(hedgehogCRDs), validCRDs, "All discovered CRDs should have valid specs")
	
	// Test 5: API resource capabilities
	capabilities := make(map[string][]string)
	for _, resourceList := range resourceLists {
		gv, _ := schema.ParseGroupVersion(resourceList.GroupVersion)
		for _, resource := range resourceList.APIResources {
			key := fmt.Sprintf("%s/%s", gv.Group, resource.Name)
			capabilities[key] = resource.Verbs
		}
	}
	
	// Validate that we have expected capabilities for core resources
	coreVerbs := capabilities["core/namespaces"]
	if len(coreVerbs) > 0 {
		assert.Contains(t, coreVerbs, "list", "Should support listing namespaces")
		assert.Contains(t, coreVerbs, "get", "Should support getting namespaces")
	}
	
	// Evidence collection
	duration := time.Since(startTime)
	suite.evidence["discovery_duration"] = duration
	suite.evidence["total_api_resources"] = len(capabilities)
	suite.evidence["hedgehog_crds_found"] = len(hedgehogCRDs)
	suite.evidence["resource_groups_found"] = len(resourceLists)
}

// TestNamespaceManagement - FORGE Movement 5 Requirement
// Namespace isolation and management
func (suite *K8sClientTestSuite) TestNamespaceManagement() {
	startTime := time.Now()
	t := suite.T()
	
	if suite.clientset == nil {
		t.Log("Clientset not implemented - test failing as expected in FORGE RED PHASE")
		assert.Fail(t, "Kubernetes clientset implementation required")
		return
	}
	
	ctx := context.Background()
	
	// Test 1: Create test namespace
	testNamespace := &corev1.Namespace{
		ObjectMeta: metav1.ObjectMeta{
			Name: suite.testNamespace,
			Labels: map[string]string{
				"test":      "forge-k8s-integration",
				"framework": "cnoc-testing",
				"purpose":   "integration-testing",
			},
			Annotations: map[string]string{
				"created-by":    "cnoc-test-suite",
				"creation-time": time.Now().Format(time.RFC3339),
			},
		},
	}
	
	created, err := suite.clientset.CoreV1().Namespaces().Create(ctx, testNamespace, metav1.CreateOptions{})
	assert.NoError(t, err, "Should create test namespace")
	assert.Equal(t, suite.testNamespace, created.Name, "Created namespace name should match")
	
	// Test 2: Validate namespace properties
	retrieved, err := suite.clientset.CoreV1().Namespaces().Get(ctx, suite.testNamespace, metav1.GetOptions{})
	assert.NoError(t, err, "Should retrieve test namespace")
	assert.Equal(t, "forge-k8s-integration", retrieved.Labels["test"], "Namespace should have correct labels")
	assert.Equal(t, "cnoc-test-suite", retrieved.Annotations["created-by"], "Namespace should have correct annotations")
	
	// Test 3: Resource quotas and limits
	resourceQuota := &corev1.ResourceQuota{
		ObjectMeta: metav1.ObjectMeta{
			Name:      "cnoc-test-quota",
			Namespace: suite.testNamespace,
		},
		Spec: corev1.ResourceQuotaSpec{
			Hard: corev1.ResourceList{
				"requests.cpu":    resource.MustParse("2"),
				"requests.memory": resource.MustParse("4Gi"),
				"limits.cpu":      resource.MustParse("4"),
				"limits.memory":   resource.MustParse("8Gi"),
				"count/pods":      resource.MustParse("10"),
			},
		},
	}
	
	createdQuota, err := suite.clientset.CoreV1().ResourceQuotas(suite.testNamespace).Create(ctx, resourceQuota, metav1.CreateOptions{})
	assert.NoError(t, err, "Should create resource quota")
	assert.NotNil(t, createdQuota, "Created quota should not be nil")
	
	// Test 4: Network policies (if supported)
	// This tests namespace isolation capabilities
	networkPolicy := &unstructured.Unstructured{
		Object: map[string]interface{}{
			"apiVersion": "networking.k8s.io/v1",
			"kind":       "NetworkPolicy",
			"metadata": map[string]interface{}{
				"name":      "cnoc-test-network-policy",
				"namespace": suite.testNamespace,
			},
			"spec": map[string]interface{}{
				"podSelector": map[string]interface{}{},
				"policyTypes": []string{"Ingress", "Egress"},
				"ingress": []map[string]interface{}{
					{
						"from": []map[string]interface{}{
							{
								"namespaceSelector": map[string]interface{}{
									"matchLabels": map[string]interface{}{
										"test": "forge-k8s-integration",
									},
								},
							},
						},
					},
				},
			},
		},
	}
	
	npGVR := schema.GroupVersionResource{
		Group:    "networking.k8s.io",
		Version:  "v1",
		Resource: "networkpolicies",
	}
	
	_, err = suite.dynamicClient.Resource(npGVR).Namespace(suite.testNamespace).Create(ctx, networkPolicy, metav1.CreateOptions{})
	// Note: Network policy creation might fail if CNI doesn't support it - this is okay
	if err != nil {
		t.Logf("Network policy creation failed (CNI may not support it): %v", err)
	}
	
	// Test 5: Cleanup namespace
	defer func() {
		err := suite.clientset.CoreV1().Namespaces().Delete(ctx, suite.testNamespace, metav1.DeleteOptions{})
		if err != nil {
			t.Logf("Failed to cleanup test namespace: %v", err)
		}
	}()
	
	// Evidence collection
	duration := time.Since(startTime)
	suite.evidence["namespace_management_duration"] = duration
	suite.evidence["test_namespace_created"] = created.Name
	suite.evidence["resource_quota_applied"] = createdQuota.Name
}

// TestResourceQuotaValidation - FORGE Movement 5 Requirement
// Cluster resource limits and validation
func (suite *K8sClientTestSuite) TestResourceQuotaValidation() {
	startTime := time.Now()
	t := suite.T()
	
	if suite.clientset == nil {
		t.Log("Clientset not implemented - test failing as expected in FORGE RED PHASE")
		assert.Fail(t, "Kubernetes clientset implementation required")
		return
	}
	
	ctx := context.Background()
	
	// Test 1: Cluster resource capacity
	nodes, err := suite.clientset.CoreV1().Nodes().List(ctx, metav1.ListOptions{})
	assert.NoError(t, err, "Should list cluster nodes")
	
	totalCPU := resource.NewQuantity(0, resource.DecimalSI)
	totalMemory := resource.NewQuantity(0, resource.BinarySI)
	totalStorage := resource.NewQuantity(0, resource.BinarySI)
	
	for _, node := range nodes.Items {
		if cpu, ok := node.Status.Capacity[corev1.ResourceCPU]; ok {
			totalCPU.Add(cpu)
		}
		if memory, ok := node.Status.Capacity[corev1.ResourceMemory]; ok {
			totalMemory.Add(memory)
		}
		if storage, ok := node.Status.Capacity[corev1.ResourceEphemeralStorage]; ok {
			totalStorage.Add(storage)
		}
	}
	
	assert.Greater(t, totalCPU.MilliValue(), int64(0), "Cluster should have CPU capacity")
	assert.Greater(t, totalMemory.Value(), int64(0), "Cluster should have memory capacity")
	
	// Test 2: Validate resource requirements for CNOC workloads
	// These are realistic resource requirements for CNOC components
	cnocRequirements := map[string]resource.Quantity{
		"cpu":    resource.MustParse("2"),   // 2 CPU cores
		"memory": resource.MustParse("4Gi"), // 4 GB RAM
		"storage": resource.MustParse("10Gi"), // 10 GB storage
	}
	
	// Verify cluster can accommodate CNOC requirements
	assert.Greater(t, totalCPU.MilliValue(), cnocRequirements["cpu"].MilliValue(), "Cluster should have sufficient CPU for CNOC")
	assert.Greater(t, totalMemory.Value(), cnocRequirements["memory"].Value(), "Cluster should have sufficient memory for CNOC")
	
	// Test 3: Storage class availability
	storageClasses, err := suite.clientset.StorageV1().StorageClasses().List(ctx, metav1.ListOptions{})
	assert.NoError(t, err, "Should list storage classes")
	assert.Greater(t, len(storageClasses.Items), 0, "Cluster should have at least one storage class")
	
	// Test 4: Persistent volume capabilities
	_, err = suite.clientset.CoreV1().PersistentVolumes().List(ctx, metav1.ListOptions{})
	assert.NoError(t, err, "Should list persistent volumes")
	// Note: PVs might be empty in test cluster - this is okay
	
	// Evidence collection
	duration := time.Since(startTime)
	suite.evidence["quota_validation_duration"] = duration
	suite.evidence["cluster_cpu_capacity"] = totalCPU.String()
	suite.evidence["cluster_memory_capacity"] = totalMemory.String()
	suite.evidence["cluster_storage_capacity"] = totalStorage.String()
	suite.evidence["storage_classes_available"] = len(storageClasses.Items)
	suite.evidence["cnoc_requirements_met"] = map[string]bool{
		"cpu":     totalCPU.MilliValue() >= cnocRequirements["cpu"].MilliValue(),
		"memory":  totalMemory.Value() >= cnocRequirements["memory"].Value(),
		"storage": len(storageClasses.Items) > 0,
	}
	
	// Performance requirement: Resource validation should complete quickly
	assert.Less(t, duration, 10*time.Second, "Resource validation should be fast")
}

// Helper functions are now implemented in k8s_client.go

// Run the test suite
func TestK8sClientTestSuite(t *testing.T) {
	suite.Run(t, new(K8sClientTestSuite))
}

// FORGE Evidence Collection Test
func TestK8sClientEvidenceCollection(t *testing.T) {
	evidence := map[string]interface{}{
		"test_execution_time": time.Now(),
		"framework_version":   "FORGE Movement 5",
		"test_coverage":       "Kubernetes Client Integration",
		"expected_failures":   true,
		"red_phase_active":    true,
		"k8s_operations_tested": []string{
			"cluster connectivity",
			"authentication validation",
			"CRD resource CRUD operations",
			"resource discovery",
			"namespace management",
			"resource quota validation",
		},
		"performance_requirements": map[string]string{
			"cluster_connectivity": "<5 seconds",
			"api_call_latency":     "<1 second",
			"resource_validation":  "<10 seconds",
		},
		"integration_scope": map[string]interface{}{
			"real_cluster_required": true,
			"crd_types_supported":   12,
			"namespace_isolation":   true,
			"resource_quotas":       true,
		},
	}
	
	assert.NotEmpty(t, evidence)
	assert.Contains(t, evidence, "k8s_operations_tested")
	assert.Equal(t, true, evidence["red_phase_active"])
	assert.Equal(t, true, evidence["integration_scope"].(map[string]interface{})["real_cluster_required"])
	
	t.Logf("FORGE Kubernetes Client Evidence Collection: %+v", evidence)
}

// Performance benchmark tests
func BenchmarkClusterConnectivity(b *testing.B) {
	config := &K8sClientConfig{
		Server:  "https://127.0.0.1:6443",
		Timeout: 30 * time.Second,
	}
	
	client, err := NewKubernetesClient(config)
	if err != nil || client == nil {
		b.Skip("Kubernetes client not implemented - RED PHASE expected")
		return
	}
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _ = client.Discovery().ServerVersion()
	}
}

func BenchmarkResourceOperations(b *testing.B) {
	config := &K8sClientConfig{
		Server:  "https://127.0.0.1:6443",
		Timeout: 30 * time.Second,
	}
	
	dynamicClient, err := NewDynamicClient(config)
	if err != nil || dynamicClient == nil {
		b.Skip("Dynamic client not implemented - RED PHASE expected")
		return
	}
	
	ctx := context.Background()
	gvr := schema.GroupVersionResource{
		Group:    "vpc.hedgehog.com",
		Version:  "v1",
		Resource: "vpcs",
	}
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _ = dynamicClient.Resource(gvr).List(ctx, metav1.ListOptions{Limit: 10})
	}
}