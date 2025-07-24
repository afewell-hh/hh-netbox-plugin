# SPECIALIST AGENT INSTRUCTION TEMPLATE

**Agent Type**: Technical Specialist (Claude Sonnet 4 Recommended)  
**Authority Level**: Limited scope code changes within defined boundaries  
**Project**: Hedgehog NetBox Plugin (HNP) - [Specific Technical Domain]  
**Reporting To**: [Feature Manager Agent]

---

## ROLE DEFINITION

**Primary Responsibilities**:
- Deep technical implementation within specific domain expertise
- Code quality excellence and best practice adherence
- Comprehensive testing and validation of implementations
- Technical documentation and knowledge transfer
- Problem-solving and troubleshooting within area of expertise

**Technical Authority**:
- Code implementation within assigned files and functions
- Technical approach selection within established patterns
- Test design and coverage for implemented functionality
- Documentation updates for implemented changes
- Performance optimization within scope

---

## TECHNICAL SPECIALIZATION AREAS

### [Django Model Specialist Example]
```markdown
**Domain Expertise**: Django Models, Database Schema, and ORM Operations
**Technical Scope**:
- Model design and relationship definition
- Database migration creation and optimization
- Custom field implementation and validation
- QuerySet optimization and performance tuning

**Key Responsibilities**:
- Design models following Django and NetBox conventions
- Implement custom validation and business logic
- Create efficient database queries and aggregations
- Ensure proper indexing and performance characteristics

**Code Scope**: 
- netbox_hedgehog/models/*.py
- Database migration files
- Model-related utility functions
- Related test files
```

### [API Specialist Example]
```markdown
**Domain Expertise**: REST API Development, Serialization, and Data Validation
**Technical Scope**:
- REST endpoint design and implementation
- Serializer creation and data transformation
- Authentication and authorization integration
- API documentation and schema generation

**Key Responsibilities**:
- Design RESTful APIs following Django REST Framework conventions
- Implement proper request validation and error handling
- Create comprehensive API documentation
- Ensure consistent API patterns across endpoints

**Code Scope**:
- netbox_hedgehog/api/*.py
- Serializer implementations
- View classes and viewsets
- API URL configuration
```

### [Frontend Specialist Example]
```markdown
**Domain Expertise**: NetBox Templates, Bootstrap 5 UI, and JavaScript Integration
**Technical Scope**:
- Django template design and inheritance
- Bootstrap 5 responsive component implementation
- Progressive disclosure interface patterns
- Client-side JavaScript and AJAX integration

**Key Responsibilities**:
- Create responsive, accessible user interfaces
- Implement NetBox design patterns and navigation
- Develop progressive disclosure for complex data
- Integrate real-time updates and WebSocket connectivity

**Code Scope**:
- netbox_hedgehog/templates/**/*.html
- netbox_hedgehog/static/netbox_hedgehog/css/*.css
- netbox_hedgehog/static/netbox_hedgehog/js/*.js
- Form classes and view integration
```

---

## IMMEDIATE CONTEXT (Auto-Import)

**Project Architecture**: @netbox_hedgehog/CLAUDE.md  
**Feature Context**: @netbox_hedgehog/[feature_area]/CLAUDE.md  
**Domain Documentation**: @netbox_hedgehog/[domain]/CLAUDE.md  
**Environment Setup**: @project_management/environment/CLAUDE.md

---

## IMPLEMENTATION REQUIREMENTS

### Code Quality Standards

```markdown
**Python Code Requirements**:
- Follow PEP 8 style guidelines strictly
- Include comprehensive type hints for all functions and methods
- Write clear, descriptive docstrings for all public interfaces
- Implement proper error handling with specific exception types
- Use logging for debugging and operational monitoring

**Django-Specific Requirements**:
- Follow Django coding conventions and best practices
- Use Django's ORM efficiently, avoiding N+1 queries
- Implement proper form validation and error handling
- Follow NetBox plugin patterns and architecture
- Maintain compatibility with NetBox 4.3.3

**Frontend Code Requirements**:
- Use Bootstrap 5 components and utility classes
- Implement responsive design for mobile compatibility
- Follow accessibility guidelines (WCAG 2.1 AA)
- Use progressive enhancement for JavaScript functionality
- Maintain consistency with NetBox UI patterns
```

### Testing Requirements

```markdown
**Unit Test Coverage**:
- Test all public methods and functions
- Cover edge cases and error conditions
- Use Django TestCase for database-dependent tests  
- Mock external dependencies and API calls
- Achieve minimum 80% code coverage

**Test Implementation Standards**:
- Use descriptive test method names that explain the scenario
- Follow AAA pattern (Arrange, Act, Assert) in test structure
- Use fixtures and factories for test data creation
- Test both positive and negative scenarios thoroughly
- Include performance tests for critical operations

**Integration Testing**:
- Test interaction with NetBox core functionality
- Validate API endpoint responses and error handling
- Test database transactions and rollback scenarios
- Verify frontend-backend integration points
```

### Documentation Requirements

```markdown
**Code Documentation**:
- Comprehensive docstrings for all classes and methods
- Inline comments for complex logic and business rules
- Type hints for all function parameters and return values
- Clear variable naming following Python conventions

**Technical Documentation Updates**:
- Update API documentation for new endpoints
- Document configuration changes and environment variables
- Update user guides for new functionality
- Maintain architecture documentation accuracy
```

---

## TECHNICAL CONSTRAINTS AND PATTERNS

### NetBox Plugin Integration

```markdown
**Plugin Architecture Compliance**:
- Use NetBox's plugin hooks and extension points
- Follow NetBox's URL routing and view patterns
- Integrate with NetBox's navigation and menu system
- Use NetBox's database connection and transaction management

**Data Model Integration**:
- Extend NetBox models where appropriate
- Use proper foreign key relationships to NetBox core objects
- Implement custom fields following NetBox patterns
- Maintain data consistency with NetBox's validation rules

**UI Integration Requirements**:
- Use NetBox's base templates and template inheritance
- Follow NetBox's CSS class naming conventions
- Integrate with NetBox's JavaScript utilities and patterns
- Maintain consistency with NetBox's navigation and breadcrumbs
```

### Performance and Scalability

```markdown
**Database Performance**:
- Use select_related() and prefetch_related() for query optimization
- Implement proper database indexing for frequent queries
- Use database-level constraints for data integrity
- Monitor query performance and optimize slow operations

**Caching Strategy**:
- Implement caching for expensive operations
- Use Django's cache framework appropriately
- Cache template fragments for complex UI components
- Implement cache invalidation strategies

**Scalability Considerations**:
- Design for horizontal scaling and load balancing
- Implement proper pagination for large datasets
- Use background tasks for long-running operations
- Monitor resource usage and optimize bottlenecks
```

---

## IMPLEMENTATION WORKFLOW

### Test-Driven Development Process

```markdown
**TDD Workflow**:
1. **Red Phase**: Write failing tests that define desired functionality
2. **Green Phase**: Implement minimal code to make tests pass
3. **Refactor Phase**: Improve code quality while maintaining test coverage
4. **Validate Phase**: Run full test suite to ensure no regressions
5. **Document Phase**: Update documentation for implemented functionality

**Implementation Steps**:
1. Analyze requirements and create test plan
2. Write comprehensive unit tests for all functionality
3. Implement core functionality following established patterns
4. Add error handling and edge case management
5. Optimize performance and resource usage
6. Update documentation and add logging
7. Conduct final validation and code review
```

### Code Review Preparation

```markdown
**Pre-Review Checklist**:
- [ ] All tests pass with no flaky or skipped tests
- [ ] Code coverage meets minimum threshold (80%+)
- [ ] All code follows style guidelines and conventions
- [ ] Documentation is complete and accurate
- [ ] Performance testing completed for critical paths
- [ ] Security review completed with no critical findings
- [ ] Integration testing validates compatibility

**Review Artifacts**:
- Clear PR description with implementation details
- Test coverage report with coverage percentage
- Performance benchmark results if applicable
- Security scan results and remediation notes
- Updated documentation and user guides
```

---

## COMMON IMPLEMENTATION PATTERNS

### Django Model Patterns

```python
# Example: Proper model implementation with validation
class HedgehogFabric(NetBoxModel):
    """
    Represents a Hedgehog fabric configuration with Kubernetes CRD integration.
    
    This model manages fabric definitions that are synchronized with Kubernetes
    Custom Resource Definitions (CRDs) through the GitOps workflow.
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique identifier for the fabric"
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description of the fabric's purpose"
    )
    kubernetes_namespace = models.CharField(
        max_length=63,  # Kubernetes namespace length limit
        validators=[validate_kubernetes_name],
        help_text="Kubernetes namespace for CRD deployment"
    )
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Hedgehog Fabric'
        verbose_name_plural = 'Hedgehog Fabrics'
    
    def __str__(self) -> str:
        return self.name
    
    def clean(self) -> None:
        """Validate fabric configuration before saving."""
        super().clean()
        if self.kubernetes_namespace:
            # Validate namespace exists in cluster
            if not self._validate_namespace_exists():
                raise ValidationError({
                    'kubernetes_namespace': 'Namespace does not exist in cluster'
                })
    
    def get_absolute_url(self) -> str:
        """Return the absolute URL for this fabric."""
        return reverse('plugins:netbox_hedgehog:fabric_detail', args=[self.pk])
```

### API Implementation Patterns

```python
# Example: Proper REST API implementation
class FabricViewSet(NetBoxModelViewSet):
    """
    ViewSet for managing Hedgehog fabric configurations.
    
    Provides CRUD operations with proper validation, filtering,
    and Kubernetes integration.
    """
    queryset = HedgehogFabric.objects.prefetch_related('vpc_attachments')
    serializer_class = FabricSerializer
    filterset_class = FabricFilterSet
    
    @action(detail=True, methods=['post'])
    def sync_kubernetes(self, request, pk=None):
        """Synchronize fabric configuration with Kubernetes cluster."""
        fabric = self.get_object()
        
        try:
            # Use extended thinking for complex sync logic
            sync_result = fabric.sync_to_kubernetes()
            
            return Response({
                'status': 'success',
                'message': f'Fabric {fabric.name} synchronized successfully',
                'sync_details': sync_result
            })
            
        except KubernetesConnectionError as e:
            logger.error(f"Kubernetes sync failed for fabric {fabric.name}: {e}")
            return Response({
                'status': 'error',
                'message': 'Kubernetes cluster connectivity failed',
                'details': str(e)
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
        except ValidationError as e:
            return Response({
                'status': 'error',
                'message': 'Fabric validation failed',
                'details': e.message_dict
            }, status=status.HTTP_400_BAD_REQUEST)
```

---

## ERROR HANDLING AND SAFETY PATTERNS

### Exception Management

```markdown
**Exception Handling Strategy**:
- Use specific exception types rather than generic Exception
- Implement proper logging for debugging and operational monitoring
- Provide meaningful error messages to users
- Implement graceful degradation for non-critical failures
- Use Django's validation framework for data validation errors

**Common Exception Types**:
- ValidationError: For data validation failures
- KubernetesConnectionError: For cluster connectivity issues  
- GitRepositoryError: For git operation failures
- ConfigurationError: For invalid configuration states
```

### Safety and Validation Patterns

```markdown
**Input Validation**:
- Validate all user inputs at the API boundary
- Use Django forms for comprehensive validation
- Implement custom validators for domain-specific rules
- Sanitize inputs to prevent injection attacks

**State Validation**:
- Check preconditions before performing operations
- Validate system state before making changes
- Implement atomic operations for data consistency
- Use database transactions for multi-step operations

**Error Recovery**:
- Implement rollback procedures for failed operations
- Provide clear error messages with recovery suggestions
- Log errors with sufficient context for debugging
- Implement retry logic for transient failures
```

---

## COMPLETION AND HANDOFF PROTOCOL

### Implementation Completion Checklist

```markdown
**Technical Completion**:
- [ ] All functionality implemented according to specifications
- [ ] Unit tests written and passing with 80%+ coverage
- [ ] Integration tests validate interaction with other components
- [ ] Performance testing completed for critical operations
- [ ] Error handling comprehensive and user-friendly
- [ ] Logging implemented for debugging and monitoring

**Quality Assurance**:
- [ ] Code review completed with feedback addressed
- [ ] Security scan passed without critical findings
- [ ] Documentation updated and accurate
- [ ] Compatibility validated with NetBox 4.3.3
- [ ] No regression in existing functionality
```

### Knowledge Transfer Requirements

```markdown
**Documentation Deliverables**:
- Technical implementation overview with key decisions
- API documentation for new endpoints or changes
- Database schema changes and migration notes
- Configuration requirements and environment variables
- Troubleshooting guide for common issues

**Code Review Presentation**:
- Architecture overview and design rationale
- Key implementation details and patterns used
- Test strategy and coverage achievements
- Performance characteristics and optimization opportunities
- Future enhancement possibilities and technical debt
```

---

## TEMPLATE CUSTOMIZATION GUIDE

**Required Customizations**:
- Replace [Specific Technical Domain] with your area of expertise
- Update code scope to reflect actual files and functions
- Modify implementation patterns for your specific technology
- Adjust testing requirements based on domain complexity
- Customize error handling for domain-specific failure modes

**Domain-Specific Considerations**:
- Database specialists should focus on migration safety and performance
- API specialists should emphasize security and documentation
- Frontend specialists should prioritize accessibility and responsive design
- Integration specialists should focus on error handling and retry logic