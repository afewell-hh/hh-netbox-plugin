package kubernetes

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/client-go/discovery"
	"k8s.io/client-go/dynamic"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	"k8s.io/client-go/tools/clientcmd"
)

// KubernetesClientImpl implements Kubernetes client operations
type KubernetesClientImpl struct {
	restConfig   *rest.Config
	clientset    kubernetes.Interface
	dynamicClient dynamic.Interface
	discoveryClient discovery.DiscoveryInterface
	config       *K8sClientConfig
}

// NewKubernetesClient creates a new Kubernetes client
func NewKubernetesClient(config *K8sClientConfig) (kubernetes.Interface, error) {
	client, err := createK8sClient(config)
	if err != nil {
		return nil, err
	}
	return client.clientset, nil
}

// NewDynamicClient creates a new dynamic Kubernetes client
func NewDynamicClient(config *K8sClientConfig) (dynamic.Interface, error) {
	client, err := createK8sClient(config)
	if err != nil {
		return nil, err
	}
	return client.dynamicClient, nil
}

// NewDiscoveryClient creates a new discovery client
func NewDiscoveryClient(config *K8sClientConfig) (discovery.DiscoveryInterface, error) {
	client, err := createK8sClient(config)
	if err != nil {
		return nil, err
	}
	return client.discoveryClient, nil
}

// createK8sClient creates a comprehensive Kubernetes client
func createK8sClient(config *K8sClientConfig) (*KubernetesClientImpl, error) {
	if config == nil {
		return nil, fmt.Errorf("client config is required")
	}
	
	restConfig, err := buildRestConfig(config)
	if err != nil {
		return nil, fmt.Errorf("failed to build rest config: %w", err)
	}
	
	// Create clientset
	clientset, err := kubernetes.NewForConfig(restConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create clientset: %w", err)
	}
	
	// Create dynamic client
	dynamicClient, err := dynamic.NewForConfig(restConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create dynamic client: %w", err)
	}
	
	// Create discovery client
	discoveryClient, err := discovery.NewDiscoveryClientForConfig(restConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create discovery client: %w", err)
	}
	
	return &KubernetesClientImpl{
		restConfig:      restConfig,
		clientset:       clientset,
		dynamicClient:   dynamicClient,
		discoveryClient: discoveryClient,
		config:          config,
	}, nil
}

// buildRestConfig builds Kubernetes REST configuration
func buildRestConfig(config *K8sClientConfig) (*rest.Config, error) {
	var restConfig *rest.Config
	var err error
	
	// Try to load from kubeconfig first
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
	
	// Try to build config from kubeconfig file
	if _, err := os.Stat(kubeconfigPath); err == nil {
		restConfig, err = clientcmd.BuildConfigFromFlags("", kubeconfigPath)
		if err == nil {
			// Apply custom configuration
			applyConfigOverrides(restConfig, config)
			return restConfig, nil
		}
	}
	
	// Fallback to in-cluster config
	restConfig, err = rest.InClusterConfig()
	if err == nil {
		applyConfigOverrides(restConfig, config)
		return restConfig, nil
	}
	
	// Fallback to building config from provided parameters
	restConfig = &rest.Config{
		Host:            config.Server,
		TLSClientConfig: rest.TLSClientConfig{},
	}
	
	if config.Token != "" {
		restConfig.BearerToken = config.Token
	}
	
	if config.CertData != nil && config.KeyData != nil {
		restConfig.TLSClientConfig.CertData = config.CertData
		restConfig.TLSClientConfig.KeyData = config.KeyData
	}
	
	if config.CAData != nil {
		restConfig.TLSClientConfig.CAData = config.CAData
	}
	
	if config.Insecure {
		restConfig.TLSClientConfig.Insecure = true
	}
	
	applyConfigOverrides(restConfig, config)
	
	return restConfig, nil
}

// applyConfigOverrides applies custom configuration to rest config
func applyConfigOverrides(restConfig *rest.Config, config *K8sClientConfig) {
	if config.Timeout > 0 {
		restConfig.Timeout = config.Timeout
	}
	
	if config.UserAgent != "" {
		restConfig.UserAgent = config.UserAgent
	}
	
	if config.QPS > 0 {
		restConfig.QPS = config.QPS
	}
	
	if config.Burst > 0 {
		restConfig.Burst = config.Burst
	}
	
	if config.Impersonate != "" {
		restConfig.Impersonate = rest.ImpersonationConfig{
			UserName: config.Impersonate,
		}
	}
}

// ClusterConnector provides cluster connection management
type ClusterConnector struct {
	client *KubernetesClientImpl
}

// NewClusterConnector creates a new cluster connector
func NewClusterConnector(config *K8sClientConfig) (*ClusterConnector, error) {
	client, err := createK8sClient(config)
	if err != nil {
		return nil, err
	}
	
	return &ClusterConnector{
		client: client,
	}, nil
}

// TestConnection tests connectivity to the cluster
func (cc *ClusterConnector) TestConnection(ctx context.Context) (*ClusterInfo, error) {
	// Test basic connectivity
	serverVersion, err := cc.client.clientset.Discovery().ServerVersion()
	if err != nil {
		return nil, fmt.Errorf("failed to get server version: %w", err)
	}
	
	// Get API versions
	apiVersions, err := cc.client.clientset.Discovery().ServerGroups()
	if err != nil {
		return nil, fmt.Errorf("failed to get API groups: %w", err)
	}
	
	// Get resources
	resourceLists, err := cc.client.discoveryClient.ServerPreferredResources()
	if err != nil {
		// Partial failure is acceptable
		resourceLists = []*metav1.APIResourceList{}
	}
	
	var allResources []metav1.APIResource
	for _, resourceList := range resourceLists {
		allResources = append(allResources, resourceList.APIResources...)
	}
	
	// Get namespaces
	namespaces, err := cc.client.clientset.CoreV1().Namespaces().List(ctx, metav1.ListOptions{})
	if err != nil {
		return nil, fmt.Errorf("failed to list namespaces: %w", err)
	}
	
	var namespaceNames []string
	for _, ns := range namespaces.Items {
		namespaceNames = append(namespaceNames, ns.Name)
	}
	
	// Get nodes
	nodes, err := cc.client.clientset.CoreV1().Nodes().List(ctx, metav1.ListOptions{})
	if err != nil {
		return nil, fmt.Errorf("failed to list nodes: %w", err)
	}
	
	// Check for CRD support
	crdSupported := false
	for _, group := range apiVersions.Groups {
		if group.Name == "apiextensions.k8s.io" {
			crdSupported = true
			break
		}
	}
	
	// Get custom resources if CRDs are supported
	var customResources []CRDDefinition
	if crdSupported {
		customResources = cc.getCustomResources(ctx)
	}
	
	// Get storage classes
	storageClasses, err := cc.client.clientset.StorageV1().StorageClasses().List(ctx, metav1.ListOptions{})
	if err != nil {
		storageClasses = nil // Not critical
	}
	
	var storageClassNames []string
	if storageClasses != nil {
		for _, sc := range storageClasses.Items {
			storageClassNames = append(storageClassNames, sc.Name)
		}
	}
	
	// Build API version list
	var apiVersionStrings []string
	for _, group := range apiVersions.Groups {
		for _, version := range group.Versions {
			apiVersionStrings = append(apiVersionStrings, version.GroupVersion)
		}
	}
	
	clusterInfo := &ClusterInfo{
		Version:         serverVersion.String(),
		APIVersions:     apiVersionStrings,
		Resources:       allResources,
		CRDsSupported:   crdSupported,
		NamespacesList:  namespaceNames,
		NodeCount:       len(nodes.Items),
		CustomResources: customResources,
		StorageClasses:  storageClassNames,
		Permissions:     make(map[string]bool),
	}
	
	return clusterInfo, nil
}

// getCustomResources retrieves custom resource definitions
func (cc *ClusterConnector) getCustomResources(ctx context.Context) []CRDDefinition {
	crdGVR := schema.GroupVersionResource{
		Group:    "apiextensions.k8s.io",
		Version:  "v1",
		Resource: "customresourcedefinitions",
	}
	
	crds, err := cc.client.dynamicClient.Resource(crdGVR).List(ctx, metav1.ListOptions{})
	if err != nil {
		return []CRDDefinition{}
	}
	
	var customResources []CRDDefinition
	for _, crd := range crds.Items {
		spec, found, _ := unstructured.NestedMap(crd.Object, "spec")
		if !found {
			continue
		}
		
		group, _, _ := unstructured.NestedString(spec, "group")
		names, found, _ := unstructured.NestedMap(spec, "names")
		if !found {
			continue
		}
		
		kind, _, _ := unstructured.NestedString(names, "kind")
		plural, _, _ := unstructured.NestedString(names, "plural")
		
		versions, found, _ := unstructured.NestedSlice(spec, "versions")
		if !found {
			continue
		}
		
		var version string
		if len(versions) > 0 {
			if versionMap, ok := versions[0].(map[string]interface{}); ok {
				version, _, _ = unstructured.NestedString(versionMap, "name")
			}
		}
		
		scope, _, _ := unstructured.NestedString(spec, "scope")
		namespaced := scope == "Namespaced"
		
		customResources = append(customResources, CRDDefinition{
			Group:      group,
			Version:    version,
			Kind:       kind,
			PluralName: plural,
			Namespaced: namespaced,
		})
	}
	
	return customResources
}

// CRDResourceManager provides CRD resource management
type CRDResourceManager struct {
	client *KubernetesClientImpl
}

// NewCRDResourceManager creates a new CRD resource manager
func NewCRDResourceManager(config *K8sClientConfig) (*CRDResourceManager, error) {
	client, err := createK8sClient(config)
	if err != nil {
		return nil, err
	}
	
	return &CRDResourceManager{
		client: client,
	}, nil
}

// CreateResource creates a CRD resource
func (crm *CRDResourceManager) CreateResource(ctx context.Context, gvr schema.GroupVersionResource, namespace string, resource *unstructured.Unstructured) (*ResourceOperationResult, error) {
	start := time.Now()
	
	var created *unstructured.Unstructured
	var err error
	
	if namespace != "" {
		created, err = crm.client.dynamicClient.Resource(gvr).Namespace(namespace).Create(ctx, resource, metav1.CreateOptions{})
	} else {
		created, err = crm.client.dynamicClient.Resource(gvr).Create(ctx, resource, metav1.CreateOptions{})
	}
	
	result := &ResourceOperationResult{
		Success:   err == nil,
		Operation: "create",
		Resource:  created,
		Duration:  time.Since(start),
	}
	
	if err != nil {
		result.Error = err.Error()
	}
	
	return result, err
}

// GetResource gets a CRD resource
func (crm *CRDResourceManager) GetResource(ctx context.Context, gvr schema.GroupVersionResource, namespace, name string) (*ResourceOperationResult, error) {
	start := time.Now()
	
	var resource *unstructured.Unstructured
	var err error
	
	if namespace != "" {
		resource, err = crm.client.dynamicClient.Resource(gvr).Namespace(namespace).Get(ctx, name, metav1.GetOptions{})
	} else {
		resource, err = crm.client.dynamicClient.Resource(gvr).Get(ctx, name, metav1.GetOptions{})
	}
	
	result := &ResourceOperationResult{
		Success:   err == nil,
		Operation: "get",
		Resource:  resource,
		Duration:  time.Since(start),
	}
	
	if err != nil {
		result.Error = err.Error()
	}
	
	return result, err
}

// UpdateResource updates a CRD resource
func (crm *CRDResourceManager) UpdateResource(ctx context.Context, gvr schema.GroupVersionResource, namespace string, resource *unstructured.Unstructured) (*ResourceOperationResult, error) {
	start := time.Now()
	
	var updated *unstructured.Unstructured
	var err error
	
	if namespace != "" {
		updated, err = crm.client.dynamicClient.Resource(gvr).Namespace(namespace).Update(ctx, resource, metav1.UpdateOptions{})
	} else {
		updated, err = crm.client.dynamicClient.Resource(gvr).Update(ctx, resource, metav1.UpdateOptions{})
	}
	
	result := &ResourceOperationResult{
		Success:   err == nil,
		Operation: "update",
		Resource:  updated,
		Duration:  time.Since(start),
	}
	
	if err != nil {
		result.Error = err.Error()
	}
	
	return result, err
}

// DeleteResource deletes a CRD resource
func (crm *CRDResourceManager) DeleteResource(ctx context.Context, gvr schema.GroupVersionResource, namespace, name string) (*ResourceOperationResult, error) {
	start := time.Now()
	
	var err error
	
	if namespace != "" {
		err = crm.client.dynamicClient.Resource(gvr).Namespace(namespace).Delete(ctx, name, metav1.DeleteOptions{})
	} else {
		err = crm.client.dynamicClient.Resource(gvr).Delete(ctx, name, metav1.DeleteOptions{})
	}
	
	result := &ResourceOperationResult{
		Success:   err == nil,
		Operation: "delete",
		Duration:  time.Since(start),
	}
	
	if err != nil {
		result.Error = err.Error()
	}
	
	return result, err
}

// ListResources lists CRD resources
func (crm *CRDResourceManager) ListResources(ctx context.Context, gvr schema.GroupVersionResource, namespace string, options metav1.ListOptions) (*ResourceOperationResult, error) {
	start := time.Now()
	
	var resourceList *unstructured.UnstructuredList
	var err error
	
	if namespace != "" {
		resourceList, err = crm.client.dynamicClient.Resource(gvr).Namespace(namespace).List(ctx, options)
	} else {
		resourceList, err = crm.client.dynamicClient.Resource(gvr).List(ctx, options)
	}
	
	result := &ResourceOperationResult{
		Success:   err == nil,
		Operation: "list",
		Duration:  time.Since(start),
	}
	
	if err != nil {
		result.Error = err.Error()
	} else if resourceList != nil {
		result.Resources = resourceList.Items
	}
	
	return result, err
}

// NamespaceManager provides namespace management
type NamespaceManager struct {
	client *KubernetesClientImpl
}

// NewNamespaceManager creates a new namespace manager
func NewNamespaceManager(config *K8sClientConfig) (*NamespaceManager, error) {
	client, err := createK8sClient(config)
	if err != nil {
		return nil, err
	}
	
	return &NamespaceManager{
		client: client,
	}, nil
}

// CreateNamespace creates a namespace
func (nm *NamespaceManager) CreateNamespace(ctx context.Context, namespace *corev1.Namespace) (*corev1.Namespace, error) {
	return nm.client.clientset.CoreV1().Namespaces().Create(ctx, namespace, metav1.CreateOptions{})
}

// GetNamespace gets a namespace
func (nm *NamespaceManager) GetNamespace(ctx context.Context, name string) (*corev1.Namespace, error) {
	return nm.client.clientset.CoreV1().Namespaces().Get(ctx, name, metav1.GetOptions{})
}

// ListNamespaces lists namespaces
func (nm *NamespaceManager) ListNamespaces(ctx context.Context, options metav1.ListOptions) (*corev1.NamespaceList, error) {
	return nm.client.clientset.CoreV1().Namespaces().List(ctx, options)
}

// DeleteNamespace deletes a namespace
func (nm *NamespaceManager) DeleteNamespace(ctx context.Context, name string) error {
	return nm.client.clientset.CoreV1().Namespaces().Delete(ctx, name, metav1.DeleteOptions{})
}

// ResourceDiscovery provides resource discovery capabilities
type ResourceDiscovery struct {
	client *KubernetesClientImpl
}

// NewResourceDiscovery creates a new resource discovery client
func NewResourceDiscovery(config *K8sClientConfig) (*ResourceDiscovery, error) {
	client, err := createK8sClient(config)
	if err != nil {
		return nil, err
	}
	
	return &ResourceDiscovery{
		client: client,
	}, nil
}

// DiscoverResources discovers available API resources
func (rd *ResourceDiscovery) DiscoverResources(ctx context.Context) ([]*metav1.APIResourceList, error) {
	return rd.client.discoveryClient.ServerPreferredResources()
}

// DiscoverCRDs discovers custom resource definitions
func (rd *ResourceDiscovery) DiscoverCRDs(ctx context.Context) ([]CRDDefinition, error) {
	crdGVR := schema.GroupVersionResource{
		Group:    "apiextensions.k8s.io",
		Version:  "v1",
		Resource: "customresourcedefinitions",
	}
	
	crds, err := rd.client.dynamicClient.Resource(crdGVR).List(ctx, metav1.ListOptions{})
	if err != nil {
		return nil, err
	}
	
	var crdDefs []CRDDefinition
	for _, crd := range crds.Items {
		crdDef := rd.parseCRDDefinition(&crd)
		if crdDef != nil {
			crdDefs = append(crdDefs, *crdDef)
		}
	}
	
	return crdDefs, nil
}

// parseCRDDefinition parses a CRD into CRDDefinition
func (rd *ResourceDiscovery) parseCRDDefinition(crd *unstructured.Unstructured) *CRDDefinition {
	spec, found, _ := unstructured.NestedMap(crd.Object, "spec")
	if !found {
		return nil
	}
	
	group, _, _ := unstructured.NestedString(spec, "group")
	names, found, _ := unstructured.NestedMap(spec, "names")
	if !found {
		return nil
	}
	
	kind, _, _ := unstructured.NestedString(names, "kind")
	plural, _, _ := unstructured.NestedString(names, "plural")
	
	versions, found, _ := unstructured.NestedSlice(spec, "versions")
	if !found {
		return nil
	}
	
	var version string
	if len(versions) > 0 {
		if versionMap, ok := versions[0].(map[string]interface{}); ok {
			version, _, _ = unstructured.NestedString(versionMap, "name")
		}
	}
	
	scope, _, _ := unstructured.NestedString(spec, "scope")
	namespaced := scope == "Namespaced"
	
	return &CRDDefinition{
		Group:      group,
		Version:    version,
		Kind:       kind,
		PluralName: plural,
		Namespaced: namespaced,
	}
}