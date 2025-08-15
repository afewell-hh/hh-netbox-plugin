#!/bin/bash

# Quick Authentication Test - Single Command Version
# ==================================================
# This provides the exact curl commands for manual testing

set -e

NETBOX_URL="http://localhost:8000"
LOGIN_URL="${NETBOX_URL}/login/"
TARGET_URL="${NETBOX_URL}/plugins/hedgehog/drift-detection/"
COOKIE_JAR="/tmp/netbox_test_cookies.txt"

# Clean up any existing cookies
rm -f "$COOKIE_JAR"

echo "🔐 Getting CSRF token and logging in..."

# Step 1: Get CSRF token
CSRF_TOKEN=$(curl -s -c "$COOKIE_JAR" "$LOGIN_URL" | grep -o 'name="csrfmiddlewaretoken" value="[^"]*"' | cut -d'"' -f4)

if [ -z "$CSRF_TOKEN" ]; then
    echo "❌ Failed to get CSRF token"
    exit 1
fi

echo "✅ CSRF token: ${CSRF_TOKEN:0:20}..."

# Step 2: Login
LOGIN_RESULT=$(curl -s -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
    -X POST \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -H "Referer: $LOGIN_URL" \
    -d "csrfmiddlewaretoken=$CSRF_TOKEN&username=admin&password=admin&next=%2F" \
    -w "HTTP_STATUS:%{http_code}" \
    "$LOGIN_URL")

if echo "$LOGIN_RESULT" | grep -q "HTTP_STATUS:302"; then
    echo "✅ Login successful"
else
    echo "❌ Login failed"
    exit 1
fi

# Step 3: Test the drift detection page
echo "🧪 Testing drift detection page..."
RESPONSE=$(curl -s -b "$COOKIE_JAR" -w "HTTP_STATUS:%{http_code}" "$TARGET_URL")
STATUS=$(echo "$RESPONSE" | grep -o "HTTP_STATUS:[0-9]*" | cut -d: -f2)

echo "📊 Result: HTTP $STATUS"

if [ "$STATUS" = "200" ]; then
    echo "🎉 SUCCESS: Drift detection page is working!"
elif [ "$STATUS" = "500" ]; then
    echo "❌ FAILED: Server error (namespace issue)"
    if echo "$RESPONSE" | grep -q "netbox_hedgehog.*not.*registered"; then
        echo "   Error: 'netbox_hedgehog' namespace not registered"
    fi
else
    echo "❓ Unexpected status: $STATUS"
fi

# Cleanup
rm -f "$COOKIE_JAR"

exit $([ "$STATUS" = "200" ] && echo 0 || echo 1)