# HNP Modernization - Test Environment
environment = "test"
aws_region  = "us-west-2"

# VPC Configuration
vpc_cidr = "10.1.0.0/16"

# EKS Configuration
kubernetes_version = "1.28"

node_groups = {
  general = {
    instance_types = ["t3.medium"]
    min_size      = 2
    max_size      = 8
    desired_size  = 3
    disk_size     = 50
    capacity_type = "ON_DEMAND"
    labels = {
      role        = "general"
      environment = "test"
    }
    taints = []
  }
  
  compute = {
    instance_types = ["c5.large"]
    min_size      = 0
    max_size      = 5
    desired_size  = 1
    disk_size     = 100
    capacity_type = "SPOT"
    labels = {
      role        = "compute"
      environment = "test"
    }
    taints = [
      {
        key    = "dedicated"
        value  = "compute"
        effect = "NO_SCHEDULE"
      }
    ]
  }
}

# Feature flags for testing
enable_irsa                        = true
enable_cluster_autoscaler          = true
enable_aws_load_balancer_controller = true
enable_ebs_csi_driver             = true
enable_efs_csi_driver             = true
enable_cert_manager               = true

# Domain configuration
domain_name = "test.hnp-modernization.local"

# Backup configuration
backup_retention_days = 14