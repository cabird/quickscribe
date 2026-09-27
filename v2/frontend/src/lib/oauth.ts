import { getAccessToken, getMsalInstance, loginRequest } from "./auth";
import { captureOAuthRequest } from "./oauthContinuation";

export interface ConsentInfo {
  client_name: string;
  client_id: string;
  redirect_uri: string;
  email: string | null;
  name: string | null;
  csrf: string;
}

export interface OAuthConnection {
  id: string;
  client_name: string;
  client_id: string;
  created_at: number;
  expires_at: number;
  revoked_at: number | null;
  last_used_at: number | null;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getAccessToken();
  if (!token) {
    captureOAuthRequest(new URL(window.location.href), sessionStorage);
    await getMsalInstance().acquireTokenRedirect(loginRequest);
    throw new Error("Sign in to Microsoft to continue.");
  }
  const response = await fetch(path, {
    ...init, credentials: "same-origin", cache: "no-store",
    headers: { ...init.headers, Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || error.error_description || "Unable to complete the request.");
  }
  return response.status === 204 ? undefined as T : response.json();
}

export const fetchConsent = (id: string) =>
  request<ConsentInfo>(`/api/oauth/consent?request=${encodeURIComponent(id)}`);
export const decideConsent = (id: string, csrf: string, decision: "approve" | "deny") =>
  request<{ redirect_uri: string }>("/api/oauth/consent", {
    method: "POST", body: new URLSearchParams({ request: id, csrf, decision }),
  });
export const fetchConnections = () => request<OAuthConnection[]>("/api/settings/oauth-connections");
export const revokeConnection = (id: string) =>
  request<void>(`/api/settings/oauth-connections/${encodeURIComponent(id)}`, { method: "DELETE" });
