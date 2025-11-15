// In production (served by Flask), API requests are relative (same origin)
// In development, we use the dev server with proxy or direct URL
export const API_BASE_URL = import.meta.env.VITE_API_URL || '';
export const AZURE_CLIENT_ID = import.meta.env.VITE_AZURE_CLIENT_ID || '';
