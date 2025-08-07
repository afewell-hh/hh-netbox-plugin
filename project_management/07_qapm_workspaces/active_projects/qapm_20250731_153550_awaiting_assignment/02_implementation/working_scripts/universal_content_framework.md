# Universal Content Framework Specification
**Framework Date**: July 31, 2025  
**Designer**: System Architecture Designer  
**Purpose**: Detailed specification for universal CLAUDE.md content framework applicable to all agent types

## Framework Overview

This specification defines a comprehensive content framework for creating neutral universal context that enhances all agent types without role confusion. The framework is based on analysis of 343 lines of role-specific content causing 12 distinct confusion patterns.

## Content Architecture Specification

### Framework Structure Definition

```
Universal CLAUDE.md Content Framework
├── Section 1: Project Technical Foundation    [~150 lines]
├── Section 2: Development Environment         [~100 lines]  
├── Section 3: Technical Standards            [~120 lines]
├── Section 4: Project Architecture           [~80 lines]
└── Section 5: HNP-Specific Context          [~100 lines]
Total Estimated Length: ~550 lines (vs 530 current)
```

### Content Category Definitions

#### Category A: Technical Foundation Information
**Purpose**: Essential project context for all technical work
**Scope**: Project identification, status, architecture, constraints
**Validation**: Must be factual, objective, immediately relevant
**Prohibited**: Process methodology, coordination requirements, authority grants

#### Category B: Development Tools and Commands  
**Purpose**: Actionable tools for all development workflows
**Scope**: Environment setup, testing, quality tools, operational commands
**Validation**: Must be executable, specific, universally applicable
**Prohibited**: Role-specific workflows, agent coordination, methodology overhead

#### Category C: Technical Standards and Patterns
**Purpose**: Implementation guidance for all technical work
**Scope**: Coding standards, patterns, quality requirements, examples
**Validation**: Must be specific, implementable, role-neutral
**Prohibited**: Authority assumptions, coordination patterns, process frameworks

#### Category D: Architecture and Navigation
**Purpose**: Structural understanding for all agent types
**Scope**: File organization, component relationships, documentation locations
**Validation**: Must enable navigation and understanding across domains
**Prohibited**: Workspace coordination, role-specific organization, management structures

#### Category E: Project-Specific Context
**Purpose**: HNP-specific technical information and constraints
**Scope**: Current capabilities, technical constraints, integration points
**Validation**: Must be project-specific, technically relevant, universally applicable
**Prohibited**: Operational coordination, role assignments, methodology requirements

## Detailed Section Specifications

### Section 1: Project Technical Foundation
**Target Length**: ~150 lines
**Content Density**: High technical value, zero methodology overhead

#### 1.1 Project Identification and Status
```markdown
# NetBox Hedgehog Plugin - Technical Context

**Project**: Self-service Kubernetes CRD management via NetBox interface
**Current Status**: Production ready with 12 CRD types operational  
**Architecture**: NetBox 4.3.3 Django plugin with Kubernetes client integration
**Last Updated**: [Current Date]
```

**Content Requirements**:
- Factual project identification
- Current operational status
- High-level architecture description
- Maintenance and update context

#### 1.2 Technology Stack Specification
```markdown
## Core Technology Stack

### Primary Framework
- **NetBox**: 4.3.3 (Django-based network management platform)
- **Python**: 3.9+ with Django 4.2.x framework
- **Database**: PostgreSQL (NetBox standard configuration)
- **Frontend**: Bootstrap 5 with NetBox-consistent styling patterns

### Integration Technologies  
- **Kubernetes**: Client library integration for CRD lifecycle management
- **GitOps**: ArgoCD integration with repository-based configuration workflows
- **API**: Django REST Framework with NetBox model integration
- **UI**: Progressive disclosure patterns with JavaScript enhancement
```

**Content Requirements**:
- Specific version requirements
- Integration technology context
- Framework and platform information
- Technical dependency understanding

#### 1.3 Dependency Specification
```python
## Key Dependencies

# Core Platform Dependencies
netbox>=4.3.3                    # NetBox platform requirement
django>=4.2.0                    # Django framework compatibility
psycopg2>=2.9.0                 # PostgreSQL database adapter

# Kubernetes Integration
kubernetes>=24.0.0               # Kubernetes Python client
pyyaml>=6.0                      # YAML configuration processing
cryptography>=3.4.8             # Security and certificate handling

# Development Dependencies  
pytest>=7.0.0                   # Testing framework
black>=22.0.0                   # Code formatting
flake8>=5.0.0                   # Code linting and quality
```

**Content Requirements**:
- Specific version constraints
- Dependency purpose explanation
- Development vs production requirements
- Integration and platform dependencies

### Section 2: Development Environment
**Target Length**: ~100 lines
**Content Density**: Maximum actionable command value

#### 2.1 Environment Setup Commands
```bash
## Environment Preparation

# Virtual Environment Management
python3 -m venv netbox_hedgehog_env        # Create isolated environment
source netbox_hedgehog_env/bin/activate    # Activate development environment
pip install --upgrade pip                  # Ensure latest pip version

# Dependency Installation
pip install -r requirements.txt            # Install project dependencies  
pip install -r requirements-dev.txt        # Install development tools
```

**Content Requirements**:
- Complete environment setup sequence
- Specific command syntax
- Clear command purpose
- Platform-agnostic where possible

#### 2.2 Testing and Validation Tools
```bash
## Testing and Quality Assurance

# Test Execution
python -m pytest                           # Execute full test suite
python -m pytest tests/test_models.py      # Run specific test module
python -m pytest tests/test_api.py -v      # Verbose output for API tests
python -m pytest --cov=netbox_hedgehog     # Execute with coverage analysis

# Code Quality Tools
black netbox_hedgehog/                     # Format code to standard
black --check netbox_hedgehog/             # Verify formatting compliance
flake8 netbox_hedgehog/                    # Lint code for quality issues
flake8 netbox_hedgehog/ --statistics       # Quality statistics report
```

**Content Requirements**:
- Complete testing workflow commands
- Quality assurance tool usage
- Specific command options and flags
- Output interpretation guidance

#### 2.3 NetBox Development Operations
```bash
## NetBox Development Operations

# Database Management
python manage.py migrate                   # Apply all migrations
python manage.py migrate netbox_hedgehog   # Apply plugin-specific migrations
python manage.py showmigrations            # Display migration status

# Development Server
python manage.py runserver                 # Start development server (port 8000)
python manage.py runserver 0.0.0.0:8080   # Custom host and port configuration

# Data Management
python manage.py loaddata initial_data     # Load development data
python manage.py shell                     # Access Django shell for debugging
```

**Content Requirements**:
- NetBox-specific operational commands
- Database migration procedures
- Development server configuration
- Data management and debugging tools

### Section 3: Technical Standards and Patterns
**Target Length**: ~120 lines
**Content Density**: Specific implementation guidance with examples

#### 3.1 Python Coding Standards
```python
## Python Implementation Standards

# Import Organization (follow PEP 8 and Django conventions)
# Standard library imports
import os
import logging
from typing import Dict, List, Optional

# Third-party imports  
import yaml
from django.db import models
from kubernetes import client, config

# Local application imports
from netbox.models import NetBoxModel
from .validators import validate_fabric_name

# Naming Conventions
class HedgehogFabric(NetBoxModel):          # PascalCase for classes
    """CamelCase class with descriptive docstring."""
    
    def validate_configuration(self) -> bool: # snake_case for methods
        """Method with type hints and clear documentation."""
        fabric_name = self.name.lower()      # snake_case for variables
        return validate_fabric_name(fabric_name)

# Constants and Configuration
DEFAULT_TIMEOUT = 30                        # UPPER_CASE for constants
MAX_RETRY_ATTEMPTS = 3
```

**Content Requirements**:
- Specific naming convention examples
- Import organization standards
- Type hinting requirements
- Documentation standards

#### 3.2 Django/NetBox Implementation Patterns
```python
## NetBox Model Implementation Patterns

# Model Definition Standards
class HedgehogFabric(NetBoxModel):
    """Hedgehog fabric configuration with NetBox integration."""
    
    # Required fields with proper constraints
    name = models.CharField(
        max_length=100, 
        unique=True,
        help_text="Unique fabric identifier"
    )
    
    # Optional fields with sensible defaults
    description = models.TextField(
        blank=True,
        help_text="Optional fabric description"  
    )
    
    # Foreign key relationships following NetBox patterns
    site = models.ForeignKey(
        to='dcim.Site',
        on_delete=models.CASCADE,
        help_text="Site where fabric is deployed"
    )
    
    class Meta:
        ordering = ['name']                  # Consistent ordering
        verbose_name_plural = 'Hedgehog Fabrics'  # Proper pluralization
        
    def __str__(self):
        return self.name                     # String representation
```

**Content Requirements**:
- NetBox model inheritance patterns
- Field definition best practices  
- Relationship implementation standards
- Meta class configuration

#### 3.3 API Implementation Standards
```python
## REST API Implementation Patterns

# Serializer Implementation
from rest_framework import serializers
from netbox.api.serializers import NetBoxModelSerializer

class HedgehogFabricSerializer(NetBoxModelSerializer):
    """API serializer with validation and formatting."""
    
    class Meta:
        model = HedgehogFabric
        fields = '__all__'
        
    def validate_name(self, value):
        """Custom field validation with clear error messages."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError(
                "Fabric name must be at least 3 characters long."
            )
        return value.strip().lower()

# ViewSet Implementation  
from netbox.api.viewsets import NetBoxModelViewSet

class HedgehogFabricViewSet(NetBoxModelViewSet):
    """API viewset following NetBox patterns."""
    queryset = HedgehogFabric.objects.all()
    serializer_class = HedgehogFabricSerializer
    filterset_class = HedgehogFabricFilterSet
```

**Content Requirements**:
- API serializer patterns
- Validation implementation examples
- ViewSet configuration standards
- Error handling patterns

### Section 4: Project Architecture and Navigation
**Target Length**: ~80 lines  
**Content Density**: Structural organization and navigation guidance

#### 4.1 Project Directory Structure
```
## Project File Organization

netbox_hedgehog/                    # Main plugin package
├── __init__.py                     # Plugin initialization
├── config.py                      # Plugin configuration
├── models/                        # Database model definitions
│   ├── __init__.py                # Model registration
│   ├── fabric.py                  # Fabric management models
│   ├── interface.py               # Interface configuration models
│   └── validators.py              # Model validation functions
├── api/                           # REST API implementation
│   ├── __init__.py                # API package initialization
│   ├── serializers.py             # Data serialization classes
│   ├── views.py                   # API endpoint implementations
│   └── urls.py                    # API URL routing
├── views/                         # Web interface views
│   ├── __init__.py                # View package initialization
│   ├── fabric.py                  # Fabric management views
│   └── generic.py                 # Shared view functionality
├── templates/                     # HTML template files
│   └── netbox_hedgehog/           # Plugin-specific templates
│       ├── fabric/                # Fabric management templates
│       └── inc/                   # Shared template components
├── static/                        # Static web assets
│   └── netbox_hedgehog/           # Plugin-specific assets
│       ├── css/                   # Stylesheet files
│       ├── js/                    # JavaScript files
│       └── img/                   # Image assets
└── tests/                         # Test suite
    ├── test_models.py             # Model testing
    ├── test_api.py                # API testing
    └── test_views.py              # View testing
```

**Content Requirements**:
- Complete directory structure mapping
- File purpose explanations
- Organization logic understanding
- Navigation guidance for all domains

#### 4.2 Documentation Architecture
```
## Documentation Organization

/architecture_specifications/       # Technical architecture documentation
├── system_architecture.md         # Overall system design
├── database_schema.md             # Data model specifications  
├── api_specification.md           # REST API documentation
└── integration_architecture.md    # External system integration

/docs/                             # User and developer documentation
├── api/                          # API documentation
├── development/                  # Development guides
├── deployment/                   # Deployment procedures
└── user_guide/                   # End-user documentation

/tests/                           # Test specifications and evidence
├── unit/                        # Unit test implementations
├── integration/                 # Integration test suites
└── fixtures/                    # Test data and fixtures
```

**Content Requirements**:
- Documentation location mapping
- Content organization logic
- Access patterns for different information types
- Integration with development workflow

### Section 5: HNP-Specific Technical Context  
**Target Length**: ~100 lines
**Content Density**: Project-specific constraints and capabilities

#### 5.1 Current Implementation Overview
```markdown
## HNP Technical Implementation Status

### Operational Capabilities
- **CRD Management**: 12 CRD types with full lifecycle support
  - VPC API: 7 CRD types (VPC, Subnet, SecurityGroup, RouteTable, etc.)
  - Wiring API: 5 CRD types (Switch, Port, Connection, etc.)
- **NetBox Integration**: Seamless UI integration with NetBox 4.3.3 patterns
- **Kubernetes Sync**: Real-time synchronization with cluster CRD status
- **GitOps Workflow**: Repository-based configuration with ArgoCD integration

### Test Coverage Status
- **Unit Tests**: 100% model coverage with comprehensive validation
- **Integration Tests**: Full API endpoint coverage with realistic scenarios  
- **UI Tests**: Progressive disclosure and workflow validation
- **End-to-End**: Complete CRD lifecycle testing with Kubernetes integration
```

**Content Requirements**:
- Specific current capabilities
- Technical implementation status
- Integration points and functionality
- Quality and testing context

#### 5.2 Technical Constraints and Requirements  
```markdown
## Technical Constraints and Integration Requirements

### Platform Compatibility
- **NetBox Version**: Must maintain NetBox 4.3.3+ compatibility
- **Django Framework**: Django 4.2.x requirement with backward compatibility
- **Python Version**: Python 3.9+ requirement for modern language features
- **Database**: PostgreSQL optimization for NetBox standard configuration

### Kubernetes Integration Constraints
- **CRD Lifecycle**: Must follow Kubernetes CRD management best practices
- **API Compatibility**: Kubernetes client library version alignment
- **Status Synchronization**: Real-time status updates without performance impact
- **Error Handling**: Graceful degradation when cluster unavailable

### UI Design Requirements
- **NetBox Consistency**: Must follow NetBox administrative interface patterns
- **Progressive Disclosure**: Complex configuration presented in manageable steps
- **Responsive Design**: Bootstrap 5 responsive patterns for all screen sizes
- **Accessibility**: WCAG compliance following NetBox accessibility standards
```

**Content Requirements**:
- Specific technical constraints
- Integration architecture requirements  
- Performance and compatibility considerations
- Design and user experience requirements

#### 5.3 Development Priorities and Focus Areas
```markdown
## Current Development Context

### Active Focus Areas
- **Performance Optimization**: CRD synchronization efficiency improvements
- **UI Enhancement**: Progressive disclosure pattern refinement
- **Integration Stability**: Kubernetes client error handling and resilience
- **Documentation**: Architecture specification completion and maintenance

### Technical Debt and Maintenance
- **Code Quality**: Ongoing refactoring for maintainability
- **Test Coverage**: Expansion of edge case and error condition testing
- **Security**: Regular dependency updates and security patch integration
- **Monitoring**: Observability and debugging capability enhancement

### Integration Architecture
- **GitOps Pipeline**: ArgoCD integration with configuration repository
- **Status Reporting**: Real-time CRD status reflection in NetBox UI
- **Error Propagation**: Meaningful error messages from Kubernetes to NetBox
- **Configuration Validation**: Pre-deployment validation of CRD configurations
```

**Content Requirements**:
- Current development priorities
- Technical debt and maintenance context
- Integration architecture understanding
- Quality and security considerations

## Content Quality Framework

### Universal Applicability Validation
**Validation Matrix**:
```
Agent Type          | Foundation | Environment | Standards | Architecture | HNP Context
Backend Specialist  |     ✓      |      ✓      |     ✓     |      ✓       |      ✓
Frontend Specialist |     ✓      |      ✓      |     ✓     |      ✓       |      ✓
Test Specialist     |     ✓      |      ✓      |     ✓     |      ✓       |      ✓
DevOps Specialist   |     ✓      |      ✓      |     ✓     |      ✓       |      ✓
Architecture Spec.  |     ✓      |      ✓      |     ✓     |      ✓       |      ✓
```

### Content Quality Requirements
**Technical Accuracy**:
- All commands tested and verified
- Code examples syntactically correct
- Version requirements accurate and current
- Integration points properly documented

**Actionable Information**:
- Every section provides immediate technical value
- Information directly supports implementation work
- Clear examples with specific technical details
- Complete workflow guidance without methodology overhead

**Role Neutrality**:
- No coordination or management instructions
- No agent spawning or orchestration references
- No authority grants beyond standard development
- No process methodologies beyond technical necessities

### Language Standards

#### Prohibited Terminology Patterns
- "Agent orchestration", "agent coordination", "agent spawning"
- "Full authority", "authority granted", "coordination authority"
- "Four-phase methodology", "systematic approach", "phase transitions"
- "Quality gates", "evidence frameworks", "validation systems"
- "Escalation triggers", "project coordination", "workspace management"

#### Required Language Patterns  
- "Development workflow", "technical approach", "implementation process"
- "Standard procedures", "development permissions", "git workflow"
- "Testing requirements", "code quality", "technical validation"
- "Project context", "technical constraints", "implementation guidance"
- "Architecture information", "integration points", "technical specifications"

### Maintenance and Evolution Guidelines

#### Content Evolution Standards
- New content must pass universal applicability validation
- Technical enhancements encouraged, methodology additions prohibited
- Project-specific information valuable, coordination requirements eliminated
- Tool and command additions beneficial, process overhead discouraged

#### Quality Assurance Process
- Regular review for role confusion pattern introduction
- Agent type testing for new content additions
- Language neutrality validation for all updates
- Technical accuracy verification for all changes

#### Success Measurement Framework
- **Task Completion Efficiency**: Reduced process overhead for technical tasks
- **Universal Utility**: Enhanced effectiveness across all agent types
- **Role Clarity**: Zero inappropriate coordination or authority assumptions
- **Content Quality**: Sustained technical value without methodology confusion

This comprehensive framework specification provides the detailed foundation for implementing neutral universal content that enhances all agent types while completely eliminating role confusion risks.