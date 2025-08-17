# Cloud NetOps Command (CNOC) Project Context

**Mission**: Enterprise-grade cloud networking operations infrastructure with bootable ISO deployment
**Status**: Production Development - Go-based CLI with Kubernetes architecture
**Branch**: modernization/k8s-foundation

## System Architecture Overview

**CNOC (Cloud NetOps Command)**: The new production system based on Go CLI, Kubernetes infrastructure, and domain-driven design patterns. This system replaces the original HNP prototype.

**HNP (Hedgehog NetBox Plugin)**: Original Python/Django prototype system preserved for reference on experimental/main branch.

## CNOC Technical Stack
- Core: Go-based cnocfab CLI utility
- Infrastructure: Kubernetes, GitOps, Terraform
- Architecture: Domain-driven design, microservices
- Deployment: Bootable ISO with pre-configured components
- Components: ArgoCD, Prometheus, Grafana, cert-manager

## HNP Prototype Stack (Reference Only)
- Backend: Django 4.2, NetBox 4.3.3 plugin architecture  
- Frontend: Bootstrap 5 with progressive disclosure UI
- Integration: Kubernetes Python client, ArgoCD GitOps
- Database: PostgreSQL (shared with NetBox core)

## Development Environment
- CNOC Branch: modernization/k8s-foundation
- HNP Reference: experimental/main  
- CLI Tool: cnocfab (replacing hossfab)
- Infrastructure: hossfab/, infrastructure/, hoss/ directories

## Quick Links
- Project Mgmt: @project_management/CLAUDE.md
- Architecture: @architecture_specifications/CLAUDE.md
- System Overview: @architecture_specifications/00_current_architecture/system_overview.md
- GitOps Architecture: @architecture_specifications/00_current_architecture/component_architecture/gitops/gitops_overview.md
- Architectural Decisions: @architecture_specifications/01_architectural_decisions/decision_log.md
- Environment: @claude_memory/environment/
- Current State: @project_management/00_current_state/
- Archive: @archive/README.md