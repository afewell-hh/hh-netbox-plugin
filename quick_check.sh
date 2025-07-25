#!/bin/bash
#
# Quick Check Script for Hedgehog Demo Validation
#
# This script can be used as a pre-commit hook or for quick validation
# during development. It runs essential tests only for fast feedback.
#
# Usage:
#   ./quick_check.sh                    # Run quick validation
#   ./quick_check.sh --verbose          # Run with detailed output
#   ./quick_check.sh --help             # Show help
#
# Exit codes:
#   0: Tests passed - safe to proceed
#   1: Tests failed - do not proceed
#   2: Environment issues - check setup
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}"
DEMO_TEST_SCRIPT="${PROJECT_ROOT}/run_demo_tests.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to show help
show_help() {
    cat << EOF
Quick Check Script for Hedgehog Demo Validation

Usage: $0 [options]

Options:
    --verbose, -v     Show detailed test output
    --help, -h        Show this help message
    --env-only        Only check environment, don't run tests
    --restart         Restart environment before testing

Examples:
    $0                # Quick validation (recommended)
    $0 --verbose      # Detailed output for debugging
    $0 --env-only     # Just check if environment is ready
    
Exit Codes:
    0: All tests passed - SAFE to proceed
    1: Tests failed - DO NOT proceed  
    2: Environment issues - check setup

This script is designed for:
- Pre-commit hooks
- Quick development feedback
- CI/CD pipeline validation
- Agent workflow integration
EOF
}

# Parse command line arguments
VERBOSE=""
ENV_ONLY=""
RESTART=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose|-v)
            VERBOSE="--verbose"
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        --env-only)
            ENV_ONLY="true"
            shift
            ;;
        --restart)
            RESTART="--restart"
            shift
            ;;
        *)
            print_status $RED "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Header
print_status $BLUE "⚡ HEDGEHOG QUICK CHECK"
print_status $BLUE "========================"
print_status $BLUE "🕐 Started: $(date '+%Y-%m-%d %H:%M:%S')"
echo

# Check if we're in the right directory
if [[ ! -f "$DEMO_TEST_SCRIPT" ]]; then
    print_status $RED "❌ Error: Could not find demo test script at $DEMO_TEST_SCRIPT"
    print_status $YELLOW "💡 Make sure you're running this from the project root directory"
    exit 2
fi

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    print_status $RED "❌ Error: python3 is not available"
    print_status $YELLOW "💡 Please install Python 3 to run demo tests"
    exit 2
fi

# Environment-only check if requested
if [[ -n "$ENV_ONLY" ]]; then
    print_status $YELLOW "🔍 Environment check only..."
    if python3 "$DEMO_TEST_SCRIPT" --check-env; then
        print_status $GREEN "✅ Environment is ready!"
        exit 0
    else
        print_status $RED "❌ Environment issues detected"
        exit 2
    fi
fi

# Restart environment if requested
if [[ -n "$RESTART" ]]; then
    print_status $YELLOW "🔄 Restarting environment..."
    if python3 "$DEMO_TEST_SCRIPT" --restart; then
        print_status $GREEN "✅ Environment restarted"
    else
        print_status $RED "❌ Environment restart failed"
        exit 2
    fi
    echo
fi

# Run quick validation
print_status $YELLOW "⚡ Running quick demo validation..."
echo

# Build command
CMD="python3 \"$DEMO_TEST_SCRIPT\" --quick"
if [[ -n "$VERBOSE" ]]; then
    CMD="$CMD $VERBOSE"
fi

# Execute the tests
if eval $CMD; then
    echo
    print_status $GREEN "🎉 QUICK CHECK: ✅ PASSED"
    print_status $GREEN "🚀 AGENT INSTRUCTION: SAFE to proceed"
    print_status $GREEN "✨ Essential demo workflows validated"
    
    # Show completion time
    print_status $BLUE "🏁 Completed: $(date '+%Y-%m-%d %H:%M:%S')"
    
    exit 0
else
    EXIT_CODE=$?
    echo
    if [[ $EXIT_CODE -eq 2 ]]; then
        print_status $RED "🔧 QUICK CHECK: ❌ ENVIRONMENT ISSUES"
        print_status $RED "🛑 AGENT INSTRUCTION: Fix environment setup"
        print_status $YELLOW "💡 Try: $0 --restart"
    else
        print_status $RED "🚨 QUICK CHECK: ❌ TESTS FAILED"
        print_status $RED "🛑 AGENT INSTRUCTION: DO NOT proceed"
        print_status $YELLOW "💡 Try: $0 --verbose (for details)"
    fi
    
    print_status $BLUE "🏁 Completed: $(date '+%Y-%m-%d %H:%M:%S')"
    
    exit $EXIT_CODE
fi