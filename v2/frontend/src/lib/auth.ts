import {
  type Configuration,
  type SilentRequest,
  PublicClientApplication,
  InteractionRequiredAuthError,
} from "@azure/msal-browser";

// ---------------------------------------------------------------------------
// Feature flag
// ---------------------------------------------------------------------------

export const authEnabled: boolean =
  import.meta.env.VITE_AUTH_ENABLED === "true";

// ---------------------------------------------------------------------------
// MSAL configuration
// ---------------------------------------------------------------------------

const clientId = import.meta.env.VITE_AZURE_CLIENT_ID ?? "";
const tenantId = import.meta.env.VITE_AZURE_TENANT_ID ?? "";

export const msalConfig: Configuration = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri: window.location.origin,
    postLogoutRedirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: "localStorage",
  },
};

export const loginRequest = {
  scopes: [`api://${clientId}/user_impersonation`],
};

// ---------------------------------------------------------------------------
// Singleton MSAL instance
// ---------------------------------------------------------------------------

let _msalInstance: PublicClientApplication | null = null;

export function getMsalInstance(): PublicClientApplication {
  if (!_msalInstance) {
    _msalInstance = new PublicClientApplication(msalConfig);
  }
  return _msalInstance;
}

export async function initializeMsal(): Promise<PublicClientApplication> {
  const instance = getMsalInstance();
  await instance.initialize();
  // Handle redirect response — must be called before any other MSAL API
  const result = await instance.handleRedirectPromise();
  if (result?.account) {
    instance.setActiveAccount(result.account);
  } else if (instance.getAllAccounts().length > 0) {
    instance.setActiveAccount(instance.getAllAccounts()[0]);
  }
  return instance;
}

// ---------------------------------------------------------------------------
// Token acquisition
// ---------------------------------------------------------------------------

export async function getAccessToken(): Promise<string | null> {
  if (!authEnabled) return null;

  const instance = getMsalInstance();
  const account = instance.getActiveAccount();
  if (!account) return null;

  try {
    const result = await instance.acquireTokenSilent({
      ...loginRequest,
      account,
    } as SilentRequest);
    return result.accessToken;
  } catch (error) {
    if (error instanceof InteractionRequiredAuthError) {
      // MsalAuthenticationTemplate will handle re-auth via redirect
      return null;
    }
    throw error;
  }
}
