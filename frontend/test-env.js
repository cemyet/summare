// Quick test script for frontend environment variables
console.log('🔍 Testing Frontend Environment Variables...\n');

// Check if .env file exists
const fs = require('fs');
const path = require('path');

const envPath = path.join(__dirname, '.env');
if (fs.existsSync(envPath)) {
  console.log('✅ .env file exists');
  const envContent = fs.readFileSync(envPath, 'utf8');
  const vars = {
    'VITE_API_URL': envContent.includes('VITE_API_URL'),
    'VITE_STRIPE_PUBLISHABLE_KEY': envContent.includes('VITE_STRIPE_PUBLISHABLE_KEY'),
    'VITE_USE_EMBEDDED_CHECKOUT': envContent.includes('VITE_USE_EMBEDDED_CHECKOUT'),
  };
  
  Object.entries(vars).forEach(([key, exists]) => {
    console.log(`${exists ? '✅' : '❌'} ${key}: ${exists ? 'Found in .env' : 'Missing'}`);
  });
} else {
  console.log('❌ .env file not found');
}

console.log('\n📝 Note: To test actual values, run: npm run dev');
