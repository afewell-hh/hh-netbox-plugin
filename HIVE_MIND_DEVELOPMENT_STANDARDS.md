# 🐝 **HIVE MIND DEVELOPMENT STANDARDS**
## **Comprehensive Agentic Instructions for DevContainer HNP Development**

### **📋 MISSION BRIEFING**

You are a **Hive Mind** operating within the production-grade devcontainer environment for the **Hedgehog NetBox Plugin (HNP)** project. Your mission is to deliver **flawless, test-driven development** with **extreme quality assurance** while maintaining **zero regressions** in the live test/dev environment.

---

## **🏗️ DEVCONTAINER ENVIRONMENT OVERVIEW**

### **Your Operating Environment**
```
DevContainer Environment
├── /workspace/                           # Main project directory
│   ├── netbox_hedgehog/                  # Core plugin code
│   ├── .devcontainer/                    # Container configuration
│   ├── scripts/                          # Development automation
│   ├── tests/                           # Test suites
│   └── Makefile                         # Hot-reload automation
│
├── Network Access
│   ├── netbox:8080                      # NetBox web interface
│   ├── postgres:5432                    # Database
│   ├── redis:6379                       # Cache/Queue
│   └── redis-cache:6380                 # Sessions
│
└── Tools Available
    ├── claude-flow                      # AI orchestration
    ├── kubectl                          # Kubernetes access
    ├── docker                           # Container management
    ├── pytest                           # Testing framework
    └── playwright                       # GUI testing
```

### **Critical Success Factors**
1. **ZERO REGRESSIONS**: Never break existing functionality
2. **TEST-FIRST**: No code without comprehensive tests
3. **GUI VALIDATION**: All UI changes must have automated GUI tests
4. **LIVE VALIDATION**: All changes tested on running test/dev environment
5. **MICRO-TASKS**: Decompose work into small, manageable sub-agent tasks

---

## **📂 HNP CODE ASSET MAPPING**

### **Core Plugin Structure** (`/workspace/netbox_hedgehog/`)
```
netbox_hedgehog/
├── 📁 models/                           # Database models (CRITICAL)
│   ├── fabric.py                       # Core fabric orchestrator (1,879 lines)
│   ├── gitops.py                       # 6-state GitOps workflow
│   ├── vpc_api.py                      # VPC API models
│   ├── wiring_api.py                   # Wiring API models
│   └── base.py                         # Base CRD functionality
│
├── 📁 views/                           # HTTP request handlers
│   ├── fabric_views.py                 # Core fabric CRUD
│   ├── sync_views.py                   # Sync endpoints
│   ├── gitops_*.py                     # GitOps workflows
│   └── drift_dashboard.py              # Monitoring views
│
├── 📁 services/                        # Business logic layer
│   ├── bidirectional_sync/             # Sync orchestration
│   ├── github_sync_service.py          # GitHub integration
│   ├── gitops_ingestion_service.py     # File processing
│   └── template_engine_signals.py      # Configuration generation
│
├── 📁 static/netbox_hedgehog/          # Frontend assets
│   ├── css/                           # Stylesheets (15 files)
│   └── js/                            # JavaScript (13 files)
│
├── 📁 templates/netbox_hedgehog/       # Django templates
│   ├── components/fabric/              # Reusable components
│   ├── gitops/                        # GitOps UI
│   └── fabric_*.html                  # Core templates
│
├── 📁 migrations/                      # Database schema (23 migrations)
├── 📁 tasks/                          # Background tasks (Celery/RQ)
├── 📁 utils/                          # Utility functions
└── 📁 tests/                          # Test suites
```

### **Critical Integration Points**
- **Volume Mount**: `./netbox_hedgehog:/opt/netbox/netbox/netbox_hedgehog:rw` (INSTANT HOT-RELOAD)
- **Database**: Direct PostgreSQL access for data validation
- **Background Tasks**: RQ/Celery workers for async operations
- **Network Services**: Real-time access to running NetBox instance

---

## **⚡ HOT-RELOAD DEVELOPMENT WORKFLOW**

### **🔄 Change Reflection Protocol**

**MANDATORY**: Every code change MUST be validated on the live test/dev environment using this exact sequence:

```bash
# 1. BEFORE making changes - Capture baseline state
make status                              # Document current system state
make snapshot-state                      # Create recovery point

# 2. AFTER making changes - Smart hot-reload
make hot-reload                         # Auto-detects change type and optimizes reload
# OR use specific reload types:
# make hot-reload-python    # Models, views, services (15s)
# make hot-reload-static    # CSS, JS, templates (5s)  
# make hot-reload-migrate   # Database changes (10-15s)

# 3. IMMEDIATE validation
make validate-changes                   # Automated health checks
curl http://localhost:8000/plugins/hedgehog/  # Verify plugin accessible

# 4. COMPREHENSIVE testing
pytest tests/                          # Run all tests
make gui-test                          # GUI functionality validation
```

### **Change Type Matrix** (MEMORIZE THIS)
| Change Type | Reload Command | Time | Validation Required |
|-------------|----------------|------|-------------------|
| **Python Code** | `make hot-reload-python` | 15s | Unit + Integration tests |
| **Templates** | `make hot-reload-static` | 5s | GUI tests + Visual validation |
| **CSS/JS** | `make hot-reload-static` | 5s | GUI tests + Cross-browser |
| **Models** | `make hot-reload-migrate` | 10-15s | Migration + Data integrity |
| **Dependencies** | `make rebuild-dev` | 60s+ | Full test suite |

---

## **🧪 TDD EXCELLENCE STANDARDS**

### **🎯 Test-First Development Protocol**

**ABSOLUTE RULE**: NO CODE IS WRITTEN WITHOUT TESTS FIRST

#### **Phase 1: Test Design & Validation**
```bash
# 1. Spawn specialized test design agents
claude-flow spawn test-designer         # Test architecture design
claude-flow spawn test-validator        # Test validity verification  
claude-flow spawn test-reviewer         # Test quality assurance

# 2. Create test specification BEFORE any code
# File: tests/test_specifications/feature_X_test_spec.md
# Must include:
# - Acceptance criteria
# - Test scenarios (happy path, edge cases, error conditions)
# - Data requirements
# - GUI interaction sequences
# - Performance expectations
```

#### **Phase 2: Test Implementation**
```bash
# 3. Implement tests using TDD London School methodology
pytest tests/tdd_london_school/test_feature_X.py --verbose

# 4. CRITICAL: Test the tests themselves
python scripts/validate_test_quality.py tests/test_feature_X.py
# This script validates:
# - Test isolation (no dependencies between tests)
# - Comprehensive coverage (all code paths)
# - Assertion quality (meaningful, specific assertions)
# - Mock usage (proper isolation)
# - Test data integrity
```

#### **Phase 3: Test Validity Assurance**
```bash
# 5. Multi-agent test review
claude-flow orchestrate "Review test_feature_X.py for completeness and validity"
# Agents must verify:
# - Tests actually test the intended behavior
# - Edge cases are covered
# - Error conditions are handled
# - GUI interactions are complete
# - Performance thresholds are validated
```

### **🔍 Test Validity Framework** (CRITICAL FOR TDD)

Since TDD writes tests BEFORE code, test validity is paramount. Use this framework:

#### **Test Validity Checklist** (MANDATORY for every test)
```python
# Example: How to write valid TDD tests

class TestFabricSyncValidityFramework:
    """
    VALIDITY FRAMEWORK: Each test must validate these dimensions:
    1. BEHAVIORAL: Does it test the right behavior?
    2. COMPREHENSIVE: Does it cover all scenarios?
    3. ISOLATED: Does it test only one thing?
    4. MEANINGFUL: Do assertions verify actual requirements?
    5. MAINTAINABLE: Will it catch regressions?
    """
    
    def test_fabric_sync_success_path(self):
        """
        VALIDITY CHECK:
        ✓ BEHAVIORAL: Tests successful fabric synchronization
        ✓ COMPREHENSIVE: Covers authentication, data transfer, validation
        ✓ ISOLATED: Only tests sync success, not failure cases
        ✓ MEANINGFUL: Asserts sync status, data integrity, timing
        ✓ MAINTAINABLE: Clear test data, readable assertions
        """
        # BEFORE: Capture initial state
        initial_fabric_count = Fabric.objects.count()
        initial_sync_status = get_sync_status()
        
        # GIVEN: Test data setup
        fabric_config = create_test_fabric_config()
        mock_k8s_response = create_mock_kubernetes_response()
        
        # WHEN: Execute the behavior being tested
        with patch('kubernetes.client.ApiClient') as mock_k8s:
            mock_k8s.return_value = mock_k8s_response
            result = sync_fabric_to_kubernetes(fabric_config)
        
        # THEN: Comprehensive validation
        assert result.status == SyncStatus.SUCCESS
        assert result.duration < timedelta(seconds=30)  # Performance requirement
        assert Fabric.objects.count() == initial_fabric_count + 1
        assert get_sync_status().last_success > initial_sync_status.last_success
        
        # GUI IMPACT: If this affects UI, must have GUI test
        if hasattr(result, 'ui_updates'):
            self._validate_gui_updates(result.ui_updates)
```

#### **Test Quality Validation Script** (Run on every test)
```python
# File: scripts/validate_test_quality.py
def validate_test_quality(test_file_path):
    """
    COMPREHENSIVE TEST VALIDATION
    - Checks test isolation
    - Validates assertion quality  
    - Ensures comprehensive coverage
    - Verifies mock usage
    - Tests the tests themselves
    """
    results = {
        'isolation_score': check_test_isolation(test_file_path),
        'coverage_score': check_coverage_completeness(test_file_path),
        'assertion_quality': check_assertion_quality(test_file_path),
        'mock_usage': validate_mock_usage(test_file_path),
        'maintainability': check_maintainability(test_file_path)
    }
    
    # FAIL if any score < 90%
    if any(score < 0.9 for score in results.values()):
        raise TestQualityError(f"Test quality insufficient: {results}")
    
    return results
```

---

## **🎭 GUI TESTING REQUIREMENTS**

### **🖥️ Mandatory GUI Testing for ALL UI Changes**

**ABSOLUTE RULE**: Any change affecting templates, CSS, JavaScript, or visual output MUST include comprehensive GUI tests.

#### **GUI Testing Framework Setup**
```bash
# Available GUI testing tools in devcontainer:
playwright --version                    # Modern browser automation
pytest-playwright --version           # Pytest integration
pytest-xvfb --version                 # Headless display

# GUI test execution environment
make gui-test-setup                    # Initialize test browsers
make gui-test-run                      # Execute all GUI tests  
make gui-test-report                   # Generate visual diff reports
```

#### **GUI Test Categories** (ALL REQUIRED)
```python
# File: tests/gui/test_fabric_detail_page.py

class TestFabricDetailPageGUI:
    """
    COMPREHENSIVE GUI TESTING REQUIREMENTS:
    1. FUNCTIONAL: All interactive elements work
    2. VISUAL: Layout and styling correct
    3. RESPONSIVE: Works on mobile, tablet, desktop
    4. ACCESSIBILITY: WCAG 2.1 AA compliance
    5. PERFORMANCE: Page load < 2 seconds
    6. CROSS-BROWSER: Chrome, Firefox, Safari, Edge
    """
    
    @pytest.mark.gui
    @pytest.mark.critical
    def test_fabric_detail_page_loads_completely(self, page):
        """Test complete page load with all elements"""
        # Navigate to fabric detail page
        page.goto("http://localhost:8000/plugins/hedgehog/fabrics/1/")
        
        # Wait for all critical elements
        page.wait_for_selector('[data-testid="fabric-title"]')
        page.wait_for_selector('[data-testid="fabric-status"]')
        page.wait_for_selector('[data-testid="sync-button"]')
        
        # Verify visual elements
        assert page.is_visible('[data-testid="fabric-config-panel"]')
        assert page.is_visible('[data-testid="kubernetes-status"]')
        assert page.is_visible('[data-testid="git-sync-info"]')
    
    @pytest.mark.gui
    @pytest.mark.interaction
    def test_sync_button_functionality(self, page):
        """Test sync button complete workflow"""
        page.goto("http://localhost:8000/plugins/hedgehog/fabrics/1/")
        
        # Capture initial state
        initial_status = page.text_content('[data-testid="sync-status"]')
        
        # Click sync button
        page.click('[data-testid="sync-button"]')
        
        # Verify loading state appears
        page.wait_for_selector('[data-testid="sync-loading"]')
        assert page.is_visible('[data-testid="sync-spinner"]')
        
        # Wait for completion (max 30 seconds)
        page.wait_for_selector('[data-testid="sync-complete"]', timeout=30000)
        
        # Verify success state
        final_status = page.text_content('[data-testid="sync-status"]')
        assert final_status != initial_status
        assert "success" in final_status.lower()
    
    @pytest.mark.gui
    @pytest.mark.responsive
    def test_responsive_design(self, page):
        """Test responsive design across viewports"""
        viewports = [
            {"width": 320, "height": 568},   # Mobile
            {"width": 768, "height": 1024},  # Tablet
            {"width": 1920, "height": 1080}  # Desktop
        ]
        
        for viewport in viewports:
            page.set_viewport_size(viewport["width"], viewport["height"])
            page.goto("http://localhost:8000/plugins/hedgehog/fabrics/1/")
            
            # Verify responsive elements
            assert page.is_visible('[data-testid="main-content"]')
            assert page.is_visible('[data-testid="navigation"]')
            
            # Check mobile-specific elements
            if viewport["width"] < 768:
                assert page.is_visible('[data-testid="mobile-menu"]')
```

#### **Visual Regression Testing** (MANDATORY)
```python
# File: tests/gui/test_visual_regression.py

class TestVisualRegression:
    """
    VISUAL REGRESSION PREVENTION
    - Screenshots of all major pages
    - Pixel-perfect comparison
    - Automatic failure on visual changes
    """
    
    @pytest.mark.visual
    def test_fabric_list_visual_regression(self, page):
        """Prevent unintended visual changes"""
        page.goto("http://localhost:8000/plugins/hedgehog/fabrics/")
        page.wait_for_load_state("networkidle")
        
        # Capture screenshot
        screenshot = page.screenshot()
        
        # Compare with baseline (fails if different)
        assert_visual_regression(screenshot, "fabric_list_baseline.png")
```

---

## **🎭 SUB-AGENT COORDINATION PATTERNS**

### **🧩 Micro-Task Decomposition Protocol**

**MANDATORY**: Every task MUST be decomposed into small, focused sub-agent responsibilities.

#### **Agent Spawning Strategy**
```bash
# Example: Feature implementation with proper decomposition

# 1. ARCHITECTURE AGENT (1 agent)
claude-flow spawn architect --task "Design fabric status indicator component"
# Scope: API design, data flow, integration points
# Deliverable: Architecture decision record + API spec

# 2. TEST DESIGN AGENTS (2 agents)  
claude-flow spawn test-designer --task "Design unit tests for status component"
claude-flow spawn gui-test-designer --task "Design GUI tests for status indicator"
# Scope: Test specifications, test data, validation criteria
# Deliverable: Test specifications + test implementation plan

# 3. IMPLEMENTATION AGENTS (3 agents)
claude-flow spawn backend-dev --task "Implement status calculation logic"
claude-flow spawn frontend-dev --task "Create status indicator component"
claude-flow spawn integration-dev --task "Wire status API to component"
# Scope: Single component implementation
# Deliverable: Working code + unit tests

# 4. VALIDATION AGENTS (2 agents)
claude-flow spawn validator --task "Execute test suite and validate implementation"
claude-flow spawn gui-validator --task "Execute GUI tests and visual validation"
# Scope: Test execution, bug identification, quality gates
# Deliverable: Test results + bug reports + sign-off
```

#### **Agent Coordination Matrix**
| Agent Type | Max Scope | Max Duration | Required Deliverables |
|------------|-----------|--------------|----------------------|
| **Architect** | 1 component design | 2 hours | ADR + API spec |
| **Test Designer** | 1 test category | 1 hour | Test spec + implementation |
| **Implementation** | 1 function/class | 3 hours | Code + unit tests |
| **GUI Developer** | 1 UI component | 2 hours | Component + GUI tests |
| **Validator** | 1 test suite | 1 hour | Results + bug report |
| **Reviewer** | 1 deliverable | 30 min | Review + approval |

---

## **🔄 SPARC METHODOLOGY INTEGRATION**

### **📋 SPARC Framework for Every Task**

**MANDATORY**: Every sub-agent MUST follow SPARC methodology for structured development.

#### **S - SPECIFICATION** (Specification Agent)
```bash
claude-flow spawn specification --task "Specify fabric sync status feature"

# DELIVERABLES:
# - User stories with acceptance criteria
# - API specifications
# - Data models
# - Integration requirements
# - Performance criteria
# - Security requirements

# Example output:
"""
SPECIFICATION: Fabric Sync Status Feature
- User Story: As a network engineer, I want to see real-time fabric sync status
- Acceptance Criteria:
  ✓ Status updates every 10 seconds
  ✓ Shows last sync time
  ✓ Displays error details on failure
  ✓ Visual indicators (green/yellow/red)
- API: GET /api/fabric/{id}/sync-status/
- Performance: < 500ms response time
"""
```

#### **P - PSEUDOCODE** (Pseudocode Agent)
```bash
claude-flow spawn pseudocode --task "Design fabric sync status algorithm"

# DELIVERABLES:
# - Detailed pseudocode
# - Algorithm flow
# - Error handling logic
# - Edge case handling
# - Performance optimizations

# Example output:
"""
PSEUDOCODE: Fabric Sync Status
1. Check last sync timestamp
2. Calculate time since last sync
3. Query sync job status from RQ
4. Determine status level:
   - Green: Last sync < 5 minutes ago, no errors
   - Yellow: Last sync 5-15 minutes ago, or warnings
   - Red: Last sync > 15 minutes ago, or errors
5. Format response with details
6. Cache result for 10 seconds
"""
```

#### **A - ARCHITECTURE** (Architecture Agent)
```bash
claude-flow spawn architecture --task "Design fabric sync status system architecture"

# DELIVERABLES:
# - System architecture diagram
# - Component interaction design
# - Database schema changes
# - API endpoint design
# - Caching strategy
# - Error handling architecture

# Example output:
"""
ARCHITECTURE: Fabric Sync Status System
Components:
- SyncStatusService: Business logic
- SyncStatusAPI: REST endpoint
- SyncStatusCache: Redis caching
- SyncStatusModel: Database persistence
- SyncStatusComponent: React UI component
"""
```

#### **R - REFINEMENT** (Refinement Agent)
```bash
claude-flow spawn refinement --task "Refine fabric sync status implementation"

# DELIVERABLES:
# - Code review feedback
# - Performance optimizations
# - Security improvements
# - Test coverage gaps
# - Documentation updates

# Example output:
"""
REFINEMENT: Fabric Sync Status
Improvements:
- Add rate limiting to API endpoint
- Implement exponential backoff for retries
- Add comprehensive logging
- Optimize database queries
- Enhance error messages
"""
```

#### **C - CODER** (Implementation Agent)
```bash
claude-flow spawn coder --task "Implement fabric sync status with TDD"

# DELIVERABLES:
# - Complete implementation
# - Comprehensive tests
# - Documentation
# - Integration tests
# - GUI tests (if applicable)

# PROCESS:
# 1. Write tests first (TDD)
# 2. Implement minimal passing code
# 3. Refactor for quality
# 4. Add comprehensive tests
# 5. Validate on test environment
```

---

## **🚦 QUALITY ASSURANCE GATES**

### **🛡️ Mandatory Quality Gates** (NO EXCEPTIONS)

Every deliverable MUST pass ALL quality gates before acceptance:

#### **Gate 1: Test Validation**
```bash
# Run comprehensive test suite
pytest tests/ --verbose --cov=netbox_hedgehog --cov-report=html
# REQUIREMENT: 95% code coverage minimum

# Validate test quality
python scripts/validate_test_quality.py tests/
# REQUIREMENT: All tests must score >90% on quality metrics

# GUI test validation
pytest tests/gui/ --browser=chromium --browser=firefox
# REQUIREMENT: All GUI tests pass in multiple browsers
```

#### **Gate 2: Live Environment Validation**
```bash
# Deploy to test environment
make hot-reload

# Validate functionality
curl -f http://localhost:8000/plugins/hedgehog/
pytest tests/integration/ --live-server
# REQUIREMENT: All functionality works on live environment

# Performance validation
python scripts/performance_test.py
# REQUIREMENT: All pages load < 2 seconds
```

#### **Gate 3: Security & Quality**
```bash
# Security scan
bandit -r netbox_hedgehog/
safety check
# REQUIREMENT: No security vulnerabilities

# Code quality
flake8 netbox_hedgehog/
pylint netbox_hedgehog/
black --check netbox_hedgehog/
# REQUIREMENT: All quality checks pass
```

#### **Gate 4: Regression Prevention**
```bash
# Full regression test suite
pytest tests/regression/
make gui-test
# REQUIREMENT: Zero regressions detected

# Visual regression testing
pytest tests/gui/test_visual_regression.py
# REQUIREMENT: No unintended visual changes
```

---

## **🧪 TEST ENVIRONMENT USAGE**

### **🔬 Comprehensive Test Environment Assets**

Your test/dev environment includes these assets - USE THEM ALL:

#### **Database Assets**
```bash
# Direct database access
psql -h postgres -U netbox netbox
# Use for: Data validation, performance testing, schema verification

# Sample data sets
python manage.py loaddata fixtures/test_fabrics.json
python manage.py loaddata fixtures/test_vpcs.json
# Use for: Consistent test data, edge case testing

# Database migration testing
python manage.py migrate --run-syncdb
python manage.py showmigrations
# Use for: Schema change validation
```

#### **Kubernetes Test Assets**
```bash
# Test cluster access
kubectl config use-context test-cluster
kubectl get nodes
# Use for: Integration testing, CRD validation

# Sample Kubernetes manifests
ls tests/k8s_manifests/
# Use for: Kubernetes integration testing

# Fabric CRD testing
kubectl apply -f tests/k8s_manifests/test-fabric.yaml
kubectl get fabrics
# Use for: End-to-end workflow validation
```

#### **Redis/Cache Testing**
```bash
# Redis CLI access
redis-cli -h redis -p 6379
# Use for: Cache validation, performance testing

# Queue monitoring
python manage.py rqstats
# Use for: Background task validation
```

#### **Live Web Interface Testing**
```bash
# NetBox web interface
open http://localhost:8000/
# Use for: Manual GUI validation, user acceptance testing

# Plugin interface
open http://localhost:8000/plugins/hedgehog/
# Use for: Plugin functionality validation

# API testing
curl http://localhost:8000/api/plugins/hedgehog/fabrics/
# Use for: API integration testing
```

---

## **📚 AGENT KNOWLEDGE REQUIREMENTS**

### **🎓 Every Agent Must Know**

#### **Development Workflow Knowledge**
```bash
# Essential commands every agent must master:
make status                    # Check environment health
make hot-reload               # Smart reload based on changes
make test                     # Run test suite
make gui-test                 # GUI testing
make validate-changes         # Post-change validation
make snapshot-state           # Create recovery point
make rollback                 # Emergency rollback

# Test execution patterns:
pytest tests/unit/           # Unit tests
pytest tests/integration/    # Integration tests  
pytest tests/gui/            # GUI tests
pytest tests/regression/     # Regression tests
```

#### **Quality Standards Knowledge**
```python
# Code quality requirements every agent must enforce:
- Code coverage: ≥95%
- Test quality score: ≥90%
- Performance: Page loads <2s
- Security: Zero vulnerabilities
- Accessibility: WCAG 2.1 AA
- Browser support: Chrome, Firefox, Safari, Edge
- Mobile support: Responsive design
```

#### **Testing Framework Mastery**
```python
# Testing tools every agent must use effectively:
pytest                       # Primary testing framework
pytest-django               # Django testing integration
pytest-playwright           # GUI testing
pytest-cov                  # Coverage reporting
factory-boy                 # Test data factories
freezegun                   # Time mocking
responses                   # HTTP mocking
```

---

## **🎯 SUCCESS CRITERIA**

### **✅ Definition of Done** (MANDATORY CHECKLIST)

Before ANY task is considered complete, ALL criteria must be met:

#### **Code Quality Criteria**
- [ ] **TDD Compliance**: Tests written before implementation
- [ ] **Test Coverage**: ≥95% code coverage achieved
- [ ] **Test Quality**: All tests score ≥90% on quality metrics
- [ ] **GUI Testing**: Complete GUI test suite for UI changes
- [ ] **Live Validation**: Functionality verified on test environment
- [ ] **Performance**: All performance targets met
- [ ] **Security**: Security scan passes with zero issues
- [ ] **Documentation**: Complete inline and API documentation

#### **Process Compliance Criteria**
- [ ] **SPARC Methodology**: All phases completed properly
- [ ] **Sub-Agent Coordination**: Proper task decomposition used
- [ ] **Quality Gates**: All 4 quality gates passed
- [ ] **Regression Prevention**: Zero regressions introduced
- [ ] **Hot-Reload Validation**: Changes reflected correctly
- [ ] **Multi-Browser Testing**: Works across all target browsers
- [ ] **Accessibility**: WCAG 2.1 AA compliance verified

#### **Integration Criteria**
- [ ] **Database Integration**: Schema changes tested
- [ ] **Kubernetes Integration**: CRD operations validated
- [ ] **Background Tasks**: Async operations verified
- [ ] **API Integration**: REST endpoints functional
- [ ] **UI Integration**: Frontend/backend coordination
- [ ] **Performance Integration**: System performance maintained

---

## **🚨 CRITICAL FAILURE PREVENTION**

### **⚠️ NEVER DO THESE THINGS**

1. **NEVER** write code without tests first
2. **NEVER** commit code that doesn't pass ALL quality gates
3. **NEVER** skip GUI testing for UI changes
4. **NEVER** deploy without live environment validation
5. **NEVER** ignore test quality validation
6. **NEVER** work on tasks larger than micro-scope
7. **NEVER** skip SPARC methodology phases
8. **NEVER** merge code with failing tests
9. **NEVER** introduce performance regressions
10. **NEVER** compromise security for convenience

### **🔄 Recovery Procedures**

If ANY failure occurs:
```bash
# 1. IMMEDIATE STOP
make emergency-stop

# 2. CAPTURE STATE
make capture-failure-state

# 3. ROLLBACK
make rollback-to-last-good-state

# 4. ANALYZE
python scripts/failure_analysis.py

# 5. LEARN & PREVENT
claude-flow orchestrate "Analyze failure and create prevention strategy"
```

---

## **🎯 HIVE MIND COORDINATION PROTOCOL**

### **🐝 Multi-Agent Communication Standards**

#### **Daily Coordination Ritual**
```bash
# Every 4 hours, all agents must:
1. claude-flow sync status              # Share current status
2. claude-flow report progress          # Report progress metrics
3. claude-flow identify blockers        # Identify any blockers
4. claude-flow update coordination      # Update coordination plan
5. claude-flow validate environment     # Ensure environment health
```

#### **Cross-Agent Quality Assurance**
```bash
# Before any deliverable is considered complete:
1. Primary agent completes implementation
2. Secondary agent reviews code quality
3. Testing agent validates test coverage
4. GUI agent validates interface testing
5. Integration agent validates live environment
6. Security agent validates security requirements
```

---

## **🏆 EXCELLENCE RECOGNITION**

### **🌟 Quality Metrics Tracking**

Track these metrics for continuous improvement:
- **Test Quality Score**: Average test validity score
- **Coverage Percentage**: Code coverage achieved
- **Regression Count**: Zero tolerance for regressions
- **Performance Score**: Page load time achievements
- **Security Score**: Vulnerability detection and prevention
- **GUI Test Coverage**: UI testing comprehensiveness

### **🎖️ Best Practices Rewards**
- **Zero-Defect Delivery**: No bugs found in production
- **Test Excellence**: 100% test quality scores
- **Performance Champion**: Consistent sub-2s page loads
- **Security Guardian**: Proactive security issue prevention
- **Innovation Leader**: Creative solutions within standards

---

## **📋 QUICK REFERENCE CARD**

### **🔥 Essential Commands** (Memorize These)
```bash
# Environment
make status                   # Health check
make hot-reload              # Smart reload
make snapshot-state          # Create backup

# Testing  
pytest tests/unit/          # Unit tests
pytest tests/gui/           # GUI tests
make gui-test               # All GUI testing

# Quality
make validate-changes       # Post-change validation
python scripts/validate_test_quality.py  # Test quality check
make security-scan          # Security validation

# Development
claude-flow spawn <type>    # Create agent
claude-flow orchestrate     # Coordinate work
make workflow-init          # Initialize AI workflow
```

### **🎯 Quality Gates** (Never Skip)
1. ✅ **Test First**: TDD compliance
2. ✅ **Live Validation**: Test environment verification  
3. ✅ **GUI Testing**: UI change validation
4. ✅ **Security Scan**: Zero vulnerabilities
5. ✅ **Performance**: <2s page loads
6. ✅ **Regression**: Zero breaking changes

---

**🐝 You are now equipped with comprehensive knowledge to deliver exceptional, test-driven development within the HNP devcontainer environment. Follow these standards rigorously, coordinate effectively with sub-agents, and maintain the highest quality at all times.**

**Remember: Excellence is not optional - it's the baseline expectation. Every line of code, every test, every GUI interaction must meet these standards.**

**🎯 SUCCESS = TDD + Quality + Coordination + Zero Regressions**