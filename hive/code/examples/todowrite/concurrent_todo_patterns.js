/**
 * Concurrent TodoWrite Pattern Examples
 * 
 * Demonstrates proper TodoWrite usage with 5-10+ todos in a SINGLE call
 * for optimal swarm coordination and parallel execution.
 */

// ✅ CORRECT: Full Project TodoWrite with ALL todos at once
const correctProjectTodoWrite = {
  pattern: "Single TodoWrite call with 10+ todos",
  implementation: `
    TodoWrite({
      todos: [
        // High Priority Core Tasks
        { 
          id: "architecture", 
          content: "Design system architecture with microservices pattern", 
          status: "in_progress", 
          priority: "high" 
        },
        { 
          id: "database-design", 
          content: "Create database schema with performance indexes", 
          status: "pending", 
          priority: "high" 
        },
        { 
          id: "authentication", 
          content: "Implement JWT authentication with refresh tokens", 
          status: "pending", 
          priority: "high" 
        },
        { 
          id: "api-endpoints", 
          content: "Build RESTful API endpoints with OpenAPI documentation", 
          status: "pending", 
          priority: "high" 
        },
        
        // Medium Priority Feature Tasks
        { 
          id: "frontend-components", 
          content: "Develop React components with TypeScript", 
          status: "pending", 
          priority: "medium" 
        },
        { 
          id: "state-management", 
          content: "Setup Redux/Zustand for client state management", 
          status: "pending", 
          priority: "medium" 
        },
        { 
          id: "unit-tests", 
          content: "Write comprehensive unit tests with Jest", 
          status: "pending", 
          priority: "medium" 
        },
        { 
          id: "integration-tests", 
          content: "Create integration tests for API endpoints", 
          status: "pending", 
          priority: "medium" 
        },
        
        // Lower Priority Polish Tasks
        { 
          id: "api-documentation", 
          content: "Generate and publish API documentation", 
          status: "pending", 
          priority: "low" 
        },
        { 
          id: "performance-optimization", 
          content: "Optimize database queries and API response times", 
          status: "pending", 
          priority: "low" 
        },
        { 
          id: "deployment-pipeline", 
          content: "Setup CI/CD pipeline with automated testing", 
          status: "pending", 
          priority: "medium" 
        },
        { 
          id: "monitoring-logging", 
          content: "Implement monitoring, logging, and alerting", 
          status: "pending", 
          priority: "medium" 
        }
      ]
    })
  `,
  
  benefits: {
    coordination: "All agents see complete task list immediately",
    parallelization: "Agents can work on independent tasks simultaneously", 
    tracking: "Single source of truth for project progress",
    efficiency: "No repeated TodoWrite overhead"
  }
};

// ✅ CORRECT: Status Update TodoWrite with batch changes
const correctStatusUpdateTodoWrite = {
  pattern: "Batch status updates with new todos",
  implementation: `
    TodoWrite({
      todos: [
        // Update existing todos with new status
        { 
          id: "architecture", 
          content: "Design system architecture with microservices pattern", 
          status: "completed", 
          priority: "high" 
        },
        { 
          id: "database-design", 
          content: "Create database schema with performance indexes", 
          status: "in_progress", 
          priority: "high" 
        },
        { 
          id: "authentication", 
          content: "Implement JWT authentication with refresh tokens", 
          status: "in_progress", 
          priority: "high" 
        },
        
        // Keep existing pending todos
        { 
          id: "api-endpoints", 
          content: "Build RESTful API endpoints with OpenAPI documentation", 
          status: "pending", 
          priority: "high" 
        },
        { 
          id: "frontend-components", 
          content: "Develop React components with TypeScript", 
          status: "pending", 
          priority: "medium" 
        },
        
        // Add new todos discovered during implementation
        { 
          id: "error-handling", 
          content: "Implement centralized error handling and logging", 
          status: "pending", 
          priority: "high" 
        },
        { 
          id: "input-validation", 
          content: "Add comprehensive input validation with Joi/Zod", 
          status: "pending", 
          priority: "high" 
        },
        { 
          id: "rate-limiting", 
          content: "Implement rate limiting and API throttling", 
          status: "pending", 
          priority: "medium" 
        },
        { 
          id: "caching-layer", 
          content: "Add Redis caching for frequently accessed data", 
          status: "pending", 
          priority: "medium" 
        },
        { 
          id: "security-audit", 
          content: "Conduct security audit and fix vulnerabilities", 
          status: "pending", 
          priority: "high" 
        }
      ]
    })
  `,
  
  coordinationPattern: "Agents check memory before updating todos to avoid conflicts"
};

// ✅ CORRECT: Cross-Agent TodoWrite with coordination
const correctCrossAgentTodoWrite = {
  pattern: "Todos spanning multiple agents with dependencies",
  implementation: `
    TodoWrite({
      todos: [
        // Researcher Agent Tasks
        { 
          id: "research-apis", 
          content: "Research REST API best practices and patterns", 
          status: "completed", 
          priority: "high",
          assignedAgent: "researcher",
          dependencies: []
        },
        { 
          id: "research-auth", 
          content: "Research authentication methods and JWT implementation", 
          status: "completed", 
          priority: "high",
          assignedAgent: "researcher", 
          dependencies: []
        },
        
        // Architect Agent Tasks
        { 
          id: "system-design", 
          content: "Design overall system architecture", 
          status: "in_progress", 
          priority: "high",
          assignedAgent: "architect",
          dependencies: ["research-apis"]
        },
        { 
          id: "database-architecture", 
          content: "Design database schema and relationships", 
          status: "pending", 
          priority: "high",
          assignedAgent: "architect",
          dependencies: ["system-design"]
        },
        
        // Coder Agent Tasks
        { 
          id: "implement-auth", 
          content: "Implement authentication service", 
          status: "pending", 
          priority: "high",
          assignedAgent: "coder",
          dependencies: ["research-auth", "system-design"]
        },
        { 
          id: "implement-api", 
          content: "Build API endpoints based on architecture", 
          status: "pending", 
          priority: "high",
          assignedAgent: "coder",
          dependencies: ["database-architecture", "implement-auth"]
        },
        
        // Tester Agent Tasks
        { 
          id: "test-strategy", 
          content: "Design comprehensive testing strategy", 
          status: "pending", 
          priority: "medium",
          assignedAgent: "tester",
          dependencies: ["system-design"]
        },
        { 
          id: "unit-tests", 
          content: "Write unit tests for all components", 
          status: "pending", 
          priority: "medium",
          assignedAgent: "tester", 
          dependencies: ["implement-api"]
        },
        
        // Coordinator Agent Tasks
        { 
          id: "progress-tracking", 
          content: "Monitor progress and coordinate between agents", 
          status: "in_progress", 
          priority: "high",
          assignedAgent: "coordinator",
          dependencies: []
        },
        { 
          id: "integration-coordination", 
          content: "Ensure smooth integration between components", 
          status: "pending", 
          priority: "medium",
          assignedAgent: "coordinator",
          dependencies: ["implement-auth", "implement-api"]
        }
      ]
    })
  `,
  
  memoryCoordination: `
    // Agents use memory to check dependencies before starting work
    mcp__claude-flow__memory_usage({ 
      action: "store", 
      key: "todos/dependencies", 
      value: dependencyGraph 
    })
  `
};

// ✅ CORRECT: Sprint Planning TodoWrite with priorities
const correctSprintPlanningTodoWrite = {
  pattern: "Sprint todos with clear priorities and estimations",
  implementation: `
    TodoWrite({
      todos: [
        // Sprint 1: Core Infrastructure (High Priority)
        { 
          id: "sprint1-setup", 
          content: "Setup development environment and tooling", 
          status: "completed", 
          priority: "high",
          sprint: 1,
          estimate: "2 days",
          tags: ["infrastructure", "setup"]
        },
        { 
          id: "sprint1-database", 
          content: "Design and implement database schema", 
          status: "in_progress", 
          priority: "high",
          sprint: 1,
          estimate: "3 days",
          tags: ["database", "schema"]
        },
        { 
          id: "sprint1-auth", 
          content: "Implement user authentication system", 
          status: "pending", 
          priority: "high",
          sprint: 1,
          estimate: "4 days",
          tags: ["authentication", "security"]
        },
        
        // Sprint 2: Core Features (High Priority)
        { 
          id: "sprint2-user-management", 
          content: "Build user management CRUD operations", 
          status: "pending", 
          priority: "high",
          sprint: 2,
          estimate: "3 days",
          tags: ["users", "crud"]
        },
        { 
          id: "sprint2-api-endpoints", 
          content: "Create RESTful API endpoints", 
          status: "pending", 
          priority: "high",
          sprint: 2,
          estimate: "5 days",
          tags: ["api", "endpoints"]
        },
        
        // Sprint 3: Advanced Features (Medium Priority)
        { 
          id: "sprint3-frontend", 
          content: "Develop React frontend components", 
          status: "pending", 
          priority: "medium",
          sprint: 3,
          estimate: "6 days",
          tags: ["frontend", "react"]
        },
        { 
          id: "sprint3-integration", 
          content: "Integrate frontend with API", 
          status: "pending", 
          priority: "medium",
          sprint: 3,
          estimate: "3 days",
          tags: ["integration", "fullstack"]
        },
        
        // Sprint 4: Quality & Polish (Medium/Low Priority)
        { 
          id: "sprint4-testing", 
          content: "Comprehensive testing suite", 
          status: "pending", 
          priority: "medium",
          sprint: 4,
          estimate: "4 days",
          tags: ["testing", "quality"]
        },
        { 
          id: "sprint4-documentation", 
          content: "API and user documentation", 
          status: "pending", 
          priority: "low",
          sprint: 4,
          estimate: "2 days",
          tags: ["documentation"]
        },
        { 
          id: "sprint4-deployment", 
          content: "Production deployment setup", 
          status: "pending", 
          priority: "medium",
          sprint: 4,
          estimate: "3 days",
          tags: ["deployment", "devops"]
        }
      ]
    })
  `
};

// ❌ WRONG: Single Todo Updates (Anti-Pattern)
const wrongSingleTodoUpdates = {
  antiPattern: "Multiple TodoWrite calls for individual todos",
  wrongImplementation: `
    // ❌ NEVER DO THIS - Breaks coordination
    Message 1: TodoWrite({ todos: [{ id: "1", content: "Task 1", status: "pending" }] })
    Message 2: TodoWrite({ todos: [{ id: "2", content: "Task 2", status: "pending" }] })
    Message 3: TodoWrite({ todos: [{ id: "1", content: "Task 1", status: "in_progress" }] })
    Message 4: TodoWrite({ todos: [{ id: "3", content: "Task 3", status: "pending" }] })
  `,
  
  problems: [
    "Agents don't see full todo context",
    "Coordination between agents breaks down",
    "Performance penalty from multiple calls",
    "Race conditions in todo updates",
    "Incomplete project visibility"
  ]
};

module.exports = {
  correctProjectTodoWrite,
  correctStatusUpdateTodoWrite,
  correctCrossAgentTodoWrite,
  correctSprintPlanningTodoWrite,
  wrongSingleTodoUpdates
};