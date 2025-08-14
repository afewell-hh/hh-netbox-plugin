#!/usr/bin/env python3
"""
Environment Variable Loader Utility

This utility provides a standardized way to load environment variables
from .env files for all NetBox Hedgehog plugin agents and scripts.
"""

import os
from pathlib import Path
from typing import Dict, Optional


def load_env_file(env_path: str = ".env", verbose: bool = True) -> Dict[str, str]:
    """
    Load environment variables from .env file.
    
    Args:
        env_path: Path to the .env file
        verbose: Whether to print loading status
        
    Returns:
        Dictionary of loaded environment variables
    """
    loaded_vars = {}
    env_file = Path(env_path)
    
    if not env_file.exists():
        if verbose:
            print(f"⚠️ Environment file {env_path} not found")
        return loaded_vars
    
    try:
        with open(env_file, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Parse key=value pairs
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    # Set environment variable
                    os.environ[key] = value
                    loaded_vars[key] = value
                else:
                    if verbose:
                        print(f"⚠️ Skipping invalid line {line_num}: {line}")
        
        if verbose:
            print(f"✅ Loaded {len(loaded_vars)} environment variables from {env_path}")
            
    except Exception as e:
        if verbose:
            print(f"❌ Error loading environment file {env_path}: {e}")
    
    return loaded_vars


def verify_required_vars(required_vars: list, env_path: str = ".env") -> bool:
    """
    Verify that required environment variables are loaded.
    
    Args:
        required_vars: List of required environment variable names
        env_path: Path to the .env file
        
    Returns:
        True if all required variables are present, False otherwise
    """
    # Load environment first
    load_env_file(env_path, verbose=False)
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print(f"💡 Please check your {env_path} file")
        return False
    
    print(f"✅ All required environment variables are present")
    return True


def get_netbox_config() -> Dict[str, str]:
    """Get NetBox configuration from environment variables."""
    return {
        'url': os.getenv('NETBOX_URL', 'http://localhost:8000'),
        'token': os.getenv('NETBOX_TOKEN', ''),
        'username': os.getenv('NETBOX_USERNAME', 'admin'),
        'password': os.getenv('NETBOX_PASSWORD', 'admin'),
        'test_url': os.getenv('TEST_NETBOX_URL', ''),
        'test_token': os.getenv('TEST_NETBOX_TOKEN', ''),
        'verify_ssl': os.getenv('NETBOX_VERIFY_SSL', 'false') == 'true'
    }


def get_k8s_config() -> Dict[str, str]:
    """Get Kubernetes configuration from environment variables."""
    return {
        'cluster_name': os.getenv('K8S_TEST_CLUSTER_NAME', 'test-cluster'),
        'config_path': os.getenv('K8S_TEST_CONFIG_PATH', '~/.kube/config'),
        'context': os.getenv('K8S_TEST_CONTEXT', ''),
        'namespace': os.getenv('K8S_TEST_NAMESPACE', 'default'),
        'api_server': os.getenv('K8S_TEST_API_SERVER', ''),
        'service_account': os.getenv('K8S_SERVICE_ACCOUNT', 'hedgehog-test-sa'),
        'token': os.getenv('K8S_SERVICE_ACCOUNT_TOKEN', '')
    }


def get_gitops_config() -> Dict[str, str]:
    """Get GitOps configuration from environment variables."""
    return {
        'repo_url': os.getenv('GITOPS_REPO_URL', ''),
        'branch': os.getenv('GITOPS_REPO_BRANCH', 'main'),
        'local_path': os.getenv('GITOPS_REPO_PATH', './test-fgd-local'),
        'auth_token': os.getenv('GITOPS_AUTH_TOKEN', ''),
        'ssh_key_path': os.getenv('GITOPS_SSH_KEY_PATH', '~/.ssh/id_rsa_gitops'),
        'sync_interval': os.getenv('GITOPS_SYNC_INTERVAL', '60'),
        'conflict_resolution': os.getenv('GITOPS_CONFLICT_RESOLUTION', 'manual'),
        'auto_push': os.getenv('GITOPS_AUTO_PUSH', 'true') == 'true'
    }


def get_testing_config() -> Dict[str, any]:
    """Get testing configuration from environment variables."""
    return {
        'prefer_real_infrastructure': os.getenv('PREFER_REAL_INFRASTRUCTURE', 'true') == 'true',
        'mock_fallback_enabled': os.getenv('MOCK_FALLBACK_ENABLED', 'false') == 'true',
        'timeout_seconds': int(os.getenv('TEST_TIMEOUT_SECONDS', '300')),
        'cleanup_enabled': os.getenv('TEST_CLEANUP_ENABLED', 'true') == 'true',
        'fabric_prefix': os.getenv('TEST_FABRIC_PREFIX', 'test-fabric'),
        'vpc_prefix': os.getenv('TEST_VPC_PREFIX', 'test-vpc')
    }


# NETBOX HEDGEHOG REQUIRED ENVIRONMENT VARIABLES
REQUIRED_VARS = [
    'NETBOX_URL',
    'K8S_TEST_CLUSTER_NAME',
    'GITOPS_REPO_URL',
    'PREFER_REAL_INFRASTRUCTURE'
]

OPTIONAL_VARS = [
    'NETBOX_TOKEN',
    'TEST_NETBOX_TOKEN',
    'K8S_TEST_CONFIG_PATH',
    'GITOPS_AUTH_TOKEN',
    'DOCKER_COMPOSE_DIR',
    'ENHANCED_HIVE_ENABLED'
]


def main():
    """Main entry point for environment loading verification."""
    print("🔧 NetBox Hedgehog Environment Variable Loader")
    print("=" * 50)
    
    # Load environment variables
    loaded_vars = load_env_file()
    
    if not loaded_vars:
        print("❌ No environment variables loaded")
        return 1
    
    # Verify required variables
    if not verify_required_vars(REQUIRED_VARS):
        print("\n💡 Create a .env file with the required variables:")
        print("cp docs/claude-optimization-research/enhanced-env-template.env .env")
        return 1
    
    # Display loaded configuration
    print("\n📋 Current Configuration:")
    print("-" * 30)
    
    netbox_config = get_netbox_config()
    print(f"NetBox URL: {netbox_config['url']}")
    print(f"NetBox Token: {'✅ Set' if netbox_config['token'] else '❌ Missing'}")
    
    k8s_config = get_k8s_config()
    print(f"K8s Cluster: {k8s_config['cluster_name']}")
    print(f"K8s Config: {k8s_config['config_path']}")
    
    gitops_config = get_gitops_config()
    print(f"GitOps Repo: {gitops_config['repo_url']}")
    print(f"GitOps Branch: {gitops_config['branch']}")
    
    testing_config = get_testing_config()
    print(f"Real Infrastructure: {'✅ Enabled' if testing_config['prefer_real_infrastructure'] else '❌ Disabled'}")
    
    print("\n✅ Environment configuration ready!")
    return 0


if __name__ == "__main__":
    exit(main())