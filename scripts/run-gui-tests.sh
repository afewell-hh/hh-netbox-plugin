#!/bin/bash

# GUI Test Runner Script
# Runs comprehensive Playwright GUI tests for NetBox Hedgehog plugin

set -e

echo "=================================================="
echo "  NetBox Hedgehog Plugin - GUI Test Runner"
echo "=================================================="

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: package.json not found. Run this script from the project root."
    exit 1
fi

# Check if NetBox is running
echo "🔍 Checking NetBox accessibility..."
if ! curl -s --connect-timeout 10 http://localhost:8000/ > /dev/null; then
    echo "❌ Error: NetBox is not accessible on http://localhost:8000/"
    echo "   Please start NetBox first: python manage.py runserver 8000"
    exit 1
fi

echo "✅ NetBox is accessible"

# Install dependencies if needed
echo "📦 Installing dependencies..."
npm install --silent

# Install Playwright browsers if needed
echo "🌐 Installing Playwright browsers..."
npx playwright install chromium --with-deps > /dev/null 2>&1

# Run the GUI tests
echo "🧪 Running GUI tests..."
export SKIP_SERVER_START=true  # Don't start server since it's already running

# Run tests with proper output
npx playwright test tests/gui/ \
    --reporter=list \
    --timeout=60000 \
    --workers=1 \
    --headed=false \
    || {
        echo ""
        echo "❌ GUI tests failed. Check the output above for details."
        echo ""
        echo "💡 Troubleshooting tips:"
        echo "   - Ensure NetBox is running on http://localhost:8000/"
        echo "   - Check that the Hedgehog plugin is properly installed"
        echo "   - Run with --debug for more verbose output: npm run test:gui:debug"
        echo ""
        exit 1
    }

echo ""
echo "✅ All GUI tests passed successfully!"
echo ""
echo "📊 Test artifacts generated:"
echo "   - HTML Report: playwright-report/index.html"
echo "   - JSON Results: test-results/gui-test-results.json"
echo ""
echo "🎉 GUI testing framework is working correctly!"