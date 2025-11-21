import axios, { AxiosInstance } from 'axios';
import { msalInstance } from '../auth/msalInstance';
import { loginRequest, authEnabled } from '../config/authConfig';

// In production (served by Flask), use relative URLs (empty baseURL)
// In development, use VITE_API_URL from .env
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

/**
 * Acquire an access token for API calls.
 *
 * If authentication is disabled, returns null.
 * If user is not logged in, triggers login redirect.
 * Tries silent token acquisition first, falls back to interactive if needed.
 */
async function getAccessToken(): Promise<string | null> {
  if (!authEnabled) {
    return null;
  }

  const accounts = msalInstance.getAllAccounts();
  if (accounts.length === 0) {
    // User not logged in, redirect to login
    await msalInstance.loginRedirect(loginRequest);
    return null;
  }

  try {
    // Try silent token acquisition (uses cached/refresh tokens)
    const response = await msalInstance.acquireTokenSilent({
      ...loginRequest,
      account: accounts[0],
    });
    return response.accessToken;
  } catch (error) {
    console.warn('Silent token acquisition failed, trying interactive:', error);
    try {
      // Silent acquisition failed, try interactive popup
      const response = await msalInstance.acquireTokenPopup(loginRequest);
      return response.accessToken;
    } catch (interactiveError) {
      console.error('Interactive token acquisition failed:', interactiveError);
      // If interactive also fails, redirect to login
      await msalInstance.loginRedirect(loginRequest);
      return null;
    }
  }
}

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor for auth
    this.client.interceptors.request.use(
      async (config) => {
        // Acquire access token if auth is enabled
        const token = await getAccessToken();
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        console.error('API Error:', error);

        // Handle 401 Unauthorized - token expired or invalid
        if (error.response?.status === 401 && authEnabled) {
          console.warn('Received 401, redirecting to login...');
          await msalInstance.loginRedirect(loginRequest);
        }

        // Don't show toast here - let individual services handle error display
        return Promise.reject(error);
      }
    );
  }

  getInstance() {
    return this.client;
  }
}

export const apiClient = new ApiClient().getInstance();
