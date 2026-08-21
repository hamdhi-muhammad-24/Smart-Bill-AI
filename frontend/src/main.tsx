import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './lib/queryClient'
import { AuthProvider } from './auth/AuthProvider'
import { ThemeProvider } from 'next-themes'
import './index.css'
import App from './App.tsx'
import React from 'react'

class ErrorBoundary extends React.Component<{children: React.ReactNode}, {hasError: boolean, error: any}> {
  constructor(props: {children: React.ReactNode}) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error: any) {
    return { hasError: true, error };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '24px', maxWidth: '600px', margin: '40px auto', fontFamily: 'system-ui, sans-serif', background: '#fee2e2', border: '1px solid #ef4444', borderRadius: '8px', color: '#991b1b' }}>
          <h2 style={{ margin: '0 0 12px 0' }}>Something went wrong</h2>
          <p style={{ margin: '0 0 12px 0' }}>An error occurred while loading the application:</p>
          <pre style={{ whiteSpace: 'pre-wrap', background: '#ffffff', padding: '12px', borderRadius: '6px', fontSize: '13px', overflowX: 'auto', border: '1px solid #fca5a5' }}>
            {this.state.error && (this.state.error.stack || this.state.error.message || String(this.state.error))}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}

import { MsalProvider } from '@azure/msal-react'
import { msalInstance } from './auth/msalConfig'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <MsalProvider instance={msalInstance}>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <AuthProvider>
              <App />
            </AuthProvider>
          </BrowserRouter>
        </QueryClientProvider>
      </MsalProvider>
    </ErrorBoundary>
  </StrictMode>,
)

