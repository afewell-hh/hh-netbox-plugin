#!/bin/bash
# Quick status check script for Hedgehog NetBox Plugin

echo "🔍 Hedgehog NetBox Plugin - Quick Status Check"
echo "=============================================="
echo ""

# Check NetBox container
echo "📦 NetBox Container Status:"
if sudo docker ps | grep -q netbox-docker-netbox-1; then
    echo "✅ NetBox container is running"
else
    echo "❌ NetBox container is NOT running"
    echo "   Run: cd gitignore/netbox-docker && sudo docker-compose up -d"
fi
echo ""

# Check plugin accessibility
echo "🌐 Plugin Web Access:"
if curl -s -I http://localhost:8000/plugins/hedgehog/ | grep -q "200 OK"; then
    echo "✅ Plugin is accessible at http://localhost:8000/plugins/hedgehog/"
else
    echo "❌ Plugin is NOT accessible"
    echo "   Check container logs: sudo docker logs netbox-docker-netbox-1 --tail 50"
fi
echo ""

# Check Kubernetes access
echo "☸️  Kubernetes Access:"
if kubectl version --client --short > /dev/null 2>&1; then
    echo "✅ kubectl is configured"
    if kubectl get nodes > /dev/null 2>&1; then
        echo "✅ Can access Kubernetes cluster"
    else
        echo "⚠️  kubectl configured but cannot access cluster"
    fi
else
    echo "❌ kubectl is NOT configured"
fi
echo ""

# Check git status
echo "📝 Git Repository Status:"
if [ -z "$(git status --porcelain)" ]; then
    echo "✅ Working directory clean"
else
    echo "⚠️  Uncommitted changes present:"
    git status --short
fi
echo ""

# Show recent commits
echo "📜 Recent Commits:"
git log --oneline -5
echo ""

# Check for IN_PROGRESS tasks
echo "📋 Current Tasks:"
if grep -q "🔄" project_management/TASK_TRACKING.md 2>/dev/null; then
    echo "🔄 IN_PROGRESS tasks found:"
    grep -A 2 "🔄" project_management/TASK_TRACKING.md | head -10
else
    echo "No IN_PROGRESS tasks. Check TASK_TRACKING.md for next TODO."
fi
echo ""

echo "=============================================="
echo "📚 Next steps:"
echo "1. Review: cat project_management/CURRENT_STATUS.md"
echo "2. Find task: cat project_management/TASK_TRACKING.md"
echo "3. Start work: Follow DEVELOPMENT_GUIDE.md"
echo ""