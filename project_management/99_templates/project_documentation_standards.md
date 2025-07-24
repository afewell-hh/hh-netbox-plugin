# Project Documentation Standards

**Purpose**: Ensure consistent, high-quality documentation across the HNP project.

## Document Structure

### Required Sections
1. **Header**: Title, metadata, status
2. **Purpose**: Clear statement of document intent
3. **Content**: Organized with clear headings
4. **Footer**: Update history, references

### Metadata Format
```markdown
**Document Type**: [Type]  
**Author**: [Agent Role]  
**Date**: [YYYY-MM-DD]  
**Status**: [Draft|Review|Approved|Deprecated]  
**Version**: [X.Y]
```

## Writing Guidelines

### Clarity
- Use simple, direct language
- Define acronyms on first use
- Include examples for complex concepts
- Avoid ambiguous terms

### Formatting
- **Headings**: Use proper hierarchy (# ## ###)
- **Lists**: Use bullets for unordered, numbers for ordered
- **Code**: Use backticks for inline, fenced blocks for multi-line
- **Tables**: Include headers and alignment
- **Emphasis**: Bold for important, italic for emphasis

### Content Rules
- Keep paragraphs short (3-5 sentences)
- Use active voice
- Include purpose for each section
- Provide actionable information

## File Naming

### Convention
`[category]_[description]_[date].md`

### Examples
- `architecture_api_design_20250723.md`
- `sprint_planning_week27_20250723.md`
- `decision_database_migration_20250723.md`

## Version Control

### Commit Messages
```
docs: [action] [component] [description]

Example:
docs: update api specification for CRD endpoints
```

### Change Tracking
- Major changes require version bump
- Include change summary in document
- Preserve historical versions in archive

## Quality Checklist

Before finalizing any document:

- [ ] Clear purpose stated
- [ ] Proper formatting applied
- [ ] All sections complete
- [ ] Examples included where helpful
- [ ] Links and references verified
- [ ] Spelling and grammar checked
- [ ] Metadata updated
- [ ] Version incremented if needed

## Document Types

### Technical Documentation
- Architecture specifications
- API documentation
- Design documents
- Integration guides

### Project Management
- Sprint plans
- Status reports
- Risk assessments
- Retrospectives

### Process Documentation
- Workflows
- Standards
- Guidelines
- Procedures

## Maintenance

- **Review Frequency**: Quarterly for standards, as-needed for content
- **Archive Policy**: Move outdated docs to history after 6 months
- **Update Triggers**: Process changes, tool updates, lessons learned