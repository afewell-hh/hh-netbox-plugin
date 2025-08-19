package services

import (
	"context"
	"fmt"
	"time"

	"github.com/hedgehog/cnoc/internal/domain"
)

// fabricApplicationServiceImpl implements FabricApplicationService interface
type fabricApplicationServiceImpl struct {
	fabricRepo    FabricRepository
	gitOpsService GitOpsService
	k8sService    KubernetesService
}

// NewFabricApplicationService creates a new fabric application service
func NewFabricApplicationService(
	fabricRepo FabricRepository,
	gitOpsService GitOpsService,
	k8sService KubernetesService,
) FabricApplicationService {
	return &fabricApplicationServiceImpl{
		fabricRepo:    fabricRepo,
		gitOpsService: gitOpsService,
		k8sService:    k8sService,
	}
}

// SynchronizeFabric performs GitOps synchronization for a fabric
func (s *fabricApplicationServiceImpl) SynchronizeFabric(ctx context.Context, command FabricSyncCommand) (*FabricSyncResult, error) {
	// Retrieve the fabric
	fabric, err := s.fabricRepo.GetByID(ctx, command.FabricID)
	if err != nil {
		return nil, fmt.Errorf("failed to get fabric %s: %w", command.FabricID, err)
	}

	// Check if fabric can perform GitOps operations
	if !fabric.CanPerformGitOps() {
		return &FabricSyncResult{
			Success:         false,
			FabricID:        command.FabricID,
			SyncedResources: 0,
			Errors: []FabricSyncError{
				{
					Code:        "FABRIC_NOT_CONFIGURED",
					Message:     "Fabric is not properly configured for GitOps operations",
					Severity:    "critical",
					Recoverable: true,
				},
			},
			RequestID: command.RequestID,
			SyncedAt:  time.Now(),
		}, nil
	}

	// Start sync performance tracking
	startTime := time.Now()

	// Build repository URL (simplified for now)
	repoURL := *fabric.GitRepositoryID
	
	// Sync from git repository
	gitResult, err := s.gitOpsService.SyncRepository(ctx, repoURL, fabric.GitOpsDirectory)
	if err != nil {
		return &FabricSyncResult{
			Success:         false,
			FabricID:        command.FabricID,
			SyncedResources: 0,
			Errors: []FabricSyncError{
				{
					Code:        "GIT_SYNC_FAILED",
					Message:     fmt.Sprintf("Git synchronization failed: %v", err),
					Severity:    "critical",
					Recoverable: true,
				},
			},
			RequestID: command.RequestID,
			SyncedAt:  time.Now(),
		}, fmt.Errorf("git synchronization failed: %w", err)
	}

	syncedResources := gitResult.FilesChanged
	var errors []FabricSyncError
	var warnings []FabricSyncWarning

	// Apply to Kubernetes if not a dry run
	if !command.DryRun {
		// Simulate applying manifests to Kubernetes
		// In a real implementation, this would parse YAML files and apply them
		err = s.k8sService.ApplyManifest(ctx, []byte("# Simulated manifest"))
		if err != nil {
			errors = append(errors, FabricSyncError{
				Code:        "K8S_APPLY_FAILED",
				Message:     fmt.Sprintf("Kubernetes apply failed: %v", err),
				Severity:    "critical",
				Recoverable: true,
			})
			syncedResources = 0
			
			// Return error for Kubernetes failures
			return &FabricSyncResult{
				Success:         false,
				FabricID:        command.FabricID,
				SyncedResources: 0,
				Errors:          errors,
				RequestID:       command.RequestID,
				SyncedAt:        time.Now(),
			}, fmt.Errorf("kubernetes apply failed: %w", err)
		}
	}

	// Update fabric git sync status
	fabric.UpdateGitSyncStatus(domain.GitSyncStatusInSync, gitResult.CommitHash)
	fabric.CachedCRDCount = syncedResources
	fabric.LastSyncTime = time.Now()
	
	// Save updated fabric
	if err := s.fabricRepo.Save(ctx, fabric); err != nil {
		warnings = append(warnings, FabricSyncWarning{
			Code:    "FABRIC_UPDATE_FAILED",
			Message: fmt.Sprintf("Failed to update fabric status: %v", err),
		})
	}

	// Calculate performance metrics
	duration := time.Since(startTime)
	performance := &SyncPerformanceMetrics{
		Duration:         duration,
		ResourcesPerSec:  float64(syncedResources) / duration.Seconds(),
		NetworkLatency:   gitResult.SyncDuration,
		ProcessingTime:   duration - gitResult.SyncDuration,
		ValidationTime:   10 * time.Millisecond, // Simulated
	}

	return &FabricSyncResult{
		Success:         len(errors) == 0,
		FabricID:        command.FabricID,
		SyncedResources: syncedResources,
		Errors:          errors,
		Warnings:        warnings,
		DriftDetected:   false, // Simplified for now
		Performance:     performance,
		SyncedAt:        time.Now(),
		RequestID:       command.RequestID,
	}, nil
}

// GetFabricStatus retrieves current fabric synchronization status
func (s *fabricApplicationServiceImpl) GetFabricStatus(ctx context.Context, fabricID string) (*FabricStatusDTO, error) {
	// Retrieve the fabric
	fabric, err := s.fabricRepo.GetByID(ctx, fabricID)
	if err != nil {
		return nil, fmt.Errorf("failed to get fabric %s: %w", fabricID, err)
	}

	// Get git repository status if configured
	var lastSyncAt *time.Time
	if fabric.CanPerformGitOps() {
		// Try to get repository status (ignore errors for now)
		if repoStatus, err := s.gitOpsService.GetRepositoryStatus(ctx, *fabric.GitRepositoryID); err == nil {
			lastSyncAt = repoStatus.LastSync
		}
	}
	if lastSyncAt == nil && fabric.LastGitSync != nil {
		lastSyncAt = fabric.LastGitSync
	}

	// Calculate health score (simplified)
	healthScore := 1.0
	if !fabric.IsConnected() {
		healthScore -= 0.3
	}
	if !fabric.IsSynced() {
		healthScore -= 0.3
	}
	if fabric.HasDrift() {
		healthScore -= 0.2
	}
	if healthScore < 0 {
		healthScore = 0
	}

	// Ensure status is not empty
	status := string(fabric.Status)
	if status == "" {
		status = string(domain.FabricStatusPlanned)
	}

	// Ensure drift status is not empty  
	driftStatus := fabric.DriftStatus
	if driftStatus == "" {
		driftStatus = "no_drift"
	}

	return &FabricStatusDTO{
		FabricID:      fabric.ID,
		Name:          fabric.Name,
		Status:        status,
		LastSyncAt:    lastSyncAt,
		ResourceCount: fabric.CachedCRDCount,
		DriftStatus:   driftStatus,
		HealthScore:   healthScore,
		Metadata: map[string]string{
			"git_repository": func() string {
				if fabric.GitRepositoryID != nil {
					return *fabric.GitRepositoryID
				}
				return ""
			}(),
			"git_directory": fabric.GitOpsDirectory,
			"git_branch":    fabric.GitOpsBranch,
		},
	}, nil
}

// ValidateFabricConfiguration validates fabric configuration
func (s *fabricApplicationServiceImpl) ValidateFabricConfiguration(ctx context.Context, fabricID string) (*FabricValidationResult, error) {
	// Retrieve the fabric
	fabric, err := s.fabricRepo.GetByID(ctx, fabricID)
	if err != nil {
		return nil, fmt.Errorf("failed to get fabric %s: %w", fabricID, err)
	}

	var errors []FabricValidationError
	var warnings []FabricValidationWarning

	// Validate domain rules
	if err := fabric.Validate(); err != nil {
		errors = append(errors, FabricValidationError{
			Code:        "DOMAIN_VALIDATION_FAILED",
			Message:     err.Error(),
			Severity:    "critical",
			Recoverable: true,
		})
	}

	// Validate GitOps configuration
	if fabric.CanPerformGitOps() {
		if err := s.gitOpsService.ValidateRepository(ctx, *fabric.GitRepositoryID); err != nil {
			errors = append(errors, FabricValidationError{
				Code:        "GIT_VALIDATION_FAILED",
				Message:     fmt.Sprintf("Git repository validation failed: %v", err),
				Resource:    *fabric.GitRepositoryID,
				Severity:    "critical",
				Recoverable: true,
			})
		}
	} else {
		warnings = append(warnings, FabricValidationWarning{
			Code:       "GITOPS_NOT_CONFIGURED",
			Message:    "Fabric is not configured for GitOps operations",
			Suggestion: "Configure git repository and directory for GitOps synchronization",
		})
	}

	// Validate Kubernetes connectivity (always check for potential issues)
	if _, err := s.k8sService.GetClusterHealth(ctx); err != nil {
		errors = append(errors, FabricValidationError{
			Code:        "K8S_VALIDATION_FAILED",
			Message:     fmt.Sprintf("Kubernetes cluster validation failed: %v", err),
			Resource:    fabric.KubernetesServer,
			Severity:    "critical",
			Recoverable: true,
		})
	}
	
	// Add warning if K8s server is not configured
	if fabric.KubernetesServer == "" {
		warnings = append(warnings, FabricValidationWarning{
			Code:       "K8S_NOT_CONFIGURED",
			Message:    "Kubernetes server is not configured",
			Suggestion: "Configure Kubernetes server endpoint for cluster operations",
		})
	}

	return &FabricValidationResult{
		Valid:           len(errors) == 0,
		FabricID:        fabricID,
		ValidationLevel: "comprehensive",
		Errors:          errors,
		Warnings:        warnings,
		ValidatedAt:     time.Now(),
		RequestID:       fmt.Sprintf("validation-%d", time.Now().Unix()),
	}, nil
}

// ListFabrics retrieves all managed fabrics
func (s *fabricApplicationServiceImpl) ListFabrics(ctx context.Context, page, pageSize int) (*FabricListDTO, error) {
	// Retrieve fabrics from repository
	fabrics, totalCount, err := s.fabricRepo.List(ctx, page, pageSize)
	if err != nil {
		return nil, fmt.Errorf("failed to list fabrics: %w", err)
	}

	// Convert to DTOs
	var items []FabricStatusDTO
	for _, fabric := range fabrics {
		// Get fabric status for each fabric
		status, err := s.GetFabricStatus(ctx, fabric.ID)
		if err != nil {
			// Continue with basic information if status retrieval fails
			status = &FabricStatusDTO{
				FabricID:    fabric.ID,
				Name:        fabric.Name,
				Status:      string(fabric.Status),
				HealthScore: 0.5, // Neutral score when status is unknown
			}
		}
		items = append(items, *status)
	}

	return &FabricListDTO{
		Items:      items,
		TotalCount: totalCount,
		Page:       page,
		PageSize:   pageSize,
		HasMore:    (page * pageSize) < totalCount,
	}, nil
}