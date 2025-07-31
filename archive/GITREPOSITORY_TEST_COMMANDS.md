# GitRepository Model Fix - Manual Testing Commands

## Overview
These commands verify that the GitRepository model authentication issue has been resolved.

## Prerequisites
1. NetBox should be running at localhost:8000
2. The new migration (0020_fix_gitrepository_created_by_field.py) should be applied
3. NetBox should be restarted to load URL configuration changes

## Test Commands

### 1. Apply Migration (run in NetBox container or environment)
```bash
# Navigate to NetBox directory and run migration
python manage.py migrate netbox_hedgehog

# Expected output: Migration 0020_fix_gitrepository_created_by_field applied successfully
```

### 2. Restart NetBox
```bash
# If using Docker Compose
docker-compose restart netbox

# Wait for NetBox to fully start (check logs)
docker-compose logs -f netbox
```

### 3. Test GitRepository List View
```bash
# Test the main GitRepository list page
curl -s -w "\nHTTP Status: %{http_code}\nTime Total: %{time_total}s\n" \
  "http://localhost:8000/plugins/hedgehog/git-repos/"

# Expected: HTTP Status: 200 (no authentication errors)
```

### 4. Test GitRepository Detail View
```bash
# Test detail view (even if no records exist, should not crash)
curl -s -w "\nHTTP Status: %{http_code}\nTime Total: %{time_total}s\n" \
  "http://localhost:8000/plugins/hedgehog/git-repos/1/"

# Expected: HTTP Status: 200 or 404 (not 500 server error)
```

### 5. Test Debug Endpoints
```bash
# Test simple template without model queries
curl -s -w "\nHTTP Status: %{http_code}\nTime Total: %{time_total}s\n" \
  "http://localhost:8000/plugins/hedgehog/debug-test/"

# Test working model (HedgehogFabric) as baseline
curl -s -w "\nHTTP Status: %{http_code}\nTime Total: %{time_total}s\n" \
  "http://localhost:8000/plugins/hedgehog/test-working-list/"

# Both should return HTTP Status: 200
```

### 6. Check NetBox Logs for Errors
```bash
# Monitor NetBox logs during testing
docker-compose logs -f netbox | grep -E "(ERROR|exception|GitRepository)"

# Expected: No authentication-related errors for GitRepository model
```

### 7. Automated Test Script
```bash
# Run the comprehensive test script
python3 test_gitrepository_fix.py

# Expected: All tests pass with success rate > 80%
```

## Success Criteria

### ✅ Fix is Working If:
1. **No Authentication Errors**: GitRepository URLs return 200 status codes
2. **No Server Crashes**: No 500 errors when accessing git-repos/ URLs  
3. **Model Accessible**: GitRepository list view loads without middleware conflicts
4. **Clean Logs**: No AUTH_USER_MODEL or foreign key constraint errors in logs
5. **Database Stable**: Migration applies successfully without conflicts

### ❌ Additional Work Needed If:
1. **500 Server Errors**: Still getting internal server errors
2. **Authentication Middleware Errors**: Logs show user authentication issues
3. **Foreign Key Constraints**: Database constraint violation errors
4. **Template Errors**: Template rendering fails due to model issues
5. **Migration Fails**: Database migration cannot be applied

## Troubleshooting Commands

### Check Database Constraints
```sql
-- Run in PostgreSQL to verify constraints were updated
\d+ netbox_hedgehog_gitrepository;

-- Should show created_by allows NULL and no unique constraint on url+created_by
```

### Check Model Loading
```bash
# In NetBox shell, test model import
python manage.py shell
>>> from netbox_hedgehog.models import GitRepository
>>> GitRepository.objects.all()
# Should not raise authentication errors
```

### Verify URL Patterns
```bash
# Check URL resolution
python manage.py shell
>>> from django.urls import reverse
>>> reverse('plugins:netbox_hedgehog:gitrepository_list')
# Should return '/plugins/hedgehog/git-repos/'
```

## Expected Behavior After Fix

1. **GitRepository List**: `/plugins/hedgehog/git-repos/` loads successfully
2. **GitRepository Detail**: `/plugins/hedgehog/git-repos/1/` returns 200 or 404 (not 500)
3. **No Auth Conflicts**: created_by field doesn't trigger authentication middleware
4. **Template Rendering**: Views render without foreign key constraint errors
5. **Model Queries**: GitRepository.objects.all() works without user context

## Files Modified in This Fix

1. **Model**: `/netbox_hedgehog/models/git_repository.py` - already correct
2. **URLs**: `/netbox_hedgehog/urls.py` - already using TemplateView approach  
3. **Migration**: `/netbox_hedgehog/migrations/0020_fix_gitrepository_created_by_field.py` - NEW
4. **Test Script**: `/test_gitrepository_fix.py` - NEW

The fix ensures GitRepository model works exactly like HedgehogFabric model regarding authentication.