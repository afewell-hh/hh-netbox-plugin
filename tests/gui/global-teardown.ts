import { FullConfig } from '@playwright/test';

async function globalTeardown(config: FullConfig) {
  console.log('Starting GUI test global teardown...');
  
  // Clean up any test artifacts or sessions
  console.log('Cleaning up test artifacts...');
  
  // Log test completion
  console.log('✅ GUI test teardown completed');
}

export default globalTeardown;