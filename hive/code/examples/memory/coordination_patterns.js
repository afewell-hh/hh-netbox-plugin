/**
 * Memory Coordination Pattern Examples
 * 
 * Demonstrates proper cross-agent memory sharing and coordination
 * using claude-flow memory operations for optimal swarm performance.
 */

// ✅ CORRECT: Cross-Agent Memory Coordination (All operations batched)
const correctCrossAgentMemoryCoordination = {
  pattern: "Batch memory operations for swarm coordination",
  implementation: `
    [BatchTool Message]:
      // Store initial project context for all agents
      mcp__claude-flow__memory_usage({
        action: "store",
        key: "swarm/project/context",
        value: {
          projectName: "E-commerce Platform",
          technologies: ["Node.js", "React", "PostgreSQL", "Docker"],
          architecture: "microservices",
          timeline: "8 weeks",
          teamSize: 6,
          priorities: ["security", "performance", "scalability"]
        }
      })
      
      // Store agent role definitions and responsibilities
      mcp__claude-flow__memory_usage({
        action: "store", 
        key: "swarm/agents/roles",
        value: {
          architect: {
            name: "System Architect",
            responsibilities: ["system design", "technology decisions", "architectural patterns"],
            dependencies: ["researcher"],
            outputs: ["architecture diagrams", "tech stack decisions", "API contracts"]
          },
          researcher: {
            name: "Tech Researcher", 
            responsibilities: ["technology evaluation", "best practices research", "security analysis"],
            dependencies: [],
            outputs: ["research reports", "technology recommendations", "security guidelines"]
          },
          backend_dev: {
            name: "Backend Developer",
            responsibilities: ["API implementation", "database design", "business logic"],
            dependencies: ["architect", "researcher"],
            outputs: ["REST APIs", "database schemas", "service implementations"]
          },
          frontend_dev: {
            name: "Frontend Developer",
            responsibilities: ["UI implementation", "user experience", "API integration"],
            dependencies: ["architect", "backend_dev"],
            outputs: ["React components", "user interfaces", "API integrations"]
          },
          qa_engineer: {
            name: "QA Engineer",
            responsibilities: ["test strategy", "automated testing", "quality assurance"],
            dependencies: ["backend_dev", "frontend_dev"],
            outputs: ["test suites", "quality reports", "bug tracking"]
          },
          coordinator: {
            name: "Project Coordinator",
            responsibilities: ["progress tracking", "task coordination", "risk management"],
            dependencies: ["all agents"],
            outputs: ["progress reports", "task assignments", "risk assessments"]
          }
        }
      })
      
      // Store coordination protocols and communication standards
      mcp__claude-flow__memory_usage({
        action: "store",
        key: "swarm/coordination/protocols", 
        value: {
          checkInFrequency: "after every major milestone",
          memoryNamespaces: {
            "swarm/research": "Research findings and recommendations",
            "swarm/architecture": "System design and architectural decisions", 
            "swarm/backend": "API development and database progress",
            "swarm/frontend": "UI development and integration status",
            "swarm/testing": "Test results and quality metrics",
            "swarm/coordination": "Project management and progress tracking"
          },
          coordinationRules: [
            "Check dependencies before starting work",
            "Store progress after each major milestone", 
            "Notify dependent agents of status changes",
            "Use standardized memory keys for consistency"
          ]
        }
      })
      
      // Store project milestones and dependencies
      mcp__claude-flow__memory_usage({
        action: "store",
        key: "swarm/project/milestones",
        value: {
          week1: {
            milestone: "Research and Architecture",
            tasks: ["technology research", "system architecture design", "API specification"],
            assignedAgents: ["researcher", "architect"],
            deliverables: ["tech stack document", "architecture diagrams", "API contracts"]
          },
          week2: {
            milestone: "Backend Foundation",
            tasks: ["database setup", "authentication system", "core API endpoints"],
            assignedAgents: ["backend_dev"],
            dependencies: ["week1"],
            deliverables: ["database schema", "auth APIs", "user management"]
          },
          week3: {
            milestone: "Frontend Foundation", 
            tasks: ["React setup", "routing", "authentication UI", "API integration"],
            assignedAgents: ["frontend_dev"],
            dependencies: ["week2"],
            deliverables: ["login/register pages", "dashboard", "API integration"]
          },
          week4: {
            milestone: "Core Features",
            tasks: ["product catalog", "shopping cart", "order management"],
            assignedAgents: ["backend_dev", "frontend_dev"],
            dependencies: ["week3"],
            deliverables: ["product APIs", "cart functionality", "order processing"]
          }
        }
      })
      
      // Store shared resources and configurations
      mcp__claude-flow__memory_usage({
        action: "store",
        key: "swarm/resources/shared",
        value: {
          codeStandards: {
            javascript: "ESLint + Prettier",
            typescript: "Strict mode enabled",
            testing: "Jest + Supertest",
            documentation: "JSDoc for functions"
          },
          environments: {
            development: "localhost with hot reload",
            staging: "Docker containers",
            production: "Kubernetes cluster"
          },
          credentials: {
            database: "stored in .env files",
            apis: "environment-specific configs",
            deployment: "CI/CD secrets management"
          }
        }
      })
      
      // Initialize agent-specific memory namespaces
      mcp__claude-flow__memory_usage({
        action: "store",
        key: "swarm/researcher/status",
        value: {
          currentTask: "Technology stack evaluation",
          progress: "initial research phase",
          findings: [],
          nextSteps: ["evaluate databases", "security frameworks", "deployment options"]
        }
      })
      
      mcp__claude-flow__memory_usage({
        action: "store", 
        key: "swarm/architect/status",
        value: {
          currentTask: "Waiting for research completion",
          progress: "requirements analysis",
          decisions: [],
          nextSteps: ["review research", "design system architecture", "create API specifications"]
        }
      })
      
      mcp__claude-flow__memory_usage({
        action: "store",
        key: "swarm/coordination/tracking",
        value: {
          activeAgents: ["researcher", "architect"],
          completedTasks: [],
          blockedTasks: [],
          upcomingDeadlines: ["Week 1 research completion", "Architecture review"],
          riskFactors: ["technology learning curve", "integration complexity"]
        }
      })
  `,
  
  benefits: {
    coordination: "All agents have complete project context from start",
    efficiency: "No repeated context loading or confusion about roles",
    scalability: "Easy to add new agents with clear integration points",
    reliability: "Consistent communication protocols across all agents"
  }
};

// ✅ CORRECT: Progress Tracking and Status Updates (Batch Memory Operations)
const correctProgressTracking = {
  pattern: "Batch memory updates for progress coordination",
  implementation: `
    [BatchTool Message - After completing research phase]:
      // Update researcher progress with findings
      mcp__claude-flow__memory_usage({
        action: "store",
        key: "swarm/researcher/status",
        value: {
          currentTask: "Research completed",
          progress: "100% complete",
          findings: [
            {
              category: "database",
              recommendation: "PostgreSQL with Prisma ORM",
              reasoning: "Strong typing, migration support, performance"
            },
            {
              category: "authentication", 
              recommendation: "JWT with refresh tokens",
              reasoning: "Stateless, scalable, secure"
            },
            {
              category: "api_framework",
              recommendation: "Express.js with TypeScript",
              reasoning: "Mature ecosystem, type safety, good performance"
            },
            {
              category: "frontend_state",
              recommendation: "Zustand for state management",
              reasoning: "Lightweight, TypeScript-first, minimal boilerplate"
            }
          ],
          artifacts: ["technology_evaluation.md", "security_guidelines.md", "performance_benchmarks.md"],
          nextSteps: ["handoff to architect", "support implementation questions"]
        }
      })
      
      // Notify architect that research is complete
      mcp__claude-flow__memory_usage({
        action: "store",
        key: "swarm/architect/status", 
        value: {
          currentTask: "System architecture design",
          progress: "starting design phase",
          dependencies: {
            research: "completed - ready to proceed",
            requirements: "analyzed and documented"
          },
          designDecisions: [
            {
              area: "overall_architecture",
              decision: "Microservices with API Gateway",
              reasoning: "Scalability and independent deployment"
            },
            {
              area: "data_flow",
              decision: "Event-driven architecture with message queues",
              reasoning: "Loose coupling and async processing"
            }
          ],
          nextSteps: ["create architecture diagrams", "define service boundaries", "design API contracts"]
        }
      })
      
      // Update coordination tracking
      mcp__claude-flow__memory_usage({
        action: "store",
        key: "swarm/coordination/tracking",
        value: {
          activeAgents: ["architect", "coordinator"],
          completedTasks: ["technology_research", "security_analysis", "performance_evaluation"],
          inProgressTasks: ["system_architecture_design", "api_contract_definition"],
          blockedTasks: [],
          upcomingDeadlines: ["Architecture completion - Week 1 end", "API contracts - Week 2 start"],
          riskFactors: [],
          milestonesCompleted: ["research_phase"],
          currentMilestone: "architecture_design"
        }
      })
      
      // Store research artifacts for other agents
      mcp__claude-flow__memory_usage({
        action: "store",
        key: "swarm/research/technology_stack",
        value: {
          backend: {
            runtime: "Node.js 18+",
            framework: "Express.js with TypeScript",
            database: "PostgreSQL 15+",
            orm: "Prisma",
            authentication: "JWT with refresh tokens",
            validation: "Zod",
            testing: "Jest + Supertest"
          },
          frontend: {
            framework: "React 18 with TypeScript",
            bundler: "Vite",
            stateManagement: "Zustand",
            uiLibrary: "Material-UI v5",
            routing: "React Router v6",
            httpClient: "Axios",
            testing: "React Testing Library + Jest"
          },
          infrastructure: {
            containerization: "Docker",
            orchestration: "Kubernetes",
            database: "PostgreSQL on managed service",
            caching: "Redis",
            monitoring: "Prometheus + Grafana",
            logging: "ELK Stack"
          }
        }
      })
      
      // Store security guidelines for implementation
      mcp__claude-flow__memory_usage({
        action: "store",
        key: "swarm/research/security_guidelines",
        value: {
          authentication: [
            "Use bcrypt for password hashing (min 12 rounds)",
            "Implement JWT access tokens (15min expiry) + refresh tokens (7 days)",
            "Rate limiting on auth endpoints",
            "Account lockout after failed attempts"
          ],
          apiSecurity: [
            "HTTPS only in production", 
            "CORS properly configured",
            "Input validation on all endpoints",
            "SQL injection prevention with parameterized queries",
            "XSS protection with Content Security Policy"
          ],
          dataProtection: [
            "Encrypt sensitive data at rest",
            "Use environment variables for secrets",
            "Regular security audits",
            "GDPR compliance for user data"
          ]
        }
      })
      
      // Update project timeline with actual progress
      mcp__claude-flow__memory_usage({
        action: "store",
        key: "swarm/project/timeline_actual",
        value: {
          week1: {
            planned: ["research", "architecture"],
            actual: ["research completed ahead of schedule", "architecture in progress"],
            variance: "+1 day ahead",
            nextWeek: ["complete architecture", "start backend implementation"]
          }
        }
      })
  `
};

// ✅ CORRECT: Dependency Management and Coordination
const correctDependencyManagement = {
  pattern: "Memory-based dependency tracking and coordination",
  implementation: `
    [BatchTool Message - Backend developer checking dependencies]:
      // Check prerequisite work from architect and researcher  
      mcp__claude-flow__memory_usage({
        action: "retrieve",
        key: "swarm/architect/status"
      })
      
      mcp__claude-flow__memory_usage({
        action: "retrieve", 
        key: "swarm/research/technology_stack"
      })
      
      mcp__claude-flow__memory_usage({
        action: "retrieve",
        key: "swarm/research/security_guidelines"
      })
      
      // Store backend implementation plan based on dependencies
      mcp__claude-flow__memory_usage({
        action: "store",
        key: "swarm/backend/implementation_plan",
        value: {
          phase1: {
            tasks: ["project setup", "database schema", "basic auth"],
            dependencies: ["architecture complete", "tech stack confirmed"],
            status: "ready to start",
            estimatedDays: 3
          },
          phase2: {
            tasks: ["user management APIs", "product catalog APIs"],
            dependencies: ["phase1 complete", "database migrations"],
            status: "blocked - waiting for phase1",
            estimatedDays: 4
          },
          phase3: {
            tasks: ["order management", "payment integration"],
            dependencies: ["phase2 complete", "external API keys"],
            status: "blocked - waiting for phase2",
            estimatedDays: 5
          }
        }
      })
      
      // Update coordination status
      mcp__claude-flow__memory_usage({
        action: "store",
        key: "swarm/backend/status",
        value: {
          currentTask: "Backend implementation planning",
          progress: "ready to begin development",
          dependencies: {
            architecture: "available and reviewed",
            research: "available and incorporated", 
            database_design: "ready to implement"
          },
          blockers: [],
          nextSteps: ["setup development environment", "implement database schema", "create auth endpoints"]
        }
      })
      
      // Notify frontend developer of API contracts
      mcp__claude-flow__memory_usage({
        action: "store",
        key: "swarm/coordination/api_contracts",
        value: {
          authentication: {
            endpoints: [
              "POST /api/auth/login",
              "POST /api/auth/register", 
              "POST /api/auth/refresh",
              "POST /api/auth/logout"
            ],
            models: ["User", "AuthTokens"],
            status: "contract defined, implementation starting"
          },
          userManagement: {
            endpoints: [
              "GET /api/users/profile",
              "PUT /api/users/profile", 
              "DELETE /api/users/account"
            ],
            models: ["UserProfile"],
            status: "contract defined, pending implementation"
          },
          products: {
            endpoints: [
              "GET /api/products",
              "GET /api/products/:id",
              "POST /api/products (admin)",
              "PUT /api/products/:id (admin)"
            ],
            models: ["Product", "Category"],
            status: "contract defined, pending implementation"
          }
        }
      })
      
      // Store shared database schema for all agents
      mcp__claude-flow__memory_usage({
        action: "store",
        key: "swarm/shared/database_schema",
        value: {
          users: {
            fields: ["id", "email", "password_hash", "created_at", "updated_at"],
            relationships: ["hasOne: user_profile", "hasMany: orders"]
          },
          user_profiles: {
            fields: ["id", "user_id", "first_name", "last_name", "avatar_url"],
            relationships: ["belongsTo: user"]
          },
          products: {
            fields: ["id", "name", "description", "price", "stock", "category_id"],
            relationships: ["belongsTo: category", "belongsToMany: orders"]
          },
          orders: {
            fields: ["id", "user_id", "total", "status", "created_at"],
            relationships: ["belongsTo: user", "belongsToMany: products"]
          }
        }
      })
  `
};

// ❌ WRONG: Fragmented Memory Operations (Anti-Pattern)
const wrongFragmentedMemoryOperations = {
  antiPattern: "Individual memory operations without coordination",
  wrongImplementation: `
    // ❌ NEVER DO THIS - Breaks memory coordination
    Message 1: mcp__claude-flow__memory_usage({ action: "store", key: "agent1", value: data1 })
    Message 2: mcp__claude-flow__memory_usage({ action: "store", key: "agent2", value: data2 })
    Message 3: mcp__claude-flow__memory_usage({ action: "retrieve", key: "agent1" })
    Message 4: mcp__claude-flow__memory_usage({ action: "store", key: "progress", value: progress })
  `,
  
  problems: [
    "Agents get partial or stale information",
    "Race conditions in memory updates",
    "Inconsistent memory state across agents",
    "No atomic operations for related data",
    "Difficult to coordinate complex dependencies"
  ]
};

module.exports = {
  correctCrossAgentMemoryCoordination,
  correctProgressTracking,
  correctDependencyManagement,
  wrongFragmentedMemoryOperations
};