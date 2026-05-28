import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

import { HashRouter } from 'react-router-dom'

import ErrorBoundary from './shared/components/ErrorBoundary.jsx'

console.log("Frontend mounting...");

try {
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <HashRouter>
        <ErrorBoundary>
          <App />
        </ErrorBoundary>
      </HashRouter>
    </StrictMode>,
  )
  console.log("App rendered successfully");
} catch (error) {
  console.error("Error rendering app:", error);
  document.getElementById('root').innerHTML = '<div style="color:red; font-family:sans-serif; padding:20px;"><h1>Error Fatal</h1><p>' + error.message + '</p></div>';
}

