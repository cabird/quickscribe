import { PublicClientApplication, EventType, EventMessage, AuthenticationResult } from '@azure/msal-browser';
import { msalConfig } from '../config/authConfig';

/**
 * MSAL instance for handling Azure AD authentication.
 *
 * This instance is initialized once and used throughout the application.
 * It handles token acquisition, caching, and refresh automatically.
 */
export const msalInstance = new PublicClientApplication(msalConfig);

// Initialize MSAL instance
// This must be called before using the instance
await msalInstance.initialize();

// Optional: Add event callbacks for authentication events
msalInstance.addEventCallback((event: EventMessage) => {
  if (event.eventType === EventType.LOGIN_SUCCESS) {
    const payload = event.payload as AuthenticationResult;
    const account = payload.account;
    msalInstance.setActiveAccount(account);
    console.log('Login successful:', account?.username);
  }

  if (event.eventType === EventType.LOGOUT_SUCCESS) {
    console.log('Logout successful');
  }

  if (event.eventType === EventType.ACQUIRE_TOKEN_FAILURE) {
    console.error('Token acquisition failed:', event.error);
  }
});

// Set the active account on page load
const accounts = msalInstance.getAllAccounts();
if (accounts.length > 0) {
  msalInstance.setActiveAccount(accounts[0]);
}
