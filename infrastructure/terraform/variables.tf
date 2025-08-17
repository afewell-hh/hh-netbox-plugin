# HNP Modernization Variables
# Common variables across all environments

variable "project_name" {
  description = "Name of the HNP modernization project"
  type        = string
  default     = "hnp-modernization"
}

variable "environment" {
  description = "Environment name (dev, test, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region for infrastructure deployment"
  type        = string
  default     = "us-west-2"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "kubernetes_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
  default     = "1.28"
}

variable "node_groups" {
  description = "EKS node group configurations"
  type = map(object({
    instance_types = list(string)
    min_size      = number
    max_size      = number
    desired_size  = number
    disk_size     = number
    capacity_type = string
    labels        = map(string)
    taints = list(object({
      key    = string
      value  = string
      effect = string
    }))
  }))
  default = {
    general = {
      instance_types = ["t3.medium"]
      min_size      = 1
      max_size      = 10
      desired_size  = 3
      disk_size     = 50
      capacity_type = "ON_DEMAND"
      labels = {
        role = "general"
      }
      taints = []
    }
  }
}

variable "git_repository" {
  description = "Git repository URL for this project"
  type        = string
  default     = "https://github.com/your-org/hnp-modernization"
}

variable "enable_irsa" {
  description = "Enable IAM Roles for Service Accounts"
  type        = bool
  default     = true
}

variable "enable_cluster_autoscaler" {
  description = "Enable cluster autoscaler"
  type        = bool
  default     = true
}

variable "enable_aws_load_balancer_controller" {
  description = "Enable AWS Load Balancer Controller"
  type        = bool
  default     = true
}

variable "enable_ebs_csi_driver" {
  description = "Enable EBS CSI driver"
  type        = bool
  default     = true
}

variable "enable_efs_csi_driver" {
  description = "Enable EFS CSI driver"
  type        = bool
  default     = true
}

variable "observability_namespace" {
  description = "Kubernetes namespace for observability stack"
  type        = string
  default     = "observability"
}

variable "gitops_namespace" {
  description = "Kubernetes namespace for GitOps tools"
  type        = string
  default     = "argocd"
}

variable "domain_name" {
  description = "Domain name for applications"
  type        = string
  default     = ""
}

variable "enable_cert_manager" {
  description = "Enable cert-manager for TLS certificates"
  type        = bool
  default     = true
}

variable "backup_retention_days" {
  description = "Backup retention period in days"
  type        = number
  default     = 30
}