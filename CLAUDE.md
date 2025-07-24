# Hedgehog NetBox Plugin (HNP) Project Context

**Mission**: Self-service Kubernetes CRD management via NetBox interface
**Status**: MVP Complete - 12 CRD types operational (49 CRDs synced)
**Branch**: feature/mvp2-database-foundation

## Technical Stack
- Backend: Django 4.2, NetBox 4.3.3 plugin architecture
- Frontend: Bootstrap 5 with progressive disclosure UI
- Integration: Kubernetes Python client, ArgoCD GitOps
- Database: PostgreSQL (shared with NetBox core)

## Environment
- NetBox Docker: localhost:8000 with plugin integrated
- HCKC Cluster: K3s at 127.0.0.1:6443
- GitOps: github.com/afewell-hh/gitops-test-1.git

## Quick Links
- Project Mgmt: @project_management/CLAUDE.md
- Architecture: @architecture_specifications/CLAUDE.md
- Environment: @claude_memory/environment/
- Current State: @project_management/00_current_state/