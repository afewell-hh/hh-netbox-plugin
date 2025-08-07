/**
 * Parallel Agent Spawning Pattern Examples
 * 
 * Demonstrates proper agent coordination with mandatory hooks
 * and memory-based communication for optimal swarm performance.
 */

// ✅ CORRECT: Full Development Swarm (8 agents in ONE message)
const correctDevelopmentSwarm = {
  pattern: "Parallel agent spawning with coordination hooks",
  implementation: `
    // Single message with ALL agent spawning
    [BatchTool Message]:
      // MCP Swarm Initialization
      mcp__claude-flow__swarm_init({ 
        topology: "hierarchical", 
        maxAgents: 8, 
        strategy: "parallel" 
      })
      
      // MCP Agent Registration (all at once)
      mcp__claude-flow__agent_spawn({ type: "coordinator", name: "Project Manager" })
      mcp__claude-flow__agent_spawn({ type: "architect", name: "System Architect" })
      mcp__claude-flow__agent_spawn({ type: "researcher", name: "Tech Researcher" })
      mcp__claude-flow__agent_spawn({ type: "coder", name: "Backend Developer" })
      mcp__claude-flow__agent_spawn({ type: "coder", name: "Frontend Developer" })
      mcp__claude-flow__agent_spawn({ type: "tester", name: "QA Engineer" })
      mcp__claude-flow__agent_spawn({ type: "reviewer", name: "Code Reviewer" })
      mcp__claude-flow__agent_spawn({ type: "optimizer", name: "Performance Expert" })
      
      // Task Agent Spawning with MANDATORY coordination hooks
      Task(\`
        You are the Project Manager agent in a coordinated swarm.
        
        MANDATORY COORDINATION PROTOCOL:
        1. START: npx claude-flow@alpha hooks pre-task --description "Project coordination and progress tracking"
        2. DURING: After EVERY decision, run npx claude-flow@alpha hooks notify --message "[decision made]"
        3. MEMORY: Store ALL coordination data using npx claude-flow@alpha hooks post-edit --memory-key "pm/[action]"
        4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
        
        Your role: Coordinate all agents, track progress, manage dependencies.
        Check memory for other agents' progress before making decisions.
        Store project timeline and milestones in memory namespace 'swarm/coordination'.
      \`)
      
      Task(\`
        You are the System Architect agent in a coordinated swarm.
        
        MANDATORY COORDINATION PROTOCOL:
        1. START: npx claude-flow@alpha hooks pre-task --description "System architecture design"
        2. DURING: After EVERY architectural decision, run npx claude-flow@alpha hooks post-edit --memory-key "architect/design"
        3. MEMORY: Check researcher's findings before designing architecture
        4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
        
        Your role: Design scalable system architecture based on research findings.
        Coordinate with backend/frontend developers for implementation feasibility.
        Store architectural decisions in memory namespace 'swarm/architecture'.
      \`)
      
      Task(\`
        You are the Tech Researcher agent in a coordinated swarm.
        
        MANDATORY COORDINATION PROTOCOL:
        1. START: npx claude-flow@alpha hooks pre-task --description "Technology research and evaluation"
        2. DURING: After EVERY research finding, run npx claude-flow@alpha hooks notify --message "Research: [finding]"
        3. MEMORY: Store ALL research in memory for other agents to access
        4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
        
        Your role: Research best practices, technologies, and implementation patterns.
        Provide evidence-based recommendations for architectural decisions.
        Store research findings in memory namespace 'swarm/research'.
      \`)
      
      Task(\`
        You are the Backend Developer agent in a coordinated swarm.
        
        MANDATORY COORDINATION PROTOCOL:
        1. START: npx claude-flow@alpha hooks pre-task --description "Backend implementation"
        2. DURING: After EVERY file change, run npx claude-flow@alpha hooks post-edit --file "[filepath]" --memory-key "backend/[component]"
        3. MEMORY: Check architect's designs and researcher's findings before coding
        4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
        
        Your role: Implement backend services based on architectural specifications.
        Coordinate with frontend developer for API contract definitions.
        Store implementation progress in memory namespace 'swarm/backend'.
      \`)
      
      Task(\`
        You are the Frontend Developer agent in a coordinated swarm.
        
        MANDATORY COORDINATION PROTOCOL:
        1. START: npx claude-flow@alpha hooks pre-task --description "Frontend implementation"
        2. DURING: After EVERY component creation, run npx claude-flow@alpha hooks post-edit --memory-key "frontend/[component]"
        3. MEMORY: Coordinate with backend developer for API integration
        4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
        
        Your role: Build user interface based on architectural specifications.
        Ensure seamless integration with backend APIs and services.
        Store UI progress in memory namespace 'swarm/frontend'.
      \`)
      
      Task(\`
        You are the QA Engineer agent in a coordinated swarm.
        
        MANDATORY COORDINATION PROTOCOL:
        1. START: npx claude-flow@alpha hooks pre-task --description "Quality assurance and testing"
        2. DURING: After EVERY test creation, run npx claude-flow@alpha hooks post-edit --memory-key "qa/tests"
        3. MEMORY: Monitor all agents' progress to create comprehensive tests
        4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
        
        Your role: Create comprehensive test suites for all components.
        Coordinate with developers to ensure testability and quality.
        Store test results in memory namespace 'swarm/testing'.
      \`)
      
      Task(\`
        You are the Code Reviewer agent in a coordinated swarm.
        
        MANDATORY COORDINATION PROTOCOL:
        1. START: npx claude-flow@alpha hooks pre-task --description "Code review and quality"
        2. DURING: After EVERY review, run npx claude-flow@alpha hooks notify --message "Review: [findings]"
        3. MEMORY: Track code quality metrics across all components
        4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
        
        Your role: Review all code for quality, security, and best practices.
        Provide feedback to developers and ensure code standards.
        Store review feedback in memory namespace 'swarm/reviews'.
      \`)
      
      Task(\`
        You are the Performance Expert agent in a coordinated swarm.
        
        MANDATORY COORDINATION PROTOCOL:
        1. START: npx claude-flow@alpha hooks pre-task --description "Performance optimization"
        2. DURING: After EVERY optimization, run npx claude-flow@alpha hooks post-edit --memory-key "perf/optimization"
        3. MEMORY: Monitor all agents' implementations for performance issues
        4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
        
        Your role: Optimize system performance and identify bottlenecks.
        Coordinate with all developers to implement performance improvements.
        Store performance metrics in memory namespace 'swarm/performance'.
      \`)
  `,
  
  benefits: {
    coordination: "All agents spawn with full context of team structure",
    communication: "Memory-based coordination prevents conflicts",
    efficiency: "Parallel work on independent components",
    quality: "Cross-agent review and validation"
  }
};

// ✅ CORRECT: Specialized GitHub Management Swarm
const correctGithubManagementSwarm = {
  pattern: "GitHub-focused agent coordination",
  implementation: `
    [BatchTool Message]:
      // GitHub-specific swarm initialization
      mcp__claude-flow__swarm_init({ 
        topology: "mesh", 
        maxAgents: 6, 
        strategy: "adaptive" 
      })
      
      // GitHub management agents
      mcp__claude-flow__agent_spawn({ type: "coordinator", name: "Repository Manager" })
      mcp__claude-flow__agent_spawn({ type: "reviewer", name: "PR Review Specialist" })
      mcp__claude-flow__agent_spawn({ type: "analyst", name: "Issue Triage Expert" })
      mcp__claude-flow__agent_spawn({ type: "coder", name: "Workflow Automation Dev" })
      mcp__claude-flow__agent_spawn({ type: "optimizer", name: "Repository Optimizer" })
      mcp__claude-flow__agent_spawn({ type: "tester", name: "CI/CD Specialist" })
      
      // Coordinated GitHub task agents
      Task(\`
        You are the Repository Manager for GitHub operations.
        
        MANDATORY COORDINATION:
        1. START: npx claude-flow@alpha hooks pre-task --description "GitHub repository management"
        2. MEMORY: Coordinate with all GitHub specialists via memory
        3. HOOKS: Use post-edit after every GitHub operation
        4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
        
        Tasks:
        - Manage repository settings and permissions
        - Coordinate release planning and versioning
        - Oversee branch protection and merge policies
        - Store repository metrics in 'github/repo-stats'
      \`)
      
      Task(\`
        You are the PR Review Specialist.
        
        MANDATORY COORDINATION:
        1. START: npx claude-flow@alpha hooks pre-task --description "Pull request review automation"
        2. MEMORY: Check repository policies before reviewing
        3. HOOKS: Store review feedback in memory after each PR
        4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
        
        Tasks:
        - Automated code quality checks
        - Security vulnerability scanning
        - Best practices validation
        - Store review patterns in 'github/pr-reviews'
      \`)
      
      Task(\`
        You are the Issue Triage Expert.
        
        MANDATORY COORDINATION:
        1. START: npx claude-flow@alpha hooks pre-task --description "Issue management and triage"
        2. MEMORY: Coordinate with developers on issue priorities
        3. HOOKS: Update issue metrics after each triage session
        4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
        
        Tasks:
        - Categorize and prioritize issues
        - Assign issues to appropriate developers
        - Track issue resolution patterns
        - Store triage data in 'github/issue-triage'
      \`)
      
      Task(\`
        You are the Workflow Automation Developer.
        
        MANDATORY COORDINATION:
        1. START: npx claude-flow@alpha hooks pre-task --description "GitHub Actions workflow development"
        2. MEMORY: Check CI/CD requirements from other agents
        3. HOOKS: Store workflow performance metrics
        4. END: npx claude-flow@alpha hooks post-task --analyze-performance true
        
        Tasks:
        - Design and implement GitHub Actions workflows
        - Automate testing, building, and deployment
        - Monitor workflow performance and reliability
        - Store automation configs in 'github/workflows'
      \`)
  `
};

// ✅ CORRECT: Cross-Agent Memory Coordination Pattern
const correctMemoryCoordination = {
  pattern: "Memory-based agent communication and coordination",
  implementation: `
    // Each agent follows this coordination pattern:
    
    // 1. Pre-task: Load context from other agents
    \`\`\`bash
    npx claude-flow@alpha hooks pre-task --description "Agent task description"
    npx claude-flow@alpha hooks session-restore --load-memory true
    \`\`\`
    
    // 2. Check dependencies from other agents
    mcp__claude-flow__memory_usage({ 
      action: "retrieve", 
      key: "swarm/dependencies/[my-agent]" 
    })
    
    // 3. During work: Store progress for other agents
    mcp__claude-flow__memory_usage({ 
      action: "store", 
      key: "swarm/[my-agent]/progress", 
      value: { 
        currentTask: "implementation details",
        completedSteps: ["step1", "step2"],
        nextSteps: ["step3", "step4"],
        blockers: [],
        artifacts: ["file1.js", "file2.js"]
      }
    })
    
    // 4. After each major step: Notify other agents
    \`\`\`bash
    npx claude-flow@alpha hooks notify --message "Completed architecture design, stored in memory" --telemetry true
    \`\`\`
    
    // 5. Before dependent work: Check prerequisites
    mcp__claude-flow__memory_usage({ 
      action: "list", 
      namespace: "swarm",
      pattern: "*/progress" 
    })
    
    // 6. Post-task: Store final results and learnings
    \`\`\`bash
    npx claude-flow@alpha hooks post-task --task-id "my-task" --analyze-performance true
    \`\`\`
  `,
  
  memoryNamespaces: {
    "swarm/coordination": "Project management and timeline data",
    "swarm/architecture": "System design decisions and diagrams", 
    "swarm/research": "Technology research and recommendations",
    "swarm/backend": "Backend implementation progress and APIs",
    "swarm/frontend": "UI components and integration status",
    "swarm/testing": "Test suites and quality metrics",
    "swarm/reviews": "Code review feedback and standards",
    "swarm/performance": "Performance metrics and optimizations"
  }
};

// ❌ WRONG: Sequential Agent Spawning (Anti-Pattern)
const wrongSequentialAgentSpawning = {
  antiPattern: "One agent per message without coordination",
  wrongImplementation: `
    // ❌ NEVER DO THIS - Breaks parallel coordination
    Message 1: Task("You are a researcher. Research APIs.")
    Message 2: Task("You are a coder. Build an API.")  
    Message 3: Task("You are a tester. Test the API.")
    Message 4: Task("You are a reviewer. Review the code.")
  `,
  
  problems: [
    "Agents don't know about each other",
    "No coordination hooks or memory usage",
    "Sequential execution prevents parallelization",
    "Missing context about overall project goals",
    "No way to track cross-agent dependencies"
  ]
};

module.exports = {
  correctDevelopmentSwarm,
  correctGithubManagementSwarm,
  correctMemoryCoordination,
  wrongSequentialAgentSpawning
};