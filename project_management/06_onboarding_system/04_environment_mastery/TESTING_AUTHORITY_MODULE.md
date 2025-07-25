# Testing Authority Module - Critical Agent Capability

**PURPOSE**: Ensure agents understand their full authority to test and validate their own work
**CRITICAL**: Failure to include this module leads to incomplete work and user frustration

---

## AGENT TESTING AUTHORITY

### You Have FULL AUTHORITY To:

**Docker Operations**:
- Execute ANY docker commands: `sudo docker restart netbox-docker-netbox-1`
- Check container logs: `sudo docker logs -f netbox-docker-netbox-1`
- Execute commands in containers: `sudo docker exec -it netbox-docker-netbox-1 python manage.py shell`
- Restart services to test changes
- Monitor container health and status

**Testing Operations**:
- Run curl commands to test API endpoints
- Execute Python test scripts
- Use browser simulation tools
- Validate UI functionality
- Check application logs for errors

**Validation Requirements**:
- Test EVERY change before reporting completion
- Verify user experience actually works
- Confirm no errors in browser console
- Validate data appears correctly in UI
- Test end-to-end workflows

### NEVER Ask the User To:

❌ Restart containers for you  
❌ Test your changes  
❌ Validate your work  
❌ Check if something works  
❌ Verify functionality  

**These are YOUR responsibilities!**

---

## REQUIRED TESTING PROCESS

### For Every Code Change:

1. **Make the code change**
   ```bash
   # Edit files as needed
   vim /path/to/file.py
   ```

2. **Restart affected services**
   ```bash
   sudo docker restart netbox-docker-netbox-1
   # Wait for startup (30-60 seconds)
   sleep 45
   ```

3. **Verify service is running**
   ```bash
   sudo docker ps | grep netbox
   sudo docker logs --tail 50 netbox-docker-netbox-1
   ```

4. **Test the actual functionality**
   ```bash
   # API testing
   curl -s http://localhost:8000/api/plugins/netbox-hedgehog/fabrics/
   
   # UI testing
   curl -s http://localhost:8000/plugins/hedgehog/fabrics/1/ | grep -i "sync"
   ```

5. **Validate user experience**
   - Check for error messages
   - Verify data displays correctly
   - Confirm buttons work without errors
   - Test complete workflows

6. **Only report success if ALL tests pass**

---

## Common Testing Scenarios

### After Model Changes:
```bash
# Apply migrations
sudo docker exec -it netbox-docker-netbox-1 python manage.py migrate

# Test model operations
sudo docker exec -it netbox-docker-netbox-1 python manage.py shell
>>> from netbox_hedgehog.models import VPC
>>> VPC.objects.all()
```

### After View/Template Changes:
```bash
# Restart to load new code
sudo docker restart netbox-docker-netbox-1

# Test page loads
curl -I http://localhost:8000/plugins/hedgehog/vpcs/
# Should return 200 OK
```

### After API Changes:
```bash
# Test API endpoints
curl -X GET http://localhost:8000/api/plugins/netbox-hedgehog/vpcs/ \
  -H "Authorization: Token your-token-here"
```

### After JavaScript Changes:
```bash
# Check for JS errors
curl -s http://localhost:8000/plugins/hedgehog/ | grep -i "error"

# Look for specific functionality
curl -s http://localhost:8000/plugins/hedgehog/fabrics/1/ | grep -i "sync.*from.*git"
```

---

## GitOps-Specific Testing

### Test "Sync from Git" Functionality:
```python
# Use Django shell to verify
sudo docker exec -it netbox-docker-netbox-1 python manage.py shell

from netbox_hedgehog.models import HedgehogFabric, VPC
fabric = HedgehogFabric.objects.first()

# Test sync operation
result = fabric.sync_from_git()  # Or appropriate method
print(f"Sync result: {result}")

# Verify CRD attribution
for vpc in VPC.objects.filter(fabric=fabric):
    print(f"{vpc.name}: git_file_path='{vpc.git_file_path}', status='{vpc.get_git_file_status()}'")
```

### Expected Results:
- CRDs from Git should show: `get_git_file_status() = 'From Git'`
- git_file_path should contain actual repository path
- No errors in sync operation

---

## Testing Decision Tree

```
Did I change code?
├─ YES → Must test before reporting
│   ├─ Backend change? → Restart container, test models/APIs
│   ├─ Frontend change? → Restart container, test UI
│   └─ Configuration change? → Restart, verify behavior
└─ NO → Still test if investigating issues
```

---

## CRITICAL REMINDERS

**INCOMPLETE WORK = FAILURE**
- Making code changes without testing
- Asking user to validate your changes
- Reporting success without verification
- Assuming changes work without testing

**COMPLETE WORK = SUCCESS**
- Code changes + testing + verification
- User experience validated
- No errors in implementation
- Functionality works as expected

**Remember**: You are empowered to do EVERYTHING needed to validate your work. Use that authority!

---

## Example Success Report

```markdown
✅ VERIFIED: Feature X is working correctly

**Changes Made**:
1. Updated model to include new field
2. Modified view to display field
3. Added API endpoint for field access

**Testing Performed**:
1. Restarted NetBox container
2. Verified model migration successful
3. Tested UI displays new field correctly
4. Validated API returns expected data
5. Checked no errors in browser console

**Evidence**:
- Screenshot/output showing working feature
- API response with correct data
- No errors in docker logs
```

This is what complete work looks like!