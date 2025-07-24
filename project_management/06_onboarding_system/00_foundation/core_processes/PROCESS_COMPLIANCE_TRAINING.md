# Process Compliance Training - Build Into Agent DNA

**GOAL**: Make git commits, testing, and documentation as natural as breathing.

## Git Workflow Muscle Memory

### Feature Branch Pattern (NEVER work on main)
```bash
# Start every task this way:
git checkout main
git pull origin main  
git checkout -b feature/task-description

# Work pattern:
# ... make changes ...
git add .
git status                    # Always verify what you're committing
git commit -m "clear description of what changed and why"
git push origin feature/task-description
```

### Commit Message Standards
- **Format**: "verb: clear description of change"  
- **Examples**:
  - `feat: add VPC peering validation to Django model`
  - `fix: resolve CRD sync race condition in kubernetes_sync.py`
  - `docs: update README with new environment setup steps`
  - `test: add integration tests for fabric creation API`

### Branch Naming Conventions
- **Features**: `feature/description-of-work`
- **Fixes**: `fix/issue-description`  
- **Documentation**: `docs/update-description`
- **Testing**: `test/test-description`

## Testing as Core Behavior

### Test-First Development (TDD Required)
1. **Write Test**: Create failing test that defines expected behavior
2. **Implement**: Write minimal code to make test pass
3. **Refactor**: Improve code while keeping tests green
4. **Validate**: Run full test suite before committing

### Testing Commands (Memorize These)
```bash
# Run all tests
python -m pytest

# Run specific test file  
python -m pytest netbox_hedgehog/tests/test_models.py

# Run with coverage
python -m pytest --cov=netbox_hedgehog

# Run tests in parallel (faster)
python -m pytest -n auto
```

### Test Categories & Requirements
- **Unit Tests**: Every new function/method requires unit test
- **Integration Tests**: API endpoints require integration testing
- **Model Tests**: Django model changes require model testing
- **UI Tests**: Template changes require manual validation

### Test Failure Response Protocol
1. **Never ignore failing tests** - they indicate real problems
2. **Understand the failure** - read error messages carefully  
3. **Fix the root cause** - don't just make tests pass
4. **Run full suite** - ensure fix doesn't break other tests
5. **Escalate if stuck** - don't spend hours debugging alone

## Documentation Integration

### README Maintenance (Keep Current)
- **New Features**: Add section explaining feature and usage
- **API Changes**: Update API documentation examples
- **Environment Changes**: Update setup instructions immediately
- **Dependencies**: Document new requirements or version changes

### Code Documentation Standards
- **Minimal Comments**: Only complex business logic needs comments
- **Docstrings**: Public functions require clear docstrings
- **Type Hints**: Use Python type hints for better IDE support
- **Examples**: Include usage examples for complex functions

### CLAUDE.md External Memory Maintenance
- **Project State**: Keep CLAUDE.md files current with project reality
- **Environment Changes**: Update environment documentation immediately
- **Process Updates**: Document new procedures as they're established
- **Reference Accuracy**: Ensure @references point to correct files

## Quality Assurance Mindset

### Definition of Done Checklist
Every task completion requires:
- [ ] **Code Quality**: Follows project conventions and standards
- [ ] **Testing**: All tests pass, new code has appropriate tests
- [ ] **Documentation**: README/docs updated for any user-facing changes
- [ ] **Git Hygiene**: Clean commit history with descriptive messages
- [ ] **Manual Validation**: Changes work as expected in development environment

### Code Review Preparation
- **Self-Review**: Review your own changes before requesting review
- **Test Coverage**: Ensure new code has adequate test coverage
- **Documentation**: Include any necessary documentation updates
- **Description**: Write clear PR description explaining changes and rationale

### Continuous Integration Awareness
- **Pre-commit Hooks**: Understand and respect automated checks
- **CI/CD Pipeline**: Know what automated tests run on PR creation
- **Build Status**: Monitor build status and fix failures immediately
- **Deployment Impact**: Consider how changes affect deployed systems

## Escalation and Communication

### When to Escalate (Don't Suffer in Silence)
- **Technical Blockers**: Stuck on technical issue for >30 minutes
- **Test Failures**: Cannot resolve failing tests after reasonable effort
- **Environment Issues**: Development environment not working as expected
- **Architecture Questions**: Unsure about design decisions or patterns
- **Data Safety**: Any risk of data loss or corruption

### How to Escalate Effectively
1. **Describe Problem**: Clear description of what you're trying to do
2. **Show Attempts**: What you've tried and what happened
3. **Specific Ask**: What specific help you need
4. **Context**: Share relevant code, error messages, or logs
5. **Urgency**: Indicate timeline and impact of blocker

### Communication Standards
- **Status Updates**: Proactive communication about progress and blockers
- **Documentation**: Write things down so others can follow your work
- **Knowledge Sharing**: Share solutions to problems others might face
- **Respectful Feedback**: Give and receive feedback constructively

## Process Automation

### Pre-commit Setup (Automated Quality)
```bash
# Install pre-commit hooks (if available)
pre-commit install

# Run pre-commit manually  
pre-commit run --all-files
```

### IDE Integration
- **Linting**: Configure editor for real-time code quality feedback
- **Testing**: Set up test runner integration for immediate feedback
- **Git Integration**: Use IDE git features for better workflow
- **Debugging**: Configure debugger for effective troubleshooting

### Workflow Optimization
- **Aliases**: Create git aliases for common commands
- **Scripts**: Automate repetitive tasks with simple scripts
- **Templates**: Use templates for common file types
- **Shortcuts**: Learn keyboard shortcuts for development tools

**COMPLIANCE ACHIEVED**: Agent demonstrates automatic git workflow, testing integration, documentation maintenance, and appropriate escalation behavior.

**VALIDATION**: Agent completes a simple feature addition following all process requirements without prompting.