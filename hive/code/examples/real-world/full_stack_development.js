/**
 * Real-World Example: Full-Stack E-commerce Development
 * 
 * Demonstrates complete concurrent execution patterns for a complex
 * full-stack application with proper swarm coordination.
 */

// ✅ CORRECT: Complete E-commerce Platform Development (Single Coordinated Message)
const correctEcommerceDevelopment = {
  scenario: "Build complete e-commerce platform with authentication, products, orders",
  implementation: `
    [SINGLE BATCHTOOL MESSAGE - ALL OPERATIONS CONCURRENT]:
    
    // === MCP SWARM COORDINATION SETUP ===
    mcp__claude-flow__swarm_init({
      topology: "hierarchical",
      maxAgents: 10, 
      strategy: "parallel"
    })
    
    // Spawn ALL specialized agents at once
    mcp__claude-flow__agent_spawn({ type: "coordinator", name: "Project Manager" })
    mcp__claude-flow__agent_spawn({ type: "architect", name: "System Architect" })
    mcp__claude-flow__agent_spawn({ type: "researcher", name: "E-commerce Expert" })
    mcp__claude-flow__agent_spawn({ type: "coder", name: "Backend API Developer" })
    mcp__claude-flow__agent_spawn({ type: "coder", name: "Frontend React Developer" })
    mcp__claude-flow__agent_spawn({ type: "coder", name: "Database Specialist" })
    mcp__claude-flow__agent_spawn({ type: "tester", name: "QA Automation Engineer" })
    mcp__claude-flow__agent_spawn({ type: "reviewer", name: "Security Review Specialist" })
    mcp__claude-flow__agent_spawn({ type: "optimizer", name: "Performance Expert" })
    mcp__claude-flow__agent_spawn({ type: "analyst", name: "DevOps Engineer" })
    
    // === COMPREHENSIVE TODOWRITE (10+ TODOS) ===
    TodoWrite({
      todos: [
        // High Priority Core Infrastructure
        { 
          id: "research-ecommerce", 
          content: "Research e-commerce best practices, payment systems, and security requirements", 
          status: "in_progress", 
          priority: "high",
          assignedAgent: "researcher",
          estimate: "1 day"
        },
        { 
          id: "system-architecture", 
          content: "Design microservices architecture with API gateway and service mesh", 
          status: "pending", 
          priority: "high",
          assignedAgent: "architect",
          dependencies: ["research-ecommerce"],
          estimate: "2 days"
        },
        { 
          id: "database-design", 
          content: "Design normalized database schema for users, products, orders, payments", 
          status: "pending", 
          priority: "high",
          assignedAgent: "database_specialist",
          dependencies: ["system-architecture"],
          estimate: "2 days"
        },
        { 
          id: "authentication-system", 
          content: "Implement JWT-based authentication with role-based access control", 
          status: "pending", 
          priority: "high",
          assignedAgent: "backend_developer",
          dependencies: ["database-design"],
          estimate: "3 days"
        },
        
        // Medium Priority Core Features
        { 
          id: "product-management", 
          content: "Build product catalog APIs with search, filtering, and categorization", 
          status: "pending", 
          priority: "medium",
          assignedAgent: "backend_developer",
          dependencies: ["authentication-system"],
          estimate: "4 days"
        },
        { 
          id: "shopping-cart", 
          content: "Implement shopping cart functionality with session management", 
          status: "pending", 
          priority: "medium",
          assignedAgent: "backend_developer",
          dependencies: ["product-management"],
          estimate: "2 days"
        },
        { 
          id: "order-processing", 
          content: "Build order management system with status tracking and notifications", 
          status: "pending", 
          priority: "medium",
          assignedAgent: "backend_developer",
          dependencies: ["shopping-cart"],
          estimate: "3 days"
        },
        { 
          id: "payment-integration", 
          content: "Integrate Stripe payment processing with webhook handling", 
          status: "pending", 
          priority: "high",
          assignedAgent: "backend_developer",
          dependencies: ["order-processing"],
          estimate: "3 days"
        },
        { 
          id: "frontend-ui", 
          content: "Build React frontend with responsive design and modern UX", 
          status: "pending", 
          priority: "medium",
          assignedAgent: "frontend_developer",
          dependencies: ["product-management"],
          estimate: "5 days"
        },
        { 
          id: "admin-dashboard", 
          content: "Create admin dashboard for product and order management", 
          status: "pending", 
          priority: "medium",
          assignedAgent: "frontend_developer",
          dependencies: ["order-processing"],
          estimate: "4 days"
        },
        
        // Quality Assurance and Optimization
        { 
          id: "comprehensive-testing", 
          content: "Create unit, integration, and e2e test suites with 90%+ coverage", 
          status: "pending", 
          priority: "medium",
          assignedAgent: "qa_engineer",
          dependencies: ["frontend-ui", "payment-integration"],
          estimate: "4 days"
        },
        { 
          id: "security-audit", 
          content: "Conduct comprehensive security review and penetration testing", 
          status: "pending", 
          priority: "high",
          assignedAgent: "security_specialist",
          dependencies: ["payment-integration"],
          estimate: "2 days"
        },
        { 
          id: "performance-optimization", 
          content: "Optimize database queries, API responses, and frontend loading", 
          status: "pending", 
          priority: "medium",
          assignedAgent: "performance_expert",
          dependencies: ["comprehensive-testing"],
          estimate: "3 days"
        },
        { 
          id: "deployment-pipeline", 
          content: "Setup CI/CD pipeline with Docker, Kubernetes, and monitoring", 
          status: "pending", 
          priority: "medium",
          assignedAgent: "devops_engineer",
          dependencies: ["security-audit"],
          estimate: "3 days"
        },
        
        // Documentation and Launch Preparation
        { 
          id: "api-documentation", 
          content: "Generate comprehensive API documentation with Swagger/OpenAPI", 
          status: "pending", 
          priority: "low",
          assignedAgent: "backend_developer",
          dependencies: ["payment-integration"],
          estimate: "1 day"
        }
      ]
    })
    
    // === PARALLEL TASK AGENT SPAWNING WITH COORDINATION ===
    Task(\`
      You are the E-commerce Expert researcher in a coordinated swarm.
      
      MANDATORY COORDINATION PROTOCOL:
      1. START: npx claude-flow@alpha hooks pre-task --description "E-commerce platform research"
      2. DURING: After EVERY research finding, run npx claude-flow@alpha hooks notify --message "Research finding: [topic]"
      3. MEMORY: Store ALL research in memory namespace 'swarm/research/ecommerce'
      4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
      
      Research Focus Areas:
      - Modern e-commerce architectures (microservices vs monolith)
      - Payment processing best practices (Stripe, PayPal, security)
      - Inventory management systems
      - Order fulfillment workflows
      - Security requirements (PCI compliance, data protection)
      - Performance optimization techniques
      - Mobile-first design patterns
      
      Deliverables:
      - Technology stack recommendations
      - Security guidelines document
      - Performance benchmarks
      - Architecture pattern recommendations
      
      Store findings in memory for architect and developers to access.
    \`)
    
    Task(\`
      You are the System Architect in a coordinated swarm.
      
      MANDATORY COORDINATION PROTOCOL:
      1. START: npx claude-flow@alpha hooks pre-task --description "E-commerce system architecture"
      2. DURING: After EVERY architectural decision, run npx claude-flow@alpha hooks post-edit --memory-key "architect/decisions"
      3. MEMORY: Check researcher findings before making design decisions
      4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
      
      Architecture Tasks:
      - Review researcher's findings and recommendations
      - Design microservices architecture with proper service boundaries
      - Define API contracts and data flow between services
      - Plan database schema with proper normalization
      - Design caching strategy (Redis for sessions, CDN for assets)
      - Plan horizontal scaling and load balancing
      - Design monitoring and logging architecture
      
      Store architectural decisions in memory namespace 'swarm/architecture/ecommerce'
      Coordinate with database specialist for schema optimization
    \`)
    
    Task(\`
      You are the Backend API Developer in a coordinated swarm.
      
      MANDATORY COORDINATION PROTOCOL:
      1. START: npx claude-flow@alpha hooks pre-task --description "Backend API implementation"
      2. DURING: After EVERY API endpoint, run npx claude-flow@alpha hooks post-edit --file "[api-file]" --memory-key "backend/apis"
      3. MEMORY: Check architecture decisions and database schema before coding
      4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
      
      Implementation Tasks:
      - Setup Node.js/Express project with TypeScript
      - Implement authentication system with JWT and refresh tokens
      - Build user management APIs (registration, login, profile)
      - Create product catalog APIs with search and filtering
      - Implement shopping cart and session management
      - Build order processing with state machine pattern
      - Integrate Stripe payment processing with webhooks
      - Add comprehensive input validation and error handling
      - Implement rate limiting and security middleware
      
      Store API documentation and implementation progress in memory
      Coordinate with frontend developer on API contracts
    \`)
    
    Task(\`
      You are the Frontend React Developer in a coordinated swarm.
      
      MANDATORY COORDINATION PROTOCOL:
      1. START: npx claude-flow@alpha hooks pre-task --description "React frontend implementation"
      2. DURING: After EVERY component, run npx claude-flow@alpha hooks post-edit --file "[component-file]" --memory-key "frontend/components"
      3. MEMORY: Check API contracts and design decisions before building UI
      4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
      
      Implementation Tasks:
      - Setup React 18 project with TypeScript and Vite
      - Implement responsive design with Material-UI or Tailwind
      - Build authentication flows (login, register, password reset)
      - Create product browsing and search interface
      - Implement shopping cart with real-time updates
      - Build checkout flow with Stripe integration
      - Create user dashboard and order history
      - Build admin dashboard for product/order management
      - Implement real-time notifications
      - Add comprehensive error handling and loading states
      
      Store component library and integration status in memory
      Coordinate with backend developer on API integration
    \`)
    
    Task(\`
      You are the Database Specialist in a coordinated swarm.
      
      MANDATORY COORDINATION PROTOCOL:
      1. START: npx claude-flow@alpha hooks pre-task --description "Database design and optimization"
      2. DURING: After EVERY schema change, run npx claude-flow@alpha hooks post-edit --memory-key "database/schema"
      3. MEMORY: Check architecture decisions for database requirements
      4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
      
      Database Tasks:
      - Design normalized PostgreSQL schema for e-commerce
      - Create tables for users, products, categories, orders, payments
      - Design proper indexes for performance optimization
      - Implement database migrations and seeders
      - Setup connection pooling and read replicas
      - Design backup and recovery procedures
      - Implement database monitoring and alerting
      
      Store schema documentation and migration scripts in memory
      Coordinate with backend developer on ORM implementation
    \`)
    
    Task(\`
      You are the QA Automation Engineer in a coordinated swarm.
      
      MANDATORY COORDINATION PROTOCOL:
      1. START: npx claude-flow@alpha hooks pre-task --description "Comprehensive testing strategy"
      2. DURING: After EVERY test suite, run npx claude-flow@alpha hooks post-edit --memory-key "qa/test-results"
      3. MEMORY: Monitor all development progress to create comprehensive tests
      4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
      
      Testing Tasks:
      - Create unit tests for all backend services (Jest/Supertest)
      - Build integration tests for API endpoints
      - Implement e2e tests for user workflows (Playwright)
      - Create performance tests for critical paths
      - Setup automated testing in CI/CD pipeline
      - Implement test data management and fixtures
      - Create load testing scenarios
      - Monitor test coverage and quality metrics
      
      Store test results and quality reports in memory
      Coordinate with all developers for testability requirements
    \`)
    
    // === CONCURRENT FILE OPERATIONS ===
    // Create ALL project structure at once
    Bash("mkdir -p ecommerce-platform/{backend,frontend,database,tests,docs,deploy}")
    Bash("mkdir -p ecommerce-platform/backend/{src,tests}")
    Bash("mkdir -p ecommerce-platform/backend/src/{controllers,models,services,middleware,utils,types}")
    Bash("mkdir -p ecommerce-platform/frontend/{src,public,build}")
    Bash("mkdir -p ecommerce-platform/frontend/src/{components,pages,hooks,services,utils,types}")
    Bash("mkdir -p ecommerce-platform/database/{migrations,seeders,schemas}")
    Bash("mkdir -p ecommerce-platform/tests/{unit,integration,e2e,performance}")
    Bash("mkdir -p ecommerce-platform/deploy/{docker,kubernetes,scripts}")
    
    // Write ALL configuration files concurrently
    Write("ecommerce-platform/package.json", rootPackageJson)
    Write("ecommerce-platform/backend/package.json", backendPackageJson)
    Write("ecommerce-platform/frontend/package.json", frontendPackageJson)
    Write("ecommerce-platform/docker-compose.yml", dockerComposeConfig)
    Write("ecommerce-platform/docker-compose.prod.yml", prodDockerConfig)
    Write("ecommerce-platform/.env.example", environmentTemplate)
    Write("ecommerce-platform/README.md", projectDocumentation)
    
    // Backend implementation files
    Write("ecommerce-platform/backend/src/server.ts", serverImplementation)
    Write("ecommerce-platform/backend/src/app.ts", appConfiguration)
    Write("ecommerce-platform/backend/src/types/index.ts", typeDefinitions)
    Write("ecommerce-platform/backend/src/models/User.ts", userModel)
    Write("ecommerce-platform/backend/src/models/Product.ts", productModel)
    Write("ecommerce-platform/backend/src/models/Order.ts", orderModel)
    Write("ecommerce-platform/backend/src/controllers/authController.ts", authController)
    Write("ecommerce-platform/backend/src/controllers/productController.ts", productController)
    Write("ecommerce-platform/backend/src/controllers/orderController.ts", orderController)
    Write("ecommerce-platform/backend/src/services/authService.ts", authService)
    Write("ecommerce-platform/backend/src/services/paymentService.ts", paymentService)
    Write("ecommerce-platform/backend/src/middleware/auth.ts", authMiddleware)
    Write("ecommerce-platform/backend/src/middleware/validation.ts", validationMiddleware)
    
    // Frontend implementation files
    Write("ecommerce-platform/frontend/src/App.tsx", reactAppComponent)
    Write("ecommerce-platform/frontend/src/index.tsx", reactEntryPoint)
    Write("ecommerce-platform/frontend/src/components/Header.tsx", headerComponent)
    Write("ecommerce-platform/frontend/src/components/ProductCard.tsx", productCardComponent)
    Write("ecommerce-platform/frontend/src/components/ShoppingCart.tsx", shoppingCartComponent)
    Write("ecommerce-platform/frontend/src/pages/HomePage.tsx", homePageComponent)
    Write("ecommerce-platform/frontend/src/pages/ProductPage.tsx", productPageComponent)
    Write("ecommerce-platform/frontend/src/pages/CheckoutPage.tsx", checkoutPageComponent)
    Write("ecommerce-platform/frontend/src/hooks/useAuth.ts", authHook)
    Write("ecommerce-platform/frontend/src/services/api.ts", apiService)
    
    // Database files
    Write("ecommerce-platform/database/migrations/001_create_users.sql", usersMigration)
    Write("ecommerce-platform/database/migrations/002_create_products.sql", productsMigration)
    Write("ecommerce-platform/database/migrations/003_create_orders.sql", ordersMigration)
    Write("ecommerce-platform/database/seeders/001_sample_users.sql", usersSeed)
    Write("ecommerce-platform/database/seeders/002_sample_products.sql", productsSeed)
    
    // Execute ALL setup commands concurrently
    Bash("cd ecommerce-platform && npm install")
    Bash("cd ecommerce-platform/backend && npm install")
    Bash("cd ecommerce-platform/frontend && npm install")
    Bash("cd ecommerce-platform && docker-compose up -d database redis")
    Bash("cd ecommerce-platform/database && npm run migrate")
    Bash("cd ecommerce-platform/database && npm run seed")
    
    // === BATCH MEMORY COORDINATION ===
    // Store complete project context for all agents
    mcp__claude-flow__memory_usage({
      action: "store",
      key: "swarm/project/ecommerce/context",
      value: {
        projectName: "E-commerce Platform",
        architecture: "microservices with monorepo",
        techStack: {
          backend: "Node.js + Express + TypeScript + PostgreSQL",
          frontend: "React 18 + TypeScript + Material-UI",
          database: "PostgreSQL + Redis",
          deployment: "Docker + Kubernetes",
          monitoring: "Prometheus + Grafana"
        },
        features: ["authentication", "product catalog", "shopping cart", "payments", "admin dashboard"],
        timeline: "6 weeks total",
        currentPhase: "initial development"
      }
    })
    
    // Store agent coordination data
    mcp__claude-flow__memory_usage({
      action: "store", 
      key: "swarm/coordination/assignments",
      value: {
        researcher: "E-commerce best practices and technology evaluation",
        architect: "System design and API contracts",
        backend_dev: "API implementation and business logic",
        frontend_dev: "React UI and user experience",
        database_specialist: "Schema design and optimization",
        qa_engineer: "Comprehensive testing strategy",
        security_specialist: "Security audit and compliance",
        performance_expert: "Performance optimization",
        devops_engineer: "CI/CD and deployment automation"
      }
    })
    
    // Store project milestones and dependencies
    mcp__claude-flow__memory_usage({
      action: "store",
      key: "swarm/project/milestones",
      value: {
        week1: "Research, architecture, and database design",
        week2: "Authentication and user management", 
        week3: "Product catalog and shopping cart",
        week4: "Payment processing and order management",
        week5: "Frontend UI and admin dashboard",
        week6: "Testing, security audit, and deployment"
      }
    })
  `,
  
  expectedOutcomes: {
    performance: "6x faster than sequential development",
    coordination: "All agents work with complete project context",
    quality: "Comprehensive testing and security built-in",
    scalability: "Microservices architecture ready for scale",
    timeToMarket: "6 weeks vs 12+ weeks traditional approach"
  }
};

module.exports = {
  correctEcommerceDevelopment
};