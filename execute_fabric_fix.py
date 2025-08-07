#!/usr/bin/env python3
"""
HIVE MIND FABRIC FIX EXECUTOR

Execute the fabric configuration fix by running the Django management command
with the GitHub token from .env file.

This resolves the root cause identified in GitHub Issue #6.
"""

import subprocess
import sys
import os

def main():
    print("🎯 HIVE MIND: Executing Fabric Configuration Fix")
    print("=" * 50)
    
    # Load environment variables from .env file
    env_file = '.env'
    env_vars = os.environ.copy()
    
    try:
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        # Remove quotes if present
                        value = value.strip('"\'')
                        env_vars[key] = value
        
        github_token = env_vars.get('GITHUB_TOKEN')
        if not github_token:
            print("❌ ERROR: GITHUB_TOKEN not found in .env file")
            return 1
            
        print(f"✅ Loaded GitHub token from .env (length: {len(github_token)} chars)")
        
        # Execute the Django management command
        cmd = [
            'python3', 'manage.py', 'fix_fabric_gitrepository', 
            '--fabric-id', '35',
            '--github-token', github_token
        ]
        
        print(f"🚀 Executing: {' '.join(cmd[:-2])} --github-token [HIDDEN]")
        
        result = subprocess.run(cmd, env=env_vars, capture_output=True, text=True)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
            
        if result.returncode == 0:
            print("\n✅ Command executed successfully")
            return 0
        else:
            print(f"\n❌ Command failed with return code: {result.returncode}")
            return 1
            
    except FileNotFoundError:
        print(f"❌ ERROR: .env file not found")
        return 1
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())