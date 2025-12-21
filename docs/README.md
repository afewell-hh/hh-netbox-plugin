# Hedgehog NetBox Plugin Documentation

Welcome to the comprehensive documentation for the Hedgehog NetBox Plugin! This plugin provides a powerful self-service catalog for managing Hedgehog Open Network Fabric resources directly from NetBox.

## 📚 Documentation Index

### Getting Started
- **[Quick Start Guide](QUICK_START.md)** - Get up and running in 5 minutes (Operational Features)
- **[DIET Quick Start](DIET_QUICK_START.md)** - Topology Planning for Pre-Sales (NEW)
- **[Installation Guide](../README.md#installation)** - Complete installation instructions
- **[Service Account Setup](SERVICE_ACCOUNT_SETUP.md)** - Kubernetes authentication setup

### User Documentation
- **[User Guide](USER_GUIDE.md)** - Comprehensive guide to all features
- **[Common Workflows](WORKFLOWS.md)** - Step-by-step workflows for daily operations
- **[Best Practices](USER_GUIDE.md#best-practices)** - Recommended practices and conventions

### Technical Documentation
- **[API Reference](API_REFERENCE.md)** - Complete REST API documentation
- **[Development Guide](../DEVELOPMENT_GUIDE.md)** - For developers and contributors
- **[Architecture Overview](../PROJECT_MANAGEMENT.md)** - Technical architecture details

### Operations
- **[Troubleshooting](USER_GUIDE.md#troubleshooting)** - Common issues and solutions
- **[Maintenance Procedures](WORKFLOWS.md#maintenance-workflows)** - Regular maintenance tasks
- **[Security Considerations](USER_GUIDE.md#security-best-practices)** - Security guidelines

## 🚀 What is the Hedgehog NetBox Plugin?

The Hedgehog NetBox Plugin is a comprehensive solution that bridges NetBox IPAM/DCIM capabilities with Hedgehog Open Network Fabric management. It provides:

### Key Capabilities

🏗️ **Multi-Fabric Management**
- Connect and manage multiple Hedgehog fabric installations
- Centralized monitoring and control from NetBox
- Fabric health monitoring and status tracking

☁️ **Self-Service VPC Catalog**
- Template-based VPC creation (Basic, Web+DB, Three-Tier, Custom)
- Real-time deployment to Kubernetes clusters
- IP address and VLAN management integration

🔌 **Infrastructure Tracking**
- Automatic discovery of switches, connections, and servers
- Physical topology visualization and monitoring
- Connection type management (unbundled, bundled, MCLAG, ESLAG)

⚡ **Bulk Operations**
- Efficient management of multiple resources
- Batch apply, update, and delete operations
- Progress tracking and error handling

🔄 **Bidirectional Synchronization**
- Automatic sync between NetBox and Kubernetes
- Detection and import of external changes
- Conflict resolution and change notifications

### Architecture Overview

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   NetBox    │◄──►│   Plugin    │◄──►│ Hedgehog    │
│   IPAM/DCIM │    │             │    │ Kubernetes  │
└─────────────┘    └─────────────┘    └─────────────┘
      │                    │                  │
      ▼                    ▼                  ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ IP/VLAN     │    │ Templates   │    │ CRDs        │
│ Management  │    │ Workflows   │    │ Controllers │
└─────────────┘    └─────────────┘    └─────────────┘
```

## 🎯 Who Should Use This Plugin?

### Network Engineers
- Manage multiple Hedgehog fabric installations
- Deploy VPCs using standardized templates
- Monitor infrastructure health and status
- Perform bulk operations efficiently

### Operations Teams
- Automate fabric onboarding processes
- Maintain consistency across environments
- Monitor resource utilization and health
- Implement change management workflows

### Developers
- Use REST API for automation and integration
- Build custom workflows and tools
- Integrate with CI/CD pipelines
- Access programmatic fabric management

### IT Managers
- Centralized visibility across all fabrics
- Standardized deployment processes
- Improved operational efficiency
- Reduced manual configuration errors

## 📖 Quick Navigation

### New Users - Operational Features
1. Start with the [Quick Start Guide](QUICK_START.md)
2. Read the [User Guide](USER_GUIDE.md) overview
3. Follow [Common Workflows](WORKFLOWS.md) for your use case

### New Users - Topology Planning (DIET)
1. Start with the [DIET Quick Start](DIET_QUICK_START.md)
2. Learn about auto-calculating switch requirements
3. Export Hedgehog wiring diagrams

### Existing NetBox Users
1. Review [Installation Guide](../README.md#installation)
2. Check [Service Account Setup](SERVICE_ACCOUNT_SETUP.md)
3. Explore [API Reference](API_REFERENCE.md) for automation

### Developers
1. Review [Development Guide](../DEVELOPMENT_GUIDE.md)
2. Check [API Reference](API_REFERENCE.md)
3. See [Code Examples](API_REFERENCE.md#code-examples)

## 🎨 Feature Highlights

### Dashboard & Monitoring
- **Fabric Overview**: Centralized health dashboard
- **Resource Statistics**: Real-time counts and utilization
- **Activity Timeline**: Track changes and operations
- **Health Indicators**: Visual status monitoring

### VPC Management
- **Template Library**: Pre-configured VPC patterns
- **Visual Designer**: Interactive VPC configuration
- **Real-time Deployment**: Immediate Kubernetes deployment
- **Status Tracking**: Monitor deployment progress

### Infrastructure Management
- **Auto-Discovery**: Automatic resource import
- **Topology Visualization**: Interactive network diagrams
- **Connection Management**: Physical and logical connections
- **Switch Configuration**: Role and profile management

### Bulk Operations
- **Multi-Selection**: Checkbox-based selection
- **Progress Tracking**: Real-time operation status
- **Error Handling**: Individual failure management
- **Confirmation Dialogs**: Safety for destructive actions

## 🔧 Technical Requirements

### NetBox Requirements
- NetBox 4.0 or higher
- Python 3.9+
- Django 4.2+
- PostgreSQL database

### Hedgehog Requirements
- Hedgehog Open Network Fabric
- Kubernetes cluster access
- Service account with appropriate permissions
- Network connectivity between NetBox and Kubernetes

### Browser Requirements
- Modern web browser (Chrome, Firefox, Safari, Edge)
- JavaScript enabled
- Responsive design supports mobile devices

## 🚦 Getting Started Checklist

- [ ] NetBox instance with plugin installed
- [ ] Access to Hedgehog Kubernetes cluster
- [ ] Service account configured with permissions
- [ ] Network connectivity verified
- [ ] User account with appropriate NetBox permissions

**Ready to start?** → [Quick Start Guide](QUICK_START.md)

## 📋 Common Use Cases

### Scenario 1: Multi-Environment Management
**Challenge**: Managing separate production, staging, and development fabrics
**Solution**: Use multiple fabric connections with environment-specific configurations

### Scenario 2: Application Deployment
**Challenge**: Consistent VPC deployment across environments
**Solution**: Use VPC templates with standardized configurations

### Scenario 3: Infrastructure Changes
**Challenge**: Tracking physical infrastructure changes
**Solution**: Automatic sync and change detection with notifications

### Scenario 4: Bulk Operations
**Challenge**: Managing hundreds of VPCs and connections
**Solution**: Bulk operations with progress tracking and error handling

### Scenario 5: Compliance and Auditing
**Challenge**: Maintaining audit trails for network changes
**Solution**: Comprehensive logging and change tracking

## 🔍 Documentation Features

### Comprehensive Coverage
- **Complete Feature Documentation**: Every capability covered
- **Step-by-Step Procedures**: Detailed workflows
- **Code Examples**: Multiple programming languages
- **Screenshots and Diagrams**: Visual learning aids

### Multiple Skill Levels
- **Beginner**: Quick start and basic operations
- **Intermediate**: Advanced workflows and bulk operations
- **Expert**: API integration and custom development

### Searchable and Organized
- **Table of Contents**: Easy navigation
- **Cross-References**: Linked related topics
- **Index**: Quick topic lookup
- **Examples**: Practical implementations

## 🤝 Support and Community

### Documentation Updates
This documentation is actively maintained and updated with each plugin release. Check for updates regularly.

### Getting Help
- **User Guide**: Comprehensive troubleshooting section
- **Workflows**: Step-by-step problem resolution
- **API Reference**: Complete technical documentation
- **Community**: Join Hedgehog community discussions

### Contributing
Contributions to documentation are welcome! See the development guide for details on contributing improvements and additions.

---

## 📄 Document Status

| Document | Status | Last Updated | Audience |
|----------|--------|--------------|----------|
| [Quick Start](QUICK_START.md) | ✅ Complete | 2025-06-29 | New Users (Operational) |
| [DIET Quick Start](DIET_QUICK_START.md) | ✅ Complete | 2024-12-21 | Pre-Sales / Design |
| [User Guide](USER_GUIDE.md) | ✅ Complete | 2025-06-29 | All Users |
| [Workflows](WORKFLOWS.md) | ✅ Complete | 2025-06-29 | Operators |
| [API Reference](API_REFERENCE.md) | ✅ Complete | 2025-06-29 | Developers |
| [Service Account Setup](SERVICE_ACCOUNT_SETUP.md) | ✅ Complete | 2025-06-29 | Administrators |

---

**Happy networking with Hedgehog! 🦔**

*For the latest updates and announcements, follow the project repository and community channels.*