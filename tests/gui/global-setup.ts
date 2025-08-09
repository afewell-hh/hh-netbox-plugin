import { chromium, FullConfig } from '@playwright/test';

async function globalSetup(config: FullConfig) {
  console.log('Starting GUI test global setup...');
  
  // Check if NetBox is accessible
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  try {
    console.log('Checking NetBox accessibility...');
    await page.goto('http://localhost:8000/', { timeout: 30000 });
    console.log('✅ NetBox is accessible');
    
    // Check if the hedgehog plugin is loaded
    const response = await page.goto('http://localhost:8000/plugins/hedgehog/', { 
      timeout: 30000,
      waitUntil: 'networkidle' 
    });
    
    if (response?.status() === 200 || response?.status() === 302) {
      console.log('✅ Hedgehog plugin is accessible');
    } else {
      console.warn(`⚠️  Hedgehog plugin returned status: ${response?.status()}`);
    }
    
  } catch (error) {
    console.error('❌ NetBox or Hedgehog plugin not accessible:', error);
    throw error;
  } finally {
    await browser.close();
  }
  
  console.log('Global setup completed successfully');
}

export default globalSetup;