package services

import (
	"context"
	"errors"
	"fmt"
	"sort"

	"github.com/hedgehog/cnoc/internal/domain/configuration"
	"github.com/hedgehog/cnoc/internal/domain/events"
	"github.com/hedgehog/cnoc/internal/domain/shared"
)

// DependencyResolver is a domain service that handles component dependency
// resolution, validation, and installation ordering following MDD principles
type DependencyResolver struct {
	componentRegistry ComponentRegistry
	eventBus         events.EventBus
}

// NewDependencyResolver creates a new dependency resolver
func NewDependencyResolver(
	componentRegistry ComponentRegistry,
	eventBus events.EventBus,
) *DependencyResolver {
	return &DependencyResolver{
		componentRegistry: componentRegistry,
		eventBus:         eventBus,
	}
}

// DependencyGraph represents the component dependency graph
type DependencyGraph struct {
	nodes map[string]*DependencyNode
	edges map[string][]string // adjacency list
}

// DependencyNode represents a component in the dependency graph
type DependencyNode struct {
	ComponentName configuration.ComponentName
	Version       shared.Version
	Dependencies  []DependencyRequirement
	Dependents    []string // components that depend on this one
}

// DependencyRequirement represents a dependency requirement
type DependencyRequirement struct {
	ComponentName     configuration.ComponentName
	VersionConstraint shared.VersionConstraint
	Optional          bool
	Reason            string
}

// ResolutionResult contains the results of dependency resolution
type ResolutionResult struct {
	Valid               bool
	InstallationOrder   []configuration.ComponentName
	MissingDependencies []MissingDependency
	CircularDependencies []CircularDependency
	VersionConflicts    []VersionConflict
	Warnings           []ResolutionWarning
}

// ResolutionWarning represents a warning during dependency resolution
type ResolutionWarning struct {
	ComponentName string
	Message       string
	Severity      WarningSeverity
}

// WarningSeverity represents the severity of resolution warnings
type WarningSeverity int

const (
	WarningSeverityLow WarningSeverity = iota
	WarningSeverityMedium
	WarningSeverityHigh
)

// ResolveDependencies resolves dependencies for a set of components
func (dr *DependencyResolver) ResolveDependencies(
	ctx context.Context,
	components []configuration.ComponentName,
) ResolutionResult {
	result := ResolutionResult{
		Valid:                true,
		InstallationOrder:    make([]configuration.ComponentName, 0),
		MissingDependencies:  make([]MissingDependency, 0),
		CircularDependencies: make([]CircularDependency, 0),
		VersionConflicts:     make([]VersionConflict, 0),
		Warnings:            make([]ResolutionWarning, 0),
	}

	// Build dependency graph
	graph, err := dr.buildDependencyGraph(ctx, components)
	if err != nil {
		result.Valid = false
		return result
	}

	// Find missing dependencies
	dr.findMissingDependencies(graph, &result)

	// Detect circular dependencies
	dr.detectCircularDependencies(graph, &result)

	// Resolve version conflicts
	dr.resolveVersionConflicts(graph, &result)

	// Generate installation order if no critical issues
	if len(result.CircularDependencies) == 0 && len(result.MissingDependencies) == 0 {
		order, err := dr.generateInstallationOrder(graph)
		if err != nil {
			result.Valid = false
		} else {
			result.InstallationOrder = order
		}
	} else {
		result.Valid = false
	}

	// Publish resolution event
	dr.publishResolutionEvent(components, result)

	return result
}

// ValidateDependencies validates dependencies without full resolution
func (dr *DependencyResolver) ValidateDependencies(
	ctx context.Context,
	components []configuration.ComponentName,
) DependencyValidationResult {
	result := DependencyValidationResult{
		Valid:               true,
		MissingDependencies: make([]MissingDependency, 0),
		CircularDependencies: make([]CircularDependency, 0),
		VersionConflicts:    make([]VersionConflict, 0),
		InstallationOrder:   make([]string, 0),
	}

	// Quick validation without full graph building
	for _, component := range components {
		deps, err := dr.componentRegistry.GetDependencies(component)
		if err != nil {
			continue
		}

		for _, dep := range deps {
			// Check if dependency is satisfied
			if !dr.isComponentPresent(dep.ComponentName, components) {
				result.MissingDependencies = append(result.MissingDependencies, MissingDependency{
					RequiredBy:      component.String(),
					ComponentName:   dep.ComponentName.String(),
					RequiredVersion: dep.VersionConstraint.String(),
					Severity:        ValidationSeverity(WarningSeverityHigh),
				})
				result.Valid = false
			}
		}
	}

	// Convert component names to strings for installation order
	if result.Valid {
		resolutionResult := dr.ResolveDependencies(ctx, components)
		for _, comp := range resolutionResult.InstallationOrder {
			result.InstallationOrder = append(result.InstallationOrder, comp.String())
		}
	}

	return result
}

// ResolveInstallOrder generates the optimal installation order for components
func (dr *DependencyResolver) ResolveInstallOrder(
	ctx context.Context,
	components []configuration.ComponentName,
) ([]configuration.ComponentName, error) {
	result := dr.ResolveDependencies(ctx, components)
	
	if !result.Valid {
		return nil, fmt.Errorf("dependency resolution failed: %d missing dependencies, %d circular dependencies",
			len(result.MissingDependencies), len(result.CircularDependencies))
	}

	return result.InstallationOrder, nil
}

// FindCircularDependencies detects circular dependencies in component set
func (dr *DependencyResolver) FindCircularDependencies(
	ctx context.Context,
	components []configuration.ComponentName,
) []CircularDependency {
	graph, err := dr.buildDependencyGraph(ctx, components)
	if err != nil {
		return nil
	}

	var cycles []CircularDependency
	dr.detectCircularDependencies(graph, &ResolutionResult{
		CircularDependencies: cycles,
	})

	return cycles
}

// GetDependencyTree returns the complete dependency tree for a component
func (dr *DependencyResolver) GetDependencyTree(
	ctx context.Context,
	component configuration.ComponentName,
) (*DependencyTree, error) {
	tree := &DependencyTree{
		Root:         component,
		Dependencies: make(map[string]*DependencyTreeNode),
	}

	err := dr.buildDependencyTree(ctx, component, tree, make(map[string]bool))
	if err != nil {
		return nil, err
	}

	return tree, nil
}

// DependencyTree represents a hierarchical dependency structure
type DependencyTree struct {
	Root         configuration.ComponentName
	Dependencies map[string]*DependencyTreeNode
}

// DependencyTreeNode represents a node in the dependency tree
type DependencyTreeNode struct {
	Component    configuration.ComponentName
	Version      shared.Version
	Optional     bool
	Dependencies []*DependencyTreeNode
	Depth        int
}

// Private implementation methods

func (dr *DependencyResolver) buildDependencyGraph(
	ctx context.Context,
	components []configuration.ComponentName,
) (*DependencyGraph, error) {
	graph := &DependencyGraph{
		nodes: make(map[string]*DependencyNode),
		edges: make(map[string][]string),
	}

	// Create nodes for all components
	for _, component := range components {
		version, err := dr.componentRegistry.GetVersion(component)
		if err != nil {
			return nil, fmt.Errorf("failed to get version for component %s: %w", component.String(), err)
		}

		dependencies, err := dr.componentRegistry.GetDependencies(component)
		if err != nil {
			return nil, fmt.Errorf("failed to get dependencies for component %s: %w", component.String(), err)
		}

		node := &DependencyNode{
			ComponentName: component,
			Version:       version,
			Dependencies:  dependencies,
			Dependents:    make([]string, 0),
		}

		graph.nodes[component.String()] = node
		graph.edges[component.String()] = make([]string, 0)
	}

	// Build edges based on dependencies
	for _, component := range components {
		node := graph.nodes[component.String()]
		for _, dep := range node.Dependencies {
			depName := dep.ComponentName.String()
			
			// Add edge from component to its dependency
			graph.edges[component.String()] = append(graph.edges[component.String()], depName)
			
			// Add reverse reference (dependent)
			if depNode, exists := graph.nodes[depName]; exists {
				depNode.Dependents = append(depNode.Dependents, component.String())
			}
		}
	}

	return graph, nil
}

func (dr *DependencyResolver) findMissingDependencies(
	graph *DependencyGraph,
	result *ResolutionResult,
) {
	for _, node := range graph.nodes {
		for _, dep := range node.Dependencies {
			depName := dep.ComponentName.String()
			
			// Check if dependency exists in the graph
			if _, exists := graph.nodes[depName]; !exists && !dep.Optional {
				result.MissingDependencies = append(result.MissingDependencies, MissingDependency{
					RequiredBy:      node.ComponentName.String(),
					ComponentName:   depName,
					RequiredVersion: dep.VersionConstraint.String(),
					Severity:        ValidationSeverityHigh,
				})
			}
		}
	}
}

func (dr *DependencyResolver) detectCircularDependencies(
	graph *DependencyGraph,
	result *ResolutionResult,
) {
	visited := make(map[string]bool)
	recStack := make(map[string]bool)
	path := make([]string, 0)

	for nodeName := range graph.nodes {
		if !visited[nodeName] {
			if dr.detectCyclesDFS(graph, nodeName, visited, recStack, path, result) {
				break // Found a cycle
			}
		}
	}
}

func (dr *DependencyResolver) detectCyclesDFS(
	graph *DependencyGraph,
	nodeName string,
	visited map[string]bool,
	recStack map[string]bool,
	path []string,
	result *ResolutionResult,
) bool {
	visited[nodeName] = true
	recStack[nodeName] = true
	path = append(path, nodeName)

	// Visit all dependencies
	for _, depName := range graph.edges[nodeName] {
		if !visited[depName] {
			if dr.detectCyclesDFS(graph, depName, visited, recStack, path, result) {
				return true
			}
		} else if recStack[depName] {
			// Found a cycle - extract the cycle from path
			cycleStart := -1
			for i, pathNode := range path {
				if pathNode == depName {
					cycleStart = i
					break
				}
			}
			
			if cycleStart != -1 {
				cycle := make([]string, 0)
				components := make([]string, 0)
				
				for i := cycleStart; i < len(path); i++ {
					cycle = append(cycle, path[i])
					components = append(components, path[i])
				}
				cycle = append(cycle, depName) // Complete the cycle
				
				result.CircularDependencies = append(result.CircularDependencies, CircularDependency{
					Components: components,
					Cycle:      cycle,
				})
				return true
			}
		}
	}

	recStack[nodeName] = false
	return false
}

func (dr *DependencyResolver) resolveVersionConflicts(
	graph *DependencyGraph,
	result *ResolutionResult,
) {
	// Track version requirements for each component
	versionRequirements := make(map[string][]VersionRequirement)

	for _, node := range graph.nodes {
		for _, dep := range node.Dependencies {
			depName := dep.ComponentName.String()
			req := VersionRequirement{
				RequiredBy:   node.ComponentName.String(),
				Constraint:   dep.VersionConstraint,
				Optional:     dep.Optional,
			}
			
			versionRequirements[depName] = append(versionRequirements[depName], req)
		}
	}

	// Check for conflicts
	for depName, requirements := range versionRequirements {
		if len(requirements) > 1 {
			conflict := dr.findVersionConflict(depName, requirements)
			if conflict != nil {
				result.VersionConflicts = append(result.VersionConflicts, *conflict)
			}
		}
	}
}

// VersionRequirement represents a version requirement
type VersionRequirement struct {
	RequiredBy string
	Constraint shared.VersionConstraint
	Optional   bool
}

func (dr *DependencyResolver) findVersionConflict(
	componentName string,
	requirements []VersionRequirement,
) *VersionConflict {
	// Simplified conflict detection - in practice this would be more sophisticated
	for i := 0; i < len(requirements); i++ {
		for j := i + 1; j < len(requirements); j++ {
			req1 := requirements[i]
			req2 := requirements[j]
			
			// Check if constraints are incompatible (simplified check)
			if req1.Constraint.String() != req2.Constraint.String() {
				return &VersionConflict{
					ComponentName:    componentName,
					RequestedVersion: req1.Constraint.String(),
					ConflictingWith:  req2.RequiredBy,
					ConflictVersion:  req2.Constraint.String(),
					Resolution:       "manual resolution required",
				}
			}
		}
	}
	
	return nil
}

func (dr *DependencyResolver) generateInstallationOrder(
	graph *DependencyGraph,
) ([]configuration.ComponentName, error) {
	// Use topological sort to determine installation order
	inDegree := make(map[string]int)
	queue := make([]string, 0)
	result := make([]configuration.ComponentName, 0)

	// Calculate in-degree for each node
	for nodeName := range graph.nodes {
		inDegree[nodeName] = 0
	}
	
	for _, edges := range graph.edges {
		for _, dep := range edges {
			if _, exists := inDegree[dep]; exists {
				inDegree[dep]++
			}
		}
	}

	// Find nodes with in-degree 0
	for nodeName, degree := range inDegree {
		if degree == 0 {
			queue = append(queue, nodeName)
		}
	}

	// Process nodes in topological order
	for len(queue) > 0 {
		// Sort queue for deterministic ordering
		sort.Strings(queue)
		
		current := queue[0]
		queue = queue[1:]
		
		// Add to result
		componentName, _ := configuration.NewComponentName(current)
		result = append(result, componentName)

		// Reduce in-degree of dependencies
		for _, dep := range graph.edges[current] {
			if _, exists := inDegree[dep]; exists {
				inDegree[dep]--
				if inDegree[dep] == 0 {
					queue = append(queue, dep)
				}
			}
		}
	}

	// Check if all nodes were processed (no cycles)
	if len(result) != len(graph.nodes) {
		return nil, errors.New("circular dependency detected during topological sort")
	}

	return result, nil
}

func (dr *DependencyResolver) buildDependencyTree(
	ctx context.Context,
	component configuration.ComponentName,
	tree *DependencyTree,
	visited map[string]bool,
) error {
	componentName := component.String()
	
	// Prevent infinite recursion
	if visited[componentName] {
		return nil
	}
	visited[componentName] = true

	// Get component dependencies
	dependencies, err := dr.componentRegistry.GetDependencies(component)
	if err != nil {
		return err
	}

	version, err := dr.componentRegistry.GetVersion(component)
	if err != nil {
		return err
	}

	// Create tree node
	node := &DependencyTreeNode{
		Component:    component,
		Version:      version,
		Dependencies: make([]*DependencyTreeNode, 0),
		Depth:        0,
	}

	tree.Dependencies[componentName] = node

	// Recursively build dependencies
	for _, dep := range dependencies {
		err := dr.buildDependencyTree(ctx, dep.ComponentName, tree, visited)
		if err != nil {
			return err
		}
		
		if depNode, exists := tree.Dependencies[dep.ComponentName.String()]; exists {
			depNode.Optional = dep.Optional
			depNode.Depth = node.Depth + 1
			node.Dependencies = append(node.Dependencies, depNode)
		}
	}

	return nil
}

func (dr *DependencyResolver) isComponentPresent(
	component configuration.ComponentName,
	components []configuration.ComponentName,
) bool {
	for _, comp := range components {
		if comp.Equals(component) {
			return true
		}
	}
	return false
}

func (dr *DependencyResolver) publishResolutionEvent(
	components []configuration.ComponentName,
	result ResolutionResult,
) {
	if dr.eventBus == nil {
		return
	}

	if result.Valid {
		// Publish successful resolution event
		for i, comp := range result.InstallationOrder {
			if i > 0 {
				prevComp := result.InstallationOrder[i-1]
				event := events.NewDependencyResolved(
					comp.String(),
					comp.String(),
					prevComp.String(),
				)
				dr.eventBus.Publish(event)
			}
		}
	} else {
		// Publish dependency violation events
		for _, missing := range result.MissingDependencies {
			event := events.NewDependencyViolated(
				missing.RequiredBy,
				missing.RequiredBy,
				missing.ComponentName,
			)
			dr.eventBus.Publish(event)
		}
	}
}