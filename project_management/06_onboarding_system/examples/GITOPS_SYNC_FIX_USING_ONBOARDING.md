# Example: GitOps Sync Fix Agent (Using Onboarding System)

**This is how the GitOps Sync Fix instructions SHOULD have been written**

---

# GitOps Sync Fix Specialist

**Agent Type**: Claude Sonnet 4  
**Task**: Fix "Sync from Git" attribution issue

## Specific Problem
- CRDs from GitOps show "Not from Git" despite being from Git repository
- Git sync completes but attribution fails
- Test repo: ${GITOPS_REPOSITORY_URL}

## Standard Training Modules
- **Environment**: @onboarding/04_environment_mastery/ENVIRONMENT_MASTER.md
- **Testing**: @onboarding/04_environment_mastery/TESTING_AUTHORITY_MODULE.md
- **Process**: @onboarding/00_foundation/UNIVERSAL_FOUNDATION.md
- **Specialist**: @onboarding/03_specialist_track/SPECIALIST_MASTERY.md

## Task-Specific Investigation
1. Check `get_git_file_status()` method implementation
2. Trace Git sync service flow in:
   - `netbox_hedgehog/services/gitops_ingestion_service.py`
   - `netbox_hedgehog/utils/git_directory_sync.py`
3. Fix attribution logic to set `git_file_path` correctly

## Success Criteria
- Phase 5 GitOps tests pass
- CRDs show "From Git" in UI
- No sync errors

---

**TOTAL LENGTH**: ~20 lines (vs 500+ lines custom)  
**EFFECTIVENESS**: Same or better (leverages tested onboarding content)