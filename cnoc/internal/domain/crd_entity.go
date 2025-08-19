package domain

import (
	"time"
	"fmt"
	"encoding/json"
)

// CRD represents a Kubernetes Custom Resource Definition entity
// Following domain-driven design patterns with value objects and business rules
type CRD struct {
	// Core identity
	id        CRDIdentifier
	name      CRDName
	namespace CRDNamespace
	kind      CRDKind
	
	// Kubernetes metadata
	apiVersion APIVersion
	labels     CRDLabels
	
	// CRD content
	manifest   CRDManifest
	
	// CNOC metadata
	status       CRDEntityStatus
	validationResult ValidationResult
	
	// GitOps tracking
	gitMetadata GitMetadata
	
	// Audit fields
	auditInfo AuditInfo
}

// Value objects for CRD entity

// CRDIdentifier represents a unique CRD identifier
type CRDIdentifier struct {
	value string
}

// NewCRDIdentifier creates a new CRD identifier
func NewCRDIdentifier(id string) (CRDIdentifier, error) {
	if id == "" {
		return CRDIdentifier{}, fmt.Errorf("CRD identifier cannot be empty")
	}
	return CRDIdentifier{value: id}, nil
}

// String returns the string representation of the identifier
func (id CRDIdentifier) String() string {
	return id.value
}

// CRDName represents a CRD name with validation
type CRDName struct {
	value string
}

// NewCRDName creates a new CRD name with validation
func NewCRDName(name string) (CRDName, error) {
	if name == "" {
		return CRDName{}, fmt.Errorf("CRD name cannot be empty")
	}
	if len(name) > 253 {
		return CRDName{}, fmt.Errorf("CRD name too long: %d characters (max 253)", len(name))
	}
	return CRDName{value: name}, nil
}

// String returns the string representation of the name
func (n CRDName) String() string {
	return n.value
}

// CRDNamespace represents a Kubernetes namespace
type CRDNamespace struct {
	value string
}

// NewCRDNamespace creates a new CRD namespace
func NewCRDNamespace(namespace string) (CRDNamespace, error) {
	if namespace == "" {
		namespace = "default"
	}
	if len(namespace) > 63 {
		return CRDNamespace{}, fmt.Errorf("namespace too long: %d characters (max 63)", len(namespace))
	}
	return CRDNamespace{value: namespace}, nil
}

// String returns the string representation of the namespace
func (n CRDNamespace) String() string {
	return n.value
}

// CRDKind represents a Kubernetes Kind
type CRDKind struct {
	value string
}

// NewCRDKind creates a new CRD kind
func NewCRDKind(kind string) (CRDKind, error) {
	if kind == "" {
		return CRDKind{}, fmt.Errorf("CRD kind cannot be empty")
	}
	return CRDKind{value: kind}, nil
}

// String returns the string representation of the kind
func (k CRDKind) String() string {
	return k.value
}

// APIVersion represents a Kubernetes API version
type APIVersion struct {
	value string
}

// NewAPIVersion creates a new API version
func NewAPIVersion(version string) (APIVersion, error) {
	if version == "" {
		return APIVersion{}, fmt.Errorf("API version cannot be empty")
	}
	return APIVersion{value: version}, nil
}

// String returns the string representation of the API version
func (v APIVersion) String() string {
	return v.value
}

// CRDLabels represents Kubernetes labels
type CRDLabels struct {
	labels map[string]string
}

// NewCRDLabels creates new CRD labels
func NewCRDLabels(labels map[string]string) CRDLabels {
	if labels == nil {
		labels = make(map[string]string)
	}
	return CRDLabels{labels: labels}
}

// Get returns a label value
func (l CRDLabels) Get(key string) (string, bool) {
	value, exists := l.labels[key]
	return value, exists
}

// Set sets a label value
func (l *CRDLabels) Set(key, value string) {
	if l.labels == nil {
		l.labels = make(map[string]string)
	}
	l.labels[key] = value
}

// All returns all labels
func (l CRDLabels) All() map[string]string {
	result := make(map[string]string)
	for k, v := range l.labels {
		result[k] = v
	}
	return result
}

// CRDManifest represents the CRD manifest content
type CRDManifest struct {
	spec   json.RawMessage
	status json.RawMessage
}

// NewCRDManifest creates a new CRD manifest
func NewCRDManifest(spec map[string]interface{}) (CRDManifest, error) {
	specBytes, err := json.Marshal(spec)
	if err != nil {
		return CRDManifest{}, fmt.Errorf("failed to marshal spec: %w", err)
	}
	return CRDManifest{
		spec:   specBytes,
		status: json.RawMessage("{}"),
	}, nil
}

// Spec returns the spec as JSON
func (m CRDManifest) Spec() json.RawMessage {
	return m.spec
}

// Status returns the status as JSON
func (m CRDManifest) Status() json.RawMessage {
	return m.status
}

// UpdateStatus updates the status portion
func (m *CRDManifest) UpdateStatus(status map[string]interface{}) error {
	statusBytes, err := json.Marshal(status)
	if err != nil {
		return fmt.Errorf("failed to marshal status: %w", err)
	}
	m.status = statusBytes
	return nil
}

// CRDEntityStatus represents the entity status
type CRDEntityStatus struct {
	value string
}

// NewCRDEntityStatus creates a new entity status
func NewCRDEntityStatus(status string) CRDEntityStatus {
	if status == "" {
		status = "pending"
	}
	return CRDEntityStatus{value: status}
}

// String returns the string representation of the status
func (s CRDEntityStatus) String() string {
	return s.value
}

// IsActive returns true if the CRD is active
func (s CRDEntityStatus) IsActive() bool {
	return s.value == "active"
}

// ValidationResult represents validation results
type ValidationResult struct {
	valid    bool
	errors   []string
	warnings []string
}

// NewValidationResult creates a new validation result
func NewValidationResult(valid bool, errors, warnings []string) ValidationResult {
	if errors == nil {
		errors = []string{}
	}
	if warnings == nil {
		warnings = []string{}
	}
	return ValidationResult{
		valid:    valid,
		errors:   errors,
		warnings: warnings,
	}
}

// IsValid returns true if validation passed
func (v ValidationResult) IsValid() bool {
	return v.valid
}

// Errors returns validation errors
func (v ValidationResult) Errors() []string {
	return v.errors
}

// Warnings returns validation warnings
func (v ValidationResult) Warnings() []string {
	return v.warnings
}

// GitMetadata represents GitOps metadata
type GitMetadata struct {
	filePath     string
	commitHash   string
	lastSynced   time.Time
	syncSource   string
}

// NewGitMetadata creates new git metadata
func NewGitMetadata(filePath, commitHash string) GitMetadata {
	return GitMetadata{
		filePath:   filePath,
		commitHash: commitHash,
		lastSynced: time.Now(),
		syncSource: "git",
	}
}

// FilePath returns the git file path
func (g GitMetadata) FilePath() string {
	return g.filePath
}

// CommitHash returns the commit hash
func (g GitMetadata) CommitHash() string {
	return g.commitHash
}

// LastSynced returns the last sync time
func (g GitMetadata) LastSynced() time.Time {
	return g.lastSynced
}

// AuditInfo represents audit information
type AuditInfo struct {
	createdAt    time.Time
	updatedAt    time.Time
	createdBy    string
	updatedBy    string
}

// NewAuditInfo creates new audit info
func NewAuditInfo(createdBy string) AuditInfo {
	now := time.Now()
	return AuditInfo{
		createdAt: now,
		updatedAt: now,
		createdBy: createdBy,
		updatedBy: createdBy,
	}
}

// CreatedAt returns the creation timestamp
func (a AuditInfo) CreatedAt() time.Time {
	return a.createdAt
}

// UpdatedAt returns the last update timestamp
func (a AuditInfo) UpdatedAt() time.Time {
	return a.updatedAt
}

// CreatedBy returns the creator
func (a AuditInfo) CreatedBy() string {
	return a.createdBy
}

// UpdatedBy returns the last updater
func (a AuditInfo) UpdatedBy() string {
	return a.updatedBy
}

// Touch updates the audit info for modification
func (a *AuditInfo) Touch(updatedBy string) {
	a.updatedAt = time.Now()
	a.updatedBy = updatedBy
}

// CRD entity constructor and methods

// NewCRD creates a new CRD entity
func NewCRD(name, namespace, kind, apiVersion string, spec map[string]interface{}) (*CRD, error) {
	// Generate ID
	id, err := NewCRDIdentifier(fmt.Sprintf("%s-%s-%d", namespace, name, time.Now().Unix()))
	if err != nil {
		return nil, fmt.Errorf("failed to create CRD identifier: %w", err)
	}
	
	// Create value objects
	crdName, err := NewCRDName(name)
	if err != nil {
		return nil, fmt.Errorf("failed to create CRD name: %w", err)
	}
	
	crdNamespace, err := NewCRDNamespace(namespace)
	if err != nil {
		return nil, fmt.Errorf("failed to create CRD namespace: %w", err)
	}
	
	crdKind, err := NewCRDKind(kind)
	if err != nil {
		return nil, fmt.Errorf("failed to create CRD kind: %w", err)
	}
	
	crdAPIVersion, err := NewAPIVersion(apiVersion)
	if err != nil {
		return nil, fmt.Errorf("failed to create API version: %w", err)
	}
	
	manifest, err := NewCRDManifest(spec)
	if err != nil {
		return nil, fmt.Errorf("failed to create CRD manifest: %w", err)
	}
	
	return &CRD{
		id:               id,
		name:             crdName,
		namespace:        crdNamespace,
		kind:             crdKind,
		apiVersion:       crdAPIVersion,
		labels:           NewCRDLabels(nil),
		manifest:         manifest,
		status:           NewCRDEntityStatus("pending"),
		validationResult: NewValidationResult(false, []string{}, []string{}),
		gitMetadata:      GitMetadata{},
		auditInfo:        NewAuditInfo("system"),
	}, nil
}

// Getters for CRD entity

// ID returns the CRD identifier
func (c *CRD) ID() CRDIdentifier {
	return c.id
}

// Name returns the CRD name
func (c *CRD) Name() string {
	return c.name.String()
}

// Namespace returns the CRD namespace
func (c *CRD) Namespace() string {
	return c.namespace.String()
}

// Kind returns the CRD kind
func (c *CRD) Kind() string {
	return c.kind.String()
}

// APIVersion returns the API version
func (c *CRD) APIVersion() string {
	return c.apiVersion.String()
}

// Labels returns the CRD labels
func (c *CRD) Labels() map[string]string {
	return c.labels.All()
}

// Manifest returns the CRD manifest
func (c *CRD) Manifest() map[string]interface{} {
	var spec map[string]interface{}
	json.Unmarshal(c.manifest.Spec(), &spec)
	return spec
}

// Status returns the entity status
func (c *CRD) Status() string {
	return c.status.String()
}

// ValidationResult returns the validation result
func (c *CRD) ValidationResult() ValidationResult {
	return c.validationResult
}

// IsActive returns true if the CRD is active
func (c *CRD) IsActive() bool {
	return c.status.IsActive()
}

// IsValid returns true if the CRD is valid
func (c *CRD) IsValid() bool {
	return c.validationResult.IsValid()
}

// CreatedAt returns creation timestamp
func (c *CRD) CreatedAt() time.Time {
	return c.auditInfo.CreatedAt()
}

// UpdatedAt returns last update timestamp
func (c *CRD) UpdatedAt() time.Time {
	return c.auditInfo.UpdatedAt()
}

// Business methods

// UpdateManifest updates the CRD manifest
func (c *CRD) UpdateManifest(spec map[string]interface{}, updatedBy string) error {
	manifest, err := NewCRDManifest(spec)
	if err != nil {
		return fmt.Errorf("failed to update manifest: %w", err)
	}
	
	c.manifest = manifest
	c.auditInfo.Touch(updatedBy)
	
	// Reset validation since manifest changed
	c.validationResult = NewValidationResult(false, []string{}, []string{})
	
	return nil
}

// SetLabel sets a label on the CRD
func (c *CRD) SetLabel(key, value string) {
	c.labels.Set(key, value)
}

// Validate performs domain validation
func (c *CRD) Validate() error {
	var errors []string
	var warnings []string
	
	// Basic validation
	if c.name.String() == "" {
		errors = append(errors, "name is required")
	}
	if c.kind.String() == "" {
		errors = append(errors, "kind is required")
	}
	if c.apiVersion.String() == "" {
		errors = append(errors, "apiVersion is required")
	}
	
	// Manifest validation
	var spec map[string]interface{}
	if err := json.Unmarshal(c.manifest.Spec(), &spec); err != nil {
		errors = append(errors, "invalid manifest spec")
	}
	
	valid := len(errors) == 0
	c.validationResult = NewValidationResult(valid, errors, warnings)
	
	if valid {
		c.status = NewCRDEntityStatus("active")
	} else {
		c.status = NewCRDEntityStatus("error")
	}
	
	if len(errors) > 0 {
		return fmt.Errorf("validation failed: %v", errors)
	}
	
	return nil
}

// UpdateGitMetadata updates git synchronization metadata
func (c *CRD) UpdateGitMetadata(filePath, commitHash string) {
	c.gitMetadata = NewGitMetadata(filePath, commitHash)
}

// MarkAsActive marks the CRD as active
func (c *CRD) MarkAsActive() {
	c.status = NewCRDEntityStatus("active")
}

// MarkAsError marks the CRD as having an error
func (c *CRD) MarkAsError(errorMessage string) {
	c.status = NewCRDEntityStatus("error")
	c.validationResult = NewValidationResult(false, []string{errorMessage}, []string{})
}

// GenerateCRDID generates a new CRD identifier
func GenerateCRDID() CRDIdentifier {
	id := fmt.Sprintf("crd-%d", time.Now().UnixNano())
	identifier, _ := NewCRDIdentifier(id)
	return identifier
}