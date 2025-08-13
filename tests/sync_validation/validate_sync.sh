#!/bin/bash
"""
Quick Sync Validation Script
Simple shell script to run sync validation tests
"""

set -e

# Configuration
FABRIC_ID=${1:-35}
BASE_URL=${2:-"http://localhost:8000"}
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🧪 Sync Validation Test Suite"
echo "=============================="
echo "Fabric ID: $FABRIC_ID"
echo "Base URL: $BASE_URL"
echo "Test Directory: $TEST_DIR"
echo ""

# Check if NetBox is running
echo "🔍 Checking NetBox availability..."
if curl -s --max-time 5 "$BASE_URL" > /dev/null; then
    echo "✅ NetBox is responding"
else
    echo "❌ NetBox is not responding at $BASE_URL"
    echo "Please ensure NetBox is running and accessible"
    exit 1
fi

# Check if fabric exists
echo "🔍 Checking fabric $FABRIC_ID..."
fabric_url="$BASE_URL/plugins/hedgehog/fabrics/$FABRIC_ID/"
if curl -s --max-time 5 "$fabric_url" | grep -q "fabric\|Fabric"; then
    echo "✅ Fabric $FABRIC_ID appears to exist"
else
    echo "⚠️  Fabric $FABRIC_ID may not exist or is not accessible"
fi

echo ""
echo "🚀 Starting validation tests..."
echo "=============================="

# Run the comprehensive test runner
cd "$TEST_DIR"
python3 run_sync_validation.py --fabric-id "$FABRIC_ID" --base-url "$BASE_URL"

echo ""
echo "✅ Validation complete. Check the generated report files for detailed results."