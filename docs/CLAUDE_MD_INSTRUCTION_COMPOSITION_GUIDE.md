# CLAUDE.md Instruction Composition Style Guide

## Core Composition Principles

### 1. Emoji-First Priority System
```markdown
🚨 = CRITICAL/MANDATORY (immediate action required)
⚠️ = IMPORTANT WARNING (proceed with caution) 
🔴 = HIGH PRIORITY (complete first)
⚡ = PERFORMANCE CRITICAL (affects speed/efficiency)
🎯 = KEY TARGET (focus area)
✅ = CORRECT APPROACH (do this)
❌ = FORBIDDEN (never do this)
```

### 2. Header Composition Formula
```markdown
## [Emoji] [INTENSITY]: [Category/Topic]
### [Emoji] [Action/Rule Type]: [Specific Instruction]
```

**Examples**:
- `## 🚀 CRITICAL: Parallel Execution & Batch Operations`
- `### 🚨 MANDATORY RULE #1: BATCH EVERYTHING`
- `### ⚡ THE GOLDEN RULE OF SWARMS`

### 3. Instruction Intensity Markers
```markdown
**MANDATORY**: [Non-negotiable requirement]
**CRITICAL**: [System-breaking if ignored]
**IMPORTANT**: [Strongly recommended]
**NEVER**: [Absolutely forbidden]
**ALWAYS**: [Without exception]
**MUST**: [Required for functionality]
```

## Instruction Templates

### Template 1: Critical Rule Declaration
```markdown
### 🚨 CRITICAL: [Rule Category]

**MANDATORY**: [Core requirement statement]

1. **[ACTION VERB]** [specific requirement]
2. **[ACTION VERB]** [specific requirement]  
3. **[ACTION VERB]** [specific requirement]

**Key Principle:**
[Explanatory statement with reasoning]
```

### Template 2: Correct vs Wrong Pattern
```markdown
### [Emoji] [Topic]

**✅ CORRECT - [Description]:**
```[language]
[Good example code/approach]
```

**❌ WRONG - [Description]:**
```[language]
[Bad example code/approach]
// [Explanation of why it's wrong]
```
```

### Template 3: Performance-Focused Instruction
```markdown
### ⚡ [Performance Area]

**[X.X]x speed improvement** when following this pattern:

1. **[Optimization technique]** - [benefit description]
2. **[Optimization technique]** - [benefit description]

**Performance Impact:**
- [Metric] improvement
- [Specific benefit]
```

### Template 4: Tool Integration Pattern
```markdown
### [Emoji] [Tool Category]

**[Tool Purpose]:**
- `[tool_name]` - [Brief description]
- `[tool_name]` - [Brief description]

**Usage Pattern:**
```[language]
[Example usage with parameters]
```
```

## Composition Rules

### 1. Information Hierarchy
1. **Priority Declaration** (CRITICAL/MANDATORY/etc.)
2. **Core Rule Statement** (What must be done)
3. **Specific Requirements** (How to do it)
4. **Examples** (Demonstrations)
5. **Reasoning** (Why it matters)

### 2. Clarity Techniques
- **Front-load importance**: Critical info first
- **Use imperatives**: Direct commands, not suggestions
- **Specific tools/parameters**: Exact technical details
- **Immediate applicability**: Ready-to-use examples

### 3. Emphasis Patterns
```markdown
**ALL CAPS** = Absolute requirements
**Title Case** = Important concepts  
**NEVER/ALWAYS** = Strict rules
`inline code` = Technical references
```

### 4. List Formatting Rules
- **Numbered lists**: For sequential steps
- **Bullet lists**: For parallel/equal items
- **Tree structures**: For hierarchical status
- **Mixed format**: When showing relationships

### 5. Code Block Guidelines
- **Language specification**: Always include
- **Comments in examples**: Explain non-obvious parts
- **Real parameters**: Use actual values, not placeholders
- **Complete examples**: Copy-paste ready

## Content Organization Patterns

### 1. Section Flow Template
```markdown
## [Major Feature Category]

### [Priority Level]: [Core Rule]
[Rule details with requirements]

### [Implementation Guidelines]  
[How-to information]

### [Examples]
[Practical demonstrations]

### [Performance/Benefits]
[Why this approach matters]
```

### 2. Cross-Reference Strategy
- **Tool definitions** → **Usage examples**
- **Rules** → **Practical applications** 
- **Problems** → **Specific solutions**
- **Concepts** → **Implementation details**

### 3. Progressive Detail Pattern
1. **Overview** (What and why)
2. **Requirements** (Must-do items)
3. **Implementation** (How-to steps)
4. **Examples** (Real usage)
5. **Advanced** (Optimization tips)

## Writing Style Rules

### 1. Voice and Tone
- **Imperative mood**: "Use this" not "You should use this"
- **Active voice**: "Claude Code handles" not "Files are handled by Claude Code"
- **Urgent tone**: Emphasize speed and efficiency
- **Technical precision**: Exact tool names and parameters

### 2. Language Patterns
```markdown
✅ DO: "MUST use BatchTool for ALL operations"
❌ AVOID: "It's recommended to use BatchTool"

✅ DO: "NEVER send multiple messages"  
❌ AVOID: "Try not to send multiple messages"

✅ DO: "2.8-4.4x speed improvement"
❌ AVOID: "Significant performance gains"
```

### 3. Technical Reference Format
- **Tool names**: `mcp__ruv-swarm__tool_name`
- **Parameters**: `{"param": "value"}`
- **Commands**: `npx command --flag value`
- **File paths**: `path/to/file.ext`

## Optimization Techniques

### 1. Information Density
- **High concept-to-word ratio**: Pack meaning efficiently
- **Eliminate redundancy**: Say it once, reference elsewhere
- **Visual shortcuts**: Emoji for quick scanning
- **Structured templates**: Reusable patterns

### 2. Scanning Optimization  
- **Emoji navigation**: Quick visual finding
- **Header hierarchy**: Clear information levels
- **Bold keywords**: Important terms stand out
- **Code differentiation**: Easy to spot examples

### 3. Action Orientation
- **Every section actionable**: Clear next steps
- **Specific directives**: Exact requirements
- **Example-rich**: Show don't just tell
- **Tool-focused**: Direct usage instructions

## Quality Checklist

### Content Review
- [ ] Priority clearly marked with emoji
- [ ] Mandatory vs optional clearly distinguished  
- [ ] Tools referenced with exact names
- [ ] Examples are copy-paste ready
- [ ] Performance benefits quantified
- [ ] Cross-references maintain consistency

### Format Review
- [ ] Headers follow emoji + intensity pattern
- [ ] Code blocks have language specification
- [ ] Lists use appropriate numbering/bullets
- [ ] Emphasis uses established bold patterns
- [ ] Visual elements aid scanning

### Effectiveness Review
- [ ] Instructions are immediately actionable
- [ ] Technical details are precise
- [ ] Examples demonstrate real usage
- [ ] Performance impact is clear
- [ ] Integration with existing patterns maintained