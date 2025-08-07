/**
 * Concurrent File Operation Pattern Examples
 * 
 * Demonstrates proper batching of Read, Write, Edit, and Bash operations
 * for maximum efficiency and coordination in swarm environments.
 */

// ✅ CORRECT: Full-Stack Project Setup (All files in ONE message)
const correctProjectSetup = {
  pattern: "Complete project scaffolding in single batch",
  implementation: `
    [BatchTool Message]:
      // Read existing configuration files for context
      Read("package.json")
      Read("tsconfig.json") 
      Read(".env.example")
      Read("docker-compose.yml")
      Read("README.md")
      
      // Create ALL directory structure at once
      Bash("mkdir -p fullstack-project/{api,frontend,database,tests,docs,deploy}")
      Bash("mkdir -p fullstack-project/api/{src,tests,dist}")
      Bash("mkdir -p fullstack-project/api/src/{controllers,models,services,middleware,utils}")
      Bash("mkdir -p fullstack-project/frontend/{src,public,build}")
      Bash("mkdir -p fullstack-project/frontend/src/{components,pages,hooks,utils,styles}")
      Bash("mkdir -p fullstack-project/tests/{unit,integration,e2e}")
      Bash("mkdir -p fullstack-project/deploy/{docker,kubernetes,scripts}")
      
      // Write ALL configuration files concurrently
      Write("fullstack-project/package.json", {
        "name": "fullstack-project",
        "version": "1.0.0",
        "scripts": {
          "dev": "concurrently \\"cd api && npm run dev\\" \\"cd frontend && npm start\\"",
          "build": "cd api && npm run build && cd ../frontend && npm run build",
          "test": "cd api && npm test && cd ../frontend && npm test",
          "deploy": "cd deploy && ./deploy.sh"
        },
        "workspaces": ["api", "frontend"]
      })
      
      Write("fullstack-project/api/package.json", {
        "name": "api",
        "version": "1.0.0",
        "scripts": {
          "dev": "nodemon src/server.ts",
          "build": "tsc",
          "test": "jest",
          "start": "node dist/server.js"
        },
        "dependencies": {
          "express": "^4.18.0",
          "cors": "^2.8.5",
          "helmet": "^7.0.0",
          "jsonwebtoken": "^9.0.0",
          "bcryptjs": "^2.4.3",
          "mongoose": "^7.0.0"
        },
        "devDependencies": {
          "@types/express": "^4.17.0",
          "@types/node": "^20.0.0",
          "typescript": "^5.0.0",
          "nodemon": "^2.0.0",
          "jest": "^29.0.0"
        }
      })
      
      Write("fullstack-project/frontend/package.json", {
        "name": "frontend",
        "version": "1.0.0",
        "scripts": {
          "start": "react-scripts start",
          "build": "react-scripts build",
          "test": "react-scripts test",
          "eject": "react-scripts eject"
        },
        "dependencies": {
          "react": "^18.2.0",
          "react-dom": "^18.2.0",
          "react-router-dom": "^6.8.0",
          "axios": "^1.3.0",
          "@mui/material": "^5.11.0",
          "@emotion/react": "^11.10.0",
          "@emotion/styled": "^11.10.0"
        }
      })
      
      Write("fullstack-project/api/src/server.ts", \`
        import express from 'express';
        import cors from 'cors';
        import helmet from 'helmet';
        import { connectDatabase } from './utils/database';
        import { authRoutes } from './controllers/auth';
        import { userRoutes } from './controllers/users';
        import { errorHandler } from './middleware/errorHandler';
        
        const app = express();
        const PORT = process.env.PORT || 3001;
        
        // Middleware
        app.use(helmet());
        app.use(cors());
        app.use(express.json());
        
        // Routes
        app.use('/api/auth', authRoutes);
        app.use('/api/users', userRoutes);
        
        // Error handling
        app.use(errorHandler);
        
        // Start server
        const startServer = async () => {
          await connectDatabase();
          app.listen(PORT, () => {
            console.log(\\\`Server running on port \\\${PORT}\\\`);
          });
        };
        
        startServer().catch(console.error);
      \`)
      
      Write("fullstack-project/frontend/src/App.tsx", \`
        import React from 'react';
        import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
        import { ThemeProvider, createTheme } from '@mui/material/styles';
        import CssBaseline from '@mui/material/CssBaseline';
        import { Header } from './components/Header';
        import { Dashboard } from './pages/Dashboard';
        import { Login } from './pages/Login';
        import { Users } from './pages/Users';
        
        const theme = createTheme({
          palette: {
            mode: 'light',
            primary: { main: '#1976d2' },
            secondary: { main: '#dc004e' }
          }
        });
        
        function App() {
          return (
            <ThemeProvider theme={theme}>
              <CssBaseline />
              <Router>
                <Header />
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/login" element={<Login />} />
                  <Route path="/users" element={<Users />} />
                </Routes>
              </Router>
            </ThemeProvider>
          );
        }
        
        export default App;
      \`)
      
      Write("fullstack-project/docker-compose.yml", \`
        version: '3.8'
        services:
          database:
            image: mongo:6
            environment:
              MONGO_INITDB_ROOT_USERNAME: admin
              MONGO_INITDB_ROOT_PASSWORD: password
            ports:
              - "27017:27017"
            volumes:
              - mongo_data:/data/db
              
          api:
            build:
              context: ./api
              dockerfile: Dockerfile
            ports:
              - "3001:3001"
            depends_on:
              - database
            environment:
              DATABASE_URL: mongodb://admin:password@database:27017/app?authSource=admin
              JWT_SECRET: your-secret-key
              
          frontend:
            build:
              context: ./frontend
              dockerfile: Dockerfile
            ports:
              - "3000:3000"
            depends_on:
              - api
              
        volumes:
          mongo_data:
      \`)
      
      Write("fullstack-project/api/Dockerfile", \`
        FROM node:18-alpine
        WORKDIR /app
        COPY package*.json ./
        RUN npm ci --only=production
        COPY . .
        RUN npm run build
        EXPOSE 3001
        CMD ["npm", "start"]
      \`)
      
      Write("fullstack-project/frontend/Dockerfile", \`
        FROM node:18-alpine as builder
        WORKDIR /app
        COPY package*.json ./
        RUN npm ci
        COPY . .
        RUN npm run build
        
        FROM nginx:alpine
        COPY --from=builder /app/build /usr/share/nginx/html
        EXPOSE 3000
        CMD ["nginx", "-g", "daemon off;"]
      \`)
      
      // Install dependencies for all projects concurrently
      Bash("cd fullstack-project && npm install")
      Bash("cd fullstack-project/api && npm install") 
      Bash("cd fullstack-project/frontend && npm install")
      
      // Run initial build and test commands
      Bash("cd fullstack-project/api && npm run build")
      Bash("cd fullstack-project/frontend && npm run build")
      Bash("cd fullstack-project && docker-compose build")
  `,
  
  coordination: `
    // Store file creation progress in memory
    mcp__claude-flow__memory_usage({
      action: "store",
      key: "files/project-setup",
      value: {
        created: ["package.json", "api/", "frontend/", "docker-compose.yml"],
        nextSteps: ["database setup", "authentication", "testing"],
        dependencies: ["Node.js", "Docker", "MongoDB"]
      }
    })
  `
};

// ✅ CORRECT: Database Migration with Comprehensive File Operations
const correctDatabaseMigration = {
  pattern: "Complete database setup and migration in single batch",
  implementation: `
    [BatchTool Message]:
      // Read existing database schema and migration files
      Read("database/schema.sql")
      Read("database/migrations/001_initial.sql")
      Read("database/migrations/002_users.sql") 
      Read("database/seeders/base_data.sql")
      Read("config/database.config.js")
      
      // Write ALL new migration files
      Write("database/migrations/003_add_user_profiles.sql", \`
        CREATE TABLE user_profiles (
          id SERIAL PRIMARY KEY,
          user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
          first_name VARCHAR(100) NOT NULL,
          last_name VARCHAR(100) NOT NULL,
          avatar_url TEXT,
          bio TEXT,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);
      \`)
      
      Write("database/migrations/004_add_posts_table.sql", \`
        CREATE TABLE posts (
          id SERIAL PRIMARY KEY,
          user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
          title VARCHAR(255) NOT NULL,
          content TEXT NOT NULL,
          status VARCHAR(20) DEFAULT 'draft',
          published_at TIMESTAMP,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX idx_posts_user_id ON posts(user_id);
        CREATE INDEX idx_posts_status ON posts(status);
        CREATE INDEX idx_posts_published_at ON posts(published_at);
      \`)
      
      Write("database/migrations/005_add_comments_table.sql", \`
        CREATE TABLE comments (
          id SERIAL PRIMARY KEY,
          post_id INTEGER REFERENCES posts(id) ON DELETE CASCADE,
          user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
          content TEXT NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX idx_comments_post_id ON comments(post_id);
        CREATE INDEX idx_comments_user_id ON comments(user_id);
      \`)
      
      Write("database/seeders/003_user_profiles.sql", \`
        INSERT INTO user_profiles (user_id, first_name, last_name, bio) VALUES
        (1, 'John', 'Doe', 'Software engineer with passion for clean code'),
        (2, 'Jane', 'Smith', 'Product manager focused on user experience'),
        (3, 'Mike', 'Johnson', 'Designer creating beautiful interfaces');
      \`)
      
      Write("database/seeders/004_sample_posts.sql", \`
        INSERT INTO posts (user_id, title, content, status, published_at) VALUES
        (1, 'Getting Started with Node.js', 'A comprehensive guide to Node.js development...', 'published', NOW()),
        (2, 'Product Strategy 101', 'Key principles for effective product management...', 'published', NOW()),
        (3, 'Design Thinking Process', 'Understanding the design thinking methodology...', 'draft', NULL);
      \`)
      
      Write("database/scripts/migrate.js", \`
        const fs = require('fs');
        const path = require('path');
        const { Pool } = require('pg');
        
        const pool = new Pool({
          connectionString: process.env.DATABASE_URL
        });
        
        async function runMigrations() {
          const migrationDir = path.join(__dirname, '../migrations');
          const files = fs.readdirSync(migrationDir).sort();
          
          for (const file of files) {
            if (file.endsWith('.sql')) {
              const filePath = path.join(migrationDir, file);
              const sql = fs.readFileSync(filePath, 'utf8');
              
              try {
                await pool.query(sql);
                console.log(\\\`✅ Migration \\\${file} completed\\\`);
              } catch (error) {
                console.error(\\\`❌ Migration \\\${file} failed:\\\`, error);
                process.exit(1);
              }
            }
          }
          
          await pool.end();
          console.log('🎉 All migrations completed successfully');
        }
        
        runMigrations().catch(console.error);
      \`)
      
      Write("database/scripts/seed.js", \`
        const fs = require('fs');
        const path = require('path');
        const { Pool } = require('pg');
        
        const pool = new Pool({
          connectionString: process.env.DATABASE_URL
        });
        
        async function runSeeders() {
          const seederDir = path.join(__dirname, '../seeders');
          const files = fs.readdirSync(seederDir).sort();
          
          for (const file of files) {
            if (file.endsWith('.sql')) {
              const filePath = path.join(seederDir, file);
              const sql = fs.readFileSync(filePath, 'utf8');
              
              try {
                await pool.query(sql);
                console.log(\\\`✅ Seeder \\\${file} completed\\\`);
              } catch (error) {
                console.error(\\\`❌ Seeder \\\${file} failed:\\\`, error);
                process.exit(1);
              }
            }
          }
          
          await pool.end();
          console.log('🌱 All seeders completed successfully');
        }
        
        runSeeders().catch(console.error);
      \`)
      
      // Execute ALL database operations
      Bash("cd database && node scripts/migrate.js")
      Bash("cd database && node scripts/seed.js") 
      Bash("cd database && psql $DATABASE_URL -c '\\dt'")  // List tables
      Bash("cd database && psql $DATABASE_URL -c 'SELECT COUNT(*) FROM users;'")
      Bash("cd database && psql $DATABASE_URL -c 'SELECT COUNT(*) FROM user_profiles;'")
      Bash("cd database && psql $DATABASE_URL -c 'SELECT COUNT(*) FROM posts;'")
  `
};

// ✅ CORRECT: Testing Suite Creation (All test files at once)
const correctTestingSuite = {
  pattern: "Comprehensive test suite creation in single batch",
  implementation: `
    [BatchTool Message]:
      // Read existing source files to understand structure
      Read("src/controllers/userController.js")
      Read("src/controllers/authController.js")
      Read("src/models/User.js")
      Read("src/services/authService.js")
      Read("src/utils/validation.js")
      
      // Write ALL test files concurrently
      Write("tests/unit/controllers/userController.test.js", userControllerTests)
      Write("tests/unit/controllers/authController.test.js", authControllerTests)
      Write("tests/unit/models/User.test.js", userModelTests)
      Write("tests/unit/services/authService.test.js", authServiceTests)
      Write("tests/unit/utils/validation.test.js", validationTests)
      
      Write("tests/integration/auth.test.js", authIntegrationTests)
      Write("tests/integration/users.test.js", userIntegrationTests)
      Write("tests/integration/posts.test.js", postIntegrationTests)
      
      Write("tests/e2e/userRegistration.test.js", e2eRegistrationTests)
      Write("tests/e2e/userLogin.test.js", e2eLoginTests)
      Write("tests/e2e/postCreation.test.js", e2ePostTests)
      
      Write("tests/helpers/testDatabase.js", testDatabaseHelpers)
      Write("tests/helpers/testAuth.js", testAuthHelpers)
      Write("tests/fixtures/users.json", userTestFixtures)
      Write("tests/fixtures/posts.json", postTestFixtures)
      
      // Create test configuration files
      Write("jest.config.js", jestConfiguration)
      Write("tests/setup.js", testSetupScript)
      Write("tests/teardown.js", testTeardownScript)
      
      // Execute ALL testing commands
      Bash("npm install --save-dev jest supertest @testing-library/react")
      Bash("npm run test:unit")
      Bash("npm run test:integration") 
      Bash("npm run test:e2e")
      Bash("npm run test:coverage")
  `
};

// ❌ WRONG: Sequential File Operations (Anti-Pattern)
const wrongSequentialFileOperations = {
  antiPattern: "Individual file operations across multiple messages",
  wrongImplementation: `
    // ❌ NEVER DO THIS - Breaks concurrent coordination
    Message 1: Read("package.json")
    Message 2: Write("server.js", content)
    Message 3: Bash("mkdir src")
    Message 4: Write("src/app.js", appContent)
    Message 5: Bash("npm install")
    Message 6: Write("Dockerfile", dockerContent)
    Message 7: Bash("docker build -t app .")
  `,
  
  problems: [
    "6x slower execution due to sequential processing",
    "Agents lose context between file operations",
    "No atomic operations - partial failures leave inconsistent state",
    "Massive token waste from repeated context setup",
    "Cannot coordinate file dependencies properly"
  ]
};

module.exports = {
  correctProjectSetup,
  correctDatabaseMigration, 
  correctTestingSuite,
  wrongSequentialFileOperations
};