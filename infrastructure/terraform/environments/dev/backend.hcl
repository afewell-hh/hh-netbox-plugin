# Development environment backend configuration
bucket         = "hnp-modernization-terraform-state-dev"
key            = "dev/terraform.tfstate"
region         = "us-west-2"
encrypt        = true
dynamodb_table = "hnp-modernization-terraform-lock-dev"

# Workspace isolation
workspace_key_prefix = "env"