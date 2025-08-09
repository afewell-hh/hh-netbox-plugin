#!/bin/bash

# GUI Test Setup Script
# Sets up the complete GUI testing framework for NetBox Hedgehog plugin

set -e

echo "=================================================="
echo "  NetBox Hedgehog Plugin - GUI Test Setup"
echo "=================================================="

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: package.json not found. Run this script from the project root."
    exit 1
fi

# Check Node.js availability
echo "🔍 Checking Node.js..."
if ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js is not installed"
    exit 1
fi

if ! command -v npx &> /dev/null; then
    echo "❌ Error: npx is not available"
    exit 1
fi

echo "✅ Node.js $(node --version) and npx available"

# Install npm dependencies
echo "📦 Installing npm dependencies..."
npm install

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
npx playwright install chromium --with-deps

# Create test directories if they don't exist
echo "📁 Setting up test directories..."
mkdir -p tests/gui
mkdir -p test-results

# Verify installation
echo "🧪 Verifying Playwright installation..."
if npx playwright --version > /dev/null 2>&1; then
    echo "✅ Playwright $(npx playwright --version) installed successfully"
else
    echo "❌ Error: Playwright installation failed"
    exit 1
fi

# Check test files
echo "📋 Checking test files..."
if [ -f "tests/gui/netbox-hedgehog.spec.ts" ]; then
    echo "✅ GUI test spec file found"
else
    echo "❌ Warning: GUI test spec file not found"
fi

if [ -f "playwright.config.ts" ]; then
    echo "✅ Playwright configuration found"
else
    echo "❌ Warning: Playwright configuration not found"
fi

echo ""
echo "🎉 GUI testing framework setup complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Start NetBox: python manage.py runserver 8000"
echo "   2. Run GUI tests: npm run test:gui"
echo "   3. Run with browser visible: npm run test:gui:headed"
echo "   4. Debug tests: npm run test:gui:debug"
echo ""
echo "📚 Available commands:"
echo "   - npm run test:gui              # Run all GUI tests"
echo "   - npm run test:gui:headed       # Run with visible browser"
echo "   - npm run test:gui:debug        # Run in debug mode"
echo "   - npm run test:gui:report       # Show last test report"
echo ""