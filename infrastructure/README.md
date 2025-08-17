# HNP Modernization Infrastructure

This directory contains the infrastructure-as-code foundation for the HNP (Hedgehog NetBox Plugin) modernization project. The infrastructure is designed to support a complete modern DevOps workflow with GitOps, observability, and multi-environment deployment capabilities.

## Architecture Overview

The infrastructure consists of four main components:

1. **Terraform** - Infrastructure provisioning and management
2. **Kubernetes** - Container orchestration and base configuration
3. **GitOps** - Application deployment and lifecycle management with ArgoCD
4. **Observability** - Monitoring, logging, and tracing stack

## Directory Structure

```
infrastructure/
├── terraform/                 # Infrastructure provisioning
│   ├── environments/          # Environment-specific configurations
│   │   ├── dev/
│   │   ├── test/
│   │   ├── staging/
│   │   └── prod/
│   ├── modules/               # Reusable Terraform modules
│   │   ├── networking/        # VPC, subnets, security groups
│   │   ├── compute/           # EKS cluster and node groups
│   │   ├── storage/           # EBS, EFS, storage classes
│   │   └── security/          # IAM roles and policies
│   └── state-management/      # Remote state configuration
├── kubernetes/                # Base Kubernetes configuration
│   ├── base/                  # Core resources (namespaces)
│   ├── overlays/              # Environment-specific overlays
│   ├── rbac/                  # Role-based access control
│   ├── network-policies/      # Network security policies
│   └── storage/               # Storage classes and PVs
├── gitops/                    # GitOps configuration
│   ├── argocd/                # ArgoCD installation and config
│   ├── applications/          # Application definitions
│   ├── repositories/          # Repository configurations
│   └── monitoring/            # GitOps monitoring
└── observability/             # Observability stack
    ├── prometheus/            # Prometheus monitoring
    ├── grafana/               # Grafana dashboards
    ├── jaeger/                # Distributed tracing
    └── logging/               # Elasticsearch, Logstash, Kibana
```

## Quick Start

### Prerequisites

Ensure you have the following tools installed:

- [Terraform](https://www.terraform.io/downloads.html) >= 1.5
- [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/)
- [Helm](https://helm.sh/docs/intro/install/) >= 3.x
- [AWS CLI](https://aws.amazon.com/cli/) configured with appropriate credentials

### Environment Setup

1. **Configure AWS credentials:**
   ```bash
   aws configure
   # or use environment variables
   export AWS_ACCESS_KEY_ID=your-access-key
   export AWS_SECRET_ACCESS_KEY=your-secret-key
   export AWS_DEFAULT_REGION=us-west-2
   ```

2. **Set environment variables:**
   ```bash
   export ENVIRONMENT=dev  # or test, staging, prod
   export AWS_REGION=us-west-2
   export PROJECT_NAME=hnp-modernization
   ```

### Deployment

#### Option 1: Automated Deployment (Recommended)

Run the deployment script for complete infrastructure setup:

```bash
cd infrastructure
chmod +x scripts/deploy.sh
./scripts/deploy.sh dev
```

#### Option 2: Manual Deployment

1. **Deploy Terraform infrastructure:**
   ```bash
   cd terraform
   terraform init -backend-config="environments/dev/backend.hcl"
   terraform plan -var-file="environments/dev/terraform.tfvars"
   terraform apply
   ```

2. **Configure kubectl:**
   ```bash
   aws eks update-kubeconfig --region us-west-2 --name hnp-modernization-dev
   ```

3. **Deploy Kubernetes base configuration:**
   ```bash
   kubectl apply -f kubernetes/base/
   kubectl apply -f kubernetes/rbac/
   kubectl apply -f kubernetes/network-policies/
   kubectl apply -f kubernetes/storage/
   ```

4. **Install ArgoCD:**
   ```bash
   kubectl create namespace argocd
   kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
   kubectl apply -f gitops/argocd/
   ```

5. **Deploy observability stack:**
   ```bash
   helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
   helm repo add grafana https://grafana.github.io/helm-charts
   helm repo update
   
   helm install prometheus prometheus-community/kube-prometheus-stack \
     --namespace observability --create-namespace \
     --values observability/prometheus/values.yaml
   ```

### Validation

Validate the deployment using the validation script:

```bash
chmod +x scripts/validate.sh
./scripts/validate.sh dev
```

## Infrastructure Components

### Terraform Modules

#### Networking Module
- Creates VPC with public/private/database subnets
- Configures NAT gateways and internet gateway
- Sets up route tables and VPC flow logs
- Implements proper subnet tagging for EKS

#### Compute Module
- Provisions EKS cluster with multiple node groups
- Configures OIDC provider for IRSA
- Sets up cluster security groups and IAM roles
- Enables cluster logging and encryption

#### Storage Module
- Creates EFS file system for shared storage
- Configures EBS CSI driver IAM roles
- Sets up storage classes for different use cases

#### Security Module
- Creates IAM roles for different access levels
- Configures service account roles for AWS services
- Sets up cluster autoscaler and load balancer controller roles

### Kubernetes Configuration

#### RBAC (Role-Based Access Control)
- **hnp-admin**: Full cluster administration rights
- **hnp-developer**: Development namespace access
- **hnp-readonly**: Read-only access across namespaces
- **hnp-monitoring**: Metrics collection access

#### Network Policies
- Default deny-all policy for security
- Namespace isolation rules
- Monitoring and DNS exceptions
- Inter-service communication rules

#### Storage Classes
- **gp3**: Default general-purpose SSD storage
- **gp3-retain**: Persistent storage with retain policy
- **efs-sc**: Shared file system storage
- **io2**: High-performance storage for databases

### GitOps with ArgoCD

#### Features
- App-of-apps pattern for managing multiple applications
- Multi-environment support (dev/test/staging/prod)
- Automatic synchronization and self-healing
- RBAC integration with cluster authentication

#### Application Management
- Declarative application definitions
- Git-based configuration management
- Rollback and deployment history
- Health monitoring and alerting

### Observability Stack

#### Prometheus
- Cluster and application metrics collection
- Custom alerting rules and policies
- Long-term metric storage
- Service discovery automation

#### Grafana
- Pre-configured dashboards for:
  - Kubernetes cluster monitoring
  - Application performance metrics
  - Infrastructure resource utilization
  - Custom business metrics

#### Jaeger
- Distributed tracing for microservices
- Performance analysis and debugging
- Request flow visualization
- Integration with application instrumentation

#### Elasticsearch/Kibana
- Centralized log aggregation
- Log analysis and searching
- Custom dashboards and visualizations
- Alert management

## Environment Management

### Development Environment
- Minimal resource allocation
- Spot instances for cost optimization
- Development-friendly policies
- Shared storage for collaboration

### Test Environment
- Production-like configuration
- Automated testing integration
- Performance testing capabilities
- Quality gate enforcement

### Staging Environment
- Production mirror for final validation
- Load testing and stress testing
- Security scanning and compliance
- User acceptance testing

### Production Environment
- High availability and redundancy
- Auto-scaling and load balancing
- Comprehensive monitoring and alerting
- Disaster recovery capabilities

## Security Considerations

### Network Security
- Private subnets for worker nodes
- Network policies for pod-to-pod communication
- Security groups and NACLs
- VPC flow logs for audit

### Identity and Access Management
- IAM roles for service accounts (IRSA)
- Least privilege access principles
- Multi-factor authentication
- Regular access review and rotation

### Data Protection
- Encryption at rest and in transit
- Secrets management with AWS Secrets Manager
- Backup and recovery procedures
- Compliance monitoring

## Monitoring and Alerting

### Key Metrics
- Cluster health and resource utilization
- Application performance and availability
- Infrastructure costs and optimization
- Security events and compliance

### Alert Channels
- Slack/Teams integration
- Email notifications
- PagerDuty for critical alerts
- Webhook integration for custom actions

## Troubleshooting

### Common Issues

1. **EKS Cluster Access Denied**
   ```bash
   aws eks update-kubeconfig --region us-west-2 --name hnp-modernization-dev
   kubectl get nodes
   ```

2. **ArgoCD UI Access**
   ```bash
   kubectl port-forward svc/argocd-server -n argocd 8080:443
   # Access at https://localhost:8080
   ```

3. **Storage Issues**
   ```bash
   kubectl get storageclass
   kubectl get pv,pvc --all-namespaces
   ```

4. **Network Policy Issues**
   ```bash
   kubectl get networkpolicy --all-namespaces
   kubectl describe networkpolicy -n hnp-modernization
   ```

### Log Analysis
- Check ArgoCD logs: `kubectl logs -n argocd deployment/argocd-server`
- Check controller logs: `kubectl logs -n kube-system deployment/aws-load-balancer-controller`
- Check node logs: `kubectl logs -n kube-system daemonset/aws-node`

## Maintenance

### Regular Tasks
- Update Kubernetes versions
- Patch security vulnerabilities
- Optimize resource allocation
- Review and rotate credentials

### Backup Procedures
- Terraform state backup
- Kubernetes resource backup with Velero
- Application data backup
- Configuration backup to Git

## Cost Optimization

### Strategies
- Use spot instances for non-critical workloads
- Implement cluster autoscaling
- Monitor and optimize resource requests/limits
- Regular rightsizing analysis

### Cost Monitoring
- AWS Cost Explorer integration
- Kubernetes resource utilization monitoring
- Application-level cost allocation
- Regular cost review and optimization

## Support and Documentation

### Additional Resources
- [EKS Best Practices Guide](https://aws.github.io/aws-eks-best-practices/)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [Prometheus Operator Guide](https://prometheus-operator.dev/)
- [Terraform AWS Provider](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)

### Getting Help
- Check logs and events for error details
- Review validation script output
- Consult AWS EKS documentation
- Contact platform team for escalation

---

This infrastructure foundation provides a robust, scalable, and maintainable platform for the HNP modernization project. It follows cloud-native best practices and provides the necessary observability and automation for efficient operations.