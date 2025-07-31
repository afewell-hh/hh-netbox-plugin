# HNP CSS Cleanup Specialist - Label Text Readability & Inline CSS Consolidation

**Agent Role**: Frontend CSS Specialist (Technical Implementation)
**Agent Type**: Claude Sonnet 4
**Authority Level**: Technical implementation decisions within CSS/Frontend domain

## IMMEDIATE CONTEXT (Level 0 - Essential)

**Current Task**: Resolve label text readability issues and consolidate inline CSS across HNP templates
**Success Criteria**: 
- All badge/label text has adequate contrast and readability
- Reduce 85+ inline style instances to centralized CSS
- Maintain existing visual design and functionality
- Pass all 71 GUI tests after changes

## Standard Setup References

**Environment Setup**
Refer to: @onboarding/04_environment_mastery/ENVIRONMENT_MASTER.md
- NetBox Docker operations at localhost:8000
- Project root: /home/ubuntu/cc/hedgehog-netbox-plugin/
- CSS files: /netbox_hedgehog/static/netbox_hedgehog/css/

**Testing Requirements**
Refer to: @onboarding/04_environment_mastery/TESTING_AUTHORITY_MODULE.md
- You have FULL testing authority
- You MUST test all changes yourself using ./run_demo_tests.py
- NEVER ask user to validate your work
- Maintain 71/71 passing tests

**Process Requirements**
Refer to: @onboarding/00_foundation/UNIVERSAL_FOUNDATION.md
- Git workflow: feature branch `feature/css-consolidation-readability`
- Commit frequently with descriptive messages
- Test-driven development approach

## Task-Specific Context

**Problem Identified**: Badge text readability issues and excessive inline CSS
- Badge text contrast issues (especially bg-secondary badges)
- 85+ inline style instances across 24 templates in `/netbox_hedgehog/templates/`
- Well-structured centralized CSS exists in `hedgehog.css` (901 lines)

**Current CSS Architecture**:
- `/netbox_hedgehog/static/netbox_hedgehog/css/hedgehog.css` (primary file)
- `/netbox_hedgehog/static/netbox_hedgehog/css/progressive-disclosure.css` (secondary)
- Bootstrap 5 framework with NetBox theme compatibility

**Critical Requirements**:
- ZERO visual regression - maintain exact appearance
- Fix badge text contrast for all color variants
- Consolidate inline styles into semantic CSS classes
- Preserve responsive behavior and Bootstrap functionality

## Implementation Strategy

**Phase 1: Badge Text Readability**
```css
/* Add to hedgehog.css */
.badge.bg-secondary {
    color: #fff !important;
}
.badge.bg-light {
    color: #212529 !important;
}
```

**Phase 2: Inline CSS Consolidation**
1. Catalog all inline styles by pattern/purpose
2. Create semantic CSS classes for common patterns
3. Replace inline styles with class references
4. Test each template after changes

**Priority Template Order**:
1. fabric_list_simple.html (recently fixed, high usage)
2. Git repository templates (recently restored)
3. Dashboard/overview templates
4. Detail view templates
5. Form templates

## Quality Gates

**Before Each Change**:
- Screenshot current appearance for comparison
- Run GUI tests to ensure 71/71 passing baseline

**After Each Template**:
- Visual validation at localhost:8000
- Responsive behavior check
- GUI test validation

**Final Validation**:
- All 71 tests passing
- Visual regression check complete
- Badge readability confirmed across all variants
- 80%+ reduction in inline CSS instances

## Technical Patterns

**CSS Class Creation**:
- Use semantic names: `.badge-readable`, `.hedgehog-mobile-stack`
- Follow existing hedgehog.css organization
- Group related styles with comments

**Template Updates**:
```html
<!-- BEFORE -->
<span class="badge bg-secondary" style="color: white;">Status</span>

<!-- AFTER -->
<span class="badge bg-secondary badge-readable">Status</span>
```

## Escalation Triggers

**Escalate Immediately If**:
- Any visual regression occurs
- GUI tests fail and can't be resolved
- Bootstrap framework conflicts arise
- Template functionality changes beyond CSS scope

**Expected Outcome**: Improved text readability, cleaner codebase with centralized CSS, zero functional or visual regressions.