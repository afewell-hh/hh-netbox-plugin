# NetBox Container Recovery Plan

## Problem Analysis
**Current State:** NetBox container (netbox-docker-netbox-1) is failing to start due to DB connectivity timeout after recent commits (especially df53aa0).

**Root Causes Identified:**
1. Plugin loading issues during container startup
2. Database migration conflicts or missing dependencies
3. Plugin configuration errors preventing proper initialization
4. Recent changes in commit df53aa0 affecting TDD tests may have broken plugin structure

## Recovery Plan - 4 Phases

### Phase 1: Immediate Fixes (Stop bleeding)
**Objective:** Address immediate blockers preventing container startup

**Sub-tasks:**
1. **Verify plugin structure integrity**
   - Agent: Structure Validator
   - Action: Check for broken imports in netbox_hedgehog/__init__.py and models/
   - Validation: All imports resolve without circular dependencies

2. **Validate database migrations**
   - Agent: DB Migration Validator  
   - Action: Check migration files 0001-0028 for syntax errors or conflicts
   - Validation: All migration files are syntactically correct

3. **Check plugin dependencies**
   - Agent: Dependency Checker
   - Action: Verify pyproject.toml and all required packages are installable
   - Validation: `pip install -e .` succeeds without errors

4. **Inspect container configuration**
   - Agent: Config Validator
   - Action: Verify plugins.py configuration matches plugin structure
   - Validation: Plugin name and config are properly aligned

### Phase 2: Container Restart (Get service running)
**Objective:** Get NetBox container running and accessible

**Sub-tasks:**
5. **Clean container state**
   - Agent: Container Manager
   - Action: Stop all containers, remove netbox container, clear any locks
   - Commands: 
     ```bash
     cd gitignore/netbox-docker
     sudo docker compose stop netbox
     sudo docker rm netbox-docker-netbox-1 
     ```

6. **Restart supporting services**
   - Agent: Infrastructure Manager
   - Action: Ensure postgres, redis, redis-cache are healthy before netbox
   - Commands:
     ```bash
     sudo docker compose up -d postgres redis redis-cache
     # Wait for healthy status
     ```

7. **Start NetBox with debug logging**
   - Agent: Container Startup Specialist
   - Action: Start netbox with DB_WAIT_DEBUG=1 for detailed error info
   - Commands:
     ```bash
     # Temporarily set debug flag in netbox.env
     echo "DB_WAIT_DEBUG=1" >> env/netbox.env
     sudo docker compose up -d netbox
     ```

8. **Monitor startup logs**
   - Agent: Log Monitor
   - Action: Watch container logs for specific error messages
   - Commands: `sudo docker logs -f netbox-docker-netbox-1`

### Phase 3: Deployment Validation (Deploy changes)
**Objective:** Ensure local code changes are properly deployed to container

**Sub-tasks:**
9. **Verify container is accessible**
   - Agent: Connectivity Tester
   - Action: Confirm basic NetBox functionality before plugin deployment
   - Test: `curl -f http://localhost:8000/login/` returns 200

10. **Deploy plugin changes**
    - Agent: Deployment Specialist
    - Action: Execute `make deploy-dev` to sync local code to container
    - Commands:
      ```bash
      make deploy-dev
      ```

11. **Validate deployment success**
    - Agent: Deployment Validator
    - Action: Verify plugin is installed in editable mode within container
    - Test: `pip list | grep netbox-hedgehog.*editable`

12. **Check static file collection**
    - Agent: Static File Manager
    - Action: Ensure CSS/JS assets are properly deployed
    - Commands: Container exec collectstatic if needed

### Phase 4: GUI Verification (Test localhost:8000)
**Objective:** Confirm full functionality through web interface

**Sub-tasks:**
13. **Test NetBox base functionality**
    - Agent: Base Functionality Tester
    - Action: Verify login page loads and basic NetBox features work
    - Test: Login form accessible and functional at http://localhost:8000

14. **Test plugin accessibility**
    - Agent: Plugin Functionality Tester  
    - Action: Access plugin endpoints and verify no 500 errors
    - Test: http://localhost:8000/plugins/hedgehog/ returns content (not 500)

15. **Validate critical plugin features**
    - Agent: Feature Validator
    - Action: Test fabric list, git repositories, and basic CRUD operations
    - Tests:
      - Fabric list page loads
      - Git repositories page accessible
      - No JavaScript console errors

16. **Run basic integration tests**
    - Agent: Integration Tester
    - Action: Execute essential plugin functionality tests
    - Commands: `python -m pytest tests/integration/ -v`

## Recovery Validation Criteria

### Phase 1 Success Criteria:
- [ ] All plugin imports resolve successfully
- [ ] Database migrations are syntactically correct
- [ ] Plugin dependencies install without errors
- [ ] Plugin configuration is valid

### Phase 2 Success Criteria:
- [ ] NetBox container starts without DB timeout
- [ ] Container logs show successful plugin loading
- [ ] http://localhost:8000/login/ returns 200 OK
- [ ] No critical errors in container logs

### Phase 3 Success Criteria:  
- [ ] `make deploy-dev` completes successfully
- [ ] Plugin shows as "editable" in container pip list
- [ ] Static files collected successfully
- [ ] Container restart completes in <30s

### Phase 4 Success Criteria:
- [ ] Login page loads completely
- [ ] Plugin URL responds (not 500/404)
- [ ] Basic navigation works without errors
- [ ] No blocking JavaScript console errors

## Emergency Rollback Procedures

**If Phase 2 fails (container won't start):**
1. Disable plugin in plugins.py: `PLUGINS = []`
2. Restart container to isolate if issue is plugin-related
3. Re-enable plugin and fix specific errors

**If Phase 3 fails (deployment issues):**
1. Manual plugin uninstall/reinstall: `pip uninstall netbox-hedgehog && pip install -e .`
2. Clear Python cache: `find . -name "*.pyc" -delete`
3. Force container rebuild if needed

**If Phase 4 fails (GUI errors):**
1. Check Django logs for template/view errors
2. Verify static file collection
3. Clear browser cache and test again

## High-Risk Areas to Monitor

1. **Database Migration Issues:** Recent commits may have introduced migration conflicts
2. **Import Dependencies:** Plugin structure changes could break circular imports  
3. **Template Rendering:** Static file collection failures affecting GUI
4. **Signal Registration:** Plugin ready() method failing during startup

## Success Metrics
- **Container startup time:** <30 seconds
- **GUI response time:** Login page <2 seconds
- **Plugin functionality:** All CRUD operations working
- **Error rate:** Zero critical errors in first 5 minutes

## Next Steps After Recovery
1. Investigate specific cause of df53aa0 commit issues
2. Add container health monitoring to prevent future failures
3. Create automated recovery scripts
4. Document root cause analysis

---

**Time Estimate:** 30-60 minutes total
**Risk Level:** Medium (database operations involved)
**Prerequisites:** Docker access, git repository state preserved