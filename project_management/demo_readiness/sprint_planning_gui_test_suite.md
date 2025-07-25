# Sprint Planning: GUI Test Suite for Demo Validation

**Sprint Duration**: July 24-30, 2025 (1 week)  
**Sprint Number**: Demo Readiness Sprint 1  
**Focus Area**: Lightweight GUI test suite for management demo validation

## Sprint Goals

1. Create lightweight test runner framework that executes in < 2 minutes
2. Implement comprehensive test coverage for all demo workflows
3. Enable agents to run tests for regression prevention

## Success Criteria

- [ ] Test suite validates all demo workflows in < 2 minutes
- [ ] Agents can run tests to verify no regressions
- [ ] CEO has confidence management demo will work perfectly
- [ ] No delays caused by discovering new issues
- [ ] Clear pass/fail output for agent usage

## Planned Work Items

### High Priority (Days 1-2)
| Task ID | Description | Specialist | Days | Status |
|---------|-------------|----------|----------|---------|
| ARCH-01 | Design lightweight test runner framework | Test Architecture | 1 | Planned |
| ARCH-02 | Create test discovery and execution system | Test Architecture | 0.5 | Planned |
| ARCH-03 | Implement clear pass/fail reporting | Test Architecture | 0.5 | Planned |
| ARCH-04 | Build agent-friendly CLI interface | Test Architecture | 0.5 | Planned |
| ARCH-05 | Ensure < 2 minute execution time | Test Architecture | 0.5 | Planned |

### High Priority (Days 3-4)
| Task ID | Description | Specialist | Days | Status |
|---------|-------------|----------|----------|---------|
| TEST-01 | Implement page load validation tests | GUI Testing | 0.5 | Planned |
| TEST-02 | Create workflow tests for demo scenarios | GUI Testing | 1 | Planned |
| TEST-03 | Build "Test Connection" button tests | GUI Testing | 0.5 | Planned |
| TEST-04 | Validate "Sync from Git" functionality | GUI Testing | 0.5 | Planned |
| TEST-05 | Test CRD CRUD operations through GUI | GUI Testing | 0.5 | Planned |

### High Priority (Days 5-6)
| Task ID | Description | Specialist | Days | Status |
|---------|-------------|----------|----------|---------|
| INT-01 | Integrate with NetBox Docker environment | Integration | 0.5 | Planned |
| INT-02 | Create test data setup/teardown | Integration | 0.5 | Planned |
| INT-03 | Build agent usage documentation | Integration | 0.5 | Planned |
| INT-04 | Implement CI/CD hooks (optional) | Integration | 0.25 | Planned |
| INT-05 | Validate regression detection works | Integration | 0.25 | Planned |

### Day 7 - Validation and Handoff
| Task ID | Description | Responsible | Days | Status |
|---------|-------------|----------|----------|---------|
| VAL-01 | Run complete test suite validation | Manager | 0.25 | Planned |
| VAL-02 | CEO demonstration and feedback | Manager | 0.25 | Planned |
| VAL-03 | Final documentation updates | Manager | 0.25 | Planned |
| VAL-04 | Handoff to maintenance team | Manager | 0.25 | Planned |

## Dependencies

- NetBox Docker environment must be running and accessible
- All 12 CRD types currently working in GUI (validated)
- GitOps sync functionality recently fixed and operational
- Access to test Kubernetes cluster for integration testing

## Risks and Mitigation

| Risk | Impact | Probability | Mitigation |
|------|---------|------------|------------|
| Scope creep - finding new bugs | High | Medium | Test only known working features |
| Over-engineering test framework | Medium | Medium | Keep it simple, focus on demo needs |
| Tests too slow for regular use | High | Low | 2-minute target, optimize constantly |
| False positives failing good code | High | Low | Test current state as baseline |

## Resources

- **Team Capacity**: 3 specialists x 2 days each = 6 specialist-days
- **Manager Overhead**: 1 day for coordination and validation
- **Total Sprint Capacity**: 7 days
- **Planned Utilization**: 90% (buffer for coordination)

## Definition of Done

- [ ] All demo workflows have test coverage
- [ ] Tests run in < 2 minutes total
- [ ] Clear pass/fail output for agents
- [ ] No false positives on current functionality
- [ ] Agent documentation complete
- [ ] CEO validates demo confidence improved
- [ ] Test suite integrated with HNP environment
- [ ] All tests passing on current codebase

## Test Coverage Requirements

### Required Demo Workflows to Test:
1. **NetBox Plugin Navigation**
   - Plugin appears in NetBox menu
   - All sections accessible
   
2. **Fabric Management Pages**
   - List view loads correctly
   - Detail view shows all fields
   
3. **All 12 CRD Types Display**
   - VPC API types (6): VPCPeering, VPCAttachment, IPv4Namespace, Connection, SwitchPort, Location
   - Wiring API types (6): Switch, ServerFacingConnector, FabricLink, Fabric, ConnectionRequirement, PortGroup
   
4. **Test Connection Button**
   - Button appears on Fabric detail page
   - Click triggers connection test
   - Success/failure message displays
   
5. **Sync from Git Attribution**
   - "Sync from Git" button visible
   - CRDs show "From Git" status
   - git_file_path populated correctly
   
6. **CRD Create/Edit Forms**
   - Forms load without errors
   - Validation works correctly
   - Save operations succeed

## Daily Coordination Schedule

**Days 1-2**: Test Architecture Specialist
- Morning: Framework design review
- Afternoon: Implementation progress check
- End of day: Handoff preparation for GUI Testing

**Days 3-4**: GUI Testing Specialist  
- Morning: Test implementation kickoff
- Afternoon: Coverage validation
- End of day: Integration readiness check

**Days 5-6**: Integration Specialist
- Morning: Environment integration
- Afternoon: Agent usage validation
- End of day: Complete suite testing

**Day 7**: Manager Validation
- Morning: Full suite execution
- Afternoon: CEO demo and feedback
- End of day: Handoff complete

## Notes

- Focus on regression prevention, not bug discovery
- Test framework should be extensible for future use
- Agent-friendly means single command execution
- Performance is critical - must stay under 2 minutes
- Documentation should include examples of agent usage