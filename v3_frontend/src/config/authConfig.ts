import { Configuration, LogLevel } from '@azure/msal-browser';

/**
 * MSAL Configuration for Azure AD Authentication
 *
 * This configuration enables frontend-driven (SPA) authentication with Azure AD.
 * The frontend acquires JWT tokens and sends them to the backend for validation.
 */
export const msalConfig: Configuration = {
  auth: {
    clientId: import.meta.env.VITE_AZURE_CLIENT_ID || '',
    authority: `https://login.microsoftonline.com/${import.meta.env.VITE_AZURE_TENANT_ID || 'common'}`,
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: 'localStorage', // Use localStorage for multi-tab support
    storeAuthStateInCookie: false, // Set to true for IE11/Edge
  },
  system: {
    loggerOptions: {
      logLevel: LogLevel.Info,
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) {
          return;
        }
        switch (level) {
          case LogLevel.Error:
            console.error(message);
            return;
          case LogLevel.Info:
            console.info(message);
            return;
          case LogLevel.Verbose:
            console.debug(message);
            return;
          case LogLevel.Warning:
            console.warn(message);
            return;
        }
      },
    },
  },
};

/**
 * Scopes to request when acquiring tokens.
 *
 * The backend expects the 'user_impersonation' scope to validate the token.
 */
export const loginRequest = {
  scopes: [`api://${import.meta.env.VITE_AZURE_CLIENT_ID}/user_impersonation`],
};

/**
 * Flag to enable/disable authentication.
 *
 * When disabled (development mode), no login is required and the backend
 * uses a default test user.
 *
 * When enabled (testing/production), full Azure AD authentication is required.
 */
export const authEnabled = import.meta.env.VITE_AUTH_ENABLED === 'true';
