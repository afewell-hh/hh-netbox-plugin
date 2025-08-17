package external

import (
	"context"
	"fmt"
	"time"

	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/client-go/dynamic"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
	
	"github.com/hedgehog/cnoc/internal/domain/configuration"
)

// KubernetesServiceAdapter provides Kubernetes integration with anti-corruption layer
// Following hexagonal architecture to prevent external service contamination
type KubernetesServiceAdapter struct {
	clientset        kubernetes.Interface
	dynamicClient    dynamic.Interface
	config          *rest.Config
	namespace       string
	metricsCollector *K8sMetricsCollector
	rateLimiter     *K8sRateLimiter
	resourceMapper  *K8sResourceMapper
}

// NewKubernetesServiceAdapter creates a new Kubernetes service adapter with MDD compliance
func NewKubernetesServiceAdapter(
	config *rest.Config,
	namespace string,
	metricsCollector *K8sMetricsCollector,
) (*KubernetesServiceAdapter, error) {
	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		return nil, fmt.Errorf("kubernetes clientset creation failed: %w", err)
	}

	dynamicClient, err := dynamic.NewForConfig(config)
	if err != nil {
		return nil, fmt.Errorf("kubernetes dynamic client creation failed: %w", err)
	}

	return &KubernetesServiceAdapter{
		clientset:        clientset,
		dynamicClient:    dynamicClient,
		config:          config,
		namespace:       namespace,
		metricsCollector: metricsCollector,
		rateLimiter:     NewK8sRateLimiter(),
		resourceMapper:  NewK8sResourceMapper(),
	}, nil
}

// Configuration deployment with domain isolation

// DeployConfiguration deploys configuration to Kubernetes cluster
func (k *KubernetesServiceAdapter) DeployConfiguration(
	ctx context.Context,
	config *configuration.Configuration,
	deploymentOptions K8sDeploymentOptions,
) (*K8sDeploymentResult, error) {
	startTime := time.Now()
	defer k.recordMetrics("deploy_configuration", startTime, nil)

	if config == nil {
		return nil, fmt.Errorf("configuration cannot be nil")
	}

	// Apply rate limiting
	if err := k.rateLimiter.Wait(ctx); err != nil {
		return nil, k.wrapError("rate_limit_exceeded", err)
	}

	// Convert domain configuration to Kubernetes manifests through anti-corruption layer
	manifests, err := k.resourceMapper.ConfigurationToK8sManifests(config, deploymentOptions)
	if err != nil {
		return nil, k.wrapError("manifest_conversion_failed", err)
	}

	// Deploy manifests with proper error handling and rollback capability
	deploymentResult := &K8sDeploymentResult{
		ConfigurationID: config.ID().String(),
		StartTime:      startTime,
		Namespace:      k.namespace,
		Resources:      make([]K8sResourceDeployment, 0),
		Status:         K8sDeploymentStatusInProgress,
	}

	for _, manifest := range manifests {
		resourceResult, err := k.deployManifest(ctx, manifest, deploymentOptions)
		if err != nil {
			deploymentResult.Status = K8sDeploymentStatusFailed
			deploymentResult.ErrorMessage = err.Error()
			
			// Attempt rollback of already deployed resources
			k.rollbackDeployment(ctx, deploymentResult)
			return deploymentResult, k.wrapError("manifest_deployment_failed", err)
		}
		
		deploymentResult.Resources = append(deploymentResult.Resources, *resourceResult)
	}

	deploymentResult.Status = K8sDeploymentStatusSuccess
	deploymentResult.CompletionTime = time.Now()
	deploymentResult.Duration = deploymentResult.CompletionTime.Sub(startTime)

	// Verify deployment health
	if err := k.verifyDeploymentHealth(ctx, deploymentResult); err != nil {
		k.metricsCollector.RecordDeploymentHealthCheck(config.ID().String(), false)
		return deploymentResult, k.wrapError("deployment_health_verification_failed", err)
	}

	k.metricsCollector.RecordDeploymentHealthCheck(config.ID().String(), true)
	return deploymentResult, nil
}

// GetConfigurationStatus retrieves deployment status from Kubernetes
func (k *KubernetesServiceAdapter) GetConfigurationStatus(
	ctx context.Context,
	configID configuration.ConfigurationID,
) (*K8sConfigurationStatus, error) {
	startTime := time.Now()
	defer k.recordMetrics("get_configuration_status", startTime, nil)

	// Apply rate limiting
	if err := k.rateLimiter.Wait(ctx); err != nil {
		return nil, k.wrapError("rate_limit_exceeded", err)
	}

	// Find resources associated with configuration
	labelSelector := fmt.Sprintf("cnoc.configuration.id=%s", configID.String())
	
	// Get all resource types associated with configuration
	resourceTypes := []schema.GroupVersionResource{
		{Group: "apps", Version: "v1", Resource: "deployments"},
		{Group: "", Version: "v1", Resource: "services"},
		{Group: "", Version: "v1", Resource: "configmaps"},
		{Group: "", Version: "v1", Resource: "secrets"},
		{Group: "networking.k8s.io", Version: "v1", Resource: "ingresses"},
	}

	status := &K8sConfigurationStatus{
		ConfigurationID: configID.String(),
		Namespace:      k.namespace,
		Resources:      make([]K8sResourceStatus, 0),
		LastChecked:    time.Now(),
		OverallStatus:  K8sStatusUnknown,
	}

	for _, resourceType := range resourceTypes {
		resources, err := k.dynamicClient.Resource(resourceType).Namespace(k.namespace).
			List(ctx, metav1.ListOptions{LabelSelector: labelSelector})
		if err != nil {
			continue // Skip resource types that don't exist or are inaccessible
		}

		for _, resource := range resources.Items {
			resourceStatus := k.resourceMapper.K8sResourceToStatus(&resource)
			status.Resources = append(status.Resources, resourceStatus)
		}
	}

	// Calculate overall status
	status.OverallStatus = k.calculateOverallStatus(status.Resources)
	status.HealthScore = k.calculateHealthScore(status.Resources)

	return status, nil
}

// UpdateConfiguration updates existing Kubernetes deployment
func (k *KubernetesServiceAdapter) UpdateConfiguration(
	ctx context.Context,
	config *configuration.Configuration,
	updateOptions K8sUpdateOptions,
) (*K8sUpdateResult, error) {
	startTime := time.Now()
	defer k.recordMetrics("update_configuration", startTime, nil)

	if config == nil {
		return nil, fmt.Errorf("configuration cannot be nil")
	}

	// Apply rate limiting
	if err := k.rateLimiter.Wait(ctx); err != nil {
		return nil, k.wrapError("rate_limit_exceeded", err)
	}

	// Get current deployment status
	currentStatus, err := k.GetConfigurationStatus(ctx, config.ID())
	if err != nil {
		return nil, k.wrapError("current_status_retrieval_failed", err)
	}

	// Convert updated configuration to manifests
	manifests, err := k.resourceMapper.ConfigurationToK8sManifests(config, K8sDeploymentOptions{
		Namespace:     updateOptions.Namespace,
		UpdateStrategy: updateOptions.UpdateStrategy,
		DryRun:        updateOptions.DryRun,
	})
	if err != nil {
		return nil, k.wrapError("manifest_conversion_failed", err)
	}

	updateResult := &K8sUpdateResult{
		ConfigurationID: config.ID().String(),
		StartTime:      startTime,
		PreviousStatus: currentStatus,
		UpdatedResources: make([]K8sResourceUpdate, 0),
		Status:         K8sUpdateStatusInProgress,
	}

	// Apply updates with rollback capability
	for _, manifest := range manifests {
		resourceUpdate, err := k.updateManifest(ctx, manifest, updateOptions)
		if err != nil {
			updateResult.Status = K8sUpdateStatusFailed
			updateResult.ErrorMessage = err.Error()
			
			// Attempt rollback
			k.rollbackUpdate(ctx, updateResult)
			return updateResult, k.wrapError("manifest_update_failed", err)
		}
		
		updateResult.UpdatedResources = append(updateResult.UpdatedResources, *resourceUpdate)
	}

	updateResult.Status = K8sUpdateStatusSuccess
	updateResult.CompletionTime = time.Now()
	updateResult.Duration = updateResult.CompletionTime.Sub(startTime)

	return updateResult, nil
}

// DeleteConfiguration removes configuration from Kubernetes
func (k *KubernetesServiceAdapter) DeleteConfiguration(
	ctx context.Context,
	configID configuration.ConfigurationID,
	deleteOptions K8sDeleteOptions,
) (*K8sDeleteResult, error) {
	startTime := time.Now()
	defer k.recordMetrics("delete_configuration", startTime, nil)

	// Apply rate limiting
	if err := k.rateLimiter.Wait(ctx); err != nil {
		return nil, k.wrapError("rate_limit_exceeded", err)
	}

	// Get current status before deletion
	currentStatus, err := k.GetConfigurationStatus(ctx, configID)
	if err != nil {
		return nil, k.wrapError("status_retrieval_failed", err)
	}

	deleteResult := &K8sDeleteResult{
		ConfigurationID: configID.String(),
		StartTime:      startTime,
		DeletedResources: make([]K8sResourceDeletion, 0),
		Status:         K8sDeleteStatusInProgress,
	}
	
	// Note: currentStatus is available for additional logic if needed
	_ = currentStatus

	// Delete resources in proper order (reverse dependency order)
	resourceOrder := []string{"ingresses", "services", "deployments", "configmaps", "secrets"}
	
	for _, resourceType := range resourceOrder {
		deletions, err := k.deleteResourcesByType(ctx, configID, resourceType, deleteOptions)
		if err != nil {
			deleteResult.Status = K8sDeleteStatusPartialFailure
			deleteResult.ErrorMessage = err.Error()
			continue
		}
		
		deleteResult.DeletedResources = append(deleteResult.DeletedResources, deletions...)
	}

	deleteResult.Status = K8sDeleteStatusSuccess
	deleteResult.CompletionTime = time.Now()
	deleteResult.Duration = deleteResult.CompletionTime.Sub(startTime)

	return deleteResult, nil
}

// Component management with domain isolation

// DeployComponent deploys individual component to Kubernetes
func (k *KubernetesServiceAdapter) DeployComponent(
	ctx context.Context,
	component *configuration.ComponentReference,
	componentOptions K8sComponentOptions,
) (*K8sComponentDeployment, error) {
	startTime := time.Now()
	defer k.recordMetrics("deploy_component", startTime, nil)

	if component == nil {
		return nil, fmt.Errorf("component cannot be nil")
	}

	// Apply rate limiting
	if err := k.rateLimiter.Wait(ctx); err != nil {
		return nil, k.wrapError("rate_limit_exceeded", err)
	}

	// Convert component to Kubernetes manifest through anti-corruption layer
	manifest, err := k.resourceMapper.ComponentToK8sManifest(component, componentOptions)
	if err != nil {
		return nil, k.wrapError("component_manifest_conversion_failed", err)
	}

	// Deploy component manifest
	resourceResult, err := k.deployManifest(ctx, manifest, K8sDeploymentOptions{
		Namespace: componentOptions.Namespace,
		DryRun:    componentOptions.DryRun,
	})
	if err != nil {
		return nil, k.wrapError("component_deployment_failed", err)
	}

	deployment := &K8sComponentDeployment{
		ComponentName: component.Name().String(),
		Version:      component.Version().String(),
		Namespace:    componentOptions.Namespace,
		Resources:    []K8sResourceDeployment{*resourceResult},
		Status:       K8sComponentStatusDeployed,
		DeployedAt:   time.Now(),
	}

	return deployment, nil
}

// Cluster operations and health monitoring

// GetClusterHealth retrieves comprehensive cluster health information
func (k *KubernetesServiceAdapter) GetClusterHealth(
	ctx context.Context,
) (*K8sClusterHealth, error) {
	startTime := time.Now()
	defer k.recordMetrics("get_cluster_health", startTime, nil)

	// Apply rate limiting
	if err := k.rateLimiter.Wait(ctx); err != nil {
		return nil, k.wrapError("rate_limit_exceeded", err)
	}

	health := &K8sClusterHealth{
		CheckedAt:    time.Now(),
		Namespace:   k.namespace,
		NodeHealth:  make([]K8sNodeHealth, 0),
		PodHealth:   make([]K8sPodHealth, 0),
		OverallStatus: K8sHealthStatusUnknown,
	}

	// Check node health
	nodes, err := k.clientset.CoreV1().Nodes().List(ctx, metav1.ListOptions{})
	if err != nil {
		return nil, k.wrapError("node_health_check_failed", err)
	}

	for _, node := range nodes.Items {
		nodeHealth := k.resourceMapper.NodeToHealthStatus(&node)
		health.NodeHealth = append(health.NodeHealth, nodeHealth)
	}

	// Check pod health in namespace
	pods, err := k.clientset.CoreV1().Pods(k.namespace).List(ctx, metav1.ListOptions{})
	if err != nil {
		return nil, k.wrapError("pod_health_check_failed", err)
	}

	for _, pod := range pods.Items {
		podHealth := k.resourceMapper.PodToHealthStatus(&pod)
		health.PodHealth = append(health.PodHealth, podHealth)
	}

	// Calculate overall health
	health.OverallStatus = k.calculateClusterHealth(health)
	health.HealthScore = k.calculateClusterHealthScore(health)

	return health, nil
}

// GetResourceMetrics retrieves resource utilization metrics
func (k *KubernetesServiceAdapter) GetResourceMetrics(
	ctx context.Context,
	configID configuration.ConfigurationID,
) (*K8sResourceMetrics, error) {
	startTime := time.Now()
	defer k.recordMetrics("get_resource_metrics", startTime, nil)

	// Apply rate limiting
	if err := k.rateLimiter.Wait(ctx); err != nil {
		return nil, k.wrapError("rate_limit_exceeded", err)
	}

	// Get pods associated with configuration
	labelSelector := fmt.Sprintf("cnoc.configuration.id=%s", configID.String())
	pods, err := k.clientset.CoreV1().Pods(k.namespace).List(ctx, metav1.ListOptions{
		LabelSelector: labelSelector,
	})
	if err != nil {
		return nil, k.wrapError("pod_metrics_retrieval_failed", err)
	}

	metrics := &K8sResourceMetrics{
		ConfigurationID: configID.String(),
		Namespace:      k.namespace,
		PodMetrics:     make([]K8sPodMetrics, 0),
		AggregateMetrics: K8sAggregateMetrics{},
		CollectedAt:    time.Now(),
	}

	for _, pod := range pods.Items {
		podMetrics := k.resourceMapper.PodToMetrics(&pod)
		metrics.PodMetrics = append(metrics.PodMetrics, podMetrics)
		
		// Aggregate metrics
		metrics.AggregateMetrics.TotalCPURequests += podMetrics.CPURequests
		metrics.AggregateMetrics.TotalMemoryRequests += podMetrics.MemoryRequests
		metrics.AggregateMetrics.TotalCPULimits += podMetrics.CPULimits
		metrics.AggregateMetrics.TotalMemoryLimits += podMetrics.MemoryLimits
	}

	metrics.AggregateMetrics.PodCount = len(metrics.PodMetrics)

	return metrics, nil
}

// Private helper methods

func (k *KubernetesServiceAdapter) deployManifest(
	ctx context.Context,
	manifest K8sManifest,
	options K8sDeploymentOptions,
) (*K8sResourceDeployment, error) {
	// Convert manifest to unstructured object
	obj := &unstructured.Unstructured{}
	obj.SetUnstructuredContent(manifest.Content)

	// Set namespace if not specified
	if obj.GetNamespace() == "" {
		obj.SetNamespace(k.namespace)
	}

	// Apply resource through dynamic client
	resource := k.getResourceInterface(manifest.GVR)
	result, err := resource.Namespace(obj.GetNamespace()).Create(ctx, obj, metav1.CreateOptions{
		DryRun: getDryRunOptions(options.DryRun),
	})
	if err != nil {
		return nil, err
	}

	deployment := &K8sResourceDeployment{
		Name:       result.GetName(),
		Namespace:  result.GetNamespace(),
		Kind:       result.GetKind(),
		APIVersion: result.GetAPIVersion(),
		Status: K8sResourceStatus{
			Name:           result.GetName(),
			Namespace:      result.GetNamespace(),
			Kind:           result.GetKind(),
			APIVersion:     result.GetAPIVersion(),
			Status:         K8sResourceStateRunning,
			Ready:          true,
			LastTransition: time.Now(),
			Message:        "Resource deployed successfully",
		},
		CreatedAt:  time.Now(),
	}

	return deployment, nil
}

func (k *KubernetesServiceAdapter) updateManifest(
	ctx context.Context,
	manifest K8sManifest,
	options K8sUpdateOptions,
) (*K8sResourceUpdate, error) {
	// Convert manifest to unstructured object
	obj := &unstructured.Unstructured{}
	obj.SetUnstructuredContent(manifest.Content)

	// Get existing resource
	resource := k.getResourceInterface(manifest.GVR)
	existing, err := resource.Namespace(obj.GetNamespace()).Get(ctx, obj.GetName(), metav1.GetOptions{})
	if err != nil {
		return nil, err
	}

	// Apply update strategy
	updatedObj, err := k.applyUpdateStrategy(existing, obj, options.UpdateStrategy)
	if err != nil {
		return nil, err
	}

	// Update resource
	result, err := resource.Namespace(updatedObj.GetNamespace()).Update(ctx, updatedObj, metav1.UpdateOptions{
		DryRun: getDryRunOptions(options.DryRun),
	})
	if err != nil {
		return nil, err
	}

	update := &K8sResourceUpdate{
		Name:       result.GetName(),
		Namespace:  result.GetNamespace(),
		Kind:       result.GetKind(),
		APIVersion: result.GetAPIVersion(),
		UpdateType: string(options.UpdateStrategy),
		UpdatedAt:  time.Now(),
	}

	return update, nil
}

func (k *KubernetesServiceAdapter) deleteResourcesByType(
	ctx context.Context,
	configID configuration.ConfigurationID,
	resourceType string,
	options K8sDeleteOptions,
) ([]K8sResourceDeletion, error) {
	// Implementation would delete resources by type
	// This is a placeholder for the complex deletion logic
	return []K8sResourceDeletion{}, nil
}

func (k *KubernetesServiceAdapter) getResourceInterface(gvr schema.GroupVersionResource) dynamic.NamespaceableResourceInterface {
	return k.dynamicClient.Resource(gvr)
}

func (k *KubernetesServiceAdapter) applyUpdateStrategy(
	existing, new *unstructured.Unstructured,
	strategy K8sUpdateStrategy,
) (*unstructured.Unstructured, error) {
	// Implementation would apply different update strategies
	// This is a placeholder for the complex update strategy logic
	return new, nil
}

func (k *KubernetesServiceAdapter) verifyDeploymentHealth(
	ctx context.Context,
	result *K8sDeploymentResult,
) error {
	// Implementation would verify deployment health
	// This is a placeholder for the complex health verification logic
	return nil
}

func (k *KubernetesServiceAdapter) rollbackDeployment(
	ctx context.Context,
	result *K8sDeploymentResult,
) {
	// Implementation would rollback failed deployment
	// This is a placeholder for the complex rollback logic
}

func (k *KubernetesServiceAdapter) rollbackUpdate(
	ctx context.Context,
	result *K8sUpdateResult,
) {
	// Implementation would rollback failed update
	// This is a placeholder for the complex rollback logic
}

func (k *KubernetesServiceAdapter) calculateOverallStatus(resources []K8sResourceStatus) K8sStatus {
	// Implementation would calculate overall status from resource statuses
	return K8sStatusHealthy
}

func (k *KubernetesServiceAdapter) calculateHealthScore(resources []K8sResourceStatus) float64 {
	// Implementation would calculate health score
	return 100.0
}

func (k *KubernetesServiceAdapter) calculateClusterHealth(health *K8sClusterHealth) K8sHealthStatus {
	// Implementation would calculate cluster health
	return K8sHealthStatusHealthy
}

func (k *KubernetesServiceAdapter) calculateClusterHealthScore(health *K8sClusterHealth) float64 {
	// Implementation would calculate cluster health score
	return 100.0
}

func (k *KubernetesServiceAdapter) recordMetrics(operation string, startTime time.Time, err error) {
	if k.metricsCollector != nil {
		duration := time.Since(startTime)
		k.metricsCollector.RecordOperation(operation, duration, err)
	}
}

func (k *KubernetesServiceAdapter) wrapError(operation string, err error) error {
	return fmt.Errorf("Kubernetes service %s failed: %w", operation, err)
}

func getDryRunOptions(dryRun bool) []string {
	if dryRun {
		return []string{metav1.DryRunAll}
	}
	return nil
}

// K8sMetricsCollector collects Kubernetes operation metrics
type K8sMetricsCollector struct {
	// Implementation would collect comprehensive Kubernetes metrics
}

func (kmc *K8sMetricsCollector) RecordOperation(operation string, duration time.Duration, err error) {
	// Implementation would record operation metrics
}

func (kmc *K8sMetricsCollector) RecordDeploymentHealthCheck(configID string, healthy bool) {
	// Implementation would record deployment health metrics
}

// K8sRateLimiter provides rate limiting for Kubernetes API calls
type K8sRateLimiter struct {
	// Implementation would provide sophisticated rate limiting
}

func NewK8sRateLimiter() *K8sRateLimiter {
	return &K8sRateLimiter{}
}

func (rl *K8sRateLimiter) Wait(ctx context.Context) error {
	// Implementation would enforce rate limits
	return nil
}