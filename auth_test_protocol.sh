#!/bin/bash

# NetBox Hedgehog Plugin - Authentication Testing Protocol
# =======================================================
# This script creates a bulletproof testing protocol that reproduces
# the exact user experience with the drift detection page.

set -e  # Exit on any error

# Configuration
NETBOX_URL="http://localhost:8000"
LOGIN_URL="${NETBOX_URL}/login/"
TARGET_URL="${NETBOX_URL}/plugins/hedgehog/drift-detection/"
USERNAME="admin"
PASSWORD="admin"
COOKIE_JAR="/tmp/netbox_cookies.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Cleanup function
cleanup() {
    rm -f "$COOKIE_JAR"
}
trap cleanup EXIT

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}NetBox Hedgehog Authentication Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo

# Step 1: Verify NetBox is running
echo -e "${YELLOW}Step 1: Checking NetBox availability...${NC}"
NETBOX_CHECK=$(curl -s -I "$NETBOX_URL" | head -n 1)
if echo "$NETBOX_CHECK" | grep -q "200 OK\|302 Found"; then
    echo -e "${GREEN}✓ NetBox is running at $NETBOX_URL${NC}"
else
    echo -e "${RED}✗ NetBox is not accessible. Is the container running?${NC}"
    echo "Response: $NETBOX_CHECK"
    echo "Try: make deploy-dev"
    exit 1
fi
echo

# Step 2: Get login page and extract CSRF token
echo -e "${YELLOW}Step 2: Extracting CSRF token from login page...${NC}"
LOGIN_PAGE=$(curl -s -c "$COOKIE_JAR" "$LOGIN_URL")

# Try multiple CSRF token extraction patterns
CSRF_TOKEN=$(echo "$LOGIN_PAGE" | grep -o "name='csrfmiddlewaretoken' value='[^']*'" | cut -d"'" -f4)
if [ -z "$CSRF_TOKEN" ]; then
    CSRF_TOKEN=$(echo "$LOGIN_PAGE" | grep -o 'name="csrfmiddlewaretoken" value="[^"]*"' | cut -d'"' -f4)
fi
if [ -z "$CSRF_TOKEN" ]; then
    CSRF_TOKEN=$(echo "$LOGIN_PAGE" | grep -o "csrfmiddlewaretoken.*value.*['\"][^'\"]*['\"]" | sed -n "s/.*value=['\"]\\([^'\"]*\\)['\"].*/\\1/p")
fi

if [ -z "$CSRF_TOKEN" ]; then
    echo -e "${RED}✗ Failed to extract CSRF token${NC}"
    echo "Login page response (first 20 lines):"
    echo "$LOGIN_PAGE" | head -n 20
    echo
    echo "Searching for CSRF patterns:"
    echo "$LOGIN_PAGE" | grep -i csrf || echo "No CSRF token found"
    exit 1
fi

echo -e "${GREEN}✓ CSRF token extracted: ${CSRF_TOKEN:0:20}...${NC}"
echo

# Step 3: Authenticate with Django login
echo -e "${YELLOW}Step 3: Authenticating with credentials...${NC}"
LOGIN_RESPONSE=$(curl -s -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
    -X POST \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -H "Referer: $LOGIN_URL" \
    -d "csrfmiddlewaretoken=$CSRF_TOKEN&username=$USERNAME&password=$PASSWORD&next=%2F" \
    -w "HTTP_STATUS:%{http_code}" \
    "$LOGIN_URL")

HTTP_STATUS=$(echo "$LOGIN_RESPONSE" | grep -o "HTTP_STATUS:[0-9]*" | cut -d: -f2)

if [ "$HTTP_STATUS" = "302" ]; then
    echo -e "${GREEN}✓ Authentication successful (redirected)${NC}"
elif [ "$HTTP_STATUS" = "200" ]; then
    # Check if login failed (stayed on login page)
    if echo "$LOGIN_RESPONSE" | grep -q "Please enter a correct username"; then
        echo -e "${RED}✗ Authentication failed - invalid credentials${NC}"
        exit 1
    else
        echo -e "${GREEN}✓ Authentication successful${NC}"
    fi
else
    echo -e "${RED}✗ Authentication failed with HTTP $HTTP_STATUS${NC}"
    exit 1
fi
echo

# Step 4: Verify authenticated session
echo -e "${YELLOW}Step 4: Verifying authenticated session...${NC}"
DASHBOARD_RESPONSE=$(curl -s -b "$COOKIE_JAR" -w "HTTP_STATUS:%{http_code}" "$NETBOX_URL/")
DASHBOARD_STATUS=$(echo "$DASHBOARD_RESPONSE" | grep -o "HTTP_STATUS:[0-9]*" | cut -d: -f2)

if [ "$DASHBOARD_STATUS" = "200" ] && echo "$DASHBOARD_RESPONSE" | grep -q "Dashboard\|NetBox"; then
    echo -e "${GREEN}✓ Authenticated session verified${NC}"
else
    echo -e "${RED}✗ Session verification failed${NC}"
    exit 1
fi
echo

# Step 5: Test the drift detection page (THE MAIN TEST)
echo -e "${YELLOW}Step 5: Testing drift detection page...${NC}"
echo -e "${BLUE}URL: $TARGET_URL${NC}"

DRIFT_RESPONSE=$(curl -s -b "$COOKIE_JAR" -w "HTTP_STATUS:%{http_code}" "$TARGET_URL")
DRIFT_STATUS=$(echo "$DRIFT_RESPONSE" | grep -o "HTTP_STATUS:[0-9]*" | cut -d: -f2)
DRIFT_CONTENT=$(echo "$DRIFT_RESPONSE" | sed 's/HTTP_STATUS:[0-9]*$//')

echo -e "${BLUE}HTTP Status: $DRIFT_STATUS${NC}"

# Analyze the response
case "$DRIFT_STATUS" in
    "200")
        echo -e "${GREEN}✓ Page loaded successfully!${NC}"
        if echo "$DRIFT_CONTENT" | grep -q "Drift Detection"; then
            echo -e "${GREEN}✓ Drift Detection page content found${NC}"
            echo -e "${GREEN}🎉 TEST PASSED: Page is working correctly${NC}"
        else
            echo -e "${YELLOW}⚠ Page loaded but content unexpected${NC}"
            echo "First 200 characters of response:"
            echo "$DRIFT_CONTENT" | head -c 200
        fi
        ;;
    "302")
        echo -e "${YELLOW}⚠ Page redirected - checking redirect location${NC}"
        REDIRECT_LOCATION=$(curl -s -I -b "$COOKIE_JAR" "$TARGET_URL" | grep -i "location:" | cut -d' ' -f2- | tr -d '\r\n')
        echo -e "${BLUE}Redirect to: $REDIRECT_LOCATION${NC}"
        ;;
    "404")
        echo -e "${RED}✗ Page not found (404)${NC}"
        echo -e "${RED}❌ TEST FAILED: URL pattern not registered${NC}"
        ;;
    "500")
        echo -e "${RED}✗ Server error (500)${NC}"
        echo -e "${RED}❌ TEST FAILED: Server error occurred${NC}"
        
        # Extract error details
        if echo "$DRIFT_CONTENT" | grep -q "NoReverseMatch"; then
            echo -e "${RED}Error: NoReverseMatch - URL namespace issue${NC}"
        fi
        if echo "$DRIFT_CONTENT" | grep -q "netbox_hedgehog.*not.*registered"; then
            echo -e "${RED}Error: 'netbox_hedgehog' namespace not registered${NC}"
        fi
        
        # Show first few lines of error
        echo -e "${YELLOW}Error details (first 10 lines):${NC}"
        echo "$DRIFT_CONTENT" | head -n 10
        ;;
    *)
        echo -e "${RED}✗ Unexpected HTTP status: $DRIFT_STATUS${NC}"
        echo -e "${RED}❌ TEST FAILED: Unexpected response${NC}"
        ;;
esac

echo
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Authentication Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "URL Tested: $TARGET_URL"
echo -e "HTTP Status: $DRIFT_STATUS"
echo -e "Authentication: ✓ Success"
echo -e "Page Status: $([ "$DRIFT_STATUS" = "200" ] && echo "✓ Working" || echo "✗ Failed")"

# Export curl command for manual testing
echo
echo -e "${YELLOW}Manual curl command for testing:${NC}"
echo "# 1. Login and save cookies:"
echo "curl -c /tmp/cookies.txt -d 'csrfmiddlewaretoken=$CSRF_TOKEN&username=$USERNAME&password=$PASSWORD' $LOGIN_URL"
echo
echo "# 2. Test the page:"
echo "curl -b /tmp/cookies.txt $TARGET_URL"

# Final exit code
if [ "$DRIFT_STATUS" = "200" ]; then
    exit 0
else
    exit 1
fi