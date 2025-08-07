/**
 * CORRECT BatchTool Usage Patterns
 * 
 * These examples demonstrate proper concurrent execution where ALL related
 * operations are batched into a SINGLE message for maximum efficiency.
 */

// ✅ CORRECT: Full-Stack API Development in ONE Message
const correctFullStackDevelopment = {
  message: "Single BatchTool Message",
  operations: [
    // MCP Coordination Setup (all at once)
    'mcp__claude-flow__swarm_init({ topology: "hierarchical", maxAgents: 8, strategy: "parallel" })',
    'mcp__claude-flow__agent_spawn({ type: "architect", name: "System Designer" })',
    'mcp__claude-flow__agent_spawn({ type: "coder", name: "API Developer" })',
    'mcp__claude-flow__agent_spawn({ type: "coder", name: "Frontend Developer" })',
    'mcp__claude-flow__agent_spawn({ type: "tester", name: "QA Engineer" })',
    'mcp__claude-flow__agent_spawn({ type: "coordinator", name: "Project Manager" })',
    
    // TodoWrite with ALL todos at once (5-10+ minimum)
    `TodoWrite({
      todos: [
        { id: "design", content: "Design API architecture", status: "in_progress", priority: "high" },
        { id: "database", content: "Setup database schema", status: "pending", priority: "high" },
        { id: "auth", content: "Implement authentication", status: "pending", priority: "high" },
        { id: "endpoints", content: "Build REST endpoints", status: "pending", priority: "high" },
        { id: "frontend", content: "Create React components", status: "pending", priority: "medium" },
        { id: "tests", content: "Write comprehensive tests", status: "pending", priority: "medium" },
        { id: "docs", content: "Generate API documentation", status: "pending", priority: "low" },
        { id: "deploy", content: "Setup CI/CD pipeline", status: "pending", priority: "medium" },
        { id: "monitor", content: "Add monitoring/logging", status: "pending", priority: "medium" },
        { id: "security", content: "Security audit/fixes", status: "pending", priority: "high" }
      ]
    })`,
    
    // Task Agent Spawning (all agents with coordination instructions)
    `Task("You are System Designer. MANDATORY: Run hooks pre-task, post-edit, post-task. Design scalable API architecture with microservices pattern.")`,
    `Task("You are API Developer. MANDATORY: Run hooks pre-task, post-edit, post-task. Implement RESTful endpoints with authentication.")`,
    `Task("You are Frontend Developer. MANDATORY: Run hooks pre-task, post-edit, post-task. Build React dashboard with API integration.")`,
    `Task("You are QA Engineer. MANDATORY: Run hooks pre-task, post-edit, post-task. Create comprehensive test suite covering all endpoints.")`,
    
    // File Operations (all directories and base files)
    'Bash("mkdir -p fullstack-app/{api,frontend,tests,docs,deploy}")',
    'Bash("mkdir -p fullstack-app/api/{routes,models,middleware,controllers}")',
    'Bash("mkdir -p fullstack-app/frontend/{src,public,components}")',
    'Bash("mkdir -p fullstack-app/tests/{unit,integration,e2e}")',
    
    // Write ALL configuration files at once
    'Write("fullstack-app/package.json", packageJsonContent)',
    'Write("fullstack-app/api/server.js", serverContent)',
    'Write("fullstack-app/frontend/package.json", frontendPackageContent)',
    'Write("fullstack-app/docker-compose.yml", dockerComposeContent)',
    'Write("fullstack-app/.env.example", envExampleContent)',
    'Write("fullstack-app/README.md", readmeContent)',
    
    // Memory Operations (store all coordination data)
    'mcp__claude-flow__memory_usage({ action: "store", key: "project/init", value: projectInitData })',
    'mcp__claude-flow__memory_usage({ action: "store", key: "agents/roles", value: agentRoleMapping })',
    'mcp__claude-flow__memory_usage({ action: "store", key: "todos/status", value: todoTrackingData })',
    
    // Command Execution (all setup commands)
    'Bash("cd fullstack-app/api && npm install")',
    'Bash("cd fullstack-app/frontend && npm install")',
    'Bash("cd fullstack-app && docker-compose up -d database")'
  ],
  
  benefits: {
    speed: "6x faster than sequential execution",
    coordination: "All agents start with complete context",
    reliability: "Atomic operation - either all succeed or all fail",
    efficiency: "Reduced token usage through batching"
  }
};

// ✅ CORRECT: Database Migration and Testing in ONE Message
const correctDatabaseMigration = {
  message: "Single BatchTool Message",
  operations: [
    // Read all existing schema files
    'Read("database/migrations/001_initial.sql")',
    'Read("database/migrations/002_users.sql")',
    'Read("database/schemas/current_schema.sql")',
    'Read("config/database.config.js")',
    
    // Write all new migration files
    'Write("database/migrations/003_new_tables.sql", migrationContent)',
    'Write("database/migrations/004_indexes.sql", indexContent)',
    'Write("database/seeds/test_data.sql", seedContent)',
    'Write("tests/database/migration_tests.js", testContent)',
    
    // Execute all database operations
    'Bash("cd database && npm run migrate:up")',
    'Bash("cd database && npm run seed:test")',
    'Bash("cd tests && npm run test:database")',
    'Bash("cd database && npm run validate:schema")',
    
    // Update todos with migration progress
    `TodoWrite({
      todos: [
        { id: "migration-001", content: "Run initial migration", status: "completed", priority: "high" },
        { id: "migration-002", content: "Add user tables", status: "completed", priority: "high" },
        { id: "migration-003", content: "Create new feature tables", status: "in_progress", priority: "high" },
        { id: "indexes", content: "Add performance indexes", status: "pending", priority: "medium" },
        { id: "seed-data", content: "Load test data", status: "pending", priority: "medium" },
        { id: "test-migration", content: "Validate migration success", status: "pending", priority: "high" },
        { id: "rollback-test", content: "Test rollback procedures", status: "pending", priority: "medium" }
      ]
    })`,
    
    // Store migration results in memory
    'mcp__claude-flow__memory_usage({ action: "store", key: "migration/results", value: migrationResults })'
  ]
};

// ✅ CORRECT: Multi-Service Deployment in ONE Message
const correctMultiServiceDeployment = {
  message: "Single BatchTool Message", 
  operations: [
    // Spawn specialized deployment agents
    'mcp__claude-flow__agent_spawn({ type: "architect", name: "Infrastructure Architect" })',
    'mcp__claude-flow__agent_spawn({ type: "coder", name: "DevOps Engineer" })',
    'mcp__claude-flow__agent_spawn({ type: "tester", name: "Deployment Tester" })',
    
    // Task agents with deployment coordination
    `Task("Infrastructure Architect: Design and validate deployment architecture for 5 microservices")`,
    `Task("DevOps Engineer: Create and execute deployment scripts with health checks")`,
    `Task("Deployment Tester: Validate all services are running correctly post-deployment")`,
    
    // Read all service configurations
    'Read("services/auth/Dockerfile")',
    'Read("services/api/Dockerfile")',
    'Read("services/frontend/Dockerfile")',
    'Read("services/database/docker-compose.yml")',
    'Read("k8s/deployment.yaml")',
    
    // Write all deployment files
    'Write("deploy/docker-compose.prod.yml", prodComposeContent)',
    'Write("deploy/kubernetes/namespace.yaml", namespaceContent)',
    'Write("deploy/kubernetes/auth-deployment.yaml", authDeploymentContent)',
    'Write("deploy/kubernetes/api-deployment.yaml", apiDeploymentContent)',
    'Write("deploy/kubernetes/frontend-deployment.yaml", frontendDeploymentContent)',
    'Write("deploy/scripts/health-check.sh", healthCheckScript)',
    'Write("deploy/scripts/rollback.sh", rollbackScript)',
    
    // Execute all deployment commands
    'Bash("cd deploy && docker-compose -f docker-compose.prod.yml build")',
    'Bash("cd deploy && kubectl apply -f kubernetes/")',
    'Bash("cd deploy && ./scripts/health-check.sh")',
    'Bash("cd deploy && kubectl get pods -n production")',
    
    // Update comprehensive todo list
    `TodoWrite({
      todos: [
        { id: "build-images", content: "Build all Docker images", status: "completed", priority: "high" },
        { id: "deploy-auth", content: "Deploy authentication service", status: "in_progress", priority: "high" },
        { id: "deploy-api", content: "Deploy API service", status: "pending", priority: "high" },
        { id: "deploy-frontend", content: "Deploy frontend service", status: "pending", priority: "high" },
        { id: "deploy-database", content: "Deploy database cluster", status: "pending", priority: "high" },
        { id: "configure-ingress", content: "Setup ingress controllers", status: "pending", priority: "medium" },
        { id: "ssl-certificates", content: "Configure SSL certificates", status: "pending", priority: "medium" },
        { id: "monitoring", content: "Deploy monitoring stack", status: "pending", priority: "medium" },
        { id: "health-checks", content: "Validate all health endpoints", status: "pending", priority: "high" },
        { id: "load-testing", content: "Run load tests on deployment", status: "pending", priority: "low" }
      ]
    })`
  ]
};

module.exports = {
  correctFullStackDevelopment,
  correctDatabaseMigration,
  correctMultiServiceDeployment
};