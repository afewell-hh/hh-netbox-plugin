# Agent Role Examples & Templates
**Practical examples of proper GitHub interaction patterns**

---

## 📋 GitHub Issue Examples

### **User Story Example (PM Agent Created)**
```markdown
**Title**: [User Story] As a NetBox admin, I want to create VPCs through a web form so that I can provision network infrastructure quickly

## User Story
As a **NetBox administrator**, I want **to create VPC resources through a web form** so that **I can quickly provision network infrastructure without writing YAML files**.

## Acceptance Criteria
- [ ] Web form displays all required VPC fields (name, CIDR block, fabric selection)
- [ ] Form validates CIDR format and shows clear error messages for invalid input
- [ ] Successful creation shows confirmation message with link to view the new VPC
- [ ] Created VPC appears immediately in the VPC list view
- [ ] VPC is properly synchronized to the associated Kubernetes cluster

## Technical Context
- VPC model already exists in `netbox_hedgehog/models/vpc_api.py`
- Follow existing form patterns from `netbox_hedgehog/forms/vpc_api.py`
- Use Django ModelForm with NetBox plugin conventions
- Reference External form implementation as a template

## Definition of Done
- [ ] Code follows NetBox plugin development patterns
- [ ] Manual testing completed with screenshot evidence
- [ ] No regressions in existing VPC functionality
- [ ] PR approved by code reviewer and merged
- [ ] Feature verified working in development environment

## Related Issues
- Depends on: #120 (Fabric management must be working)
- Blocks: #125 (VPC editing functionality)
- Related: #118 (Kubernetes connectivity improvements)

**Labels**: `user-story`, `role:coder`, `effort/medium`, `priority/high`
**Milestone**: Sprint 2024-08-15
**Assignee**: @coder-agent
```

### **Technical Task Example (Architect Agent Created)**
```markdown
**Title**: [Technical] Refactor VPC validation to use Django field validators

## Technical Requirement
Move VPC model validation logic from custom save() method to Django field validators for better testability and consistency with NetBox patterns.

## Business Context
Current validation approach makes automated testing difficult and doesn't follow Django/NetBox conventions. This refactoring will enable comprehensive test coverage and improve code maintainability.

## Technical Details
**Current State**:
- Validation logic embedded in `VPC.save()` method
- Inconsistent error message formats
- Difficult to unit test validation scenarios
- Custom validation patterns not aligned with NetBox conventions

**Target State**:
- Django field validators on VPC model fields
- Consistent error messages following NetBox format patterns
- Unit testable validation components
- Alignment with existing NetBox model validation patterns

## Acceptance Criteria
- [ ] All validation moved from `save()` method to field validators
- [ ] Error messages consistent with NetBox validation message format
- [ ] Migration created for any necessary model field changes
- [ ] Existing VPC creation functionality still works exactly the same
- [ ] Unit tests can be written for individual validation rules

## Implementation Guidance
1. Study existing NetBox model validation patterns in core models
2. Use Django's built-in validators where possible (`RegexValidator`, etc.)
3. Create custom validators following Django conventions for complex rules
4. Ensure backward compatibility with existing VPC data
5. Test thoroughly with both valid and invalid data inputs

**Labels**: `technical-debt`, `role:coder`, `effort/small`, `priority/medium`
**Milestone**: Sprint 2024-08-15
**Assignee**: @coder-agent
```

---

## 💬 Status Update Examples

### **Coder Agent Progress Update**
```markdown
## Status Update - Coder Agent - 2024-08-08

**Current State**: In Progress (Day 2 of estimated 3-day task)

**Progress This Period**:
- ✅ Completed VPC model field validation implementation
- ✅ Created Django migration for model changes  
- ✅ Updated VPC form to use new validation approach
- 🔄 Currently working on error message formatting consistency

**Testing Completed**:
- Manual testing: Valid CIDR formats accepted correctly
- Manual testing: Invalid formats show appropriate error messages
- Regression testing: Existing VPC creation workflow still functional

**Next Steps**:
- Complete error message format standardization
- Add unit tests for new validation logic
- Update PR with latest changes and test evidence
- Request code review from @reviewer-agent

**Blockers**: None currently

**Questions/Concerns**: 
- Error message format - should we match NetBox core exactly or maintain plugin-specific format? (cc: @architect-agent)

**Confidence in Timeline**: High - on track for completion by end of sprint

**Evidence**: 
- Screenshot of working form validation: [attached]
- Migration file created: `0021_update_vpc_validation.py`
- Updated model code follows Django best practices
```

### **Project Manager Daily Standup**
```markdown
## Daily Standup Update - PM Agent - 2024-08-08

**Sprint Progress Overview**:
- **Sprint Goal**: Implement user-friendly VPC management interface
- **Completion**: 60% (6 of 10 planned story points complete)
- **Days Remaining**: 8 days in sprint

**Issues Completed Since Last Update**:
- ✅ #123: VPC creation form validation - merged and deployed
- ✅ #118: Kubernetes connectivity error handling - tested and verified

**Issues In Progress**:
- 🔄 #124: VPC list view with filtering (Coder Agent) - 80% complete, testing phase
- 🔄 #125: VPC editing capabilities (Coder Agent) - blocked waiting on #124
- 🔄 #121: Architecture review for bulk operations (Architect Agent) - analysis phase

**Blockers Identified**:
- **Medium Impact**: Issue #125 blocked by dependency on #124 - expected resolution today
- **Low Impact**: Staging environment slow - may affect testing timeline

**Team Coordination Needs**:
- Code review needed for PR #124 - @reviewer-agent please prioritize
- Architecture guidance needed on bulk delete UX - @architect-agent input requested

**Risk Assessment**:
- **Sprint Goal**: Low risk - core functionality on track
- **Quality**: Medium risk - need more testing time for complex features

**Actions Taken**:
- Requested priority code review for blocking PR
- Created follow-up issue for staging environment performance
- Updated sprint board with current progress status

**Tomorrow's Focus**:
- Unblock issue #125 by completing #124 review/merge
- Begin sprint retrospective planning
- Monitor testing progress on completed features
```

### **Architect Review Comment**
```markdown
## Architecture Review - 2024-08-08

**PR Reviewed**: #124 - VPC List View Implementation

**Overall Assessment**: ✅ **Approved** with minor suggestions

**Architectural Compliance**:
- ✅ Follows NetBox plugin ListView patterns correctly
- ✅ Uses appropriate Django ORM optimization (select_related, prefetch_related)
- ✅ Consistent with existing VPC model API design
- ✅ Proper separation of concerns (view logic vs template presentation)

**Performance Considerations**:
- ✅ Query optimization implemented for fabric relationships
- ⚠️ **Suggestion**: Add pagination for large VPC lists (future scalability)
- ✅ Filtering implementation efficient and follows NetBox patterns

**Security & Standards**:
- ✅ Proper Django permission checking implemented
- ✅ Input validation follows established patterns
- ✅ No SQL injection or XSS vulnerabilities identified

**Specific Recommendations**:
1. **Minor Enhancement**: Consider adding `ordering` to VPC model Meta for consistent list sorting
2. **Future Consideration**: Document pagination strategy in ADR when implementing bulk operations
3. **Code Quality**: Excellent adherence to NetBox plugin conventions

**Technical Debt Assessment**: No technical debt introduced

**Future Architecture Impact**: 
- This implementation provides good foundation for planned bulk operations feature
- Filter pattern can be reused across other CRD list views
- Performance approach scalable to larger data sets

**Merge Recommendation**: ✅ **Approve and merge** - ready for production deployment

**Follow-up Actions**:
- [ ] Create issue for pagination implementation (next sprint)
- [ ] Document list view pattern for other CRD types (add to standards)

**Testing Verification**: Manual testing evidence provided shows correct functionality
```

---

## 🚨 Emergency Situation Examples

### **Critical Bug Report**
```markdown
## 🚨 CRITICAL BUG - Production Impact

**Issue**: VPC creation form causing 500 errors for all users after latest deployment

**Impact**: 
- **User Impact**: Complete inability to create VPCs (primary plugin function)
- **Business Impact**: Production workflow blocked for all NetBox administrators  
- **Timeline Impact**: Sprint goal at risk if not resolved within 4 hours

**Error Details**:
- Error message: "AttributeError: 'VPC' object has no attribute 'validate_cidr'"
- Occurs on: All VPC creation attempts via web form
- Started: ~30 minutes ago after deployment of PR #124
- Affected users: All users attempting VPC creation

**Attempted Solutions**:
1. ✅ Verified issue reproduces in development environment
2. ✅ Checked recent code changes - likely related to validation refactoring
3. ✅ Confirmed database migration completed successfully
4. 🔄 Currently investigating validation method naming in new code

**Immediate Action Plan**:
1. **Hotfix branch created**: `hotfix-124-vpc-validation-error`
2. **Root cause identified**: Method name mismatch in validation refactor
3. **Fix implemented**: Corrected method name in VPC model
4. **Testing**: Manual verification in progress

**Help Needed**:
- @reviewer-agent: Urgent code review needed for hotfix PR (within 1 hour)
- @pm-agent: Stakeholder communication about production impact
- @architect-agent: Review fix for any architectural concerns

**Rollback Plan**: 
- Database rollback not needed (migration unaffected)
- Code rollback available if hotfix fails testing

**Follow-up Required**:
- Root cause analysis issue to be created after resolution
- Process improvement: better pre-deployment testing for validation changes

**Status Updates**: Will provide updates every 30 minutes until resolved

---
**Next Update**: 2024-08-08 15:30 or when resolved
```

### **Blocker Escalation**
```markdown
## BLOCKER - Coder Agent

**Issue**: Cannot complete VPC editing feature - Kubernetes API authentication failing consistently

**Impact**: 
- **Timeline**: Issue #125 blocked (3 days remaining in sprint)
- **Dependencies**: Issues #126 and #127 also depend on this functionality
- **Sprint Goal**: At risk - VPC editing is core deliverable

**Attempted Solutions**:
1. ✅ Verified Kubernetes credentials are correct
2. ✅ Tested connection from Django shell - same error
3. ✅ Reviewed Kubernetes client configuration code
4. ✅ Compared with working VPC creation code - no obvious differences
5. ❌ Docker container restart - no improvement
6. ❌ Credential refresh - still failing

**Technical Details**:
```python
Error: kubernetes.client.exceptions.ApiException: (403) 
Reason: Forbidden
HTTP response body: {"kind":"Status","message":"vpcs.vpc.githedgehog.com is forbidden"}
```

**Analysis**:
- Error suggests permissions issue specific to VPC editing operations
- VPC creation works fine with same credentials
- May be related to Kubernetes RBAC configuration differences
- Could be API version mismatch for PATCH vs POST operations

**Help Needed**:
- @architect-agent: Review Kubernetes integration architecture for RBAC requirements
- @pm-agent: Assess impact on sprint timeline, consider scope adjustment
- **Urgent**: Need guidance on debugging Kubernetes permissions

**Workaround Available**: No - VPC editing completely blocked

**Business Context**: VPC editing is essential for users to modify network configurations without recreating resources

**Escalation Reason**: Blocked for 8 hours, affecting sprint deliverable

**Next Steps if Unresolved**: 
- Consider removing VPC editing from current sprint scope
- Create separate issue for Kubernetes permissions debugging
- Focus on completing other sprint goals

**Timeline**: Need resolution path within 24 hours to maintain sprint goal
```

---

## ✅ Success Examples

### **Completed Feature Summary**
```markdown
## Feature Completion Summary - VPC Creation Form

**User Story**: #123 - As a NetBox admin, I want to create VPCs through a web form

**Completion Status**: ✅ **DELIVERED** - All acceptance criteria met

**Evidence of Success**:

### Acceptance Criteria Verification
- ✅ **Web form with required fields**: [Screenshot: form_display.png]
  - Name field with validation
  - CIDR block field with format validation  
  - Fabric selection dropdown populated correctly
  
- ✅ **Form validation with clear errors**: [Screenshot: validation_errors.png]
  - Invalid CIDR format shows: "Enter a valid CIDR block (e.g., 10.0.0.0/16)"
  - Empty required fields highlighted with clear messaging
  
- ✅ **Success confirmation**: [Screenshot: success_message.png]
  - Green success banner: "VPC 'test-vpc' created successfully"
  - Direct link to view created VPC provided
  
- ✅ **VPC appears in list**: [Screenshot: vpc_list.png]
  - New VPC visible immediately after creation
  - Correct fabric association displayed
  - Status shows as "Pending" until sync completes
  
- ✅ **Kubernetes synchronization**: [Screenshot: k8s_verification.png]
  - VPC resource created in target Kubernetes cluster
  - Status updated to "Synced" after successful creation

### Technical Implementation Summary
**Files Modified**:
- `netbox_hedgehog/forms/vpc_api.py` - Added VPCCreateForm with validation
- `netbox_hedgehog/views/vpc_api.py` - Added VPCCreateView using NetBox patterns
- `netbox_hedgehog/templates/vpc_create.html` - Bootstrap form template
- `netbox_hedgehog/urls.py` - Added create URL pattern

**Code Quality**:
- ✅ Follows NetBox plugin development patterns
- ✅ Django ModelForm conventions used appropriately
- ✅ Proper error handling and user feedback
- ✅ No technical debt introduced

**Testing Evidence**:
- Manual testing: All acceptance criteria verified with screenshots
- Regression testing: Existing VPC functionality unaffected
- Error condition testing: All validation scenarios work correctly
- Integration testing: End-to-end workflow from form to Kubernetes verified

### Business Value Delivered
**User Impact**: NetBox administrators can now create VPCs through intuitive web interface instead of writing YAML files manually

**Process Improvement**: Reduces VPC creation time from ~10 minutes (YAML creation + kubectl apply) to ~30 seconds (web form submission)

**Quality Impact**: Form validation prevents common configuration errors that previously required troubleshooting

### Post-Deployment Verification
- ✅ Feature verified working in staging environment
- ✅ No user-reported issues after 48 hours in production
- ✅ Performance metrics: Average form submission < 2 seconds
- ✅ Error rate: 0% (no 500 errors related to VPC creation)

**Sprint Impact**: Completed on schedule, unblocked dependent issues #125 and #126

**Team Feedback**: "This is exactly what our users needed - simple and reliable" - Stakeholder feedback
```

---

## 🔄 Process Improvement Examples

### **Sprint Retrospective Actions**
```markdown
## Sprint Retrospective Actions - Sprint 2024-08-15

**What Went Well** 👍
- GitHub Issue workflow kept everyone aligned on priorities
- Clear user story format made implementation requirements obvious  
- Daily status updates through issue comments maintained good visibility
- Cross-functional collaboration between Coder and Architect agents effective

**What Could Be Improved** 🔧
1. **Effort Estimation Accuracy**
   - **Issue**: 3 out of 8 issues took longer than estimated
   - **Root Cause**: Underestimated testing and integration complexity
   - **Action**: Create effort estimation guidelines with testing time included

2. **Dependency Management**
   - **Issue**: Issue #125 blocked unexpectedly by Kubernetes permissions
   - **Root Cause**: Dependencies not identified during sprint planning  
   - **Action**: Add dependency checklist to issue creation template

3. **Code Review Timeline**
   - **Issue**: PRs waited average 18 hours for review
   - **Root Cause**: No dedicated review time blocks scheduled
   - **Action**: Schedule dedicated PR review sessions 3x per week

**Action Items for Next Sprint** 🎯

### 1. Create Effort Estimation Guidelines
- [ ] **Owner**: @pm-agent
- [ ] **Due**: Before next sprint planning
- [ ] **Description**: Document estimation approach including testing time, integration complexity, and buffer for unknowns

### 2. Implement Dependency Mapping Process
- [ ] **Owner**: @pm-agent  
- [ ] **Due**: Next sprint planning session
- [ ] **Description**: Add dependency identification step to issue creation, create dependency visualization

### 3. Establish Code Review Schedule
- [ ] **Owner**: @reviewer-agent
- [ ] **Due**: Start of next sprint
- [ ] **Description**: Schedule Tuesday/Thursday/Friday 2-3 PM for PR review focus time

### 4. Architecture Review Integration
- [ ] **Owner**: @architect-agent
- [ ] **Due**: Within 1 week
- [ ] **Description**: Define when architectural review is needed, integrate with PR process

**Process Experiments to Try Next Sprint** 📊
1. **GitHub Project Boards**: Visual kanban for better progress tracking
2. **Issue Templates**: Standardize user story and technical task formats
3. **PR Templates**: Ensure consistent review information provided
4. **Definition of Done Checklist**: Standard checklist for all issue types

**Team Satisfaction Survey Results**
- **Process Clarity**: 4.2/5 (up from 3.8 last sprint)
- **Tool Effectiveness**: 4.0/5 (GitHub workflow working well)
- **Communication**: 4.3/5 (status updates appreciated)
- **Workload Balance**: 3.7/5 (room for improvement in estimation)

**Continuous Improvement Commitment**
- Review these action items in next sprint retrospective
- Measure improvement using same satisfaction survey
- Adjust process based on what works/doesn't work
- Maintain focus on delivering user value while improving team experience

**Success Metrics for Next Sprint**
- Effort estimation accuracy: 80% of issues within 25% of estimate
- Average PR review time: < 12 hours
- Dependency blockers: 0 mid-sprint surprises
- Team satisfaction: Maintain above 4.0/5 average
```

---

These examples demonstrate proper GitHub interaction patterns for each agent role. Use them as templates for your own communications, adapting the specific details to your actual work context.