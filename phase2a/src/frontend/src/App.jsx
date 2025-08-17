/**
 * Hedgehog Platform Frontend Application
 * Progressive Web App with Agent Coordination UI
 */

import React from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ApolloClient, InMemoryCache, ApolloProvider } from '@apollo/client'

// Components
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import AgentCoordination from './pages/AgentCoordination'
import FabricManagement from './pages/FabricManagement'
import Migration from './pages/Migration'
import Settings from './pages/Settings'

// Styles
import './App.css'

// Create clients
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
    },
  },
})

const apolloClient = new ApolloClient({
  uri: 'http://localhost:8102/graphql',
  cache: new InMemoryCache(),
  defaultOptions: {
    watchQuery: {
      errorPolicy: 'all',
    },
    query: {
      errorPolicy: 'all',
    },
  },
})

function App() {
  return (
    <ApolloProvider client={apolloClient}>
      <QueryClientProvider client={queryClient}>
        <Router>
          <Layout>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/agents" element={<AgentCoordination />} />
              <Route path="/fabrics" element={<FabricManagement />} />
              <Route path="/migration" element={<Migration />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </Layout>
        </Router>
      </QueryClientProvider>
    </ApolloProvider>
  )
}

export default App