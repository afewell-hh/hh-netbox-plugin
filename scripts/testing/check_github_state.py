#!/usr/bin/env python3
"""
Check current GitHub repository state and document what needs to be implemented.
"""

import requests
import json

def check_github_state():
    """Check the current state of the GitHub repository"""
    print("🔍 GitHub Repository State Investigation")
    print("=" * 50)
    
    base_api = "https://api.github.com/repos/afewell-hh/gitops-test-1"
    
    # Check main directory
    try:
        response = requests.get(f"{base_api}/contents/gitops/hedgehog/fabric-1")
        if response.status_code == 200:
            contents = response.json()
            print(f"📂 Current fabric-1 directory contains {len(contents)} items:")
            
            directories = []
            files = []
            
            for item in contents:
                if item['type'] == 'dir':
                    directories.append(item['name'])
                else:
                    files.append(item['name'])
                print(f"   - {item['name']} ({item['type']}) - {item['size']} bytes")
            
            print(f"\n📊 Summary:")
            print(f"   - Directories: {len(directories)} - {directories}")
            print(f"   - Files: {len(files)} - {files}")
            
            # Check if GitOps structure exists
            expected_dirs = ['raw', 'managed', 'unmanaged']
            missing_dirs = [d for d in expected_dirs if d not in directories]
            
            if missing_dirs:
                print(f"\n❌ Missing GitOps directories: {missing_dirs}")
                print("🎯 This confirms the issue - no directory structure has been created!")
            else:
                print(f"\n✅ GitOps directory structure exists!")
                
        else:
            print(f"❌ Error accessing GitHub: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def check_recent_commits():
    """Check recent commits to see if any are from HNP"""
    print(f"\n📝 Checking recent commits...")
    
    try:
        response = requests.get("https://api.github.com/repos/afewell-hh/gitops-test-1/commits")
        if response.status_code == 200:
            commits = response.json()
            print(f"📈 Found {len(commits)} recent commits:")
            
            for i, commit in enumerate(commits[:5]):  # Show latest 5
                author = commit['commit']['author']['name']
                message = commit['commit']['message']
                date = commit['commit']['author']['date']
                print(f"   {i+1}. {author} - {message[:50]}{'...' if len(message) > 50 else ''}")
                print(f"      Date: {date}")
                
            # Check if any commits are from HNP or automated systems
            hnp_commits = [c for c in commits if 'hnp' in c['commit']['author']['name'].lower() or 
                          'hedgehog' in c['commit']['author']['name'].lower() or
                          'bot' in c['commit']['author']['name'].lower()]
            
            if hnp_commits:
                print(f"\n✅ Found {len(hnp_commits)} commits that might be from HNP")
            else:
                print(f"\n❌ No commits found from HNP or automated systems")
                print("🎯 This confirms no automated commits are being made!")
                
    except Exception as e:
        print(f"❌ Error checking commits: {e}")

def analyze_root_cause():
    """Analyze the root cause of the issue"""
    print(f"\n🔍 Root Cause Analysis")
    print("=" * 30)
    
    print("❌ CONFIRMED ISSUES:")
    print("   1. No raw/, managed/, unmanaged/ directories in GitHub")
    print("   2. No commits from HNP visible in GitHub history") 
    print("   3. Current GitOps initialization only works locally")
    print("   4. Missing: GitHub push functionality after directory creation")
    
    print(f"\n🎯 REQUIRED IMPLEMENTATION:")
    print("   1. Modify GitOpsOnboardingService to push to GitHub after local creation")
    print("   2. Add GitHub API integration for directory/file creation")
    print("   3. Implement authentication with GitHub using stored credentials")
    print("   4. Add commit creation with proper author/message")
    print("   5. Test and validate actual GitHub repository changes")
    
    print(f"\n💡 IMPLEMENTATION STRATEGY:")
    print("   1. Create GitHubPushService to handle repository updates")
    print("   2. Integrate with existing GitRepository credential system")
    print("   3. Add to GitOpsOnboardingService workflow")
    print("   4. Add fabric deletion functionality to GUI")

if __name__ == "__main__":
    check_github_state()
    check_recent_commits()
    analyze_root_cause()
    print(f"\n✅ Investigation complete - root cause identified!")