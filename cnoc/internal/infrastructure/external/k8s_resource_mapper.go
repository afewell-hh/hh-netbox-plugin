package external

import (
	"encoding/json"
	"fmt"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime/schema"
	
	"github.com/hedgehog/cnoc/internal/domain/configuration"
)

// K8sResourceMapper provides anti-corruption layer for Kubernetes resource mapping
// Following MDD principles to maintain domain model purity from external service details
type K8sResourceMapper struct {
	labelPrefix      string
	annotationPrefix string
	resourceVersion  string
}

// NewK8sResourceMapper creates a new Kubernetes resource mapper with MDD compliance
func NewK8sResourceMapper() *K8sResourceMapper {
	return &K8sResourceMapper{
		labelPrefix:      "cnoc.hedgehog.io",
		annotationPrefix: "cnoc.hedgehog.io",
		resourceVersion:  "v1",
	}
}

// Configuration to Kubernetes manifest conversion

// ConfigurationToK8sManifests converts domain configuration to Kubernetes manifests
func (m *K8sResourceMapper) ConfigurationToK8sManifests(
	config *configuration.Configuration,
	options K8sDeploymentOptions,
) ([]K8sManifest, error) {
	if config == nil {
		return nil, fmt.Errorf("configuration cannot be nil")
	}

	manifests := make([]K8sManifest, 0)

	// Create ConfigMap for configuration data
	configMapManifest, err := m.createConfigurationConfigMap(config, options)
	if err != nil {
		return nil, fmt.Errorf("configmap creation failed: %w", err)
	}
	manifests = append(manifests, configMapManifest)

	// Create manifests for each component
	for _, component := range config.Components() {
		if !component.Enabled() {
			continue // Skip disabled components
		}

		componentManifests, err := m.createComponentManifests(component, config, options)
		if err != nil {
			return nil, fmt.Errorf("component %s manifest creation failed: %w", component.Name().String(), err)
		}
		manifests = append(manifests, componentManifests...)
	}

	// Create enterprise configuration resources if present
	if config.EnterpriseConfiguration() != nil {
		enterpriseManifests, err := m.createEnterpriseManifests(config.EnterpriseConfiguration(), config, options)
		if err != nil {
			return nil, fmt.Errorf("enterprise configuration manifest creation failed: %w", err)
		}
		manifests = append(manifests, enterpriseManifests...)
	}

	return manifests, nil
}

// ComponentToK8sManifest converts single component to Kubernetes manifest
func (m *K8sResourceMapper) ComponentToK8sManifest(
	component *configuration.ComponentReference,
	options K8sComponentOptions,
) (K8sManifest, error) {
	if component == nil {
		return K8sManifest{}, fmt.Errorf("component cannot be nil")
	}

	// Create deployment manifest for component
	deployment := m.createComponentDeployment(component, options)
	
	// Convert to unstructured format
	content, err := m.structuredToUnstructured(deployment)
	if err != nil {
		return K8sManifest{}, fmt.Errorf("deployment conversion failed: %w", err)
	}

	manifest := K8sManifest{
		GVR: schema.GroupVersionResource{
			Group:    "apps",
			Version:  "v1",
			Resource: "deployments",
		},
		Content: content,
		Hash:    m.calculateManifestHash(content),
	}

	return manifest, nil
}

// Kubernetes resource to status conversion

// K8sResourceToStatus converts Kubernetes resource to status representation
func (m *K8sResourceMapper) K8sResourceToStatus(resource *unstructured.Unstructured) K8sResourceStatus {
	status := K8sResourceStatus{
		Name:       resource.GetName(),
		Namespace:  resource.GetNamespace(),
		Kind:       resource.GetKind(),
		APIVersion: resource.GetAPIVersion(),
		Status:     m.determineResourceState(resource),
		Ready:      m.isResourceReady(resource),
		Conditions: m.extractConditions(resource),
		LastTransition: m.getLastTransitionTime(resource),
		Message:    m.extractStatusMessage(resource),
	}

	// Extract replica status for deployments
	if resource.GetKind() == "Deployment" {
		status.Replicas = m.extractReplicaStatus(resource)
	}

	return status
}

// NodeToHealthStatus converts Kubernetes node to health status
func (m *K8sResourceMapper) NodeToHealthStatus(node *corev1.Node) K8sNodeHealth {
	nodeHealth := K8sNodeHealth{
		NodeName:      node.Name,
		Status:        m.determineNodeHealthStatus(node),
		Ready:         m.isNodeReady(node),
		Schedulable:   !node.Spec.Unschedulable,
		Conditions:    m.convertNodeConditions(node.Status.Conditions),
		Capacity:      m.convertNodeCapacity(node.Status.Capacity),
		Allocatable:   m.convertNodeCapacity(node.Status.Allocatable),
		Usage:         m.calculateNodeUsage(node),
		LastHeartbeat: m.getNodeLastHeartbeat(node),
	}

	return nodeHealth
}

// PodToHealthStatus converts Kubernetes pod to health status
func (m *K8sResourceMapper) PodToHealthStatus(pod *corev1.Pod) K8sPodHealth {
	podHealth := K8sPodHealth{
		PodName:      pod.Name,
		Namespace:    pod.Namespace,
		Status:       m.determinePodHealthStatus(pod),
		Phase:        string(pod.Status.Phase),
		Ready:        m.isPodReady(pod),
		Containers:   m.convertContainerStatuses(pod.Status.ContainerStatuses),
		Conditions:   m.convertPodConditions(pod.Status.Conditions),
		RestartCount: m.calculateTotalRestarts(pod.Status.ContainerStatuses),
		LastRestart:  m.getLastRestartTime(pod.Status.ContainerStatuses),
	}

	return podHealth
}

// PodToMetrics converts Kubernetes pod to metrics representation
func (m *K8sResourceMapper) PodToMetrics(pod *corev1.Pod) K8sPodMetrics {
	metrics := K8sPodMetrics{
		PodName:        pod.Name,
		Namespace:      pod.Namespace,
		CPURequests:    m.extractResourceRequest(pod, corev1.ResourceCPU),
		CPULimits:      m.extractResourceLimit(pod, corev1.ResourceCPU),
		MemoryRequests: m.extractResourceRequest(pod, corev1.ResourceMemory),
		MemoryLimits:   m.extractResourceLimit(pod, corev1.ResourceMemory),
		ContainerMetrics: m.extractContainerMetrics(pod),
		NetworkMetrics:   m.extractNetworkMetrics(pod),
		StorageMetrics:   m.extractStorageMetrics(pod),
	}

	return metrics
}

// Private helper methods for manifest creation

func (m *K8sResourceMapper) createConfigurationConfigMap(
	config *configuration.Configuration,
	options K8sDeploymentOptions,
) (K8sManifest, error) {
	// Create configuration data
	configData := map[string]string{
		"configuration.json": m.serializeConfiguration(config),
		"metadata.json":     m.serializeConfigurationMetadata(config),
	}

	// Add component configurations
	for _, component := range config.Components() {
		if component.Enabled() {
			componentKey := fmt.Sprintf("component-%s.json", component.Name().String())
			configData[componentKey] = m.serializeComponent(component)
		}
	}

	configMap := &corev1.ConfigMap{
		TypeMeta: metav1.TypeMeta{
			APIVersion: "v1",
			Kind:       "ConfigMap",
		},
		ObjectMeta: metav1.ObjectMeta{
			Name:        fmt.Sprintf("%s-config", config.Name().String()),
			Namespace:   options.Namespace,
			Labels:      m.createConfigurationLabels(config, options.Labels),
			Annotations: m.createConfigurationAnnotations(config, options.Annotations),
		},
		Data: configData,
	}

	content, err := m.structuredToUnstructured(configMap)
	if err != nil {
		return K8sManifest{}, err
	}

	return K8sManifest{
		GVR: schema.GroupVersionResource{
			Group:    "",
			Version:  "v1",
			Resource: "configmaps",
		},
		Content: content,
		Hash:    m.calculateManifestHash(content),
	}, nil
}

func (m *K8sResourceMapper) createComponentManifests(
	component *configuration.ComponentReference,
	config *configuration.Configuration,
	options K8sDeploymentOptions,
) ([]K8sManifest, error) {
	manifests := make([]K8sManifest, 0)

	// Create deployment for component
	deployment := m.createComponentDeployment(component, K8sComponentOptions{
		Namespace:   options.Namespace,
		Labels:      options.Labels,
		Annotations: options.Annotations,
	})

	deploymentContent, err := m.structuredToUnstructured(deployment)
	if err != nil {
		return nil, err
	}

	manifests = append(manifests, K8sManifest{
		GVR: schema.GroupVersionResource{
			Group:    "apps",
			Version:  "v1",
			Resource: "deployments",
		},
		Content: deploymentContent,
		Hash:    m.calculateManifestHash(deploymentContent),
	})

	// Create service for component if needed
	if m.componentNeedsService(component) {
		service := m.createComponentService(component, config, options)
		serviceContent, err := m.structuredToUnstructured(service)
		if err != nil {
			return nil, err
		}

		manifests = append(manifests, K8sManifest{
			GVR: schema.GroupVersionResource{
				Group:    "",
				Version:  "v1",
				Resource: "services",
			},
			Content: serviceContent,
			Hash:    m.calculateManifestHash(serviceContent),
		})
	}

	return manifests, nil
}

func (m *K8sResourceMapper) createComponentDeployment(
	component *configuration.ComponentReference,
	options K8sComponentOptions,
) interface{} {
	// This is a simplified deployment creation
	// In a real implementation, this would be much more comprehensive
	deployment := map[string]interface{}{
		"apiVersion": "apps/v1",
		"kind":       "Deployment",
		"metadata": map[string]interface{}{
			"name":      component.Name().String(),
			"namespace": options.Namespace,
			"labels":    m.createComponentLabels(component, options.Labels),
			"annotations": m.createComponentAnnotations(component, options.Annotations),
		},
		"spec": map[string]interface{}{
			"replicas": component.Resources().Replicas(),
			"selector": map[string]interface{}{
				"matchLabels": map[string]interface{}{
					fmt.Sprintf("%s/component", m.labelPrefix): component.Name().String(),
				},
			},
			"template": map[string]interface{}{
				"metadata": map[string]interface{}{
					"labels": m.createComponentLabels(component, options.Labels),
				},
				"spec": map[string]interface{}{
					"containers": []map[string]interface{}{
						{
							"name":  component.Name().String(),
							"image": fmt.Sprintf("%s:%s", component.Name().String(), component.Version().String()),
							"resources": map[string]interface{}{
								"requests": map[string]interface{}{
									"cpu":    component.Resources().CPU(),
									"memory": component.Resources().Memory(),
								},
								"limits": map[string]interface{}{
									"cpu":    component.Resources().CPU(),
									"memory": component.Resources().Memory(),
								},
							},
						},
					},
				},
			},
		},
	}

	return deployment
}

func (m *K8sResourceMapper) createComponentService(
	component *configuration.ComponentReference,
	config *configuration.Configuration,
	options K8sDeploymentOptions,
) interface{} {
	// Simplified service creation
	service := map[string]interface{}{
		"apiVersion": "v1",
		"kind":       "Service",
		"metadata": map[string]interface{}{
			"name":      fmt.Sprintf("%s-service", component.Name().String()),
			"namespace": options.Namespace,
			"labels":    m.createComponentLabels(component, options.Labels),
		},
		"spec": map[string]interface{}{
			"selector": map[string]interface{}{
				fmt.Sprintf("%s/component", m.labelPrefix): component.Name().String(),
			},
			"ports": []map[string]interface{}{
				{
					"port":       80,
					"targetPort": 8080,
					"protocol":   "TCP",
				},
			},
		},
	}

	return service
}

func (m *K8sResourceMapper) createEnterpriseManifests(
	enterpriseConfig *configuration.EnterpriseConfiguration,
	config *configuration.Configuration,
	options K8sDeploymentOptions,
) ([]K8sManifest, error) {
	manifests := make([]K8sManifest, 0)

	// Create security policies if required
	if enterpriseConfig.EncryptionRequired() {
		securityManifest, err := m.createSecurityPolicyManifest(enterpriseConfig, config, options)
		if err != nil {
			return nil, err
		}
		manifests = append(manifests, securityManifest)
	}

	// Create backup configuration if required
	if enterpriseConfig.BackupRequired() {
		backupManifest, err := m.createBackupConfigManifest(enterpriseConfig, config, options)
		if err != nil {
			return nil, err
		}
		manifests = append(manifests, backupManifest)
	}

	return manifests, nil
}

// Helper methods for status extraction

func (m *K8sResourceMapper) determineResourceState(resource *unstructured.Unstructured) K8sResourceState {
	// Simplified state determination
	if conditions, found, _ := unstructured.NestedSlice(resource.Object, "status", "conditions"); found {
		for _, condition := range conditions {
			if condMap, ok := condition.(map[string]interface{}); ok {
				if condType, ok := condMap["type"].(string); ok && condType == "Ready" {
					if status, ok := condMap["status"].(string); ok && status == "True" {
						return K8sResourceStateRunning
					}
				}
			}
		}
	}
	return K8sResourceStateUnknown
}

func (m *K8sResourceMapper) isResourceReady(resource *unstructured.Unstructured) bool {
	return m.determineResourceState(resource) == K8sResourceStateRunning
}

func (m *K8sResourceMapper) extractConditions(resource *unstructured.Unstructured) []K8sCondition {
	conditions := make([]K8sCondition, 0)
	
	if conditionsSlice, found, _ := unstructured.NestedSlice(resource.Object, "status", "conditions"); found {
		for _, condition := range conditionsSlice {
			if condMap, ok := condition.(map[string]interface{}); ok {
				k8sCondition := K8sCondition{
					Type:   getStringFromMap(condMap, "type"),
					Status: getStringFromMap(condMap, "status"),
					Reason: getStringFromMap(condMap, "reason"),
					Message: getStringFromMap(condMap, "message"),
				}
				
				if lastUpdateTime := getStringFromMap(condMap, "lastUpdateTime"); lastUpdateTime != "" {
					if t, err := time.Parse(time.RFC3339, lastUpdateTime); err == nil {
						k8sCondition.LastUpdateTime = t
					}
				}
				
				if lastTransitionTime := getStringFromMap(condMap, "lastTransitionTime"); lastTransitionTime != "" {
					if t, err := time.Parse(time.RFC3339, lastTransitionTime); err == nil {
						k8sCondition.LastTransitionTime = t
					}
				}
				
				conditions = append(conditions, k8sCondition)
			}
		}
	}
	
	return conditions
}

func (m *K8sResourceMapper) extractReplicaStatus(resource *unstructured.Unstructured) *K8sReplicaStatus {
	replicaStatus := &K8sReplicaStatus{}
	
	if replicas, found, _ := unstructured.NestedInt64(resource.Object, "spec", "replicas"); found {
		replicaStatus.Desired = int32(replicas)
	}
	
	if replicas, found, _ := unstructured.NestedInt64(resource.Object, "status", "replicas"); found {
		replicaStatus.Current = int32(replicas)
	}
	
	if replicas, found, _ := unstructured.NestedInt64(resource.Object, "status", "readyReplicas"); found {
		replicaStatus.Ready = int32(replicas)
	}
	
	if replicas, found, _ := unstructured.NestedInt64(resource.Object, "status", "availableReplicas"); found {
		replicaStatus.Available = int32(replicas)
	}
	
	if replicas, found, _ := unstructured.NestedInt64(resource.Object, "status", "unavailableReplicas"); found {
		replicaStatus.Unavailable = int32(replicas)
	}
	
	return replicaStatus
}

// Node health status helpers

func (m *K8sResourceMapper) determineNodeHealthStatus(node *corev1.Node) K8sHealthStatus {
	for _, condition := range node.Status.Conditions {
		if condition.Type == corev1.NodeReady {
			if condition.Status == corev1.ConditionTrue {
				return K8sHealthStatusHealthy
			}
			return K8sHealthStatusUnhealthy
		}
	}
	return K8sHealthStatusUnknown
}

func (m *K8sResourceMapper) isNodeReady(node *corev1.Node) bool {
	for _, condition := range node.Status.Conditions {
		if condition.Type == corev1.NodeReady {
			return condition.Status == corev1.ConditionTrue
		}
	}
	return false
}

func (m *K8sResourceMapper) convertNodeConditions(conditions []corev1.NodeCondition) []K8sCondition {
	k8sConditions := make([]K8sCondition, len(conditions))
	for i, condition := range conditions {
		k8sConditions[i] = K8sCondition{
			Type:               string(condition.Type),
			Status:             string(condition.Status),
			LastUpdateTime:     condition.LastHeartbeatTime.Time,
			LastTransitionTime: condition.LastTransitionTime.Time,
			Reason:             condition.Reason,
			Message:            condition.Message,
		}
	}
	return k8sConditions
}

func (m *K8sResourceMapper) convertNodeCapacity(capacity corev1.ResourceList) K8sNodeCapacity {
	return K8sNodeCapacity{
		CPU:              capacity.Cpu().String(),
		Memory:           capacity.Memory().String(),
		Storage:          capacity.StorageEphemeral().String(),
		Pods:             int32(capacity.Pods().Value()),
		EphemeralStorage: capacity.StorageEphemeral().String(),
	}
}

// Utility methods

func (m *K8sResourceMapper) createConfigurationLabels(config *configuration.Configuration, additionalLabels map[string]string) map[string]string {
	labels := map[string]string{
		fmt.Sprintf("%s/configuration.id", m.labelPrefix):   config.ID().String(),
		fmt.Sprintf("%s/configuration.name", m.labelPrefix): config.Name().String(),
		fmt.Sprintf("%s/configuration.mode", m.labelPrefix): string(config.Mode()),
		fmt.Sprintf("%s/version", m.labelPrefix):           config.Version().String(),
		fmt.Sprintf("%s/managed-by", m.labelPrefix):        "cnoc",
	}
	
	// Add additional labels
	for key, value := range additionalLabels {
		labels[key] = value
	}
	
	// Add domain labels
	for key, value := range config.Labels() {
		labels[fmt.Sprintf("%s/domain.%s", m.labelPrefix, key)] = value
	}
	
	return labels
}

func (m *K8sResourceMapper) createConfigurationAnnotations(config *configuration.Configuration, additionalAnnotations map[string]string) map[string]string {
	annotations := map[string]string{
		fmt.Sprintf("%s/configuration.description", m.annotationPrefix): config.Description(),
		fmt.Sprintf("%s/configuration.status", m.annotationPrefix):     string(config.Status()),
		fmt.Sprintf("%s/component.count", m.annotationPrefix):          fmt.Sprintf("%d", len(config.Components())),
		fmt.Sprintf("%s/created-at", m.annotationPrefix):               time.Now().Format(time.RFC3339),
	}
	
	// Add additional annotations
	for key, value := range additionalAnnotations {
		annotations[key] = value
	}
	
	// Add domain annotations
	for key, value := range config.Annotations() {
		annotations[fmt.Sprintf("%s/domain.%s", m.annotationPrefix, key)] = value
	}
	
	return annotations
}

func (m *K8sResourceMapper) createComponentLabels(component *configuration.ComponentReference, additionalLabels map[string]string) map[string]string {
	labels := map[string]string{
		fmt.Sprintf("%s/component", m.labelPrefix):          component.Name().String(),
		fmt.Sprintf("%s/component.version", m.labelPrefix):  component.Version().String(),
		fmt.Sprintf("%s/component.enabled", m.labelPrefix):  fmt.Sprintf("%t", component.Enabled()),
		fmt.Sprintf("%s/managed-by", m.labelPrefix):         "cnoc",
	}
	
	// Add additional labels
	for key, value := range additionalLabels {
		labels[key] = value
	}
	
	return labels
}

func (m *K8sResourceMapper) createComponentAnnotations(component *configuration.ComponentReference, additionalAnnotations map[string]string) map[string]string {
	annotations := map[string]string{
		fmt.Sprintf("%s/component.namespace", m.annotationPrefix): component.Resources().Namespace(),
		fmt.Sprintf("%s/component.replicas", m.annotationPrefix):  fmt.Sprintf("%d", component.Resources().Replicas()),
		fmt.Sprintf("%s/component.cpu", m.annotationPrefix):       component.Resources().CPU(),
		fmt.Sprintf("%s/component.memory", m.annotationPrefix):    component.Resources().Memory(),
	}
	
	// Add additional annotations
	for key, value := range additionalAnnotations {
		annotations[key] = value
	}
	
	return annotations
}

func (m *K8sResourceMapper) serializeConfiguration(config *configuration.Configuration) string {
	// Simplified serialization - in production, use proper JSON marshaling
	configData := map[string]interface{}{
		"id":          config.ID().String(),
		"name":        config.Name().String(),
		"description": config.Description(),
		"mode":        string(config.Mode()),
		"version":     config.Version().String(),
		"status":      string(config.Status()),
	}
	
	jsonData, _ := json.Marshal(configData)
	return string(jsonData)
}

func (m *K8sResourceMapper) serializeConfigurationMetadata(config *configuration.Configuration) string {
	metadata := map[string]interface{}{
		"labels":      config.Labels(),
		"annotations": config.Annotations(),
		"components":  len(config.Components()),
	}
	
	jsonData, _ := json.Marshal(metadata)
	return string(jsonData)
}

func (m *K8sResourceMapper) serializeComponent(component *configuration.ComponentReference) string {
	componentData := map[string]interface{}{
		"name":    component.Name().String(),
		"version": component.Version().String(),
		"enabled": component.Enabled(),
		"config":  component.Configuration().Data(),
	}
	
	jsonData, _ := json.Marshal(componentData)
	return string(jsonData)
}

func (m *K8sResourceMapper) structuredToUnstructured(obj interface{}) (map[string]interface{}, error) {
	data, err := json.Marshal(obj)
	if err != nil {
		return nil, err
	}
	
	var unstructuredObj map[string]interface{}
	if err := json.Unmarshal(data, &unstructuredObj); err != nil {
		return nil, err
	}
	
	return unstructuredObj, nil
}

func (m *K8sResourceMapper) calculateManifestHash(content map[string]interface{}) string {
	// Simplified hash calculation - in production, use proper hashing
	jsonData, _ := json.Marshal(content)
	return fmt.Sprintf("hash-%d", len(jsonData))
}

func (m *K8sResourceMapper) componentNeedsService(component *configuration.ComponentReference) bool {
	// Simplified logic - in production, analyze component configuration
	return true
}

// Placeholder implementations for unimplemented methods

func (m *K8sResourceMapper) getLastTransitionTime(resource *unstructured.Unstructured) time.Time {
	return time.Now()
}

func (m *K8sResourceMapper) extractStatusMessage(resource *unstructured.Unstructured) string {
	if message, found, _ := unstructured.NestedString(resource.Object, "status", "message"); found {
		return message
	}
	return ""
}

func (m *K8sResourceMapper) calculateNodeUsage(node *corev1.Node) K8sNodeUsage {
	return K8sNodeUsage{
		CPUPercent:     0.0,
		MemoryPercent:  0.0,
		StoragePercent: 0.0,
		PodCount:       0,
	}
}

func (m *K8sResourceMapper) getNodeLastHeartbeat(node *corev1.Node) time.Time {
	for _, condition := range node.Status.Conditions {
		if condition.Type == corev1.NodeReady {
			return condition.LastHeartbeatTime.Time
		}
	}
	return time.Now()
}

func (m *K8sResourceMapper) determinePodHealthStatus(pod *corev1.Pod) K8sHealthStatus {
	if pod.Status.Phase == corev1.PodRunning {
		return K8sHealthStatusHealthy
	}
	return K8sHealthStatusUnhealthy
}

func (m *K8sResourceMapper) isPodReady(pod *corev1.Pod) bool {
	for _, condition := range pod.Status.Conditions {
		if condition.Type == corev1.PodReady {
			return condition.Status == corev1.ConditionTrue
		}
	}
	return false
}

func (m *K8sResourceMapper) convertContainerStatuses(statuses []corev1.ContainerStatus) []K8sContainerHealth {
	containerHealths := make([]K8sContainerHealth, len(statuses))
	for i, status := range statuses {
		containerHealths[i] = K8sContainerHealth{
			Name:         status.Name,
			Ready:        status.Ready,
			RestartCount: status.RestartCount,
			Status:       K8sHealthStatusHealthy, // Simplified
			CurrentState: "running",              // Simplified
		}
	}
	return containerHealths
}

func (m *K8sResourceMapper) convertPodConditions(conditions []corev1.PodCondition) []K8sCondition {
	k8sConditions := make([]K8sCondition, len(conditions))
	for i, condition := range conditions {
		k8sConditions[i] = K8sCondition{
			Type:               string(condition.Type),
			Status:             string(condition.Status),
			LastUpdateTime:     condition.LastProbeTime.Time,
			LastTransitionTime: condition.LastTransitionTime.Time,
			Reason:             condition.Reason,
			Message:            condition.Message,
		}
	}
	return k8sConditions
}

func (m *K8sResourceMapper) calculateTotalRestarts(statuses []corev1.ContainerStatus) int32 {
	var total int32
	for _, status := range statuses {
		total += status.RestartCount
	}
	return total
}

func (m *K8sResourceMapper) getLastRestartTime(statuses []corev1.ContainerStatus) *time.Time {
	// Simplified implementation
	if len(statuses) > 0 {
		now := time.Now()
		return &now
	}
	return nil
}

func (m *K8sResourceMapper) extractResourceRequest(pod *corev1.Pod, resource corev1.ResourceName) string {
	// Simplified resource extraction
	return "100m"
}

func (m *K8sResourceMapper) extractResourceLimit(pod *corev1.Pod, resource corev1.ResourceName) string {
	// Simplified resource extraction
	return "200m"
}

func (m *K8sResourceMapper) extractContainerMetrics(pod *corev1.Pod) []K8sContainerMetrics {
	return []K8sContainerMetrics{}
}

func (m *K8sResourceMapper) extractNetworkMetrics(pod *corev1.Pod) K8sNetworkMetrics {
	return K8sNetworkMetrics{}
}

func (m *K8sResourceMapper) extractStorageMetrics(pod *corev1.Pod) K8sStorageMetrics {
	return K8sStorageMetrics{}
}

func (m *K8sResourceMapper) createSecurityPolicyManifest(
	enterpriseConfig *configuration.EnterpriseConfiguration,
	config *configuration.Configuration,
	options K8sDeploymentOptions,
) (K8sManifest, error) {
	return K8sManifest{}, nil
}

func (m *K8sResourceMapper) createBackupConfigManifest(
	enterpriseConfig *configuration.EnterpriseConfiguration,
	config *configuration.Configuration,
	options K8sDeploymentOptions,
) (K8sManifest, error) {
	return K8sManifest{}, nil
}

// Utility helper functions

func getStringFromMap(m map[string]interface{}, key string) string {
	if value, ok := m[key].(string); ok {
		return value
	}
	return ""
}