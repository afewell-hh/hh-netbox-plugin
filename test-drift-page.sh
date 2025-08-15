#!/bin/bash
# One-liner test for drift detection page
# Usage: ./test-drift-page.sh

CSRF=$(curl -s -c /tmp/nb.jar http://localhost:8000/login/ | grep -o 'value="[^"]*"' | head -1 | cut -d'"' -f2)
curl -s -b /tmp/nb.jar -c /tmp/nb.jar -d "csrfmiddlewaretoken=$CSRF&username=admin&password=admin" http://localhost:8000/login/ > /dev/null
STATUS=$(curl -s -b /tmp/nb.jar -w "%{http_code}" -o /dev/null http://localhost:8000/plugins/hedgehog/drift-detection/)
rm -f /tmp/nb.jar
echo "Drift detection page: HTTP $STATUS $([ "$STATUS" = "200" ] && echo "✅ WORKING" || echo "❌ FAILED")"
exit $([ "$STATUS" = "200" ] && echo 0 || echo 1)