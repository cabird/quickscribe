import React from 'react';
import ReactDOM from 'react-dom/client';
import { MsalProvider } from '@azure/msal-react';
import App from './App';
import { msalInstance } from './auth/msalInstance';
import { authEnabled } from './config/authConfig';

// Conditionally wrap with MsalProvider based on auth configuration
const AppWithAuth = authEnabled ? (
  <MsalProvider instance={msalInstance}>
    <App />
  </MsalProvider>
) : (
  <App />
);

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {AppWithAuth}
  </React.StrictMode>
);
