# HNP Modernization - Development Environment
environment = "dev"
aws_region  = "us-west-2"

# VPC Configuration
vpc_cidr = "10.0.0.0/16"

# EKS Configuration
kubernetes_version = "1.28"

node_groups = {
  general = {
    instance_types = ["t3.medium"]
    min_size      = 1
    max_size      = 5
    desired_size  = 2
    disk_size     = 50
    capacity_type = "ON_DEMAND"
    labels = {
      role        = "general"
      environment = "dev"
    }
    taints = []
  }
  
  system = {
    instance_types = ["t3.small"]
    min_size      = 1
    max_size      = 3
    desired_size  = 1
    disk_size     = 30
    capacity_type = "SPOT"
    labels = {
      role        = "system"
      environment = "dev"
    }
    taints = [
      {
        key    = "CriticalAddonsOnly"
        value  = "true"
        effect = "NO_SCHEDULE"
      }
    ]
  }
}

# Feature flags for development
enable_irsa                        = true
enable_cluster_autoscaler          = true
enable_aws_load_balancer_controller = true
enable_ebs_csi_driver             = true
enable_efs_csi_driver             = true
enable_cert_manager               = true

# Domain configuration (optional for dev)
domain_name = "dev.hnp-modernization.local"

# Backup configuration
backup_retention_days = 7