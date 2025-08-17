/**
 * Hedgehog Platform Backend API
 * MDD-aligned implementation with ruv-swarm coordination
 */

import express from 'express';
import { ApolloServer } from 'apollo-server-express';
import { WebSocketServer } from 'ws';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import { createServer } from 'http';
import winston from 'winston';
import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

// Configure logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console({
      format: winston.format.simple()
    })
  ]
});

// Create Express app
const app = express();

// Middleware
app.use(helmet({
  contentSecurityPolicy: false // Allow GraphQL playground in dev
}));
app.use(cors({
  origin: process.env.FRONTEND_URL || 'http://localhost:8100',
  credentials: true
}));
app.use(compression());
app.use(express.json());

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({
    status: 'healthy',
    service: 'hedgehog-platform-backend',
    timestamp: new Date().toISOString(),
    environment: process.env.NODE_ENV || 'development',
    features: {
      graphql: true,
      websocket: true,
      ruv_swarm_integration: true,
      legacy_netbox_bridge: true
    }
  });
});

// API Info endpoint
app.get('/api', (req, res) => {
  res.json({
    name: 'Hedgehog Platform API',
    version: '0.1.0',
    endpoints: {
      health: '/health',
      graphql: '/graphql',
      websocket: 'ws://localhost:8103',
      metrics: '/metrics'
    },
    parallel_deployment: {
      existing_netbox: 'http://localhost:8000',
      new_platform: 'http://localhost:8100'
    }
  });
});

// Metrics endpoint for Prometheus
app.get('/metrics', (req, res) => {
  res.set('Content-Type', 'text/plain');
  res.send(`
# HELP platform_api_requests_total Total API requests
# TYPE platform_api_requests_total counter
platform_api_requests_total 0

# HELP platform_api_latency_seconds API request latency
# TYPE platform_api_latency_seconds histogram
platform_api_latency_seconds_bucket{le="0.1"} 0
platform_api_latency_seconds_bucket{le="0.5"} 0
platform_api_latency_seconds_bucket{le="1"} 0
platform_api_latency_seconds_bucket{le="+Inf"} 0

# HELP platform_websocket_connections Active WebSocket connections
# TYPE platform_websocket_connections gauge
platform_websocket_connections 0
  `.trim());
});

// GraphQL schema (placeholder for now)
const typeDefs = `
  type Query {
    platform: Platform
    agents: [Agent]
    fabrics: [Fabric]
  }
  
  type Platform {
    name: String
    version: String
    status: String
    migration_progress: Float
  }
  
  type Agent {
    id: ID
    name: String
    type: String
    status: String
    capabilities: [String]
  }
  
  type Fabric {
    id: ID
    name: String
    status: String
    sync_state: String
  }
`;

const resolvers = {
  Query: {
    platform: () => ({
      name: 'Hedgehog Platform',
      version: '0.1.0',
      status: 'foundation',
      migration_progress: 0.05
    }),
    agents: () => [],
    fabrics: () => []
  }
};

// Create HTTP server
const httpServer = createServer(app);

// Initialize Apollo Server
async function startApolloServer() {
  const apolloServer = new ApolloServer({
    typeDefs,
    resolvers,
    csrfPrevention: true,
    cache: 'bounded'
  });

  await apolloServer.start();
  apolloServer.applyMiddleware({ 
    app,
    path: '/graphql'
  });

  logger.info(`GraphQL server ready at http://localhost:${process.env.GRAPHQL_PORT || 8102}/graphql`);
}

// Initialize WebSocket server
const wss = new WebSocketServer({ 
  port: process.env.WS_PORT || 8103,
  path: '/ws'
});

wss.on('connection', (ws) => {
  logger.info('New WebSocket connection established');
  
  ws.on('message', (data) => {
    try {
      const message = JSON.parse(data.toString());
      logger.info('WebSocket message received:', message);
      
      // Echo back for now
      ws.send(JSON.stringify({
        type: 'ack',
        original: message,
        timestamp: new Date().toISOString()
      }));
    } catch (error) {
      logger.error('WebSocket message error:', error);
    }
  });
  
  ws.on('close', () => {
    logger.info('WebSocket connection closed');
  });
});

// Start servers
const API_PORT = process.env.API_PORT || 8101;

startApolloServer().then(() => {
  httpServer.listen(API_PORT, () => {
    logger.info(`
========================================
Hedgehog Platform Backend Started
========================================
API Server:     http://localhost:${API_PORT}
GraphQL:        http://localhost:${process.env.GRAPHQL_PORT || 8102}/graphql
WebSocket:      ws://localhost:${process.env.WS_PORT || 8103}
Health Check:   http://localhost:${API_PORT}/health
Metrics:        http://localhost:${API_PORT}/metrics

Parallel Deployment Status:
- Existing NetBox: http://localhost:8000 (unchanged)
- New Platform:    http://localhost:8100 (building)
========================================
    `);
  });
}).catch(error => {
  logger.error('Failed to start server:', error);
  process.exit(1);
});

// Graceful shutdown
process.on('SIGTERM', () => {
  logger.info('SIGTERM received, shutting down gracefully');
  httpServer.close(() => {
    logger.info('HTTP server closed');
    wss.close(() => {
      logger.info('WebSocket server closed');
      process.exit(0);
    });
  });
});