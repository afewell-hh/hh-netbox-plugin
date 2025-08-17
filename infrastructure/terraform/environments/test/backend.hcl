# Test environment backend configuration
bucket         = "hnp-modernization-terraform-state-test"
key            = "test/terraform.tfstate"
region         = "us-west-2"
encrypt        = true
dynamodb_table = "hnp-modernization-terraform-lock-test"

# Workspace isolation
workspace_key_prefix = "env"