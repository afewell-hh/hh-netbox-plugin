# MEMORY-AWARE TASK ASSESSMENT ALGORITHM

**Algorithm Type**: Task Complexity vs Agent Capacity Assessment  
**Purpose**: Prevent memory overload-induced false completion syndrome  
**Input Scale**: 1-5 complexity scale with agent memory capacity matching  
**Output**: Go/No-Go decision with task decomposition recommendations  

---

## ALGORITHM OVERVIEW

### Core Problem Addressed
- **100% false completion rate** in complex projects due to memory overload
- **No systematic method** for matching task complexity to agent capacity
- **Repeated failure loops** from assigning impossible tasks to single agents

### Algorithm Logic
```
IF (Task_Complexity > Agent_Memory_Capacity) THEN
    RETURN Task_Decomposition_Required
ELSE IF (Task_Complexity == Agent_Memory_Capacity) THEN  
    RETURN Proceed_With_External_Memory_Support
ELSE
    RETURN Proceed_Direct_Assignment
```

---

## STEP-BY-STEP ASSESSMENT ALGORITHM

### Phase 1: Task Complexity Assessment

#### Step 1.1: Information Density Analysis
**Algorithm**: Count discrete information elements requiring simultaneous retention

```markdown
COMPLEXITY_SCORE = 0

FOR EACH requirement IN task_requirements:
    IF requirement.dependencies > 0:
        COMPLEXITY_SCORE += requirement.dependencies * 0.5
    COMPLEXITY_SCORE += 1

FOR EACH context_item IN required_context:
    COMPLEXITY_SCORE += context_item.complexity_weight

INITIAL_COMPLEXITY = COMPLEXITY_SCORE
```

**Implementation Checklist**:
- [ ] Count number of discrete requirements (each = +1 point)
- [ ] Count interdependencies between requirements (each = +0.5 points)  
- [ ] Count context elements agent must retain (each = variable weight)
- [ ] Sum total for Initial Complexity Score

#### Step 1.2: Cognitive Load Calculation
**Algorithm**: Assess mental processing requirements

```markdown
COGNITIVE_LOAD = 0

# Decision Points Assessment
FOR EACH decision_point IN task_flow:
    IF decision_point.options > 2:
        COGNITIVE_LOAD += (decision_point.options - 2) * 0.3
    COGNITIVE_LOAD += 0.5

# Context Switching Assessment  
FOR EACH context_switch IN task_execution:
    COGNITIVE_LOAD += 0.8

# Validation Complexity Assessment
FOR EACH validation_step IN required_validation:
    COGNITIVE_LOAD += validation_step.complexity_factor

FINAL_COGNITIVE_LOAD = COGNITIVE_LOAD
```

**Implementation Checklist**:
- [ ] Count decision points with >2 options (each extra option = +0.3 points)
- [ ] Count required context switches (each = +0.8 points)
- [ ] Assess validation complexity (variable based on validation type)
- [ ] Sum for Final Cognitive Load Score

#### Step 1.3: Memory Persistence Requirements
**Algorithm**: Calculate working memory duration needs

```markdown
MEMORY_PERSISTENCE = 0

FOR EACH information_element IN task_information:
    retention_duration = information_element.required_retention_time
    information_complexity = information_element.complexity_level
    
    MEMORY_PERSISTENCE += (retention_duration * information_complexity) / 100

# External Reference Availability Assessment
external_reference_reduction = count_available_external_references() * 0.2
MEMORY_PERSISTENCE = max(0, MEMORY_PERSISTENCE - external_reference_reduction)

FINAL_MEMORY_PERSISTENCE = MEMORY_PERSISTENCE
```

**Implementation Checklist**:
- [ ] Estimate how long agent must retain each information element
- [ ] Assess complexity of each information element (1-5 scale)
- [ ] Calculate persistence burden score
- [ ] Reduce score based on available external references
- [ ] Finalize Memory Persistence Score

#### Step 1.4: Complexity Scale Assignment
**Algorithm**: Convert scores to 1-5 complexity scale

```markdown
COMPLEXITY_FACTORS = [
    INITIAL_COMPLEXITY,
    FINAL_COGNITIVE_LOAD, 
    FINAL_MEMORY_PERSISTENCE
]

WEIGHTED_COMPLEXITY = (
    INITIAL_COMPLEXITY * 0.4 +
    FINAL_COGNITIVE_LOAD * 0.4 +
    FINAL_MEMORY_PERSISTENCE * 0.2
)

IF WEIGHTED_COMPLEXITY <= 2.0:
    TASK_COMPLEXITY = 1  # Simple
ELSE IF WEIGHTED_COMPLEXITY <= 4.0:
    TASK_COMPLEXITY = 2  # Moderate
ELSE IF WEIGHTED_COMPLEXITY <= 6.0:
    TASK_COMPLEXITY = 3  # Complex
ELSE IF WEIGHTED_COMPLEXITY <= 8.0:
    TASK_COMPLEXITY = 4  # Very Complex
ELSE:
    TASK_COMPLEXITY = 5  # Extremely Complex
```

**Final Complexity Assessment**:
- **1 - Simple**: Single focus, minimal dependencies, <2 hours
- **2 - Moderate**: 2-3 focus areas, some dependencies, 2-4 hours  
- **3 - Complex**: Multiple focus areas, significant dependencies, 4-8 hours
- **4 - Very Complex**: Many focus areas, complex dependencies, 8-16 hours
- **5 - Extremely Complex**: Overwhelming focus areas, intricate dependencies, >16 hours

---

### Phase 2: Agent Memory Capacity Assessment

#### Step 2.1: Agent Type Memory Baselines
**Algorithm**: Assign base memory capacity by agent specialization

```markdown
AGENT_MEMORY_BASELINES = {
    "coordinator": 3,          # Can handle moderate coordination
    "analyst": 4,              # Higher analytical capacity
    "optimizer": 2,            # Focused optimization tasks
    "architect": 4,            # Complex system design
    "researcher": 3,           # Research and investigation  
    "coder": 2,                # Implementation focus
    "tester": 2,               # Testing and validation
    "reviewer": 3,             # Review and assessment
    "specialist": 3,           # Domain-specific expertise
    "documenter": 2,           # Documentation creation
    "monitor": 2               # Monitoring and tracking
}

BASE_MEMORY_CAPACITY = AGENT_MEMORY_BASELINES[agent_type]
```

#### Step 2.2: Context Load Assessment
**Algorithm**: Adjust capacity based on existing context burden

```markdown
CURRENT_CONTEXT_LOAD = 0

# Active Project Context
FOR EACH active_project IN agent_workspace:
    CURRENT_CONTEXT_LOAD += active_project.complexity_level * 0.3

# Required Domain Knowledge
FOR EACH domain IN required_expertise:
    IF domain NOT IN agent_existing_knowledge:
        CURRENT_CONTEXT_LOAD += domain.learning_burden * 0.5

# Integration Requirements  
FOR EACH integration IN required_integrations:
    CURRENT_CONTEXT_LOAD += integration.complexity * 0.2

CONTEXT_ADJUSTED_CAPACITY = max(1, BASE_MEMORY_CAPACITY - CURRENT_CONTEXT_LOAD)
```

#### Step 2.3: External Memory Support Assessment
**Algorithm**: Calculate available external memory augmentation

```markdown
EXTERNAL_MEMORY_BOOST = 0

# File-based External Memory
IF workspace_files_available:
    EXTERNAL_MEMORY_BOOST += 0.5

# Documentation References
IF comprehensive_documentation_available:
    EXTERNAL_MEMORY_BOOST += 0.3

# Previous Agent Context
IF related_agent_context_available:
    EXTERNAL_MEMORY_BOOST += 0.4

# Structured Templates
IF structured_templates_available:
    EXTERNAL_MEMORY_BOOST += 0.2

FINAL_AGENT_CAPACITY = CONTEXT_ADJUSTED_CAPACITY + EXTERNAL_MEMORY_BOOST
```

---

### Phase 3: Capacity-Task Matching Decision

#### Step 3.1: Direct Matching Algorithm
**Algorithm**: Compare task complexity to agent capacity

```markdown
CAPACITY_GAP = TASK_COMPLEXITY - FINAL_AGENT_CAPACITY

IF CAPACITY_GAP <= 0:
    DECISION = "PROCEED_DIRECT_ASSIGNMENT"
    CONFIDENCE = min(100, 80 + (abs(CAPACITY_GAP) * 10))
    
ELSE IF CAPACITY_GAP <= 1.0:
    DECISION = "PROCEED_WITH_EXTERNAL_MEMORY_SUPPORT"
    CONFIDENCE = max(60, 80 - (CAPACITY_GAP * 20))
    
ELSE IF CAPACITY_GAP <= 2.0:
    DECISION = "TASK_DECOMPOSITION_REQUIRED" 
    CONFIDENCE = 40
    
ELSE:
    DECISION = "TASK_IMPOSSIBLE_FOR_SINGLE_AGENT"
    CONFIDENCE = 90
```

#### Step 3.2: Risk Assessment
**Algorithm**: Evaluate assignment risks

```markdown
RISK_FACTORS = []

IF CAPACITY_GAP > 0.5:
    RISK_FACTORS.append("MEMORY_OVERLOAD_RISK")
    
IF TASK_COMPLEXITY >= 4 AND FINAL_AGENT_CAPACITY <= 3:
    RISK_FACTORS.append("FALSE_COMPLETION_RISK")
    
IF required_context_switches > 3:
    RISK_FACTORS.append("CONTEXT_LOSS_RISK")
    
IF external_dependencies > agent_integration_capacity:
    RISK_FACTORS.append("INTEGRATION_FAILURE_RISK")

OVERALL_RISK = len(RISK_FACTORS) / 4.0  # Normalize to 0-1 scale
```

#### Step 3.3: Decomposition Strategy Generation
**Algorithm**: Generate task breakdown when needed

```markdown
IF DECISION == "TASK_DECOMPOSITION_REQUIRED":
    
    decomposition_strategy = []
    
    # Functional Decomposition
    FOR EACH major_function IN task_functions:
        IF major_function.complexity <= FINAL_AGENT_CAPACITY:
            decomposition_strategy.append({
                "type": "direct_assignment",
                "function": major_function,
                "estimated_capacity": major_function.complexity
            })
        ELSE:
            sub_functions = decompose_function(major_function)
            FOR EACH sub_function IN sub_functions:
                decomposition_strategy.append({
                    "type": "sub_assignment", 
                    "function": sub_function,
                    "estimated_capacity": sub_function.complexity
                })
    
    # Sequential vs Parallel Assessment
    FOR EACH decomposed_task IN decomposition_strategy:
        IF decomposed_task.dependencies:
            decomposed_task.execution_type = "sequential"
        ELSE:
            decomposed_task.execution_type = "parallel"
```

---

## ALGORITHM OUTPUT SPECIFICATION

### Decision Matrix Output
```markdown
ASSESSMENT_RESULT = {
    "task_complexity": TASK_COMPLEXITY,
    "agent_capacity": FINAL_AGENT_CAPACITY,
    "capacity_gap": CAPACITY_GAP,
    "decision": DECISION,
    "confidence": CONFIDENCE,
    "risk_level": OVERALL_RISK,
    "risk_factors": RISK_FACTORS,
    "external_memory_required": (DECISION == "PROCEED_WITH_EXTERNAL_MEMORY_SUPPORT"),
    "decomposition_strategy": decomposition_strategy if applicable,
    "estimated_success_probability": calculate_success_probability()
}
```

### Success Probability Calculation
```markdown
base_success_rate = 0.9  # Base rate for properly matched tasks

# Adjust for capacity gap
IF CAPACITY_GAP <= 0:
    capacity_adjustment = 0.0
ELSE IF CAPACITY_GAP <= 0.5:
    capacity_adjustment = -0.1
ELSE IF CAPACITY_GAP <= 1.0:
    capacity_adjustment = -0.3
ELSE:
    capacity_adjustment = -0.6

# Adjust for risk factors
risk_adjustment = -0.1 * len(RISK_FACTORS)

# Adjust for external memory support
external_memory_adjustment = 0.1 if external_memory_available else 0.0

SUCCESS_PROBABILITY = max(0.1, base_success_rate + capacity_adjustment + risk_adjustment + external_memory_adjustment)
```

---

## IMPLEMENTATION INTEGRATION PROTOCOL

### Integration with QAPM Agent Spawning
**Phase Integration Point**: Before Phase 1 (Agent Type Selection)

```markdown
ENHANCED_AGENT_SPAWNING_PHASE_0 = {
    "phase_name": "Memory Capacity Assessment",
    "duration": "15-30 minutes",
    "inputs": ["task_description", "requirements_list", "context_information"],
    "algorithm": "MEMORY_AWARE_TASK_ASSESSMENT_ALGORITHM",
    "outputs": ["complexity_rating", "capacity_requirements", "assignment_decision"],
    "next_phase_conditions": {
        "PROCEED_DIRECT_ASSIGNMENT": "Continue to Phase 1 - Agent Type Selection",
        "PROCEED_WITH_EXTERNAL_MEMORY_SUPPORT": "Continue to Phase 1 with external memory setup",
        "TASK_DECOMPOSITION_REQUIRED": "Execute decomposition before agent selection",
        "TASK_IMPOSSIBLE_FOR_SINGLE_AGENT": "Escalate to multi-agent coordination planning"
    }
}
```

### File-Based Implementation Support
**External Memory File Structure**:
```
/workspace/external_memory/
├── task_context.md           # Core task information
├── requirements_matrix.md    # Detailed requirements
├── decision_history.md       # Previous decisions and rationale
├── reference_materials/      # Supporting documentation
└── agent_handoff_logs/       # Context transfer records
```

---

## VALIDATION AND TESTING PROTOCOL

### Algorithm Validation Tests
```markdown
TEST_CASES = [
    {
        "name": "Simple Task - Direct Assignment",
        "task_complexity": 1,
        "agent_capacity": 2,
        "expected_decision": "PROCEED_DIRECT_ASSIGNMENT",
        "expected_confidence": ">80%"
    },
    {
        "name": "Complex Task - Decomposition Required", 
        "task_complexity": 4,
        "agent_capacity": 2,
        "expected_decision": "TASK_DECOMPOSITION_REQUIRED",
        "expected_confidence": "40%"
    },
    {
        "name": "Borderline Task - External Memory Support",
        "task_complexity": 3,
        "agent_capacity": 2.5,
        "expected_decision": "PROCEED_WITH_EXTERNAL_MEMORY_SUPPORT",
        "expected_confidence": "60-80%"
    }
]
```

### Success Metrics
- **False Completion Reduction**: Target <5% (from current 100%)
- **First-Attempt Success Rate**: Target >80% (from current ~20%)
- **Task-Agent Mismatch Detection**: Target >95% accuracy
- **Memory Overload Prevention**: Target >90% prevention rate

---

## ALGORITHM MAINTENANCE AND EVOLUTION

### Continuous Improvement Protocol
```markdown
MONTHLY_ALGORITHM_REVIEW = {
    "performance_metrics_analysis": "Review success/failure rates",
    "threshold_adjustment": "Adjust complexity/capacity thresholds based on evidence",
    "new_risk_factor_identification": "Add newly discovered risk patterns",
    "baseline_capacity_updates": "Refine agent type memory baselines"
}
```

### Feedback Integration System
```markdown
FOR EACH completed_task_assignment:
    actual_success = measure_task_success()
    predicted_success = ASSESSMENT_RESULT.estimated_success_probability
    
    prediction_error = abs(actual_success - predicted_success)
    
    IF prediction_error > 0.2:
        add_to_algorithm_improvement_queue(task_details, prediction_error)
```

---

## CRITICAL SUCCESS FACTORS

### Must-Have Implementation Requirements
1. **Mathematical Precision**: All scoring must be consistent and repeatable
2. **Evidence-Based Thresholds**: All threshold values based on real project data
3. **Fast Execution**: Algorithm must complete in <5 minutes for any task
4. **Clear Decision Rationale**: All decisions must include reasoning trail
5. **Failure Recovery**: Algorithm must identify its own limitation boundaries

### Integration Success Dependencies  
1. **QAPM Training Integration**: Algorithm must be embedded in core QAPM training
2. **Tool Integration**: Must integrate with existing QAPM tools and workflows
3. **Evidence Validation**: Must demonstrate improved outcomes in real projects
4. **User Adoption**: QAPMs must consistently use the algorithm for all task assignments

---

**ALGORITHM STATUS**: ✅ SPECIFICATION COMPLETE  
**Next Phase**: Adaptive Failure Recovery Methodology Algorithm Development  
**Implementation Ready**: Full step-by-step algorithmic framework provided