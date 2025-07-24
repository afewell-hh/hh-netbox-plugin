# NetBox Hedgehog Plugin Core

**Purpose**: Core plugin implementation for Kubernetes CRD management
**Version**: 0.0.0 (MVP Complete)

## Directory Structure
- models/: Django models for 12 CRD types + HedgehogFabric
- views/: List/Detail views with sync functionality  
- api/: REST API endpoints and serializers
- tables/: NetBox table definitions for UI
- forms/: Django forms for CRD management
- utils/: Kubernetes sync and helper utilities
- templates/: HTML templates with Bootstrap 5
- migrations/: Database schema migrations

## Key Features
1. Test Connection: Validates K8s cluster connectivity
2. Sync Now: Imports CRDs from Kubernetes cluster
3. CRD Management: CRUD operations for 12 types
4. Real-time Updates: Watch patterns for state sync

## CRD Types
**VPC API**: Connection, External, Rack, VPC, IPv4Namespace
**Wiring API**: Server, Switch, SwitchGroup, VLANNamespace, VPCVRF, VPCAttachment, VRFVLANAttachment

## Integration Points
- NetBox Plugin API for registration
- Kubernetes Python Client for cluster ops
- PostgreSQL for data persistence
- Bootstrap 5 for UI components