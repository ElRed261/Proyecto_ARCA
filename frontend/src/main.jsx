import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'

import { HashRouter } from 'react-router-dom'

console.log("Frontend mounting...");

try {
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <HashRouter>
        <App />
      </HashRouter>
    </StrictMode>,
  )
  console.log("App rendered successfully");
} catch (error) {
  console.error("Error rendering app:", error);
  document.getElementById('root').innerHTML = '<h1 style="color:red;">Error: ' + error.message + '</h1>';
}

