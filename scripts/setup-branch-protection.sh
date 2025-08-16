#!/bin/bash

# GitHub Branch Protection Setup Script for HNP Modernization
# This script provides the GitHub CLI commands to set up branch protection rules
# Run this script after ensuring GitHub CLI is installed and authenticated

set -e

REPO="afewell-hh/hh-netbox-plugin"

echo "🔒 Setting up GitHub Branch Protection Rules for HNP Modernization"
echo "Repository: $REPO"
echo ""

# Check if GitHub CLI is available
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is not installed. Please install it first:"
    echo "   https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "❌ GitHub CLI is not authenticated. Please run: gh auth login"
    exit 1
fi

echo "✅ GitHub CLI is available and authenticated"
echo ""

# Function to create branch protection rule
setup_protection() {
    local branch=$1
    local protection_level=$2
    local additional_flags=$3
    
    echo "🛡️  Setting up protection for branch: $branch (Level: $protection_level)"
    
    case $protection_level in
        "maximum")
            # Legacy/stable - maximum protection (read-only)
            gh api repos/$REPO/branches/$branch/protection \
                --method PUT \
                --field required_status_checks='{"strict":true,"contexts":[]}' \
                --field enforce_admins=true \
                --field required_pull_request_reviews='{"required_approving_review_count":2,"dismiss_stale_reviews":true,"require_code_owner_reviews":true}' \
                --field restrictions='{"users":[],"teams":[]}' \
                --field allow_force_pushes=false \
                --field allow_deletions=false
            ;;
        "high")
            # Main branch - high protection
            gh api repos/$REPO/branches/$branch/protection \
                --method PUT \
                --field required_status_checks='{"strict":true,"contexts":["ci/django-tests","ci/integration-tests","ci/security-scan"]}' \
                --field enforce_admins=true \
                --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true,"require_code_owner_reviews":false}' \
                --field restrictions=null \
                --field allow_force_pushes=false \
                --field allow_deletions=false
            ;;
        "medium")
            # Modernization branches - medium protection
            gh api repos/$REPO/branches/$branch/protection \
                --method PUT \
                --field required_status_checks='{"strict":true,"contexts":["ci/component-tests"]}' \
                --field enforce_admins=false \
                --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":false,"require_code_owner_reviews":false}' \
                --field restrictions=null \
                --field allow_force_pushes=true \
                --field allow_deletions=false
            ;;
        "low")
            # Experimental branches - low protection
            gh api repos/$REPO/branches/$branch/protection \
                --method PUT \
                --field required_status_checks='{"strict":false,"contexts":[]}' \
                --field enforce_admins=false \
                --field required_pull_request_reviews='{"required_approving_review_count":0,"dismiss_stale_reviews":false,"require_code_owner_reviews":false}' \
                --field restrictions=null \
                --field allow_force_pushes=true \
                --field allow_deletions=false
            ;;
    esac
    
    echo "   ✅ Protection configured for $branch"
}

# Set up protection for each branch
echo "📋 Configuring branch protection rules..."
echo ""

# Legacy branch - maximum protection (read-only)
setup_protection "legacy/stable" "maximum"

# Main branch - high protection
setup_protection "main" "high"

# Modernization branches - medium protection
setup_protection "modernization/main" "medium"
setup_protection "modernization/k8s-foundation" "medium"
setup_protection "modernization/nextjs-frontend" "medium"
setup_protection "modernization/wasm-modules" "medium"
setup_protection "modernization/integration" "medium"

# Experimental branch - low protection
setup_protection "experimental/main" "low"

echo ""
echo "🎉 Branch protection setup complete!"
echo ""
echo "📊 Summary of protection levels:"
echo "   🔒 legacy/stable        - MAXIMUM (read-only)"
echo "   🛡️  main                - HIGH (strict reviews + CI)"
echo "   🔐 modernization/*      - MEDIUM (flexible development)"
echo "   🔓 experimental/main    - LOW (rapid iteration)"
echo ""
echo "📖 For more details, see: docs/GIT_BRANCH_STRUCTURE.md"

# Additional setup recommendations
echo ""
echo "🔧 Additional Setup Recommendations:"
echo ""
echo "1. Set up CODEOWNERS file:"
echo "   Create .github/CODEOWNERS with appropriate team assignments"
echo ""
echo "2. Configure CI/CD workflows:"
echo "   Ensure .github/workflows/ contains branch-specific pipelines"
echo ""
echo "3. Set up auto-merge policies:"
echo "   Configure dependabot and other automated PRs"
echo ""
echo "4. Monitor branch health:"
echo "   Set up alerts for failed CI/CD runs and stale branches"

echo ""
echo "✨ Run this script when ready to apply protection rules!"