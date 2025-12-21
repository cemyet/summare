// Summare Frontend - Updated 2025-12-21
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// Suppress harmless Chrome extension errors globally
// These errors are caused by browser extensions trying to inject code into iframes
// and don't affect the functionality of the application
const originalError = console.error;
console.error = (...args: any[]) => {
  const message = args[0]?.toString() || '';
  
  // Filter out extension-related errors
  if (
    message.includes('chrome-extension://') ||
    message.includes('runtime/sendMessage') ||
    message.includes('message channel closed') ||
    message.includes('A listener indicated an asynchronous response')
  ) {
    return; // Suppress these errors
  }
  
  // Log all other errors normally
  originalError.apply(console, args);
};

createRoot(document.getElementById("root")!).render(<App />);
