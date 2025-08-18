# API Design Context

## Contract-First Principles
- **OpenAPI 3.1**: Complete specification before implementation
- **Schema Validation**: 100% request/response validation
- **Version Management**: Semantic versioning with backward compatibility
- **Error Handling**: Standardized error responses with problem details

## NetBox API Patterns
- **Serializer Integration**: DRF serializers with NetBox patterns
- **ViewSet Inheritance**: Extend NetBox generic viewsets
- **Permission Classes**: Implement NetBox permission framework
- **Filtering Support**: Use django-filter with NetBox patterns

## Quality Requirements
- API contract validation with Spectral
- Multi-client compatibility testing
- Performance testing under load
- Security vulnerability assessment

## Handoff Protocol
- Validated contracts to implementation teams
- Generated client stubs for testing
- Documentation completeness verification
- Integration testing requirements defined