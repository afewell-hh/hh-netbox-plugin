
# How to Access the Fabric Edit Page

## Issue: "The edit fabric page is not loading"

### Root Cause:
The edit page requires authentication, which is correct security behavior.

### Solution:
1. Navigate to NetBox at http://localhost:8000
2. You will be redirected to the login page
3. Enter your NetBox credentials
4. After successful login, navigate to Plugins > Hedgehog > Fabrics
5. Select a fabric and click Edit

### Default Credentials (if set up):
- Username: admin
- Password: (check with your NetBox administrator)

### If you don't have credentials:
Contact your NetBox administrator to:
1. Create a user account for you
2. Grant appropriate permissions for the Hedgehog plugin
3. Provide you with login credentials

### Testing Edit Page Access:
After logging in, test the edit page:
```
http://localhost:8000/plugins/hedgehog/fabrics/<fabric_id>/edit/
```

The page should load with a form containing:
- Fabric name field
- Description field  
- Kubernetes configuration
- Save/Cancel buttons

### If the page still doesn't load after authentication:
1. Check browser console for JavaScript errors
2. Verify you have edit permissions for fabrics
3. Ensure the fabric ID exists
4. Contact support with specific error messages
